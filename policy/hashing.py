"""Canonical hashing for verified policies."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Term, Var


def canonical_dict(node: Any) -> Any:
    """Produce canonical dictionary representation excluding metadata and provenance."""
    if isinstance(node, Const):
        return {
            "node": "Const",
            "sort": node.sort.value,
            "value": f"{node.value.numerator}/{node.value.denominator}",
        }
    if isinstance(node, Var):
        return {
            "node": "Var",
            "name": node.name,
        }
    if isinstance(node, BinOp):
        return {
            "node": "BinOp",
            "op": node.op,
            "lhs": canonical_dict(node.lhs),
            "rhs": canonical_dict(node.rhs),
        }
    if isinstance(node, Coerced):
        return {
            "node": "Coerced",
            "coercion_id": node.coercion_id,
            "inner": canonical_dict(node.inner),
        }
    if isinstance(node, Cmp):
        return {
            "node": "Cmp",
            "op": node.op,
            "lhs": canonical_dict(node.lhs),
            "rhs": canonical_dict(node.rhs),
        }
    if isinstance(node, Policy):
        d: dict[str, Any] = {
            "action": node.action,
            "triggers": [canonical_dict(t) for t in node.triggers],
            "invariants": [canonical_dict(inv) for inv in node.invariants],
            "allow_tokens": sorted(node.allow_tokens),
            "allow_routers": sorted(node.allow_routers),
            "allow_recipients": sorted(node.allow_recipients),
            "approval_above_usd": canonical_dict(node.approval_above_usd) if node.approval_above_usd else None,
        }
        return d
    return node


def policy_hash(policy: Policy) -> str:
    """Compute sha256 hash over canonical JSON representation."""
    d = canonical_dict(policy)
    canonical_json = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
