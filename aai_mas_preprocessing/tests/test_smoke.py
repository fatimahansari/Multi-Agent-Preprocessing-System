"""Smoke test for the full MAS preprocessing pipeline.

Runs without a live Ollama instance by mocking _call_llm on every LLM-backed
agent.  The executor subprocess *does* run real Python code, so pandas, numpy,
and scikit-learn must be installed in the test environment.

Run with:
    cd aai_mas_preprocessing
    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Hardcoded mock return values
# ---------------------------------------------------------------------------

_PLAN_DICT = {
    "cleaning_steps": [
        {
            "step_name": "drop_duplicates",
            "columns": [],
            "reason": "test",
            "action": "df.drop_duplicates(inplace=True)",
        }
    ],
    "outlier_steps": [],
    "feature_steps": [
        {
            "step_name": "scale_income",
            "columns": ["income"],
            "technique": "standard",
            "reason": "test",
            "action": "scale income",
        }
    ],
    "validation_steps": [
        {
            "step_name": "null_check",
            "columns": [],
            "reason": "test",
            "action": "assert no nulls",
        }
    ],
}

_PLANNER_RESPONSE = json.dumps(_PLAN_DICT)

_CLEANER_CODE = "df.drop_duplicates(inplace=True)"

_OUTLIER_CODE = ""

_FEATURE_ENGINEER_CODE = (
    "from sklearn.preprocessing import StandardScaler\n"
    "scaler = StandardScaler()\n"
    "df[['income']] = scaler.fit_transform(df[['income']])\n"
)

_VALIDATION_CODE = "print('\\u2713 Validation passed')"

# Executor self-heal mock — only called if the script fails; returns the
# current synthesized code unchanged so the retry path is exercised but
# does not introduce new bugs.
_EXECUTOR_FIX_SENTINEL = "__EXECUTOR_FIX_SENTINEL__"


# ---------------------------------------------------------------------------
# Fixture: synthetic CSV on disk
# ---------------------------------------------------------------------------

@pytest.fixture()
def synthetic_csv(tmp_path: Path) -> Path:
    """Write a 20-row synthetic dataset to a temp file and return its path."""
    data = {
        "age":      [25, 32, 47, 51, 62, 19, 38, 44, 29, 55,
                     34, 41, 27, 60, 48, 33, 39, 52, 23, 45],
        "income":   [40000.0, 55000.0, 72000.0, 90000.0, 62000.0,
                     30000.0, 48000.0, 85000.0, 37000.0, 95000.0,
                     52000.0, 67000.0, 43000.0, 88000.0, 74000.0,
                     50000.0, 61000.0, 79000.0, 35000.0, 69000.0],
        "city":     (["London", "Paris", "Berlin"] * 7)[:20],
        "has_loan": ([True, False] * 10),
        "price":    [200.0 + i * 15.5 for i in range(20)],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "test_dataset.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_mock(return_value: str) -> MagicMock:
    """Return a MagicMock that always returns *return_value* when called."""
    m = MagicMock(return_value=return_value)
    return m


def _executor_fix_side_effect(system_prompt: str, user_prompt: str) -> str:  # noqa: ARG001
    """Return the synthesized code unchanged so retry doesn't break things."""
    # Extract the current code from the user prompt ("Current code:\n{code}\n").
    marker = "Current code:\n"
    if marker in user_prompt:
        code_and_rest = user_prompt.split(marker, 1)[1]
        code = code_and_rest.split("\n\nExecution error:")[0]
        return code
    return "# executor fallback\n"


# ---------------------------------------------------------------------------
# Main smoke test
# ---------------------------------------------------------------------------

@patch("agents.planner_agent.PlannerAgent._call_llm",
       new_callable=lambda: lambda *_: _make_llm_mock(_PLANNER_RESPONSE))
