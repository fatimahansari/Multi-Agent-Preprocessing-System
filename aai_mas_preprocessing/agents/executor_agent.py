"""Executor / Self-Healer. Runs synthesized code, LLM fix loop."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, List

from core.agent_base import BaseAgent

if TYPE_CHECKING:
    from core.shared_state import MASState

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_EXEC_TIMEOUT = 300   # seconds per attempt (5 min is plenty for ≤100k rows)

_SYSTEM_PROMPT = (
    "You are an expert Python ML engineer. "
    "Fix the provided preprocessing code without changing the preprocessing intent. "
    "Return only valid corrected Python code — no markdown, no explanation."
)

_FIX_USER_TEMPLATE = """\
Current code:
{synthesized_code}

Execution error:
{stderr}

Dataset columns available: {columns}
Target column: {target_column}

Return the complete corrected Python script.\
"""


class ExecutorAgent(BaseAgent):
    """Runs the synthesized preprocessing script and self-heals on failure.

    Retry loop (up to ``_MAX_RETRIES`` attempts):
      1. Execute script with ``subprocess.run``.
      2. On failure, call the LLM with the current code + stderr.
      3. Overwrite the script file with the LLM's fix.
      4. Recurse into ``run()`` to re-execute.

    The ``retry_count`` in state acts as the recursion guard.
    """

    def __init__(self, llm_model: str, api_key: str) -> None:
        super().__init__(
            name="executor",
            llm_model=llm_model,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Execute the synthesized script, healing and retrying on failure."""

        # --- resolve script path ------------------------------------------
        # CodeSynthesizerAgent writes the path under "script"; the spec also
        # mentions "synthesized_code" — accept either key for robustness.
        file_history = state.get("file_history", {})
        script_path_str = (
            file_history.get("script")
            or file_history.get("synthesized_code")
            or ""
        )

        if not script_path_str:
            msg = "ExecutorAgent: no script path found in state['file_history']."
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        script_path = Path(script_path_str)
        if not script_path.exists():
            msg = f"ExecutorAgent: script file not found at '{script_path}'."
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        self._log(
            state,
            f"Executing script (attempt {state.get('retry_count', 0) + 1} / "
            f"{_MAX_RETRIES + 1}): {script_path}",
        )

        # --- run the script -----------------------------------------------
        # On Windows, CREATE_NEW_PROCESS_GROUP isolates the child from the
        # parent's Ctrl-C / job-object signals (e.g. those fired by uvicorn's
        # watchfiles reload), preventing spurious 0xC000013A crashes.
        _extra_kwargs = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if sys.platform == "win32"
            else {}
        )

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=_EXEC_TIMEOUT,
                **_extra_kwargs,
            )
        except subprocess.TimeoutExpired:
            msg = f"Script execution timed out after {_EXEC_TIMEOUT} s (attempt {state['retry_count'] + 1})."
            logger.error(msg)
            state["errors"].append(msg)
            return self._attempt_fix(
                state,
                script_path,
                stderr=msg,
                code=script_path.read_text(encoding="utf-8"),
            )
        except OSError as exc:
            msg = f"Could not launch script process: {exc}"
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        # --- success -------------------------------------------------------
        if result.returncode == 0:
            if result.stdout:
                state["execution_log"].append(result.stdout)
            self._log(state, "Script executed successfully.")
            state["status"] = "done"
            return state

        # --- failure — enter self-heal loop --------------------------------
        stderr_text = (result.stderr or result.stdout or "").strip()
        self._log(state, f"Script failed (returncode={result.returncode}).")
        if stderr_text:
            state["execution_log"].append(
                f"[attempt {state.get('retry_count', 0) + 1} stderr]\n{stderr_text}"
            )

        return self._attempt_fix(
            state,
            script_path,
            stderr=stderr_text,
            code=script_path.read_text(encoding="utf-8"),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _attempt_fix(
        self,
        state: "MASState",
        script_path: Path,
        stderr: str,
        code: str,
    ) -> "MASState":
        """Increment retry counter, call LLM for a fix, then recurse into run()."""

        state["retry_count"] = state.get("retry_count", 0) + 1

        if state["retry_count"] > _MAX_RETRIES:
            msg = (
                f"Max retries ({_MAX_RETRIES}) exceeded. "
                f"Last error: {stderr[:300]}"
            )
            logger.error(msg)
            state["errors"].append("Max retries exceeded")
            state["status"] = "error"
            return state

        self._log(
            state,
            f"Requesting LLM fix (retry {state['retry_count']}/{_MAX_RETRIES}) …",
        )

        # Build the fix prompt.
        columns: List[str] = list(state.get("report", {}).get("columns", {}).keys())
        target_column = state.get("target_column", "target")

        user_prompt = _FIX_USER_TEMPLATE.format(
            synthesized_code=code,
            stderr=stderr,
            columns=columns,
            target_column=target_column,
        )

        try:
            fixed_code = self._call_llm(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except RuntimeError as exc:
            msg = f"LLM fix request failed: {exc}"
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        fixed_code = _strip_code_fences(fixed_code)

        if not fixed_code.strip():
            msg = "LLM returned empty fix — aborting self-heal."
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        # Overwrite script file with fixed code.
        try:
            script_path.write_text(fixed_code, encoding="utf-8")
        except OSError as exc:
            msg = f"Could not overwrite script with fix: {exc}"
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        # Sync in-memory state so recursive call uses the latest code.
        state["synthesized_code"] = fixed_code
        self._log(state, f"Script overwritten with LLM fix ({len(fixed_code)} chars).")

        # Recurse — retry_count in state guards against infinite loops.
        return self.run(state)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Remove ```python / ``` fences that LLMs often wrap responses in."""
    text = text.strip()
    fence_match = re.search(r"```(?:python)?\s*([\s\S]*?)```", text)
    if fence_match:
        return fence_match.group(1).strip()
    # Fallback: strip leading/trailing fence lines manually.
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
