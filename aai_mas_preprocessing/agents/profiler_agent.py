"""Deterministic data profiler. Generates compact report JSON."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

import pandas as pd

from core.agent_base import BaseAgent

if TYPE_CHECKING:
    from core.shared_state import MASState

logger = logging.getLogger(__name__)


# ===========================================================================
# Pure helper functions — no agent state, fully unit-testable
# ===========================================================================

def infer_task_type(df: pd.DataFrame, target_column: str) -> str:
    """Infer whether the ML task is regression, classification, or forecasting.

    Rules (evaluated in priority order):
    1. **forecasting**  — dataset contains at least one datetime column AND
       the target is numeric.
    2. **classification** — target is categorical (object / bool / category dtype)
       OR is numeric but has ≤ 20 unique values AND
       (unique_count / total_rows) < 0.05.
    3. **regression** — default fallback.

    Parameters
    ----------
    df:
        The loaded DataFrame (before any preprocessing).
    target_column:
        Name of the column to predict.

    Returns
    -------
    str
        One of ``"forecasting"``, ``"classification"``, or ``"regression"``.
    """
    if target_column not in df.columns:
        logger.warning(
            "Target column '%s' not found in DataFrame — defaulting to 'regression'.",
            target_column,
        )
        return "regression"

    target_series = df[target_column]
    target_is_numeric = pd.api.types.is_numeric_dtype(target_series)

    # --- rule 1: forecasting ------------------------------------------------
    has_datetime_col = any(
        pd.api.types.is_datetime64_any_dtype(df[c])
        or _column_looks_like_datetime(df[c])
        for c in df.columns
        if c != target_column
    )
    if has_datetime_col and target_is_numeric:
        return "forecasting"

    # --- rule 2: classification ---------------------------------------------
    target_is_categorical = pd.api.types.is_object_dtype(target_series) or \
        pd.api.types.is_bool_dtype(target_series) or \
        isinstance(target_series.dtype, pd.CategoricalDtype)

    if target_is_categorical:
        return "classification"

    if target_is_numeric:
        n_unique = target_series.nunique(dropna=True)
        ratio = n_unique / max(len(df), 1)
        if n_unique <= 20 and ratio < 0.05:
            return "classification"

    # --- rule 3: regression (default) ----------------------------------------
    return "regression"


def generate_compact_report(df: pd.DataFrame, target_column: str) -> Dict[str, Any]:
    """Build a compact JSON-serialisable profile of *df*.

    Schema
    ------
    ::

        {
          "dataset_overview": {
            "num_rows": int,
            "num_columns": int,
            "duplicate_rows": int,
            "memory_mb": float,
            "datetime_columns": [str, ...]
          },
          "columns": {
            "<col_name>": {
              "dtype": str,
              "null_count": int,
              "null_pct": float,       # 0–100
              "unique_count": int,
              "is_numeric": bool,
              "is_categorical": bool,
              "is_datetime": bool,
              # numeric only:
              "mean": float | None,
              "std": float | None,
              "min": float | None,
              "max": float | None,
              "median": float | None,
              "skewness": float | None,
              # categorical / object only:
              "top_values": {str: int},  # up to 5 most-frequent values
            },
            ...
          },
          "target_column": str
        }

    Parameters
    ----------
    df:
        Loaded DataFrame.
    target_column:
        Name of the column to predict.

    Returns
    -------
    dict
        Compact profiling report.
    """
    datetime_columns: List[str] = []
    columns_info: Dict[str, Any] = {}

    for col in df.columns:
        series = df[col]
        dtype_str = str(series.dtype)
        null_count = int(series.isnull().sum())
        null_pct = round(null_count / max(len(df), 1) * 100, 2)
        unique_count = int(series.nunique(dropna=True))

        is_numeric = pd.api.types.is_numeric_dtype(series)
        is_datetime = (
            pd.api.types.is_datetime64_any_dtype(series)
            or _column_looks_like_datetime(series)
        )
        is_categorical = (
            not is_numeric
            and not is_datetime
        )

        if is_datetime:
            datetime_columns.append(col)

        col_info: Dict[str, Any] = {
            "dtype": dtype_str,
            "null_count": null_count,
            "null_pct": null_pct,
            "unique_count": unique_count,
            "is_numeric": is_numeric,
            "is_categorical": is_categorical,
            "is_datetime": is_datetime,
            # filled conditionally below
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
            "median": None,
            "skewness": None,
            "top_values": {},
        }

        if is_numeric:
            non_null = series.dropna()
            col_info["mean"]     = _safe_float(non_null.mean())
            col_info["std"]      = _safe_float(non_null.std())
            col_info["min"]      = _safe_float(non_null.min())
            col_info["max"]      = _safe_float(non_null.max())
            col_info["median"]   = _safe_float(non_null.median())
            col_info["skewness"] = _safe_float(non_null.skew())

        if is_categorical or (is_numeric and unique_count <= 30):
            top = (
                series.dropna()
                .astype(str)
                .value_counts()
                .head(5)
                .to_dict()
            )
            col_info["top_values"] = {str(k): int(v) for k, v in top.items()}

        columns_info[col] = col_info

    report: Dict[str, Any] = {
        "dataset_overview": {
            "num_rows": len(df),
            "num_columns": len(df.columns),
            "duplicate_rows": int(df.duplicated().sum()),
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1_048_576, 3),
            "datetime_columns": datetime_columns,
        },
        "columns": columns_info,
        "target_column": target_column,
    }
    return report


# ===========================================================================
# Agent class
# ===========================================================================

class ProfilerAgent(BaseAgent):
    """Deterministic profiler — loads the CSV, builds the report, infers task type.

    Does **not** call any LLM.  The ``llm_model`` and ``llm_endpoint``
    constructor arguments are accepted for interface consistency but are
    never used.
    """

    def __init__(
        self,
        llm_model: str = "",
        api_key: str = "",
    ) -> None:
        super().__init__(
            name="profiler",
            llm_model=llm_model,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Profile the dataset and update state with report + task_type."""
        dataset_path = state["dataset_path"]
        target_column = state["target_column"]

        self._log(state, f"Loading CSV: {dataset_path}")
        try:
            df = pd.read_csv(dataset_path)
        except Exception as exc:
            msg = f"Failed to load CSV '{dataset_path}': {exc}"
            logger.error(msg)
            state["errors"].append(msg)
            state["status"] = "error"
            return state

        self._log(state, f"Loaded {len(df)} rows × {len(df.columns)} columns.")

        # --- profiling ------------------------------------------------------
        report = generate_compact_report(df, target_column)
        state["report"] = report
        self._log(state, "Compact report generated.")

        # --- task type inference --------------------------------------------
        task_type = infer_task_type(df, target_column)
        state["task_type"] = task_type
        self._log(state, f"Inferred task type: {task_type}")

        # --- persist report to disk next to the CSV -------------------------
        csv_path = Path(dataset_path).resolve()
        report_path = csv_path.parent / f"{csv_path.stem}_report.json"
        try:
            with open(report_path, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, default=str)
            abs_report_path = str(report_path.resolve())
            state["file_history"]["report"] = abs_report_path
            self._log(state, f"Report saved to: {abs_report_path}")
        except OSError as exc:
            msg = f"Could not save report JSON: {exc}"
            logger.warning(msg)
            state["errors"].append(msg)

        # --- advance pipeline status ----------------------------------------
        state["status"] = "planning"
        self._log(state, "Status → planning.")
        return state


# ===========================================================================
# Private module helpers
# ===========================================================================

def _column_looks_like_datetime(series: pd.Series) -> bool:
    """Heuristic: try parsing the first non-null string value as a datetime."""
    if not pd.api.types.is_object_dtype(series):
        return False
    sample = series.dropna().head(5)
    if sample.empty:
        return False
    try:
        pd.to_datetime(sample, infer_datetime_format=True, errors="raise")
        return True
    except Exception:
        return False


def _safe_float(value: Any) -> "float | None":
    """Convert a numpy scalar to a plain Python float, returning None on NaN/Inf."""
    try:
        f = float(value)
        if f != f:      # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None
