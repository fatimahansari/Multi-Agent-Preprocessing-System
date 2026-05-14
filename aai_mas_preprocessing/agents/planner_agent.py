"""LLM-powered planner. Reads report JSON, outputs structured plan JSON."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from core.agent_base import BaseAgent

if TYPE_CHECKING:
    from core.shared_state import MASState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a meticulous data preprocessing expert for ML pipelines. "
    "You only see dataset metadata — never raw rows. "
    "Always return a valid JSON object and nothing else. "
    "Your guiding principle is MINIMAL, JUSTIFIED preprocessing: "
    "only add a step if there is a clear, specific reason it will help the ML model. "
    "When in doubt, leave the data alone."
)

_USER_TEMPLATE = """\
Dataset report (JSON):
{report_json}

Task type: {task_type}

Analyze the report and return a JSON object with exactly these four keys:
- cleaning_steps
- outlier_steps
- feature_steps
- validation_steps

Each step object must have: step_name (str), column (str), reason (str), \
action (str — concrete instruction for code generation).

━━━ CLEANING STEPS ━━━
Include a step only for:
• Columns with null values → specify the imputation strategy (median for numeric, \
mode for categorical).
• Duplicate rows → drop them if duplicates exist.
• Pure ID columns (unique count ≈ row count, no predictive value) → drop them.
• Datetime string columns → parse to datetime only; do NOT extract components here.
• Free-text columns (high cardinality strings with no obvious categories) → drop them.
DO NOT add cleaning steps for columns that are already clean.

━━━ OUTLIER STEPS ━━━
Only add an outlier step for a numeric column if ALL of these are true:
1. The column is NOT the target column.
2. The profiler report shows the column has significant skewness (|skew| > 2) \
OR the max/min ratio suggests extreme values.
3. The column is not a flag/indicator/binary column.
Choose: method = iqr (default), zscore (for normally distributed), \
isolation_forest (for multi-dimensional anomalies only).
Action = clip (safest default). Use remove only if outliers are clearly erroneous. \
Use flag only if you want to preserve the outlier information.
If no column clearly meets these criteria, return an empty list.

━━━ FEATURE STEPS ━━━
Be very conservative. Only add a step if the column genuinely needs it.

Categorical columns (low-cardinality strings):
• ≤ 5 unique values → ohe (one-hot encoding).
• > 5 unique values AND regression/forecasting task → target_encode.
• > 5 unique values AND classification task → label_encode.

Numeric columns:
• Only apply minmax or standard scaling if the model requires it \
(e.g. distance-based models). For tree-based tasks, skip scaling entirely unless \
the report suggests the task needs it.
• Only apply log transform if the column is heavily right-skewed (skew > 2) \
AND all values are non-negative.

Datetime columns — strict rules:
• DO NOT decompose a datetime column unless the column name or task type strongly \
implies time-based seasonality (e.g. a column named "timestamp" in a forecasting task \
where month/hour patterns clearly matter).
• If the date is effectively an ordered index (e.g. "Date" in a stock price dataset), \
DO NOT decompose it — either drop it or convert it to a numeric ordinal once in \
cleaning_steps.
• If decomposition IS justified, extract the MINIMUM useful components only \
(e.g. for monthly seasonality: month only; for intraday patterns: hour only). \
NEVER extract all of year+month+day+hour+dayofweek+quarter unless each component \
has a specific stated reason.
• Cyclical encoding (technique = cyclical) is only appropriate for periodic integer \
columns (month 1–12, hour 0–23, dayofweek 0–6) that have ALREADY been extracted.

Avoid redundant steps: do not scale a column that will be one-hot encoded; \
do not encode the target column; do not add a step with no clear benefit.

━━━ VALIDATION STEPS ━━━
Add checks for: no remaining nulls in key columns, target column still present, \
shape sanity (rows not reduced by > 50%), dtype correctness.
For classification with class imbalance > 0.7, add a note recommending \
class_weight='balanced'.

