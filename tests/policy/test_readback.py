"""Tests for readback generation and canonical round-trip property."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.readback import readback
from policy.readers.rule_reader import RuleReader
from policy.sorts import Sort


@pytest.fixture(scope="module")
def rule_reader():
    return RuleReader()


def test_readback_gas_and_balance_floor(rule_reader):
    p = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
    )
    rb = readback(p)
    assert "Buy only when gas is at most 20 gwei." in rb
    assert "Keep the balance after each trade at least $500." in rb


def test_roundtrip_reader_a_on_readback(rule_reader):
    """Round-trip property:

    Reader A applied to its own readback text must return a policy equal to the original.
    """
    p = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
    )
    rb = readback(p)
    # Reader A parses readback text
    roundtripped = rule_reader.read(rb)
    assert roundtripped.triggers[0] == p.triggers[0]
    assert roundtripped.invariants[0] == p.invariants[0]
