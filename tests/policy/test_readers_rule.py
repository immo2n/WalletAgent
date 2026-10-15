"""Unit tests for deterministic RuleReader."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.errors import Unreadable
from policy.readers.rule_reader import RuleReader
from policy.sorts import Sort


@pytest.fixture(scope="module")
def reader():
    return RuleReader()


def test_p1_buy_eth_gas_under_20_gwei(reader):
    p = reader.read("Buy ETH when gas is under 20 gwei.")
    assert len(p.triggers) == 1
    trig = p.triggers[0]
    assert trig.op == "le"
    assert trig.lhs == Var("gas")
    assert trig.rhs == Const(Fraction(20, 1), Sort.GWEI)


def test_p2_never_let_balance_go_under_500_dollars(reader):
    p = reader.read("Never let my balance go under 500 dollars.")
    assert len(p.invariants) == 1
    inv = p.invariants[0]
    assert inv.op == "ge"
    assert inv.lhs == BinOp("sub", Var("balance"), Var("trade"))
    assert inv.rhs == Const(Fraction(500, 1), Sort.USD)


def test_p3_dont_spend_more_than_300_dollars_in_one_tx(reader):
    p = reader.read("Don't spend more than 300 dollars in one transaction.")
    assert len(p.invariants) == 1
    inv = p.invariants[0]
    assert inv.op == "le"
    assert inv.lhs == Var("trade")
    assert inv.rhs == Const(Fraction(300, 1), Sort.USD)


def test_p4_no_more_than_1000_dollars_per_day(reader):
    p = reader.read("No more than 1000 dollars per day in total.")
    assert len(p.invariants) == 1
    inv = p.invariants[0]
    assert inv.op == "le"
    assert inv.lhs == BinOp("add", Var("spent_today"), Var("trade"))
    assert inv.rhs == Const(Fraction(1000, 1), Sort.USD)


def test_p5_gas_under_5_percent_yields_ill_typed_cmp(reader):
    p = reader.read("Buy if gas price is under 5% and do not go under 500 dollars balance.")
    assert len(p.triggers) == 1
    trig = p.triggers[0]
    # LHS is GWEI, RHS is RATIO (ill-typed, un-repaired)
    assert trig.lhs == Var("gas")
    assert trig.rhs == Const(Fraction(5, 100), Sort.RATIO)

    assert len(p.invariants) == 1
    inv = p.invariants[0]
    assert inv.op == "ge"
    assert inv.lhs == BinOp("sub", Var("balance"), Var("trade"))
    assert inv.rhs == Const(Fraction(500, 1), Sort.USD)


def test_p6_combined_rules(reader):
    p = reader.read("Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.")
    assert len(p.triggers) == 1
    assert p.triggers[0].lhs == Var("gas")
    assert len(p.invariants) == 1
    assert p.invariants[0].lhs == BinOp("sub", Var("balance"), Var("trade"))


def test_p7_allow_tokens(reader):
    p = reader.read("Only trade WETH and USDC.")
    assert set(p.allow_tokens) == {"WETH", "USDC"}


def test_p8_approval_above_usd(reader):
    p = reader.read("Ask me before anything over 500 dollars.")
    assert p.approval_above_usd == Const(Fraction(500, 1), Sort.USD)


def test_garbage_and_vague_prompts_raise_unreadable(reader):
    with pytest.raises(Unreadable):
        reader.read("Buy the dip.")

    with pytest.raises(Unreadable):
        reader.read("Double my money.")

    with pytest.raises(Unreadable):
        reader.read("Hello world random text.")
