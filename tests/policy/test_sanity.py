"""Tests for sanity checks: contradictory, vacuous, and redundant constraints."""
from fractions import Fraction
from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.sanity import sanity
from policy.sorts import Sort


def test_clean_policy_sanity():
    p = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
    )
    problems = sanity(p)
    assert len(problems) == 0


def test_contradictory_policy():
    # gas <= 10 and gas >= 15 cannot both be satisfied
    p = Policy(
        action="swap_buy",
        triggers=[
            Cmp("le", Var("gas"), Const(Fraction(10, 1), Sort.GWEI)),
            Cmp("ge", Var("gas"), Const(Fraction(15, 1), Sort.GWEI)),
        ],
    )
    problems = sanity(p)
    assert any("Contradictory" in prob for prob in problems)


def test_vacuous_policy():
    # In DOMAIN, gas >= 1 is always true. So gas >= 0 can never be violated.
    p = Policy(
        action="swap_buy",
        triggers=[Cmp("ge", Var("gas"), Const(Fraction(0, 1), Sort.GWEI))],
    )
    problems = sanity(p)
    assert any("vacuous" in prob for prob in problems)


def test_redundant_policy():
    # trade <= 200 and trade <= 300: trade <= 300 is redundant because trade <= 200 implies it
    p = Policy(
        action="swap_buy",
        invariants=[
            Cmp("le", Var("trade"), Const(Fraction(200, 1), Sort.USD)),
            Cmp("le", Var("trade"), Const(Fraction(300, 1), Sort.USD)),
        ],
    )
    problems = sanity(p)
    assert any("redundant" in prob for prob in problems)
