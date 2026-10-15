"""Equivalence checking between two policies and counterexample extraction."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal
from z3 import And, Not, Solver, sat, unknown

from policy.ast import Policy
from policy.errors import SolverTimeout
from policy.z3_compile import DOMAIN, V, compile_policy


@dataclass(frozen=True)
class Finding:
    direction: Literal["B_stricter", "B_looser"]
    state: dict[str, Fraction]
    explanation: str

    def display_state(self) -> dict[str, str]:
        """Readable decimal display of state values (rounding for display only)."""
        out: dict[str, str] = {}
        for k, v in self.state.items():
            if v.denominator == 1:
                out[k] = str(v.numerator)
            else:
                out[k] = f"{float(v):.4g} ({v.numerator}/{v.denominator})"
        return out


def _extract_state(model) -> dict[str, Fraction]:
    state: dict[str, Fraction] = {}
    for name, var_ref in V.items():
        val = model.eval(var_ref, model_completion=True)
        if hasattr(val, "as_fraction"):
            state[name] = Fraction(val.as_fraction())
        else:
            state[name] = Fraction(str(val))
    return state


def compare(pa: Policy, pb: Policy, timeout_ms: int = 5000) -> list[Finding]:
    """Compare two policies over DOMAIN.

    Checks:
    1. A and not B -> states allowed by A but blocked by B (B is stricter).
    2. B and not A -> states allowed by B but blocked by A (B is looser).

    Returns list of Findings. Raises SolverTimeout on timeout.
    """
    named_a = compile_policy(pa)
    named_b = compile_policy(pb)

    expr_a = And(*list(named_a.values())) if named_a else And()
    expr_b = And(*list(named_b.values())) if named_b else And()

    findings: list[Finding] = []

    # 1. A and not B (B is stricter)
    s1 = Solver()
    s1.set("timeout", timeout_ms)
    s1.add(*DOMAIN)
    s1.add(expr_a)
    s1.add(Not(expr_b))

    res1 = s1.check()
    if res1 == unknown:
        raise SolverTimeout("Solver timed out checking A and not B")
    elif res1 == sat:
        state = _extract_state(s1.model())
        findings.append(
            Finding(
                direction="B_stricter",
                state=state,
                explanation="Policy A permits this state, but Policy B rejects it.",
            )
        )

    # 2. B and not A (B is looser)
    s2 = Solver()
    s2.set("timeout", timeout_ms)
    s2.add(*DOMAIN)
    s2.add(expr_b)
    s2.add(Not(expr_a))

    res2 = s2.check()
    if res2 == unknown:
        raise SolverTimeout("Solver timed out checking B and not A")
    elif res2 == sat:
        state = _extract_state(s2.model())
        findings.append(
            Finding(
                direction="B_looser",
                state=state,
                explanation="Policy B permits this state, but Policy A rejects it.",
            )
        )

    return findings