class TestMASSmoke:
    """Namespace that groups smoke-test cases; avoids module-level patch leakage."""

    def test_full_pipeline(self, synthetic_csv: Path) -> None:  # noqa: PLR0914
        """End-to-end smoke test with all LLM calls mocked."""

        with (
            patch("agents.planner_agent.PlannerAgent._call_llm",
                  return_value=_PLANNER_RESPONSE),
            patch("agents.cleaner_agent.CleanerAgent._call_llm",
                  return_value=_CLEANER_CODE),
            patch("agents.outlier_agent.OutlierAgent._call_llm",
                  return_value=_OUTLIER_CODE),
            patch("agents.feature_engineer_agent.FeatureEngineerAgent._call_llm",
                  return_value=_FEATURE_ENGINEER_CODE),
            patch("agents.validation_agent.ValidationAgent._call_llm",
                  return_value=_VALIDATION_CODE),
            patch("agents.executor_agent.ExecutorAgent._call_llm",
                  side_effect=_executor_fix_side_effect),
        ):
            from mas_orchestrator import run_mas

            result = run_mas(str(synthetic_csv), "price")

        # ------------------------------------------------------------------
        # Assertions
        # ------------------------------------------------------------------

        # 1. Pipeline must not be stuck in "pending" or "profiling"
        assert result["status"] in {"done", "error"}, (
            f"Unexpected status: {result['status']!r}\n"
            f"Errors: {result.get('errors', [])}"
        )

        # 2. Profiler must have populated the report
        assert result["report"], "report should be a non-empty dict"
        assert "dataset_overview" in result["report"], (
            "report missing 'dataset_overview' key"
        )
        assert result["report"]["dataset_overview"]["num_rows"] == 20

        # 3. Plan must have all four required sections
        plan = result["plan"]
        for key in ("cleaning_steps", "outlier_steps", "feature_steps", "validation_steps"):
            assert key in plan, f"plan missing key: {key!r}"

        # 4. Agent outputs must include at minimum cleaner and feature_engineer
        outputs = result.get("agent_outputs", {})
        assert "cleaner" in outputs, "agent_outputs missing 'cleaner'"
        assert "feature_engineer" in outputs, "agent_outputs missing 'feature_engineer'"

        # 5. Synthesized script file must exist on disk
        file_history = result.get("file_history", {})
        script_path_str = file_history.get("script", "")
        assert script_path_str, "file_history['script'] is empty"
        assert Path(script_path_str).exists(), (
            f"Synthesized script not found on disk: {script_path_str}"
        )
        assert script_path_str.endswith("_preprocessing.py"), (
            f"Script filename has unexpected suffix: {script_path_str}"
        )

    def test_report_column_keys(self, synthetic_csv: Path) -> None:
        """Verify the profiler report contains expected per-column metadata."""

        with (
            patch("agents.planner_agent.PlannerAgent._call_llm",
                  return_value=_PLANNER_RESPONSE),
            patch("agents.cleaner_agent.CleanerAgent._call_llm",
                  return_value=_CLEANER_CODE),
            patch("agents.outlier_agent.OutlierAgent._call_llm",
                  return_value=_OUTLIER_CODE),
            patch("agents.feature_engineer_agent.FeatureEngineerAgent._call_llm",
                  return_value=_FEATURE_ENGINEER_CODE),
            patch("agents.validation_agent.ValidationAgent._call_llm",
                  return_value=_VALIDATION_CODE),
            patch("agents.executor_agent.ExecutorAgent._call_llm",
                  side_effect=_executor_fix_side_effect),
        ):
            from mas_orchestrator import run_mas

            result = run_mas(str(synthetic_csv), "price")

        report_columns = result["report"].get("columns", {})
        for col in ("age", "income", "city", "has_loan", "price"):
            assert col in report_columns, f"report missing column: {col!r}"

        # Each column entry must have the base profiler keys.
        for col, info in report_columns.items():
            for key in ("dtype", "null_count", "null_pct", "unique_count",
                        "is_numeric", "is_categorical", "is_datetime"):
                assert key in info, (
                    f"report['columns'][{col!r}] missing key {key!r}"
                )

    def test_task_type_inferred(self, synthetic_csv: Path) -> None:
        """Verify task_type is set to a known value after profiling."""

        with (
            patch("agents.planner_agent.PlannerAgent._call_llm",
                  return_value=_PLANNER_RESPONSE),
            patch("agents.cleaner_agent.CleanerAgent._call_llm",
                  return_value=_CLEANER_CODE),
            patch("agents.outlier_agent.OutlierAgent._call_llm",
                  return_value=_OUTLIER_CODE),
            patch("agents.feature_engineer_agent.FeatureEngineerAgent._call_llm",
                  return_value=_FEATURE_ENGINEER_CODE),
            patch("agents.validation_agent.ValidationAgent._call_llm",
                  return_value=_VALIDATION_CODE),
            patch("agents.executor_agent.ExecutorAgent._call_llm",
                  side_effect=_executor_fix_side_effect),
        ):
            from mas_orchestrator import run_mas

            result = run_mas(str(synthetic_csv), "price")

        assert result["task_type"] in {"regression", "classification", "forecasting"}, (
            f"Unexpected task_type: {result['task_type']!r}"
        )


