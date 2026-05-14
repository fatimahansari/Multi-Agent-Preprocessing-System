"""Feature Engineer Agent. Encoding, scaling, transforms."""

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
    "You are an expert ML feature engineer. "
    "Generate only executable Python code for a pandas DataFrame named df. "
    "No imports. Do not encode or scale the target column. "
    "Use sklearn and numpy as if already imported."
)

_USER_TEMPLATE = """\
Generate a Python code snippet (no imports, no main block) that applies feature \
engineering transformations to a pandas DataFrame called `df`.

### Target column (NEVER encode, scale, or drop this column)
{target_column}

### Task type
{task_type}

### Feature engineering steps to implement (JSON)
{feature_steps_json}

### Technique reference — implement each step exactly as specified below

ohe (One-Hot Encoding):
  df = pd.get_dummies(df, columns=[<col>, ...], drop_first=True)
  Cast new bool columns to int: df = df.astype({{c: int for c in df.select_dtypes(bool).columns}})
  Do NOT hardcode any downstream column names after this step.

label_encode (Label Encoding):
  le_{{col}} = LabelEncoder()
  df["{{col}}_encoded"] = le_{{col}}.fit_transform(df["{{col}}"].astype(str))
  df = df.drop(columns=["{{col}}"])

target_encode (Target Encoding — regression/classification only):
  _target_map_{{col}} = df.groupby("{{col}}")["{{target_column}}"].mean()
  df["{{col}}"] = df["{{col}}"].map(_target_map_{{col}})
  Fill any unmapped NaN with the global mean: df["{{col}}"] = df["{{col}}"].fillna(df["{{target_column}}"].mean())

minmax (Min-Max Scaling):
  minmax_scaler = MinMaxScaler()
  df[[<cols>]] = minmax_scaler.fit_transform(df[[<cols>]])

standard (Standard Scaling):
  standard_scaler = StandardScaler()
  df[[<cols>]] = standard_scaler.fit_transform(df[[<cols>]])

log (Log Transform):
  Apply numpy.log1p to each specified column:
  df["{{col}}"] = np.log1p(df["{{col}}"].clip(lower=0))
  (clip at 0 first to guard against negative values from upstream clipping)

cyclical (Cyclical Encoding for already-extracted integer columns):
  For a month column (period = 12):
    df["{{col}}_sin"] = np.sin(2 * np.pi * df["{{col}}"] / 12)
    df["{{col}}_cos"] = np.cos(2 * np.pi * df["{{col}}"] / 12)
  For a dayofweek column (period = 7):
    df["{{col}}_sin"] = np.sin(2 * np.pi * df["{{col}}"] / 7)
    df["{{col}}_cos"] = np.cos(2 * np.pi * df["{{col}}"] / 7)
  Drop the original integer column after encoding.

### Important constraints
1. Process steps in the order they appear in the JSON above.
2. Never encode, scale, or drop the target column `{target_column}`.
3. Store any scaler instances as `minmax_scaler` and `standard_scaler` \
(these variables may be referenced later for inverse transforms).
4. After OHE, do NOT reference specific column names that may have been renamed.
5. Use descriptive per-column variable names (e.g. `le_age`, `_target_map_city`) \
to avoid name collisions across steps.
6. Return only the Python code block — no explanation, no markdown fences.\
"""


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class FeatureEngineerAgent(BaseAgent):
    """Generates feature engineering code driven by the plan's feature_steps.

    Reads ``state["plan"]["feature_steps"]``, calls the LLM, and stores the
    result in ``state["agent_outputs"]["feature_engineer"]``.
    """

    def __init__(self, llm_model: str, api_key: str) -> None:
        super().__init__(
            name="feature_engineer",
            llm_model=llm_model,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Generate feature engineering code via LLM and store it in state."""
        feature_steps = state.get("plan", {}).get("feature_steps", [])

        if not feature_steps:
            self._log(state, "No feature engineering steps found — skipping.")
            state["agent_outputs"]["feature_engineer"] = (
                "# No feature engineering steps required.\n"
            )
            return state

        self._log(
            state,
            f"Building feature engineering prompt for {len(feature_steps)} step(s) …",
        )
        user_prompt = self._build_prompt(state, feature_steps)

        self._log(state, "Calling LLM for feature engineering code …")
        try:
            code_snippet = self._call_llm(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
        except RuntimeError as exc:
            msg = str(exc)
            logger.error(msg)
            state["errors"].append(msg)
            fallback = _minimal_fallback(feature_steps, state.get("target_column", ""))
            state["agent_outputs"]["feature_engineer"] = fallback
            self._log(state, "LLM unavailable — fallback feature engineering code stored.")
            return state

        cleaned = _strip_code_fences(code_snippet)
        state["agent_outputs"]["feature_engineer"] = cleaned
        self._log(state, f"Code snippet generated ({len(cleaned)} chars)")
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, state: "MASState", feature_steps: list) -> str:
        target_column = state.get("target_column", "target")
        task_type = state.get("task_type", "unknown")
        return _USER_TEMPLATE.format(
            target_column=target_column,
            task_type=task_type,
            feature_steps_json=json.dumps(feature_steps, indent=2),
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


def _minimal_fallback(feature_steps: list, target_column: str) -> str:
    """Deterministic fallback: apply only safe, import-free transformations.

    When the LLM is unreachable, this function generates conservative code that:
    - log-transforms positively-skewed numeric columns (technique=log)
    - skips anything requiring sklearn (minmax, standard, label_encode, ohe)
      since those require import statements that won't be available in the snippet
    """
    lines = [
        "# FeatureEngineerAgent fallback — LLM unavailable.",
        "# Only log transforms are applied; sklearn-based steps are skipped.",
        "",
    ]

    applied_any = False
    for step in feature_steps:
        technique = step.get("technique", "")
        cols = step.get("columns") or ([step["column"]] if "column" in step else [])

        if technique == "log":
            for col in cols:
                if col == target_column:
                    continue
                lines += [
                    f"# log1p transform: {col}",
                    f"df[{col!r}] = np.log1p(df[{col!r}].clip(lower=0))",
                    "",
                ]
                applied_any = True
        elif technique in ("minmax", "standard", "ohe", "label_encode",
                           "target_encode", "cyclical"):
            lines.append(
                f"# SKIPPED (fallback mode): technique='{technique}' "
                f"for columns {cols} — re-run with LLM available."
            )

    if not applied_any:
        lines.append("# No log-transform steps found; no changes applied.")

    return "\n".join(lines) + "\n"
