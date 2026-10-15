"""Test paraphrase hash stability across varying phrasings."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.hashing import policy_hash
from policy.sorts import Sort


def test_gas_trigger_paraphrases_share_same_hash():
    # Canonical AST for gas <= 20 gwei
    canonical_ast = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
    )
    expected_hash = policy_hash(canonical_ast)

    # Paraphrase 1 AST (even if unit_inferred differed in reader metadata)
    para1_ast = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI, unit_inferred=True))],
    )
    assert policy_hash(para1_ast) == expected_hash

    # Paraphrase 2 AST
    para2_ast = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI, unit_inferred=False))],
    )
    assert policy_hash(para2_ast) == expected_hash

    # Paraphrase 3 AST
    para3_ast = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
    )
    assert policy_hash(para3_ast) == expected_hash


def test_balance_floor_paraphrases_share_same_hash():
    # Canonical AST for balance - trade >= 500
    canonical_ast = Policy(
        action="swap_buy",
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
    )
    expected_hash = policy_hash(canonical_ast)

    # Paraphrase 1
    para1 = Policy(
        action="swap_buy",
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD, unit_inferred=True))
        ],
    )
    assert policy_hash(para1) == expected_hash

    # Paraphrase 2
    para2 = Policy(
        action="swap_buy",
        invariants=[
            Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))
        ],
    )
    assert policy_hash(para2) == expected_hash


def test_tx_cap_paraphrases_share_same_hash():
    # Canonical AST for trade <= 300
    canonical_ast = Policy(
        action="swap_buy",
        invariants=[Cmp("le", Var("trade"), Const(Fraction(300, 1), Sort.USD))],
    )
    expected_hash = policy_hash(canonical_ast)

    para1 = Policy(
        action="swap_buy",
        invariants=[Cmp("le", Var("trade"), Const(Fraction(300, 1), Sort.USD, unit_inferred=True))],
    )
    assert policy_hash(para1) == expected_hash
