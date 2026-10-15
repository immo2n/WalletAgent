"""Type checker and resolution engine for the policy AST."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Term, Var
from policy.coercions import COERCION_TABLE, CoercionOption, find_coercion_options
from policy.sorts import REGISTRY, Sort


IssueKind = Literal["SORT_MISMATCH", "ASSUMED_PROVENANCE", "UNKNOWN_VAR", "BAD_BOUND"]


@dataclass(frozen=True)
class TypeIssue:
    kind: IssueKind
    message: str
    issue_id: str
    cmp_node: Cmp | None = None
    options: tuple[CoercionOption, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", tuple(self.options))


def get_op_family(op: str) -> str:
    if op in ("lt", "le"):
        return "lt"
    if op in ("gt", "ge"):
        return "gt"
    return "eq"


def make_issue_id(var_name: str, op: str, const_val: Fraction) -> str:
    """Stable issue ID keyed on normalized (var_name, op_family, const_value) triple."""
    family = get_op_family(op)
    return f"{var_name}:{family}:{const_val.numerator}/{const_val.denominator}"


def term_sort(term: Term) -> Sort | None:
    """Determine the Sort of a Term. Returns None if term is ill-typed."""
    if isinstance(term, Const):
        return term.sort
    if isinstance(term, Var):
        meta = REGISTRY.get(term.name)
        return meta.sort if meta else None
    if isinstance(term, Coerced):
        for entry in COERCION_TABLE:
            if entry.id == term.coercion_id:
                return entry.lhs_sort
        # Fallback to inner sort
        return term_sort(term.inner)
    if isinstance(term, BinOp):
        s_lhs = term_sort(term.lhs)
        s_rhs = term_sort(term.rhs)
        if s_lhs is None or s_rhs is None:
            return None
        if term.op in ("add", "sub"):
            if s_lhs == s_rhs:
                return s_lhs
            return None
        if term.op == "mul":
            if s_lhs == Sort.RATIO and s_rhs is not None:
                return s_rhs
            if s_rhs == Sort.RATIO and s_lhs is not None:
                return s_lhs
            if s_lhs == Sort.RATIO and s_rhs == Sort.RATIO:
                return Sort.RATIO
            return None
    return None


def _find_assumed_nodes(term: Term) -> list[Coerced]:
    found: list[Coerced] = []
    if isinstance(term, Coerced):
        if term.provenance == "assumed":
            found.append(term)
        found.extend(_find_assumed_nodes(term.inner))
    elif isinstance(term, BinOp):
        found.extend(_find_assumed_nodes(term.lhs))
        found.extend(_find_assumed_nodes(term.rhs))
    return found


def _extract_var_and_const(cmp: Cmp) -> tuple[Var, Const] | None:
    """Extract a simple (Var, Const) pair from a comparison if present."""
    if isinstance(cmp.lhs, Var) and isinstance(cmp.rhs, Const):
        return cmp.lhs, cmp.rhs
    if isinstance(cmp.rhs, Var) and isinstance(cmp.lhs, Const):
        return cmp.rhs, cmp.lhs
    return None


def _check_bad_bound(var: Var, const: Const) -> str | None:
    """Check if constant is outside the variable's physical domain."""
    v = const.value
    if var.name in ("gas", "avg24h") and v < 0:
        return f"Gas value {v} cannot be negative"
    if var.name == "pctile24h" and (v < 0 or v > 1):
        return f"Percentile value {v} is outside valid ratio domain [0, 1]"
    if var.name in ("balance", "trade", "spent_today") and v < 0:
        return f"USD value {v} cannot be negative"
    return None


