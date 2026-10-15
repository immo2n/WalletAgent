"""Sanity checks for policies: satisfiability, non-vacuousness, and non-redundancy."""
from __future__ import annotations

from z3 import And, Not, Solver, sat, unknown, unsat

from policy.ast import Policy
from policy.errors import SolverTimeout
from policy.z3_compile import DOMAIN, compile_policy


def sanity(policy: Policy, timeout_ms: int = 5000) -> list[str]:
    """Run sanity checks on policy:

    1. Contradictory: is there any satisfying state in DOMAIN?
    2. Per-rule vacuous: can the rule ever be violated in DOMAIN?
    3. Per-rule redundant: is the rule implied by the other rules in DOMAIN?

    Returns a list of human-readable problem descriptions (empty if clean).
    """
    named = compile_policy(policy)
    if not named:
        return []

    rule_names = list(named.keys())
    rule_exprs = list(named.values())
    problems: list[str] = []

    # 1. Contradictory check
    s = Solver()
    s.set("timeout", timeout_ms)
    s.add(*DOMAIN)
    s.add(*rule_exprs)
    res = s.check()
    if res == unknown:
        raise SolverTimeout("Solver timed out checking policy satisfiability")
    elif res == unsat:
        problems.append("Contradictory policy: No state in DOMAIN can satisfy all policy rules simultaneously.")
        return problems  # If contradictory, vacuous/redundancy checks are not informative

    # 2. Per-rule vacuous check (can rule ever be violated in DOMAIN?)
    for name, expr in named.items():
        sv = Solver()
        sv.set("timeout", timeout_ms)
        sv.add(*DOMAIN)
        sv.add(Not(expr))
        res_v = sv.check()
        if res_v == unknown:
            raise SolverTimeout(f"Solver timed out checking vacuousness for rule {name}")
        elif res_v == unsat:
            problems.append(f"Rule '{name}' is vacuous: it is always satisfied across all valid domain states.")

    # 3. Per-rule redundant check (is rule implied by other rules?)
    if len(rule_names) > 1:
        for i, (name, expr) in enumerate(named.items()):
            sr = Solver()
            sr.set("timeout", timeout_ms)
            sr.add(*DOMAIN)
            # Add all other rules
            for j, other_expr in enumerate(rule_exprs):
                if i != j:
                    sr.add(other_expr)
            # Add negation of this rule
            sr.add(Not(expr))
            res_r = sr.check()
            if res_r == unknown:
                raise SolverTimeout(f"Solver timed out checking redundancy for rule {name}")
            elif res_r == unsat:
                problems.append(f"Rule '{name}' is redundant: it is logically implied by other constraints.")

    return problems
