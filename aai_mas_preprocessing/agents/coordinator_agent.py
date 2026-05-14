"""Coordinator. Parses plan, dispatches tasks to specialist agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.agent_base import BaseAgent

if TYPE_CHECKING:
    from core.shared_state import MASState
    from agents.cleaner_agent import CleanerAgent
    from agents.outlier_agent import OutlierAgent
    from agents.feature_engineer_agent import FeatureEngineerAgent
    from agents.validation_agent import ValidationAgent
    from agents.code_synthesizer_agent import CodeSynthesizerAgent

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """Orchestrates specialist agents in the MAS preprocessing pipeline.

    The coordinator embodies the MAS communication pattern: it does not perform
    any data transformation itself — it dispatches work to specialist agents,
    collects their outputs into shared state, and provides fault-tolerant
    progression (non-fatal errors are logged but the pipeline continues).

    Parameters
    ----------
    llm_model, llm_endpoint:
        Passed to ``BaseAgent`` for interface consistency; the coordinator
        itself never calls the LLM.
    cleaner:
        ``CleanerAgent`` instance.
    outlier:
        ``OutlierAgent`` instance.
    feature_engineer:
        ``FeatureEngineerAgent`` instance.
    validation:
        ``ValidationAgent`` instance.
    synthesizer:
        ``CodeSynthesizerAgent`` instance.
    """

    def __init__(
        self,
        llm_model: str = "",
        api_key: str = "",
        *,
        cleaner: "CleanerAgent",
        outlier: "OutlierAgent",
        feature_engineer: "FeatureEngineerAgent",
        validation: "ValidationAgent",
        synthesizer: "CodeSynthesizerAgent",
    ) -> None:
        super().__init__(
            name="coordinator",
            llm_model=llm_model,
            api_key=api_key,
        )
        self.cleaner = cleaner
        self.outlier = outlier
        self.feature_engineer = feature_engineer
        self.validation = validation
        self.synthesizer = synthesizer

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Dispatch work to each specialist agent in sequence."""
        self._log(state, "Coordinator dispatching to specialist agents …")

        pipeline = [
            self.cleaner,
            self.outlier,
            self.feature_engineer,
            self.validation,
            self.synthesizer,
        ]

        for agent in pipeline:
            errors_before = len(state.get("errors", []))

            self._log(state, f"→ Running {agent.name} …")
            try:
                state = agent.run(state)
            except Exception as exc:  # noqa: BLE001
                msg = (
                    f"Unhandled exception in agent '{agent.name}': "
                    f"{type(exc).__name__}: {exc}"
                )
                logger.exception(msg)
                state.setdefault("errors", []).append(msg)

            errors_after = len(state.get("errors", []))
            new_errors = errors_after - errors_before
            if new_errors:
                new_error_msgs = state["errors"][errors_before:]
                logger.warning(
                    "[coordinator] %d new error(s) from agent '%s' — continuing: %s",
                    new_errors,
                    agent.name,
                    "; ".join(new_error_msgs),
                )
                self._log(
                    state,
                    f"WARNING: {new_errors} error(s) from '{agent.name}' "
                    f"(pipeline continues): {'; '.join(new_error_msgs)}",
                )

        collected = list(state.get("agent_outputs", {}).keys())
        self._log(
            state,
            f"Coordinator: all specialist agents complete. "
            f"Snippets collected: {collected}",
        )
        return state
