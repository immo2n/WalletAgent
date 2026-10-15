"""Mutation testing suite for policy equivalence checker.

100% of mutations must be caught by compare().
"""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Var
from policy.compare import compare
from policy.sorts import Sort


@pytest.fixture
def base_policy() -> Policy:
    # Trigger: gas <= avg24h * (1 - 5%)
    trigger = Cmp(
        op="le",
        lhs=Var("gas"),
        rhs=Coerced(
            inner=BinOp(
                op="mul",
                lhs=Var("avg24h"),
                rhs=BinOp("sub", Const(Fraction(1, 1), Sort.RATIO), Const(Fraction(5, 100), Sort.RATIO)),
            ),
            coercion_id="pct_below_avg24h",
            provenance="confirmed",
        ),
    )
    # Invariant 1: balance - trade >= 500
    inv1 = Cmp(
        op="ge",
        lhs=BinOp("sub", Var("balance"), Var("trade")),
        rhs=Const(Fraction(500, 1), Sort.USD),
    )
    # Invariant 2: trade <= 300
    inv2 = Cmp(
        op="le",
        lhs=Var("trade"),
        rhs=Const(Fraction(300, 1), Sort.USD),
    )
    return Policy(
        action="swap_buy",
        triggers=[trigger],
        invariants=[inv1, inv2],
    )


def test_compare_identity(base_policy):
    assert len(compare(base_policy, base_policy)) == 0


def test_compare_symmetry(base_policy):
    # Mutated policy: trade <= 200
    mutated = Policy(
        action=base_policy.action,
        triggers=base_policy.triggers,
        invariants=[
            base_policy.invariants[0],
            Cmp("le", Var("trade"), Const(Fraction(200, 1), Sort.USD)),
        ],
    )
    f_ab = compare(base_policy, mutated)
    f_ba = compare(mutated, base_policy)

    assert len(f_ab) > 0
    assert len(f_ba) > 0

    # Opposite directions
    directions_ab = {f.direction for f in f_ab}
    directions_ba = {f.direction for f in f_ba}
    if "B_stricter" in directions_ab:
        assert "B_looser" in directions_ba
    if "B_looser" in directions_ab:
        assert "B_stricter" in directions_ba


def test_mutation_flip_comparison_operator_trigger(base_policy):
    mutated = Policy(
        action=base_policy.action,
        triggers=[
            Cmp("ge", base_policy.triggers[0].lhs, base_policy.triggers[0].rhs)
        ],
        invariants=base_policy.invariants,
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_flip_comparison_operator_inv1(base_policy):
    mutated = Policy(
        action=base_policy.action,
        triggers=base_policy.triggers,
        invariants=[
            Cmp("le", base_policy.invariants[0].lhs, base_policy.invariants[0].rhs),
            base_policy.invariants[1],
        ],
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_flip_comparison_operator_inv2(base_policy):
    mutated = Policy(
        action=base_policy.action,
        triggers=base_policy.triggers,
        invariants=[
            base_policy.invariants[0],
            Cmp("ge", base_policy.invariants[1].lhs, base_policy.invariants[1].rhs),
        ],
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_change_constant_by_one_unit_inv1(base_policy):
    # 500 -> 501
    mutated = Policy(
        action=base_policy.action,
        triggers=base_policy.triggers,
        invariants=[
            Cmp("ge", base_policy.invariants[0].lhs, Const(Fraction(501, 1), Sort.USD)),
            base_policy.invariants[1],
        ],
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_change_constant_by_one_unit_inv2(base_policy):
    # 300 -> 299
    mutated = Policy(
        action=base_policy.action,
        triggers=base_policy.triggers,
        invariants=[
            base_policy.invariants[0],
            Cmp("le", base_policy.invariants[1].lhs, Const(Fraction(299, 1), Sort.USD)),
        ],
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_before_after_confusion(base_policy):
    # Swap balance - trade >= 500 for balance >= 500
    mutated = Policy(
        action=base_policy.action,
        triggers=base_policy.triggers,
        invariants=[
            Cmp("ge", Var("balance"), Const(Fraction(500, 1), Sort.USD)),
            base_policy.invariants[1],
        ],
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_drop_one_invariant(base_policy):
    # Drop trade <= 300
    mutated = Policy(
        action=base_policy.action,
        triggers=base_policy.triggers,
        invariants=[base_policy.invariants[0]],
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_change_coercion(base_policy):
    # Change pct_below_avg24h to lowest_pctile24h (pctile24h <= 5%)
    mutated = Policy(
        action=base_policy.action,
        triggers=[
            Cmp(
                "le",
                Var("pctile24h"),
                Coerced(Const(Fraction(5, 100), Sort.RATIO), "lowest_pctile24h", "confirmed"),
            )
        ],
        invariants=base_policy.invariants,
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0


def test_mutation_add_extra_trigger(base_policy):
    mutated = Policy(
        action=base_policy.action,
        triggers=[
            base_policy.triggers[0],
            Cmp("le", Var("gas"), Const(Fraction(10, 1), Sort.GWEI)),
        ],
        invariants=base_policy.invariants,
    )
    findings = compare(base_policy, mutated)
    assert len(findings) > 0
