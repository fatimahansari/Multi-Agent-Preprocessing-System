"""Validation Agent. Post-processing checks on cleaned data."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from core.agent_base import BaseAgent

if TYPE_CHECKING:
    from core.shared_state import MASState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a data quality engineer. "
    "Generate only executable Python validation code for a pandas DataFrame "
    "named df. Use try/except for all assertions so warnings are printed but "
    "execution continues. No imports."
)

_USER_TEMPLATE = """\
You are validating a preprocessed dataset. Generate Python validation code \
(no imports, no main block) for a pandas DataFrame called `df`.

### Context
- Target column : {target_column}
- Task type     : {task_type}
- Dataset shape : {rows} rows × {cols} columns

### Validation steps requested by the planner
{validation_steps}

### Required checks (wrap every assert in try/except — print a WARNING, never raise):
1. assert df.isnull().sum().sum() == 0
2. assert "{target_column}" in df.columns
3. assert len(df) > 10
4. assert not np.isinf(df.select_dtypes('number')).any().any()
{class_imbalance_instruction}
5. Print "✓ Validation passed" if all checks complete without fatal errors.

Return only the Python code block, no explanation.
"""

_CLASS_IMBALANCE_LINE = (
    "4b. If the plan flags class imbalance, print: "
    "\"WARNING: class imbalance detected — consider class_weight='balanced'\""
)


class ValidationAgent(BaseAgent):
    """Runs post-processing sanity checks on the cleaned DataFrame.

    Reads ``state["plan"]["validation_steps"]`` plus dataset metadata from
    ``state["report"]``, asks the LLM to produce a self-contained validation
    code snippet, and stores the result in
    ``state["agent_outputs"]["validation"]``.
    """

    # BaseAgent subclasses identify themselves by name so the coordinator
    # can route results into agent_outputs with the correct key.
    name: str = "validation"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Generate validation code via LLM and store it in state."""
        logger.info("[ValidationAgent] Building validation prompt …")

        user_prompt = self._build_prompt(state)

        logger.info("[ValidationAgent] Calling LLM …")
        try:
            code_snippet = self._call_llm(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"ValidationAgent LLM call failed: {exc}"
            logger.error(msg)
            state["errors"].append(msg)
            # Store an empty-but-safe fallback so the pipeline can continue.
            state["agent_outputs"]["validation"] = _FALLBACK_CODE
            return state

        cleaned = _strip_code_fences(code_snippet)
        state["agent_outputs"]["validation"] = cleaned
        logger.info("[ValidationAgent] Code snippet stored in agent_outputs.")
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, state: "MASState") -> str:
        """Assemble the user-facing prompt from state contents."""
        plan = state.get("plan", {})
        validation_steps: list = plan.get("validation_steps", [])
        report = state.get("report", {})
        overview = report.get("dataset_overview", {})

        rows = overview.get("num_rows", "unknown")
        cols = overview.get("num_columns", "unknown")
        target_column = state.get("target_column", "target")
        task_type = state.get("task_type", "unknown")

        # Pretty-print the step list so the LLM has full context.
        steps_text = (
            json.dumps(validation_steps, indent=2)
            if validation_steps
            else "No explicit validation steps — apply all standard checks."
        )

        # Only include the class-imbalance line for classification tasks.
        class_imbalance_instruction = ""
        if task_type == "classification":
            flags_imbalance = any(
                "imbalance" in str(step).lower() for step in validation_steps
            )
            if flags_imbalance:
                class_imbalance_instruction = _CLASS_IMBALANCE_LINE + "\n"

        return _USER_TEMPLATE.format(
            target_column=target_column,
            task_type=task_type,
            rows=rows,
            cols=cols,
            validation_steps=steps_text,
            class_imbalance_instruction=class_imbalance_instruction,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Remove ```python / ``` fences that some LLMs wrap their output in."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


# Safe fallback — used when the LLM call itself fails so the pipeline
# can continue and the synthesizer has *something* to merge.
_FALLBACK_CODE = """\
# ValidationAgent: LLM unavailable — running minimal built-in checks only.
try:
    assert df.isnull().sum().sum() == 0
except AssertionError:
    print("WARNING: df contains null values after cleaning.")

try:
    assert len(df) > 10
except AssertionError:
    print("WARNING: DataFrame has 10 or fewer rows.")

print("\\u2713 Validation passed (fallback mode).")
"""
