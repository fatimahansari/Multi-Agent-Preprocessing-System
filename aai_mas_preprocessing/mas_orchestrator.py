"""LangGraph MAS orchestrator. Entry point for the full pipeline."""

from __future__ import annotations

import logging
import os

from langgraph.graph import END, StateGraph

from agents.cleaner_agent import CleanerAgent
from agents.code_synthesizer_agent import CodeSynthesizerAgent
from agents.coordinator_agent import CoordinatorAgent
from agents.executor_agent import ExecutorAgent
from agents.feature_engineer_agent import FeatureEngineerAgent
from agents.outlier_agent import OutlierAgent
from agents.planner_agent import PlannerAgent
from agents.profiler_agent import ProfilerAgent
from agents.validation_agent import ValidationAgent
from core.llm_config import get_api_key, get_model
from core.shared_state import MASState, create_initial_state

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def _build_agents() -> dict:
    """Instantiate all agents using env-configured LLM settings."""
    model   = get_model()
    api_key = get_api_key()

    logger.info("LLM model : %s", model)

    profiler = ProfilerAgent()                              # deterministic — no LLM

    planner = PlannerAgent(
        llm_model=model,
        api_key=api_key,
    )

    cleaner          = CleanerAgent(llm_model=model, api_key=api_key)
    outlier          = OutlierAgent(llm_model=model, api_key=api_key)
    feature_engineer = FeatureEngineerAgent(llm_model=model, api_key=api_key)
    validation       = ValidationAgent(
        name="validation",
        llm_model=model,
        api_key=api_key,
    )
    synthesizer = CodeSynthesizerAgent()                    # deterministic — no LLM

    coordinator = CoordinatorAgent(
        cleaner=cleaner,
        outlier=outlier,
        feature_engineer=feature_engineer,
        validation=validation,
        synthesizer=synthesizer,
    )

    executor = ExecutorAgent(llm_model=model, api_key=api_key)

    return {
        "profiler": profiler,
        "planner": planner,
        "coordinator": coordinator,
        "executor": executor,
    }


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(agents: dict | None = None) -> "CompiledGraph":
    """Build and compile the LangGraph StateGraph for the MAS pipeline.

    DAG:
        profile → plan → coordinate → execute → END

    Parameters
    ----------
    agents:
        Pre-built agent dict (used for testing / dependency injection).
        If ``None``, ``_build_agents()`` is called automatically.

    Returns
    -------
    CompiledGraph
        A compiled LangGraph application ready for ``.invoke()``.
    """
    if agents is None:
        agents = _build_agents()

    graph = StateGraph(MASState)

    # --- nodes ----------------------------------------------------------------
    graph.add_node("profile",    agents["profiler"].run)
    graph.add_node("plan",       agents["planner"].run)
    graph.add_node("coordinate", agents["coordinator"].run)
    graph.add_node("execute",    agents["executor"].run)

    # --- edges ----------------------------------------------------------------
    graph.set_entry_point("profile")
    graph.add_edge("profile",    "plan")
    graph.add_edge("plan",       "coordinate")
    graph.add_edge("coordinate", "execute")
    graph.add_edge("execute",    END)

    app = graph.compile()

    # Print ASCII diagram so the user can verify the topology at startup.
    try:
        print(app.get_graph().draw_ascii())
    except Exception:  # noqa: BLE001 — diagram is informational only
        logger.debug("ASCII graph diagram unavailable.", exc_info=True)

    return app


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_mas(csv_path: str, target_column: str) -> dict:
    """Run the full MAS preprocessing pipeline on a CSV file.

    Parameters
    ----------
    csv_path:
        Absolute or relative path to the input CSV dataset.
    target_column:
        Name of the column to predict (preserved untouched through preprocessing).

    Returns
    -------
    dict
        Final ``MASState`` after the pipeline completes (or errors out).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("MAS Preprocessing Pipeline — starting")
    logger.info("  CSV    : %s", csv_path)
    logger.info("  Target : %s", target_column)
    logger.info("=" * 60)

    state = create_initial_state(
        dataset_path=csv_path,
        target_column=target_column,
    )
    state["status"] = "profiling"

    app = build_graph()

    try:
        final_state: dict = app.invoke(state)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline raised an unhandled exception: %s", exc)
        state["errors"].append(f"Unhandled pipeline exception: {exc}")
        state["status"] = "error"
        return dict(state)

    # --- summary print --------------------------------------------------------
    output_csv = final_state.get("file_history", {}).get("output_csv", "—")
    script_path = final_state.get("file_history", {}).get("script", "—")
    errors = final_state.get("errors", [])

    print("\n" + "=" * 60)
    print("MAS Preprocessing Pipeline — COMPLETE")
    print(f"  Dataset   : {csv_path}")
    print(f"  Target    : {target_column}")
    print(f"  Task type : {final_state.get('task_type', '—')}")
    print(f"  Status    : {final_state.get('status', '—')}")
    print(f"  Output CSV: {output_csv}")
    print(f"  Script    : {script_path}")
    print(f"  Retries   : {final_state.get('retry_count', 0)}")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for err in errors:
            print(f"    • {err}")
    print("=" * 60 + "\n")

    return final_state
