"""Acceptance test suite over the Section 5 T1 prompt table."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Const, Policy, Var
from policy.errors import Unreadable
from policy.hashing import policy_hash
from policy.loop import Rejected, VerifiedPolicy, verify_policy
from policy.readers.llm_reader import LLMReader
from policy.readers.mock import MockLLMClient
from policy.readers.rule_reader import RuleReader
from policy.sorts import Sort
from policy.typecheck import resolve, typecheck


@pytest.fixture(scope="module")
def rule_reader():
    return RuleReader()


def test_t1_p1_buy_eth_gas_under_20_gwei(rule_reader):
    p = rule_reader.read("Buy ETH when gas is under 20 gwei.")
    assert len(typecheck(p)) == 0
    assert p.triggers[0] == Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))


def test_t1_p2_balance_floor(rule_reader):
    p = rule_reader.read("Never let my balance go under 500 dollars.")
    assert len(typecheck(p)) == 0
    assert p.invariants[0] == Cmp("ge", BinOp("sub", Var("balance"), Var("trade")), Const(Fraction(500, 1), Sort.USD))


def test_t1_p3_per_tx_cap(rule_reader):
    p = rule_reader.read("Don't spend more than 300 dollars in one transaction.")
    assert len(typecheck(p)) == 0
    assert p.invariants[0] == Cmp("le", Var("trade"), Const(Fraction(300, 1), Sort.USD))


def test_t1_p4_daily_cap(rule_reader):
    p = rule_reader.read("No more than 1000 dollars per day in total.")
    assert len(typecheck(p)) == 0
    assert p.invariants[0] == Cmp("le", BinOp("add", Var("spent_today"), Var("trade")), Const(Fraction(1000, 1), Sort.USD))


def test_t1_p5_and_different_hashes_for_coercions(rule_reader):
    p = rule_reader.read("Buy if gas price is under 5% and do not go under 500 dollars balance.")
    issues = typecheck(p)
    assert len(issues) == 1
    assert issues[0].kind == "SORT_MISMATCH"
    assert len(issues[0].options) == 4

    p_below = resolve(p, issues[0].issue_id, "pct_below_avg24h")
    p_pctile = resolve(p, issues[0].issue_id, "lowest_pctile24h")

    hash_below = policy_hash(p_below)
    hash_pctile = policy_hash(p_pctile)

    # Different clarification choices must yield different hashes
    assert hash_below != hash_pctile


def test_t1_p6_combined(rule_reader):
    p = rule_reader.read("Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.")
    assert len(typecheck(p)) == 0
    assert len(p.triggers) == 1
    assert len(p.invariants) == 1


def test_t1_p7_allow_tokens(rule_reader):
    p = rule_reader.read("Only trade WETH and USDC.")
    assert set(p.allow_tokens) == {"WETH", "USDC"}


def test_t1_p8_approval_above(rule_reader):
    p = rule_reader.read("Ask me before anything over 500 dollars.")
    assert p.approval_above_usd == Const(Fraction(500, 1), Sort.USD)


def test_t1_p9_buy_the_dip_refusal(rule_reader):
    with pytest.raises(Unreadable):
        rule_reader.read("Buy the dip.")


def test_t1_p10_double_my_money_refusal(rule_reader):
    with pytest.raises(Unreadable):
        rule_reader.read("Double my money.")
