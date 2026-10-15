"""Tests for Z3 compilation and comparison."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.compare import compare
from policy.errors import UnresolvedTypeIssues
from policy.sorts import Sort
from policy.z3_compile import compile_policy


def test_compile_clean_policy():
    p = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
    )
    named = compile_policy(p)
    assert "gas<=20" in named
    assert "balance-trade>=500" in named


def test_compile_ill_typed_policy_raises():
    p = Policy(
        action="swap_buy",
        triggers=[Cmp("lt", Var("gas"), Const(Fraction(5, 100), Sort.RATIO))],
    )
    with pytest.raises(UnresolvedTypeIssues):
        compile_policy(p)


def test_compare_identical_policies_is_empty():
    p = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
    )
    findings = compare(p, p)
    assert len(findings) == 0
