"""Compile typed policy AST into named Z3 constraints and expressions."""
from __future__ import annotations

from fractions import Fraction
from typing import Any
from z3 import And, ArithRef, BoolRef, Real, RealVal

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Term, Var
from policy.errors import UnresolvedTypeIssues
from policy.sorts import Sort
from policy.typecheck import typecheck

# -----------------------------------------------------------------------------
# Z3 state variables & Domain bounds
# -----------------------------------------------------------------------------
V: dict[str, ArithRef] = {
    "gas": Real("gas"),
    "avg24h": Real("avg24h"),
    "pctile24h": Real("pctile24h"),
    "balance": Real("balance"),
    "trade": Real("trade"),
    "spent_today": Real("spent_today"),
}

DOMAIN: list[BoolRef] = [
    V["gas"] >= RealVal(1),
    V["avg24h"] >= RealVal(1),
    V["pctile24h"] >= RealVal(0),
    V["pctile24h"] <= RealVal(1),
    V["balance"] >= RealVal(0),
    V["trade"] >= RealVal(1),
    V["trade"] <= V["balance"],
    V["spent_today"] >= RealVal(0),
]


# -----------------------------------------------------------------------------
# Human-readable stable naming functions
# -----------------------------------------------------------------------------
def term_name(term: Term) -> str:
    if isinstance(term, Var):
        return term.name
    if isinstance(term, Const):
        if term.sort == Sort.RATIO:
            pct = term.value * 100
            if pct.denominator == 1:
                return f"{pct.numerator}%"
            return f"{float(pct):.2f}%"
        if term.value.denominator == 1:
            return str(term.value.numerator)
        return f"{term.value.numerator}/{term.value.denominator}"
    if isinstance(term, Coerced):
        return term_name(term.inner)
    if isinstance(term, BinOp):
        lhs_str = term_name(term.lhs)
        rhs_str = term_name(term.rhs)
        if term.op == "add":
            return f"{lhs_str}+{rhs_str}"
        elif term.op == "sub":
            return f"{lhs_str}-{rhs_str}"
        elif term.op == "mul":
            if isinstance(term.rhs, BinOp):
                return f"{lhs_str}*({rhs_str})"
            return f"{lhs_str}*{rhs_str}"
    return "unknown"


def cmp_name(cmp: Cmp) -> str:
    op_map = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "=="}
    return f"{term_name(cmp.lhs)}{op_map[cmp.op]}{term_name(cmp.rhs)}"


def constraint_names(policy: Policy) -> list[str]:
    return [cmp_name(c) for c in (policy.triggers + policy.invariants)]


# -----------------------------------------------------------------------------
# Z3 expression compilation
# -----------------------------------------------------------------------------
def compile_term(term: Term) -> ArithRef:
    if isinstance(term, Var):
        return V[term.name]
    if isinstance(term, Const):
        return RealVal(f"{term.value.numerator}/{term.value.denominator}")
    if isinstance(term, Coerced):
        return compile_term(term.inner)
    if isinstance(term, BinOp):
        l = compile_term(term.lhs)
        r = compile_term(term.rhs)
        if term.op == "add":
            return l + r
        elif term.op == "sub":
            return l - r
        elif term.op == "mul":
            return l * r
        raise ValueError(f"Unknown BinOp: {term.op}")
    raise ValueError(f"Unknown Term type: {type(term)}")


def compile_cmp(cmp: Cmp) -> BoolRef:
    l = compile_term(cmp.lhs)
    r = compile_term(cmp.rhs)
    if cmp.op == "lt":
        return l < r
    elif cmp.op == "le":
        return l <= r
    elif cmp.op == "gt":
        return l > r
    elif cmp.op == "ge":
        return l >= r
    elif cmp.op == "eq":
        return l == r
    raise ValueError(f"Unknown Cmp op: {cmp.op}")


def compile_policy(policy: Policy) -> dict[str, BoolRef]:
    """Compile policy into named Z3 constraints.

    Raises UnresolvedTypeIssues if the policy has any type issues.
    """
    issues = typecheck(policy)
    if issues:
        raise UnresolvedTypeIssues(issues)

    named: dict[str, BoolRef] = {}
    for c in policy.triggers:
        named[cmp_name(c)] = compile_cmp(c)
    for c in policy.invariants:
        named[cmp_name(c)] = compile_cmp(c)
    return named
