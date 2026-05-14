"""Abstract base class for all agents."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from abc import ABC, abstractmethod

from core.llm_config import ANTHROPIC_API_URL, ANTHROPIC_VERSION


class BaseAgent(ABC):
    """Common foundation for every specialist agent in the MAS pipeline.

    Parameters
    ----------
    name:
        Human-readable identifier used in log messages and as the key written
        into ``state["agent_outputs"]``.
    llm_model:
        Claude model tag, e.g. ``"claude-3-5-sonnet-20241022"``.
    api_key:
        Anthropic API key. Agents that do not call the LLM (Profiler,
        Synthesizer, Coordinator) may pass an empty string.
    """

    def __init__(self, name: str, llm_model: str, api_key: str) -> None:
        self.name      = name
        self.llm_model = llm_model
        self.api_key   = api_key

    # ------------------------------------------------------------------
    # Abstract interface — every agent must implement this
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, state: dict) -> dict:
        """Execute the agent's task.

        Parameters
        ----------
        state:
            The shared ``MASState`` dict passed through the LangGraph graph.

        Returns
        -------
        dict
            The same ``MASState`` dict with relevant fields updated.
        """

    # ------------------------------------------------------------------
    # Concrete helpers available to all subclasses
    # ------------------------------------------------------------------

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """POST a request to the Anthropic Messages API.

        Parameters
        ----------
        system_prompt:
            Instruction that sets the model's role / constraints.
        user_prompt:
            The actual task description / data to send.

        Returns
        -------
        str
            The text content of the first response block.

        Raises
        ------
        RuntimeError
            Wraps any HTTP or JSON error and tags it with the agent name so
            callers can identify which agent failed.
        """
        if not self.api_key:
            raise RuntimeError(
                f"[{self.name}] ANTHROPIC_API_KEY is empty. "
                "Set it in your .env file or environment."
            )

        payload = json.dumps({
            "model":      self.llm_model,
            "max_tokens": 4096,
            "system":     system_prompt,
            "messages":   [{"role": "user", "content": user_prompt}],
        }).encode("utf-8")

        req = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=payload,
            headers={
                "Content-Type":    "application/json",
                "x-api-key":       self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(
                f"[{self.name}] Anthropic API HTTP {exc.code}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"[{self.name}] Could not reach Anthropic API: {exc.reason}"
            ) from exc

        try:
            data = json.loads(raw)
            return data["content"][0]["text"]
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"[{self.name}] Unexpected Anthropic response format: {exc}\n"
                f"Raw: {raw[:300]}"
            ) from exc

    def _log(self, state: dict, message: str) -> dict:
        """Append a tagged log line to ``state["execution_log"]``.

        Parameters
        ----------
        state:
            The shared MASState dict (mutated in-place).
        message:
            The message text to append.

        Returns
        -------
        dict
            The same ``state`` dict, for convenient chaining.
        """
        entry = f"[{self.name}] {message}"
        state.setdefault("execution_log", []).append(entry)
        return state
