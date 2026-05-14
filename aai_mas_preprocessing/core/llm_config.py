"""LLM config. Reads from env: ANTHROPIC_API_KEY and ANTHROPIC_MODEL."""

from __future__ import annotations

import os

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL      = "claude-3-5-sonnet-20241022"


def get_api_key() -> str:
    """Return the Anthropic API key from env. Raises if not set."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key, or set the env var directly."
        )
    return key


def get_model() -> str:
    """Return the Claude model tag from env or the project default."""
    return os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
