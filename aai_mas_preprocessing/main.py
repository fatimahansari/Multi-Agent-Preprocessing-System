"""CLI entry point. Accepts --csv and --target arguments.

Example usage:
    python main.py --csv ../Datasets/Housing.csv --target price
    python main.py --csv ../Datasets/Titanic.csv --target Survived --save-state
    python main.py --csv data.csv --target label --model claude-3-haiku-20240307
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Load .env file before anything else so llm_config can read the key.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; user can set the env var directly

from core.llm_config import DEFAULT_MODEL


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "MAS Preprocessing Pipeline — "
            "runs a multi-agent system to automatically preprocess a CSV dataset."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--csv",
        required=True,
        metavar="PATH",
        help="Path to the input CSV dataset.",
    )
    parser.add_argument(
        "--target",
        required=True,
        metavar="COLUMN",
        help="Name of the target column to predict (will not be modified).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
        metavar="TAG",
        help="Claude model tag. Overrides $ANTHROPIC_MODEL env var.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        metavar="KEY",
        help=(
            "Anthropic API key. Overrides $ANTHROPIC_API_KEY env var and .env file. "
            "Prefer setting it in .env rather than the command line."
        ),
    )
    parser.add_argument(
        "--save-state",
        action="store_true",
        help=(
            "Serialize the final MASState to "
            "{dataset_stem}_mas_state.json next to the CSV."
        ),
    )

    return parser.parse_args(argv)


def _validate_csv(csv_path: str) -> Path:
    """Return resolved Path or print an error and exit(1)."""
    p = Path(csv_path)
    if not p.exists():
        print(f"ERROR: CSV file not found: '{csv_path}'", file=sys.stderr)
        sys.exit(1)
    if not p.is_file():
        print(f"ERROR: Path is not a file: '{csv_path}'", file=sys.stderr)
        sys.exit(1)
    return p.resolve()


def _save_state(final_state: dict, csv_path: Path) -> None:
    """Write the final MASState to JSON, replacing synthesized_code body with its path."""
    serializable = dict(final_state)

    script_path = serializable.get("file_history", {}).get("script")
    if serializable.get("synthesized_code"):
        serializable["synthesized_code"] = (
            f"<see file: {script_path}>" if script_path else "<generated — path unavailable>"
        )

    out_path = csv_path.parent / f"{csv_path.stem}_mas_state.json"
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(serializable, fh, indent=2, default=str)
        print(f"State saved → {out_path}")
    except OSError as exc:
        print(f"WARNING: Could not save state file: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    csv_path = _validate_csv(args.csv)

    # Propagate CLI args into env so all agents pick them up automatically.
    os.environ["ANTHROPIC_MODEL"] = args.model
    if args.api_key:
        os.environ["ANTHROPIC_API_KEY"] = args.api_key

    # Import here (after env vars are set) so llm_config sees the correct values.
    from mas_orchestrator import run_mas  # noqa: PLC0415

    final_state = run_mas(str(csv_path), args.target)

    if args.save_state:
        _save_state(final_state, csv_path)

    status = final_state.get("status", "error")

    if status == "done":
        sys.exit(0)

    errors = final_state.get("errors", [])
    if errors:
        print("\nPipeline errors:", file=sys.stderr)
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}", file=sys.stderr)
    else:
        print(f"\nPipeline ended with status '{status}'.", file=sys.stderr)

    sys.exit(1)


if __name__ == "__main__":
    main()
