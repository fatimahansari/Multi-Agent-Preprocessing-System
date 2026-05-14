"""FastAPI backend for the IntelliPrep MAS Preprocessing System.

Endpoints
---------
POST /api/upload              — upload a CSV file, get back server path
POST /api/run                 — start pipeline, get back run_id
GET  /api/progress/{run_id}   — SSE stream of real-time log events
GET  /api/result/{run_id}     — final state once pipeline completes
GET  /api/download/{run_id}   — download preprocessed CSV
GET  /api/health              — liveness check

Run with:
    cd aai_mas_preprocessing
    uvicorn api.server:app --reload --reload-exclude "Pre Processed Dataset" --reload-exclude "run_store" --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

# Load .env before anything imports llm_config so ANTHROPIC_API_KEY is available.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# Ensure the package root (aai_mas_preprocessing/) is importable
_PKG_ROOT = Path(__file__).parent.parent.resolve()
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="IntelliPrep MAS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Run store — in-memory dict backed by per-run JSON files on disk.
#
# Layout:  <pkg_root>/run_store/<run_id>.json
#
# On startup the directory is scanned so completed runs survive server
# reloads.  Only the metadata (status, final_state) is persisted; the
# events list is ephemeral (SSE is fire-and-forget).
# ---------------------------------------------------------------------------

_STORE_DIR = _PKG_ROOT / "run_store"
_STORE_DIR.mkdir(exist_ok=True)

run_store: dict[str, dict] = {}
_store_lock = threading.Lock()


def _store_path(run_id: str) -> Path:
    return _STORE_DIR / f"{run_id}.json"


def _persist_run(run_id: str) -> None:
    """Write the completed/errored run metadata to disk (called under lock)."""
    entry = run_store.get(run_id)
    if entry is None or entry.get("status") == "running":
        return
    payload = {
        "status":      entry.get("status"),
        "final_state": entry.get("final_state"),
        "csv_path":    entry.get("csv_path", ""),
    }
    try:
        _store_path(run_id).write_text(json.dumps(payload, default=str), encoding="utf-8")
    except Exception:
        pass  # persistence is best-effort; SSE fallback still works


def _load_run_from_disk(run_id: str) -> dict | None:
    """Read a persisted run from disk; returns None if not found or corrupt."""
    p = _store_path(run_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {
            "events":      [],          # events are ephemeral
            "status":      data.get("status", "done"),
            "final_state": data.get("final_state"),
            "csv_path":    data.get("csv_path", ""),
        }
    except Exception:
        return None


def _get_run(run_id: str) -> dict | None:
    """Return run entry from memory, falling back to disk on cache miss."""
    with _store_lock:
        if run_id in run_store:
            return run_store[run_id]

    entry = _load_run_from_disk(run_id)
    if entry is not None:
        with _store_lock:
            run_store[run_id] = entry   # warm the in-memory cache
    return entry

# Thread-local: each worker thread stores its own run_id here so the global
# _log patch can route events to the correct run.
_tl = threading.local()

# ---------------------------------------------------------------------------
# Global one-time patch of BaseAgent._log
# (safe for concurrent runs because routing uses thread-local run_id)
# ---------------------------------------------------------------------------

def _install_log_interceptor() -> None:
    """Replace BaseAgent._log with a version that also pushes SSE events."""
    from core.agent_base import BaseAgent

    _original_log = BaseAgent._log

    def _patched_log(self, state: dict, message: str) -> dict:
        run_id: str | None = getattr(_tl, "run_id", None)
        if run_id:
            _push_event(run_id, self.name, message, "log")
        return _original_log(self, state, message)

    BaseAgent._log = _patched_log  # type: ignore[method-assign]


# Install once at import time so all threads see the patched version.
_install_log_interceptor()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _push_event(
    run_id: str,
    agent: str,
    message: str,
    event_type: str = "log",
) -> None:
    """Thread-safe append of an SSE event to the run store."""
    event = {
        "type": event_type,
        "agent": agent,
        "message": message,
        "ts": time.time(),
    }
    with _store_lock:
        if run_id in run_store:
            run_store[run_id]["events"].append(event)


def _sanitize_state(state: dict) -> dict:
    """Strip large / non-serialisable fields before sending to client."""
    out = {}
    for k, v in state.items():
        if k == "synthesized_code":
            script = state.get("file_history", {}).get("script", "")
            out["synthesized_code_path"] = script
            continue
        try:
            json.dumps(v, default=str)
            out[k] = v
        except Exception:
            out[k] = str(v)
    return out


def _build_comparison_report(raw_csv: str, processed_csv: str) -> dict:
    """Compute a before/after comparison report between raw and preprocessed CSVs."""
    try:
        import pandas as pd
        import numpy as np

        raw = pd.read_csv(raw_csv)
        proc = pd.read_csv(processed_csv)

        def _col_stats(df: pd.DataFrame) -> dict:
            stats = {}
            for col in df.columns:
                s = df[col]
                entry: dict = {"dtype": str(s.dtype), "nulls": int(s.isna().sum())}
                if pd.api.types.is_numeric_dtype(s):
                    entry["mean"] = round(float(s.mean()), 4) if not s.isna().all() else None
                    entry["std"]  = round(float(s.std()),  4) if not s.isna().all() else None
                    entry["min"]  = round(float(s.min()),  4) if not s.isna().all() else None
                    entry["max"]  = round(float(s.max()),  4) if not s.isna().all() else None
                else:
                    entry["unique"] = int(s.nunique())
                stats[col] = entry
            return stats

        raw_stats  = _col_stats(raw)
        proc_stats = _col_stats(proc)

        added_cols   = [c for c in proc.columns if c not in raw.columns]
        removed_cols = [c for c in raw.columns  if c not in proc.columns]

        # Sanitise any NaN/Inf that would break JSON serialisation
        def _clean(obj):
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean(i) for i in obj]
            return obj

        return _clean({
            "raw": {
                "rows": int(raw.shape[0]),
                "cols": int(raw.shape[1]),
                "total_nulls": int(raw.isna().sum().sum()),
                "columns": raw_stats,
            },
            "processed": {
                "rows": int(proc.shape[0]),
                "cols": int(proc.shape[1]),
                "total_nulls": int(proc.isna().sum().sum()),
                "columns": proc_stats,
            },
            "changes": {
                "rows_delta": int(proc.shape[0] - raw.shape[0]),
                "cols_delta": int(proc.shape[1] - raw.shape[1]),
                "nulls_delta": int(proc.isna().sum().sum() - raw.isna().sum().sum()),
                "added_columns": added_cols,
                "removed_columns": removed_cols,
            },
        })
    except Exception as exc:
        return {"error": str(exc)}

# ---------------------------------------------------------------------------
# Pipeline worker (runs in a daemon thread)
# ---------------------------------------------------------------------------

def _run_pipeline(
    run_id: str,
    csv_path: str,
    target_column: str,
) -> None:
    """Execute the MAS pipeline; push progress events via _push_event."""
    _tl.run_id = run_id

    try:
        _push_event(run_id, "system", "Pipeline started.", "system")

        # Import here so env vars are already set when agents are instantiated.
        from mas_orchestrator import run_mas

        final_state = run_mas(csv_path, target_column)

        sanitized = _sanitize_state(dict(final_state))
        pipeline_status = final_state.get("status", "done")

        with _store_lock:
            run_store[run_id]["final_state"] = sanitized
            run_store[run_id]["status"] = pipeline_status

        # Build and attach a before/after comparison report when both CSVs exist.
        raw_csv_path  = csv_path
        proc_csv_path = (sanitized.get("file_history") or {}).get("output_csv", "")
        if proc_csv_path and Path(proc_csv_path).exists():
            report = _build_comparison_report(raw_csv_path, proc_csv_path)
            sanitized["comparison_report"] = report
            with _store_lock:
                run_store[run_id]["final_state"] = sanitized

        # Persist to disk so /api/result survives server reloads.
        with _store_lock:
            _persist_run(run_id)

        # Push the plan as a dedicated SSE event so the frontend can display
        # preprocessing steps immediately without waiting for /api/result.
        plan = sanitized.get("plan") or {}
        if plan:
            _push_event(run_id, "system", json.dumps(plan), "plan")

        _push_event(
            run_id,
            "system",
            f"Pipeline finished — status: {pipeline_status}",
            "complete",
        )

    except Exception as exc:  # noqa: BLE001
        with _store_lock:
            run_store[run_id]["status"] = "error"
            _persist_run(run_id)
        _push_event(run_id, "system", f"Unhandled error: {exc}", "error")

    finally:
        _tl.run_id = None

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    csv_path: str
    target_column: str

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)) -> dict:
    """Save an uploaded CSV to a temp dir; return its server-side path."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    tmp_dir = Path(tempfile.gettempdir()) / "mas_uploads"
    tmp_dir.mkdir(exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    dest = tmp_dir / safe_name
    content = await file.read()
    dest.write_bytes(content)

    # Quick sanity-check: is the file at least a bit like a CSV?
    try:
        first_line = content.split(b"\n")[0].decode("utf-8", errors="replace")
        if "," not in first_line and "\t" not in first_line:
            raise ValueError("No comma or tab separator detected.")
        columns = [c.strip().strip('"') for c in first_line.split(",")]
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}") from exc

    return {
        "csv_path": str(dest),
        "filename": file.filename,
        "size_bytes": len(content),
        "columns": columns,
    }


