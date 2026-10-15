"""Extract on-chain enforcement parameters from a verified policy."""
from __future__ import annotations

from typing import Any

from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.hashing import policy_hash


def _find_min_balance_after(policy: Policy) -> int | None:
    for inv in policy.invariants:
        # balance - trade >= X
        if inv.op in ("ge", "gt") and isinstance(inv.rhs, Const):
            if isinstance(inv.lhs, BinOp) and inv.lhs.op == "sub":
                if isinstance(inv.lhs.lhs, Var) and inv.lhs.lhs.name == "balance":
                    if isinstance(inv.lhs.rhs, Var) and inv.lhs.rhs.name == "trade":
                        return int(inv.rhs.value)
    return None


def _find_per_tx_cap(policy: Policy) -> int | None:
    for inv in policy.invariants:
        # trade <= X
        if inv.op in ("le", "lt") and isinstance(inv.rhs, Const):
            if isinstance(inv.lhs, Var) and inv.lhs.name == "trade":
                return int(inv.rhs.value)
    return None


def _find_daily_cap(policy: Policy) -> int | None:
    for inv in policy.invariants:
        # spent_today + trade <= X or spent_today <= X
        if inv.op in ("le", "lt") and isinstance(inv.rhs, Const):
            if isinstance(inv.lhs, Var) and inv.lhs.name == "spent_today":
                return int(inv.rhs.value)
            if isinstance(inv.lhs, BinOp) and inv.lhs.op == "add":
                vars_in_lhs = {inv.lhs.lhs.name if isinstance(inv.lhs.lhs, Var) else None,
                               inv.lhs.rhs.name if isinstance(inv.lhs.rhs, Var) else None}
                if vars_in_lhs == {"spent_today", "trade"}:
                    return int(inv.rhs.value)
    return None


def params(policy: Policy) -> dict[str, Any]:
    """Derive on-chain enforcement parameters from verified policy."""
    p: dict[str, Any] = {
        "policyHash": policy_hash(policy),
    }

    min_bal = _find_min_balance_after(policy)
    if min_bal is not None:
        p["minBalanceAfterUsd"] = min_bal

    per_tx = _find_per_tx_cap(policy)
    if per_tx is not None:
        p["perTxCapUsd"] = per_tx

    daily = _find_daily_cap(policy)
    if daily is not None:
        p["dailyCapUsd"] = daily

    if policy.approval_above_usd is not None:
        p["approvalAboveUsd"] = int(policy.approval_above_usd.value)

    if policy.allow_tokens:
        p["allowTokens"] = list(policy.allow_tokens)

    if policy.allow_routers:
        p["allowRouters"] = list(policy.allow_routers)

    if policy.allow_recipients:
        p["allowRecipients"] = list(policy.allow_recipients)

    return p
