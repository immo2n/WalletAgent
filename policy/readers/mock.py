"""Mock LLM client with scripted responses and call history tracking."""
from __future__ import annotations

from typing import Any


class MockLLMClient:
    """Mock LLMClient for offline testing. Returns a scripted sequence of JSON dictionaries."""

    def __init__(self, scripts: dict[str, list[dict[str, Any]]] | None = None):
        self.scripts: dict[str, list[dict[str, Any]]] = {k: list(v) for k, v in (scripts or {}).items()}
        self.call_history: list[dict[str, Any]] = []
        self.default_responses: list[dict[str, Any]] = []

    def set_script(self, key: str, responses: list[dict[str, Any]]) -> None:
        self.scripts[key] = list(responses)

    def set_default_responses(self, responses: list[dict[str, Any]]) -> None:
        self.default_responses = list(responses)

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.call_history.append({"system": system, "user": user, "schema": schema})

        # Match user text against known script keys
        for key, resp_list in self.scripts.items():
            if key in user and resp_list:
                return resp_list.pop(0)

        if self.default_responses:
            return self.default_responses.pop(0)

        raise RuntimeError(f"MockLLMClient has no scripted response for prompt: {user[:60]!r}")
