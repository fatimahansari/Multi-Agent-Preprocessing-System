"""Outlier Agent. Detects and resolves outliers per column."""

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
    "You are an expert Python ML engineer specializing in outlier treatment. "
    "Generate only executable pandas/sklearn code for a DataFrame named df. "
    "No imports. Clip numeric values in-place; do not reassign df itself."
)

_USER_TEMPLATE = """\
Generate a Python code snippet (no imports, no main block) that performs outlier \
treatment on a pandas DataFrame called `df`.

### Target column (NEVER modify this column)
{target_column}

### Outlier steps to implement (JSON)
{outlier_steps_json}

### Rules the generated code MUST follow

IQR method  (method = "iqr"):
  Q1  = df[col].quantile(0.25)
  Q3  = df[col].quantile(0.75)
  IQR = Q3 - Q1
  lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
  action = "clip"   → df[col] = df[col].clip(lower=lower, upper=upper)
  action = "remove" → df = df[(df[col] >= lower) & (df[col] <= upper)]  (use .copy())
  action = "flag"   → df["{col}_outlier_flag"] = ~df[col].between(lower, upper)

Z-score method  (method = "zscore"):
  mean, std = df[col].mean(), df[col].std()
  z         = (df[col] - mean) / std
  action = "clip"   → df[col] = df[col].clip(lower=mean - 3*std, upper=mean + 3*std)
  action = "remove" → df = df[z.abs() <= 3].copy()
  action = "flag"   → df["{col}_outlier_flag"] = z.abs() > 3

IsolationForest method  (method = "isolation_forest"):
  Fit IsolationForest(contamination=0.05, random_state=42) on df[[col]].
  Predict labels (-1 = outlier, 1 = inlier).
  Always flag (regardless of action field):
    df["{col}_outlier_flag"] = (model.predict(df[[col]]) == -1)
  If action = "remove": also drop rows where {col}_outlier_flag is True, then drop the flag column.

Important:
- Process each step independently; do NOT modify the target column `{target_column}`.
- When action = "remove" and df is reassigned, always call .copy() to avoid SettingWithCopyWarning.
- Use descriptive variable names per column (e.g. q1_{col}, q3_{col}) to avoid collisions.
- Return only the Python code block — no explanation, no markdown fences.\
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class OutlierAgent(BaseAgent):
    """Generates per-column outlier treatment code driven by the plan.

    Reads ``state["plan"]["outlier_steps"]``, calls the LLM, and stores the
    resulting snippet in ``state["agent_outputs"]["outlier"]``.
    """

    def __init__(self, llm_model: str, api_key: str) -> None:
        super().__init__(
            name="outlier",
            llm_model=llm_model,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Generate outlier treatment code via LLM and store it in state."""
        outlier_steps = state.get("plan", {}).get("outlier_steps", [])

        if not outlier_steps:
            self._log(state, "No outlier steps required — skipping.")
            state["agent_outputs"]["outlier"] = "# No outlier treatment required.\n"
            return state

        self._log(state, f"Building outlier prompt for {len(outlier_steps)} step(s) …")
        user_prompt = self._build_prompt(state, outlier_steps)

        self._log(state, "Calling LLM for outlier treatment code …")
        try:
            code_snippet = self._call_llm(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except RuntimeError as exc:
            msg = str(exc)
            logger.error(msg)
            state["errors"].append(msg)
            fallback = _minimal_fallback(outlier_steps, state.get("target_column", ""))
            state["agent_outputs"]["outlier"] = fallback
            self._log(state, "LLM unavailable — fallback outlier code stored.")
            return state

        cleaned = _strip_code_fences(code_snippet)
        state["agent_outputs"]["outlier"] = cleaned
        self._log(state, f"Code snippet generated ({len(cleaned)} chars)")
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, state: "MASState", outlier_steps: list) -> str:
        target_column = state.get("target_column", "target")
        return _USER_TEMPLATE.format(
            target_column=target_column,
            outlier_steps_json=json.dumps(outlier_steps, indent=2),
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


def _minimal_fallback(outlier_steps: list, target_column: str) -> str:
    """IQR-clip fallback for every numeric column listed in outlier_steps.

    Used only when the LLM is unreachable so the pipeline can still proceed.
    Applies IQR clipping (the safest action) regardless of the requested method.
    """
    lines = [
        "# OutlierAgent fallback — LLM unavailable; applying IQR clip to all listed columns.",
        "",
    ]
    for step in outlier_steps:
        cols = step.get("columns") or ([step["column"]] if "column" in step else [])
        for col in cols:
            if col == target_column:
                continue
            var = col.replace(" ", "_").replace("-", "_")
            lines += [
                f"# IQR clip: {col}",
                f"_q1_{var} = df[{col!r}].quantile(0.25)",
                f"_q3_{var} = df[{col!r}].quantile(0.75)",
                f"_iqr_{var} = _q3_{var} - _q1_{var}",
                f"df[{col!r}] = df[{col!r}].clip(",
                f"    lower=_q1_{var} - 1.5 * _iqr_{var},",
                f"    upper=_q3_{var} + 1.5 * _iqr_{var},",
                f")",
                "",
            ]

    if len(lines) == 2:
        lines.append("# No eligible columns found in outlier_steps.")

    # Clean up temporary variables.
    lines += [
        "# Clean up temporary IQR variables.",
        "for _v in [k for k in dir() if k.startswith(('_q1_', '_q3_', '_iqr_'))]:",
        "    del _v",
    ]
    return "\n".join(lines) + "\n"
