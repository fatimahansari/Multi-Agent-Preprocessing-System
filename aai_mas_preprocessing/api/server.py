"""FastAPI backend for the IntelliPrep MAS Preprocessing System.

Endpoints
---------
POST /api/upload              — upload a CSV file, get back server path
POST /api/run                 — start pipeline, get back run_id
GET  /api/progress/{run_id}   — SSE stream of real-time log events
GET  /api/result/{run_id}     — final state once pipeline completes
GET  /api/health              — liveness check

Run with:
    cd aai_mas_preprocessing
    uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
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
from fastapi.responses import StreamingResponse
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
# In-memory run store  {run_id → {events, status, final_state, csv_path}}
# ---------------------------------------------------------------------------

run_store: dict[str, dict] = {}
_store_lock = threading.Lock()

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

        with _store_lock:
            run_store[run_id]["final_state"] = _sanitize_state(dict(final_state))
            run_store[run_id]["status"] = final_state.get("status", "done")

        _push_event(
            run_id,
            "system",
            f"Pipeline finished — status: {run_store[run_id]['status']}",
            "complete",
        )

    except Exception as exc:  # noqa: BLE001
        with _store_lock:
            run_store[run_id]["status"] = "error"
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
    if run_id not in run_store:
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
    """Return the final MASState once the run is complete."""
    if run_id not in run_store:
        raise HTTPException(status_code=404, detail="Run ID not found.")

    run = run_store[run_id]
    if run["status"] == "running":
        raise HTTPException(status_code=202, detail="Pipeline still running.")

    return {"status": run["status"], "final_state": run["final_state"]}


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
