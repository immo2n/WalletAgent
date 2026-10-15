"""Base protocols and exceptions for policy readers."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from policy.ast import Policy
from policy.errors import Unreadable

__all__ = ["Reader", "Unreadable"]


@runtime_checkable
class Reader(Protocol):
    """Protocol for a policy reader (deterministic or LLM)."""
    def read(self, text: str, feedback: Any = None) -> Policy:
        """Parse natural language instruction text into a typed Policy AST.

        Raises Unreadable if the input cannot be parsed.
        """
        ...
