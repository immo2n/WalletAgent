"""Tests for type checker, issue reporting, and deterministic resolution."""
from fractions import Fraction
import pytest

from policy.ast import Cmp, Coerced, Const, Policy, Var
from policy.sorts import Sort
from policy.typecheck import resolve, typecheck


def test_gas_under_5_percent_produces_one_sort_mismatch_with_4_options():
    p = Policy(
        action="swap_buy",
        triggers=[
            Cmp("lt", Var("gas"), Const(Fraction(5, 100), Sort.RATIO))
        ],
    )
    issues = typecheck(p)
    assert len(issues) == 1
    issue = issues[0]
    assert issue.kind == "SORT_MISMATCH"
    assert issue.issue_id == "gas:lt:1/20"
    assert len(issue.options) == 4

    option_ids = [opt.id for opt in issue.options]
    assert option_ids == [
        "pct_below_avg24h",
        "pct_above_avg24h",
        "lowest_pctile24h",
        "absolute_reinterpret",
    ]

    # Verify option descriptions
    descriptions = [opt.description for opt in issue.options]
    assert descriptions == [
        "gas is at least 5% below its 24h average",
        "gas is at least 5% above its 24h average",
        "gas is within the lowest 5% of the last 24h",
        "5 gwei, not a percentage",
    ]


def test_gas_under_20_gwei_and_bare():
    # Explicit gwei
    p1 = Policy(
        action="swap_buy",
        triggers=[Cmp("lt", Var("gas"), Const(Fraction(20, 1), Sort.GWEI, unit_inferred=False))],
    )
    assert len(typecheck(p1)) == 0

    # Bare 20, unit inferred
    p2 = Policy(
        action="swap_buy",
        triggers=[Cmp("lt", Var("gas"), Const(Fraction(20, 1), Sort.GWEI, unit_inferred=True))],
    )
    assert len(typecheck(p2)) == 0
    assert p2.triggers[0].rhs.unit_inferred is True


def test_assumed_provenance_issue():
    p = Policy(
        action="swap_buy",
        triggers=[
            Cmp(
                "le",
                Var("gas"),
                Coerced(
                    inner=Const(Fraction(20, 1), Sort.GWEI),
                    coercion_id="absolute_reinterpret",
                    provenance="assumed",
                ),
            )
        ],
    )
    issues = typecheck(p)
    assert len(issues) == 1
    assert issues[0].kind == "ASSUMED_PROVENANCE"


def test_resolve_with_each_option_typechecks_clean():
    p = Policy(
        action="swap_buy",
        triggers=[
            Cmp("lt", Var("gas"), Const(Fraction(5, 100), Sort.RATIO))
        ],
    )
    issues = typecheck(p)
    issue = issues[0]

    for opt in issue.options:
        resolved_policy = resolve(p, issue.issue_id, opt.id)
        # Must typecheck clean with 0 issues
        new_issues = typecheck(resolved_policy)
        assert len(new_issues) == 0, f"Option {opt.id} failed typecheck: {new_issues}"


def test_resolving_same_issue_in_two_different_asts_yields_equal_subtrees():
    # Reader A produced lt, Reader B produced le, same var and constant
    pa = Policy(
        action="swap_buy",
        triggers=[Cmp("lt", Var("gas"), Const(Fraction(5, 100), Sort.RATIO))],
    )
    pb = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(5, 100), Sort.RATIO))],
    )

    issue_a = typecheck(pa)[0]
    issue_b = typecheck(pb)[0]
    assert issue_a.issue_id == issue_b.issue_id == "gas:lt:1/20"

    # Resolve both with pct_below_avg24h
    resolved_a = resolve(pa, issue_a.issue_id, "pct_below_avg24h")
    resolved_b = resolve(pb, issue_b.issue_id, "pct_below_avg24h")

    assert resolved_a.triggers[0] == resolved_b.triggers[0]
