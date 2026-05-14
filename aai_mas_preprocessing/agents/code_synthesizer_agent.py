"""Code Synthesizer. Merges agent outputs into a single .py file."""

from __future__ import annotations

import logging
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

from core.agent_base import BaseAgent

if TYPE_CHECKING:
    from core.shared_state import MASState

logger = logging.getLogger(__name__)

# Ordered list of (agent_outputs key, section heading) pairs.
# The synthesizer processes them in exactly this order.
_SNIPPET_ORDER: List[Tuple[str, str]] = [
    ("cleaner",          "CLEANING"),
    ("outlier",          "OUTLIER TREATMENT"),
    ("feature_engineer", "FEATURE ENGINEERING"),
    ("validation",       "VALIDATION"),
]

# ---------------------------------------------------------------------------
# Fixed boilerplate blocks
# ---------------------------------------------------------------------------

_HEADER_TEMPLATE = """\
# =============================================================================
# Auto-generated preprocessing script
# Generated : {timestamp}
# Dataset   : {dataset_path}
# Target    : {target_column}
# Task type : {task_type}
# =============================================================================

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, MinMaxScaler, StandardScaler
from sklearn.ensemble import IsolationForest

"""

_LOAD_BLOCK_TEMPLATE = """\
# -----------------------------------------------------------------------------
# Load dataset
# -----------------------------------------------------------------------------
df = pd.read_csv({dataset_path!r})
print(f"Loaded dataset: {{len(df)}} rows × {{len(df.columns)}} columns")

"""

_SAVE_BLOCK_TEMPLATE = """\

# -----------------------------------------------------------------------------
# Save processed dataset
# -----------------------------------------------------------------------------
_output_path = {output_path!r}
df.to_csv(_output_path, index=False)
print(f"Saved processed dataset → {{_output_path}}")
print(f"Final shape: {{df.shape[0]}} rows × {{df.shape[1]}} columns")
"""

_SECTION_DIVIDER = """\
# -----------------------------------------------------------------------------
# {heading}
# -----------------------------------------------------------------------------
"""


class CodeSynthesizerAgent(BaseAgent):
    """Merges per-agent code snippets into one runnable Python preprocessing script.

    Does **not** call any LLM — this is a deterministic assembly step.

    Output path convention:
      ``<project_root>/Pre Processed Dataset/<csv_stem>_preprocessed.csv``
      ``<project_root>/Pre Processed Dataset/<csv_stem>_preprocessing.py``
    """

    def __init__(
        self,
        llm_model: str = "",
        api_key: str = "",
    ) -> None:
        super().__init__(
            name="code_synthesizer",
            llm_model=llm_model,
            api_key=api_key,
        )

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def run(self, state: "MASState") -> "MASState":
        """Assemble all agent snippets into a single Python script."""
        self._log(state, "Assembling synthesized preprocessing script …")

        dataset_path = state.get("dataset_path", "dataset.csv")
        target_column = state.get("target_column", "target")
        task_type = state.get("task_type", "unknown")
        agent_outputs = state.get("agent_outputs", {})

        csv_path = Path(dataset_path).resolve()
        output_dir = Path(__file__).resolve().parents[1] / "Pre Processed Dataset"
        output_csv = output_dir / f"{csv_path.stem}_preprocessed.csv"
        script_path = output_dir / f"{csv_path.stem}_preprocessing.py"

        # --- build the script section by section ----------------------------
        parts: List[str] = []

        # 1. Header + imports
        parts.append(
            _HEADER_TEMPLATE.format(
                timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                dataset_path=str(csv_path),
                target_column=target_column,
                task_type=task_type,
            )
        )

        # 2. Load block
        parts.append(_LOAD_BLOCK_TEMPLATE.format(dataset_path=str(csv_path)))

        # 3. Agent snippets — in fixed order, skipping missing/empty entries
        included: List[str] = []
        skipped: List[str] = []

        for key, heading in _SNIPPET_ORDER:
            snippet = agent_outputs.get(key, "").strip()
            if not snippet:
                skipped.append(key)
                self._log(state, f"Skipping empty snippet: {key}")
                continue

            parts.append(_SECTION_DIVIDER.format(heading=heading))
            parts.append(snippet)
            parts.append("\n")
            included.append(key)

        # 4. Save block
        parts.append(_SAVE_BLOCK_TEMPLATE.format(output_path=str(output_csv)))

        synthesized = "\n".join(parts)

        # --- store in state -------------------------------------------------
        state["synthesized_code"] = synthesized
        state["file_history"]["output_csv"] = str(output_csv)
        self._log(
            state,
            f"Script assembled — {len(synthesized)} chars, "
            f"sections included: {included}, skipped: {skipped}",
        )

        # --- persist script to disk -----------------------------------------
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            script_path.write_text(synthesized, encoding="utf-8")
            abs_script = str(script_path.resolve())
            state["file_history"]["script"] = abs_script
            self._log(state, f"Script saved to: {abs_script}")
        except OSError as exc:
            msg = f"Could not write synthesized script: {exc}"
            logger.warning(msg)
            state["errors"].append(msg)

        state["status"] = "executing"
        self._log(state, "Status → executing.")
        return state
