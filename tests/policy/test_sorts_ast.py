"""Tests for sorts, AST definitions, immutability, and JSON round-tripping."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Var, parse_fraction
from policy.sorts import REGISTRY, Sort


def test_fraction_parsing():
    assert parse_fraction("0.05") == Fraction(1, 20)
    assert parse_fraction("5") == Fraction(5, 1)
    assert parse_fraction("1/20") == Fraction(1, 20)
    assert parse_fraction("5/1") == Fraction(5, 1)
    assert parse_fraction(5) == Fraction(5, 1)
    assert parse_fraction(Fraction(1, 20)) == Fraction(1, 20)


def test_var_registry_and_unknown_rejection():
    v = Var("gas")
    assert v.sort == Sort.GWEI
    assert v.name == "gas"

    with pytest.raises(ValueError, match="Unknown state variable"):
        Var("unknown_var_xyz")


def test_frozen_immutability():
    c = Const(Fraction(5, 1), Sort.GWEI)
    with pytest.raises(AttributeError):
        c.value = Fraction(10, 1)  # type: ignore

    v = Var("balance")
    with pytest.raises(AttributeError):
        v.name = "trade"  # type: ignore

    p = Policy(action="swap_buy")
    with pytest.raises(AttributeError):
        p.action = "transfer"  # type: ignore


def test_ast_json_roundtrip():
    # Build a complex policy
    p = Policy(
        action="swap_buy",
        triggers=[
            Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI, unit_inferred=False))
        ],
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
        allow_tokens=["WETH", "USDC"],
        allow_routers=["0x1111111254fb6c44bac0bed2854e76f90643097d"],
        allow_recipients=["0x1234567890123456789012345678901234567890"],
        approval_above_usd=Const(Fraction(500, 1), Sort.USD),
    )

    data = p.to_json()
    p2 = Policy.from_json(data)
    assert p == p2
    assert p.triggers[0].lhs == p2.triggers[0].lhs
    assert p.triggers[0].rhs.value == p2.triggers[0].rhs.value
    assert p.invariants[0].lhs.op == p2.invariants[0].lhs.op
