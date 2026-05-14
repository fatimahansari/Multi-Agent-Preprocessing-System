"""Cleaner Agent. Handles missing values, duplicates, ID/datetime removal."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from core.agent_base import BaseAgent

if TYPE_CHECKING:
    from core.shared_state import MASState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert Python ML data engineer. "
    "Generate only executable Python code for a pandas DataFrame named df. "
    "No imports. No comments explaining what you are about to do — only code. "
    "Follow the cleaning steps exactly."
)

_USER_TEMPLATE = """\
You are generating a Python code snippet (no imports, no main block) that cleans \
a pandas DataFrame called `df`.

### Dataset file
{dataset_filename}

### Target column (NEVER modify or drop this column)
{target_column}

### Column names and dtypes
{columns_json}

### Cleaning steps to implement (JSON)
{cleaning_steps_json}

### Rules the generated code MUST follow
1. Drop duplicate rows if any cleaning step mentions duplicates.
2. Drop every column listed as an ID or index column by its exact name.
3. Missing-value strategy per column:
   - Numeric column with < 50 % nulls  → fill with column median.
   - Categorical/object column with < 50 % nulls → fill with column mode (first value).
   - Any column with ≥ 50 % nulls → drop all rows where that column is null.
4. For each datetime column identified in the steps:
   a. Parse it with pd.to_datetime (errors='coerce').
   b. Extract and add new columns: _year, _month, _day, _dayofweek, _quarter.
   c. Add cyclical encodings:
      _month_sin  = sin(2π * month  / 12)
      _month_cos  = cos(2π * month  / 12)
      _dow_sin    = sin(2π * dayofweek / 7)
      _dow_cos    = cos(2π * dayofweek / 7)
   d. Drop the original datetime column after extraction.
5. Drop every free-text column explicitly flagged in the cleaning steps.
6. Do NOT touch the target column `{target_column}` in any step.

Return only the Python code block, no explanation, no markdown fences.\
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class CleanerAgent(BaseAgent):
    """Generates a pandas-based cleaning code snippet driven by the plan.

    Reads ``state["plan"]["cleaning_steps"]`` and column metadata from
    ``state["report"]["columns"]``, calls the LLM for code generation, and
    stores the result in ``state["agent_outputs"]["cleaner"]``.
    """

    def __init__(self, llm_model: str, api_key: str) -> None:
        super().__init__(
            name="cleaner",
            llm_model=llm_model,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Generate cleaning code via LLM and store it in state."""
        self._log(state, "Extracting cleaning steps from plan …")

        cleaning_steps = state.get("plan", {}).get("cleaning_steps", [])
        if not cleaning_steps:
            self._log(state, "No cleaning steps found — skipping.")
            state["agent_outputs"]["cleaner"] = "# No cleaning steps required.\n"
            return state

        user_prompt = self._build_prompt(state, cleaning_steps)

        self._log(state, "Calling LLM for cleaning code …")
        try:
            code_snippet = self._call_llm(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except RuntimeError as exc:
            msg = str(exc)
            logger.error(msg)
            state["errors"].append(msg)
            state["agent_outputs"]["cleaner"] = _minimal_fallback(
                cleaning_steps, state.get("target_column", "")
            )
            self._log(state, "LLM unavailable — fallback cleaning code stored.")
            return state

        cleaned = _strip_code_fences(code_snippet)
        state["agent_outputs"]["cleaner"] = cleaned
        self._log(
            state,
            f"Code snippet generated ({len(cleaned)} chars)",
        )
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, state: "MASState", cleaning_steps: list) -> str:
        """Assemble the user-facing prompt from state contents."""
        report = state.get("report", {})
        target_column = state.get("target_column", "target")

        # Slim column summary: name → dtype (keeps prompt concise)
        columns_raw = report.get("columns", {})
        columns_summary = {
            col: info.get("dtype", "unknown")
            for col, info in columns_raw.items()
        }

        dataset_filename = _dataset_filename(state)

        return _USER_TEMPLATE.format(
            dataset_filename=dataset_filename,
            target_column=target_column,
            columns_json=json.dumps(columns_summary, indent=2),
            cleaning_steps_json=json.dumps(cleaning_steps, indent=2),
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Remove ```python / ``` fences that LLMs often wrap responses in."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _dataset_filename(state: "MASState") -> str:
    """Return the dataset filename from file_history or fall back to dataset_path."""
    file_history = state.get("file_history", {})
    path = file_history.get("dataset") or state.get("dataset_path", "unknown")
    # Return just the basename so the prompt stays tidy.
    from pathlib import Path  # local import keeps module-level deps minimal
    try:
        return Path(path).name
    except Exception:
        return str(path)


def _minimal_fallback(cleaning_steps: list, target_column: str) -> str:
    """Return a bare-minimum deterministic cleaning snippet for the fallback case.

    This is intentionally conservative — it only performs operations that are
    safe to run without LLM interpretation (drop duplicates, basic null handling).
    """
    lines = [
        "# CleanerAgent fallback — LLM unavailable.",
        "",
        "# Drop fully duplicate rows.",
        "df = df.drop_duplicates()",
        "",
    ]

    # Null handling: use a generic strategy since we don't have the LLM's column analysis.
    lines += [
        "# Fill numeric nulls with median; categorical nulls with mode.",
        "for _col in df.columns:",
    ]
    if target_column:
        lines += [f"    if _col == {target_column!r}:"]
        lines += [        "        continue"]
    lines += [
        "    if df[_col].dtype.kind in 'biufc':  # numeric kinds",
        "        df[_col] = df[_col].fillna(df[_col].median())",
        "    else:",
        "        _mode = df[_col].mode()",
        "        if not _mode.empty:",
        "            df[_col] = df[_col].fillna(_mode.iloc[0])",
        "",
        "# Remove helper variable.",
        "del _col",
    ]
    return "\n".join(lines) + "\n"