# ---------------------------------------------------------------------------
# Isolated unit: test create_initial_state
# ---------------------------------------------------------------------------

def test_create_initial_state() -> None:
    """create_initial_state returns a fully-formed MASState with correct defaults."""
    from core.shared_state import create_initial_state

    state = create_initial_state("/data/sample.csv", "target_col")

    assert state["dataset_path"] == "/data/sample.csv"
    assert state["target_column"] == "target_col"
    assert state["status"] == "pending"
    assert state["retry_count"] == 0
    assert state["report"] == {}
    assert state["agent_outputs"] == {}
    assert state["synthesized_code"] == ""
    assert state["execution_log"] == []
    assert state["errors"] == []
    assert "cleaning_steps" in state["plan"]
    assert "outlier_steps" in state["plan"]
    assert "feature_steps" in state["plan"]
    assert "validation_steps" in state["plan"]


# ---------------------------------------------------------------------------
# Isolated unit: test profiler (no LLM, no mocking needed)
# ---------------------------------------------------------------------------

def test_profiler_generate_report(tmp_path: Path) -> None:
    """generate_compact_report produces expected schema on a known DataFrame."""
    from agents.profiler_agent import generate_compact_report, infer_task_type

    df = pd.DataFrame({
        "age":    [25, 30, 35],
        "city":   ["A", "B", "A"],
        "price":  [100.0, 200.0, 300.0],
    })

    report = generate_compact_report(df, "price")

    assert report["dataset_overview"]["num_rows"] == 3
    assert report["dataset_overview"]["num_columns"] == 3
    assert report["target_column"] == "price"
    assert "age" in report["columns"]
    assert report["columns"]["age"]["is_numeric"] is True
    assert report["columns"]["city"]["is_categorical"] is True
    assert report["columns"]["age"]["null_count"] == 0


def test_infer_task_type_regression() -> None:
    from agents.profiler_agent import infer_task_type

    df = pd.DataFrame({"x": range(100), "y": [float(i) * 1.5 for i in range(100)]})
    assert infer_task_type(df, "y") == "regression"


def test_infer_task_type_classification_low_cardinality() -> None:
    from agents.profiler_agent import infer_task_type

    df = pd.DataFrame({"x": range(200), "label": [0, 1, 2] * 66 + [0, 1]})
    assert infer_task_type(df, "label") == "classification"


def test_infer_task_type_classification_categorical() -> None:
    from agents.profiler_agent import infer_task_type

    df = pd.DataFrame({"x": range(50), "cat": ["yes", "no"] * 25})
    assert infer_task_type(df, "cat") == "classification"