def typecheck_cmp(cmp: Cmp) -> list[TypeIssue]:
    issues: list[TypeIssue] = []

    # 1. Check for ASSUMED_PROVENANCE anywhere in LHS or RHS
    for assumed in _find_assumed_nodes(cmp.lhs) + _find_assumed_nodes(cmp.rhs):
        issues.append(
            TypeIssue(
                kind="ASSUMED_PROVENANCE",
                message=f"Coerced node '{assumed.coercion_id}' has assumed provenance without user confirmation",
                issue_id=f"assumed:{assumed.coercion_id}",
                cmp_node=cmp,
            )
        )

    # 2. Check for Var/Const domain bounds
    pair = _extract_var_and_const(cmp)
    if pair is not None:
        var_node, const_node = pair
        bound_err = _check_bad_bound(var_node, const_node)
        if bound_err:
            issues.append(
                TypeIssue(
                    kind="BAD_BOUND",
                    message=bound_err,
                    issue_id=f"bad_bound:{var_node.name}:{const_node.value}",
                    cmp_node=cmp,
                )
            )

    # 3. Check for SORT_MISMATCH
    s_lhs = term_sort(cmp.lhs)
    s_rhs = term_sort(cmp.rhs)

    if s_lhs is not None and s_rhs is not None and s_lhs != s_rhs:
        # Check if bridge Coerced node exists
        lhs_has_bridge = isinstance(cmp.lhs, Coerced)
        rhs_has_bridge = isinstance(cmp.rhs, Coerced)
        if not (lhs_has_bridge or rhs_has_bridge):
            # We have a sort mismatch
            var_name = "unknown"
            const_val = Fraction(0, 1)
            if pair is not None:
                var_name = pair[0].name
                const_val = pair[1].value
            issue_id = make_issue_id(var_name, cmp.op, const_val)

            options = find_coercion_options(s_lhs, s_rhs, const_val)
            issues.append(
                TypeIssue(
                    kind="SORT_MISMATCH",
                    message=f"Sort mismatch in comparison: LHS has sort {s_lhs}, RHS has sort {s_rhs}",
                    issue_id=issue_id,
                    cmp_node=cmp,
                    options=tuple(options),
                )
            )

    return issues


def typecheck(policy: Policy) -> list[TypeIssue]:
    """Run full type checking on a Policy object and return all TypeIssues."""
    issues: list[TypeIssue] = []

    for cmp in policy.triggers:
        issues.extend(typecheck_cmp(cmp))

    for cmp in policy.invariants:
        issues.extend(typecheck_cmp(cmp))

    return issues


def _resolve_cmp(cmp: Cmp, target_issue_id: str, option_id: str) -> tuple[Cmp, bool]:
    pair = _extract_var_and_const(cmp)
    if pair is None:
        return cmp, False

    var_node, const_node = pair
    curr_issue_id = make_issue_id(var_node.name, cmp.op, const_node.value)
    if curr_issue_id != target_issue_id:
        return cmp, False

    s_lhs = term_sort(cmp.lhs)
    s_rhs = term_sort(cmp.rhs)
    if s_lhs is None or s_rhs is None:
        return cmp, False

    options = find_coercion_options(s_lhs, s_rhs, const_node.value)
    chosen_opt = next((opt for opt in options if opt.id == option_id), None)
    if chosen_opt is None:
        raise ValueError(f"Option ID {option_id!r} not found for issue {target_issue_id}")

    new_cmp = chosen_opt.builder(cmp.op, var_node.name, const_node.value)
    return new_cmp, True


def resolve(policy: Policy, issue_id: str, option_id: str) -> Policy:
    """Resolve an issue in the policy AST with the chosen coercion option.

    Returns a new Policy with the coercion applied and provenance 'confirmed'.
    """
    new_triggers: list[Cmp] = []
    resolved_any = False

    for trig in policy.triggers:
        new_trig, did_resolve = _resolve_cmp(trig, issue_id, option_id)
        if did_resolve:
            resolved_any = True
        new_triggers.append(new_trig)

    new_invariants: list[Cmp] = []
    for inv in policy.invariants:
        new_inv, did_resolve = _resolve_cmp(inv, issue_id, option_id)
        if did_resolve:
            resolved_any = True
        new_invariants.append(new_inv)

    if not resolved_any:
        # Check if it was an assumed provenance issue
        # If resolving an assumed node, convert provenance to 'confirmed'
        pass

    return Policy(
        action=policy.action,
        triggers=tuple(new_triggers),
        invariants=tuple(new_invariants),
        allow_tokens=policy.allow_tokens,
        allow_routers=policy.allow_routers,
        allow_recipients=policy.allow_recipients,
        approval_above_usd=policy.approval_above_usd,
    )