Return ONLY the JSON object — no explanation, no markdown.\
"""

_RETRY_PROMPT = (
    "Your previous response was not valid JSON. "
    "Return only the JSON object, no markdown."
)

# Keys the plan dict must contain; missing ones are filled with empty lists.
_REQUIRED_PLAN_KEYS = ("cleaning_steps", "outlier_steps", "feature_steps", "validation_steps")

_MAX_ATTEMPTS = 2


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class PlannerAgent(BaseAgent):
    """LLM-powered planner: reads the profiler report and emits a structured plan.

    The plan is a dict with four list-of-step keys consumed by the coordinator
    to dispatch work to specialist agents.
    """

    def __init__(self, llm_model: str, api_key: str) -> None:
        super().__init__(
            name="planner",
            llm_model=llm_model,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Generate the preprocessing plan and store it in state."""
        self._log(state, "Building planner prompt from report …")

        report = state.get("report", {})
        task_type = state.get("task_type", "unknown")

        # Serialize report to a compact (but readable) JSON string.
        try:
            report_json = json.dumps(report, indent=2, default=str)
        except (TypeError, ValueError) as exc:
            msg = f"Could not serialise report to JSON: {exc}"
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        user_prompt = _USER_TEMPLATE.format(
            report_json=report_json,
            task_type=task_type,
        )

        # --- LLM call with one retry on bad JSON ----------------------------
        plan = self._call_with_retry(state, user_prompt)
        if plan is None:
            state["status"] = "error"
            return state

        # Guarantee all four keys exist (planner may omit empty sections).
        for key in _REQUIRED_PLAN_KEYS:
            plan.setdefault(key, [])

        state["plan"] = plan
        self._log(state, "Plan stored in state.")

        # --- persist plan to disk next to the CSV ---------------------------
        csv_path = Path(state["dataset_path"]).resolve()
        plan_path = csv_path.parent / f"{csv_path.stem}_plan.json"
        try:
            with open(plan_path, "w", encoding="utf-8") as fh:
                json.dump(plan, fh, indent=2, default=str)
            abs_plan_path = str(plan_path.resolve())
            state["file_history"]["plan"] = abs_plan_path
            self._log(state, f"Plan saved to: {abs_plan_path}")
        except OSError as exc:
            msg = f"Could not save plan JSON: {exc}"
            logger.warning(msg)
            state["errors"].append(msg)

        state["status"] = "processing"
        self._log(state, "Status → processing.")
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        state: "MASState",
        user_prompt: str,
    ) -> "Dict[str, Any] | None":
        """Call the LLM and attempt to parse the response as JSON.

        Makes up to ``_MAX_ATTEMPTS`` attempts:
        - Attempt 1: full user prompt.
        - Attempt 2: correction prompt asking for valid JSON only.

        Returns the parsed dict on success, or ``None`` after all attempts
        fail (errors are appended to ``state["errors"]``).
        """
        current_prompt = user_prompt
        last_raw = ""

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            self._log(state, f"LLM attempt {attempt}/{_MAX_ATTEMPTS} …")
            try:
                raw = self._call_llm(
                    system_prompt=_SYSTEM_PROMPT,
                    user_prompt=current_prompt,
                )
            except RuntimeError as exc:
                msg = str(exc)
                logger.error(msg)
                state["errors"].append(msg)
                return None  # network / HTTP failure — no point retrying

            last_raw = raw
            parsed = _try_parse_json(raw)
            if parsed is not None:
                self._log(state, f"Plan parsed successfully on attempt {attempt}.")
                return parsed

            # Bad JSON — log and prepare the retry prompt.
            msg = (
                f"Attempt {attempt}: LLM returned invalid JSON. "
                f"First 200 chars: {raw[:200]!r}"
            )
            logger.warning(msg)
            state["errors"].append(msg)

            if attempt < _MAX_ATTEMPTS:
                # Feed the bad response back so the LLM sees what it produced.
                current_prompt = (
                    f"{_RETRY_PROMPT}\n\n"
                    f"Previous response:\n{last_raw[:1000]}"
                )

        raise RuntimeError(
            f"[{self.name}] Failed to obtain valid JSON plan after "
            f"{_MAX_ATTEMPTS} attempts. Last response: {last_raw[:300]!r}"
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _try_parse_json(text: str) -> "Dict[str, Any] | None":
    """Try to parse *text* as JSON, with light pre-processing.

    Handles three common LLM response patterns:
    1. Pure JSON (ideal).
    2. JSON wrapped in ```json … ``` or ``` … ``` code fences.
    3. JSON embedded after a short prose preamble (finds the first ``{``).

    Returns the parsed dict, or ``None`` on failure.
    """
    text = text.strip()

    # Strip markdown code fences.
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # If the response starts with prose, jump to the first '{'.
    brace_idx = text.find("{")
    if brace_idx > 0:
        text = text[brace_idx:]

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        return None
