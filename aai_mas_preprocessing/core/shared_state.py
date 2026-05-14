"""Shared MAS state / message bus using TypedDict."""

from __future__ import annotations

from typing import Dict, List, Literal, TypedDict


# ---------------------------------------------------------------------------
# Fine-grained sub-structure for the plan produced by PlannerAgent
# ---------------------------------------------------------------------------

class StepDict(TypedDict, total=False):
    """A single preprocessing step inside any plan section."""
    action: str          # e.g. "impute_median", "drop_duplicates", …
    column: str          # target column (may be absent for row-level steps)
    strategy: str        # free-form strategy hint for the specialist agent
    reason: str          # human-readable explanation from the planner


class PlanDict(TypedDict, total=False):
    """Structured plan produced by PlannerAgent."""
    cleaning_steps: List[StepDict]
    outlier_steps: List[StepDict]
    feature_steps: List[StepDict]
    validation_steps: List[StepDict]


# ---------------------------------------------------------------------------
# Master shared state — passed between every node in the LangGraph graph
# ---------------------------------------------------------------------------

StatusLiteral = Literal[
    "pending",
    "profiling",
    "planning",
    "processing",
    "synthesizing",
    "executing",
    "done",
    "error",
]


class MASState(TypedDict):
    # ---- inputs ---------------------------------------------------------- #
    dataset_path: str
    target_column: str
    task_type: str                     # "regression" | "classification" | "forecasting"

    # ---- agent artefacts ------------------------------------------------- #
    report: Dict                       # profiler output (dataset_overview, columns, …)
    plan: PlanDict                     # planner output
    agent_outputs: Dict[str, str]      # agent_name  → Python code snippet
    synthesized_code: str              # merged final script from CodeSynthesizer
    execution_log: List[str]           # stdout / stderr history
    errors: List[str]                  # errors captured across agents
    file_history: Dict[str, str]       # label → absolute file path

    # ---- control --------------------------------------------------------- #
    status: StatusLiteral
    retry_count: int                   # executor self-healing counter


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_initial_state(
    dataset_path: str,
    target_column: str,
) -> MASState:
    """Return a fresh MASState with all fields set to empty / default values."""
    return MASState(
        dataset_path=dataset_path,
        target_column=target_column,
        task_type="",
        report={},
        plan=PlanDict(
            cleaning_steps=[],
            outlier_steps=[],
            feature_steps=[],
            validation_steps=[],
        ),
        agent_outputs={},
        synthesized_code="",
        execution_log=[],
        errors=[],
        file_history={},
        status="pending",
        retry_count=0,
    )
