"""Controlled English readback generator for verified policies."""
from __future__ import annotations

from fractions import Fraction
from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Var
from policy.sorts import Sort


def _fmt_val(f: Any) -> str:
    if isinstance(f, Fraction):
        if f.denominator == 1:
            return str(f.numerator)
        fl = float(f)
        if Fraction(str(round(fl, 6))) == f:
            return f"{fl:g}"
        return f"{f.numerator}/{f.denominator}"
    if isinstance(f, (int, float)):
        return f"{f:g}"
    return str(f)


def _render_trigger(cmp: Cmp) -> str:
    # Check for Coerced node in rhs
    if isinstance(cmp.rhs, Coerced):
        cid = cmp.rhs.coercion_id
        if cid == "pct_below_avg24h":
            # Extract r from BinOp
            # inner = BinOp("mul", Var("avg24h"), BinOp("sub", Const(1), Const(r)))
            inner = cmp.rhs.inner
            if isinstance(inner, BinOp) and isinstance(inner.rhs, BinOp) and isinstance(inner.rhs.rhs, Const):
                pct = int(inner.rhs.rhs.value * 100)
                return f"Buy only when gas is at least {pct}% below its 24h average."
        elif cid == "lowest_pctile24h":
            if isinstance(cmp.rhs.inner, Const):
                pct = int(cmp.rhs.inner.value * 100)
                return f"Buy only when gas is within the lowest {pct}% of the last 24h."
        elif cid == "absolute_reinterpret":
            if isinstance(cmp.rhs.inner, Const):
                val = _fmt_val(cmp.rhs.inner.value)
                return f"Buy only when gas is at most {val} gwei."

    # Standard triggers
    if isinstance(cmp.lhs, Var) and cmp.lhs.name == "gas" and isinstance(cmp.rhs, Const):
        val = _fmt_val(cmp.rhs.value)
        op_phrase = "at most" if cmp.op in ("le", "lt") else "at least"
        return f"Buy only when gas is {op_phrase} {val} gwei."

    return "Trigger condition active."


def _render_invariant(cmp: Cmp) -> str:
    # balance - trade >= X
    if isinstance(cmp.lhs, BinOp) and cmp.lhs.op == "sub":
        if isinstance(cmp.lhs.lhs, Var) and cmp.lhs.lhs.name == "balance":
            if isinstance(cmp.lhs.rhs, Var) and cmp.lhs.rhs.name == "trade":
                if isinstance(cmp.rhs, Const):
                    val = _fmt_val(cmp.rhs.value)
                    return f"Keep the balance after each trade at least ${val}."

    # trade <= X
    if isinstance(cmp.lhs, Var) and cmp.lhs.name == "trade":
        if isinstance(cmp.rhs, Const):
            val = _fmt_val(cmp.rhs.value)
            return f"Don't spend more than ${val} in one transaction."

    # spent_today + trade <= X
    if isinstance(cmp.lhs, BinOp) and cmp.lhs.op == "add":
        vars_in_lhs = {cmp.lhs.lhs.name if isinstance(cmp.lhs.lhs, Var) else None,
                       cmp.lhs.rhs.name if isinstance(cmp.lhs.rhs, Var) else None}
        if vars_in_lhs == {"spent_today", "trade"} and isinstance(cmp.rhs, Const):
            val = _fmt_val(cmp.rhs.value)
            return f"No more than ${val} per day in total."

    return "Invariant condition active."


def readback(policy: Policy) -> str:
    """Generate deterministic controlled English sentences for a verified policy."""
    sentences: list[str] = []

    for trig in policy.triggers:
        sentences.append(_render_trigger(trig))

    for inv in policy.invariants:
        sentences.append(_render_invariant(inv))

    if policy.allow_tokens:
        tokens_str = " and ".join(sorted(policy.allow_tokens))
        sentences.append(f"Only trade {tokens_str}.")

    if policy.approval_above_usd is not None:
        val = _fmt_val(policy.approval_above_usd.value)
        sentences.append(f"Ask me before anything over ${val}.")

    return " ".join(sentences)