@app.post("/api/run")
async def start_run(body: RunRequest) -> dict:
    """Start the MAS pipeline; return a run_id for SSE polling."""
    if not Path(body.csv_path).exists():
        raise HTTPException(status_code=404, detail="CSV file not found on server.")

    run_id = str(uuid.uuid4())
    with _store_lock:
        run_store[run_id] = {
            "events": [],
            "status": "running",
            "final_state": None,
            "csv_path": body.csv_path,
        }

    thread = threading.Thread(
        target=_run_pipeline,
        args=(
            run_id,
            body.csv_path,
            body.target_column,
        ),
        daemon=True,
        name=f"mas-run-{run_id[:8]}",
    )
    thread.start()

    return {"run_id": run_id}


@app.get("/api/progress/{run_id}")
async def stream_progress(run_id: str) -> StreamingResponse:
    """SSE stream: yields JSON event objects as the pipeline progresses."""
    if _get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run ID not found.")

    async def generate():
        sent = 0
        # Yield a keep-alive comment immediately so the browser doesn't time out.
        yield ": connected\n\n"

        while True:
            with _store_lock:
                events = list(run_store.get(run_id, {}).get("events", []))
                status = run_store.get(run_id, {}).get("status", "running")

            while sent < len(events):
                yield f"data: {json.dumps(events[sent])}\n\n"
                sent += 1

            if status in ("done", "error") and sent >= len(events):
                # One final status event so the client knows it's over.
                yield f"data: {json.dumps({'type': 'done', 'status': status})}\n\n"
                break

            await asyncio.sleep(0.25)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/result/{run_id}")
async def get_result(run_id: str) -> dict:
    """Return the final MASState once the run is complete.

    Falls back to the persisted disk copy when the run is no longer in the
    in-memory store (e.g. after a hot-reload).
    """
    run = _get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run ID not found.")

    if run["status"] == "running":
        raise HTTPException(status_code=202, detail="Pipeline still running.")

    return {"status": run["status"], "final_state": run["final_state"]}


@app.get("/api/download/{run_id}")
async def download_csv(run_id: str) -> FileResponse:
    """Stream the preprocessed CSV to the browser as a file download."""
    run = _get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run ID not found.")

    if run["status"] == "running":
        raise HTTPException(status_code=202, detail="Pipeline still running.")

    final = run.get("final_state") or {}
    csv_path = (final.get("file_history") or {}).get("output_csv", "")
    if not csv_path or not Path(csv_path).exists():
        raise HTTPException(status_code=404, detail="Preprocessed CSV not found.")

    filename = Path(csv_path).name
    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["Pre Processed Dataset", "run_store"],
    )
