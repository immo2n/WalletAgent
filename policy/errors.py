"""Exceptions for the policy package."""
from __future__ import annotations


class PolicyError(Exception):
    """Base error for all policy package errors."""
    pass


class Unreadable(PolicyError):
    """Raised when an instruction cannot be parsed into a typed policy AST."""
    def __init__(self, message: str, raw_text: str = ""):
        super().__init__(message)
        self.message = message
        self.raw_text = raw_text


class UnresolvedTypeIssues(PolicyError):
    """Raised when attempting to compile or verify a policy with unresolved type issues."""
    def __init__(self, issues: list[object]):
        super().__init__(f"Policy has unresolved type issues: {issues}")
        self.issues = issues


class SolverTimeout(PolicyError):
    """Raised when Z3 solver exceeds allocated timeout."""
    pass


class SanityCheckFailed(PolicyError):
    """Raised when a policy fails sanity checks (unsatisfiable, vacuous, redundant)."""
    def __init__(self, reasons: list[str]):
        super().__init__(f"Sanity checks failed: {reasons}")
        self.reasons = reasons
