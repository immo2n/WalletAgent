"""Tests for verify_policy orchestration covering all 6 demo scenarios."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Var
from policy.errors import Unreadable
from policy.loop import NeedsHumanReview, Rejected, VerifiedPolicy, verify_policy
from policy.readers.base import Reader
from policy.readers.llm_reader import LLMReader
from policy.readers.mock import MockLLMClient
from policy.readers.rule_reader import RuleReader
from policy.sorts import Sort


class DummyReader(Reader):
    def __init__(self, policy: Policy | None = None, should_fail: bool = False):
        self.policy = policy
        self.should_fail = should_fail

    def read(self, text: str, feedback: object = None) -> Policy:
        if self.should_fail:
            raise Unreadable("DummyReader failed parse", raw_text=text)
        assert self.policy is not None
        return self.policy


def test_scenario_1_p5_ambiguity_resolved_and_misparse_repaired():
    """Scenario 1:

    P5 with ambiguity resolved: clarification asked once,
    LLM mis-parse (balance floor checked before the trade) caught with a counterexample,
    repaired on attempt 2, VERIFIED.
    """
    rule_reader = RuleReader()
    text = "Buy if gas price is under 5% and do not go under 500 dollars balance."

    mock_client = MockLLMClient()
    # Attempt 1: staged mis-parse (balance >= 500 instead of balance - trade >= 500)
    attempt1_ast = {
        "node": "Policy",
        "action": "swap_buy",
        "triggers": [
            {
                "node": "Cmp",
                "op": "le",
                "lhs": {"node": "Var", "name": "gas"},
                "rhs": {"node": "Const", "value": "1/20", "sort": "RATIO", "unit_inferred": False},
            }
        ],
        "invariants": [
            {
                "node": "Cmp",
                "op": "ge",
                "lhs": {"node": "Var", "name": "balance"},  # Bug: checks balance before trade!
                "rhs": {"node": "Const", "value": "500/1", "sort": "USD", "unit_inferred": False},
            }
        ],
        "allow_tokens": [],
        "allow_routers": [],
        "allow_recipients": [],
        "approval_above_usd": None,
    }
    # Attempt 2: repaired parse
    attempt2_ast = {
        "node": "Policy",
        "action": "swap_buy",
        "triggers": [
            {
                "node": "Cmp",
                "op": "le",
                "lhs": {"node": "Var", "name": "gas"},
                "rhs": {"node": "Const", "value": "1/20", "sort": "RATIO", "unit_inferred": False},
            }
        ],
        "invariants": [
            {
                "node": "Cmp",
                "op": "ge",
                "lhs": {
                    "node": "BinOp",
                    "op": "sub",
                    "lhs": {"node": "Var", "name": "balance"},
                    "rhs": {"node": "Var", "name": "trade"},
                },
                "rhs": {"node": "Const", "value": "500/1", "sort": "USD", "unit_inferred": False},
            }
        ],
        "allow_tokens": [],
        "allow_routers": [],
        "allow_recipients": [],
        "approval_above_usd": None,
    }

    mock_client.set_default_responses([attempt1_ast, attempt2_ast])
    llm_reader = LLMReader(mock_client)

    clarification_count = 0

    def ask_user(q, options):
        nonlocal clarification_count
        clarification_count += 1
        return "pct_below_avg24h"

    res = verify_policy(text, rule_reader, llm_reader, ask_user)

    assert isinstance(res, VerifiedPolicy)
    assert res.status == "VERIFIED"
    assert res.attempts == 2
    assert clarification_count == 1
    assert "Keep the balance after each trade at least $500." in res.readback


def test_scenario_2_p6_clean_verified_on_attempt_1():
    """Scenario 2: P6 clean: VERIFIED on attempt 1, no questions."""
    rule_reader = RuleReader()
    text = "Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars."

    mock_client = MockLLMClient()
    mock_client.set_default_responses([
        {
            "node": "Policy",
            "action": "swap_buy",
            "triggers": [
                {
                    "node": "Cmp",
                    "op": "le",
                    "lhs": {"node": "Var", "name": "gas"},
                    "rhs": {"node": "Const", "value": "20/1", "sort": "GWEI", "unit_inferred": False},
                }
            ],
            "invariants": [
                {
                    "node": "Cmp",
                    "op": "ge",
                    "lhs": {
                        "node": "BinOp",
                        "op": "sub",
                        "lhs": {"node": "Var", "name": "balance"},
                        "rhs": {"node": "Var", "name": "trade"},
                    },
                    "rhs": {"node": "Const", "value": "500/1", "sort": "USD", "unit_inferred": False},
                }
            ],
            "allow_tokens": [],
            "allow_routers": [],
            "allow_recipients": [],
            "approval_above_usd": None,
        }
    ])
    llm_reader = LLMReader(mock_client)

    questions_asked = 0

    def ask_user(q, options):
        nonlocal questions_asked
        questions_asked += 1
        return options[0].id

    res = verify_policy(text, rule_reader, llm_reader, ask_user)

    assert isinstance(res, VerifiedPolicy)
    assert res.status == "VERIFIED"
    assert res.attempts == 1
    assert questions_asked == 0


def test_scenario_3_llm_never_converges_needs_human_review():
    """Scenario 3: LLM never converges: NeedsHumanReview after 2 repairs, nothing else produced."""
    p_a = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
        invariants=[Cmp("le", Var("trade"), Const(Fraction(100, 1), Sort.USD))],
    )
    # LLM keeps insisting on trade <= 500
    p_b_wrong = {
        "node": "Policy",
        "action": "swap_buy",
        "triggers": [
            {
                "node": "Cmp",
                "op": "le",
                "lhs": {"node": "Var", "name": "gas"},
                "rhs": {"node": "Const", "value": "20/1", "sort": "GWEI", "unit_inferred": False},
            }
        ],
        "invariants": [
            {
                "node": "Cmp",
                "op": "le",
                "lhs": {"node": "Var", "name": "trade"},
                "rhs": {"node": "Const", "value": "500/1", "sort": "USD", "unit_inferred": False},
            }
        ],
        "allow_tokens": [],
        "allow_routers": [],
        "allow_recipients": [],
        "approval_above_usd": None,
    }

    mock_client = MockLLMClient()
    mock_client.set_default_responses([p_b_wrong, p_b_wrong, p_b_wrong])
    llm_reader = LLMReader(mock_client)

    res = verify_policy("trade max 100", DummyReader(p_a), llm_reader, lambda q, opts: opts[0].id)

    assert isinstance(res, NeedsHumanReview)
    assert res.status == "NEEDS_HUMAN_REVIEW"
    assert res.last_counterexample is not None


def test_scenario_4_llm_silently_picks_coercion_rejected():
    """Scenario 4:

    LLM silently picks a coercion (provenance assumed): REJECTED
    even though Z3 finds the two readings equivalent.
    """
    # Reader A has assumed provenance
    p_a = Policy(
        action="swap_buy",
        triggers=[
            Cmp(
                "le",
                Var("gas"),
                Coerced(Const(Fraction(5, 1), Sort.GWEI), "absolute_reinterpret", provenance="assumed"),
            )
        ],
    )
    # Reader B also has assumed provenance
    p_b_json = {
        "node": "Policy",
        "action": "swap_buy",
        "triggers": [
            {
                "node": "Cmp",
                "op": "le",
                "lhs": {"node": "Var", "name": "gas"},
                "rhs": {
                    "node": "Coerced",
                    "inner": {"node": "Const", "value": "5/1", "sort": "GWEI", "unit_inferred": False},
                    "coercion_id": "absolute_reinterpret",
                    "provenance": "assumed",
                },
            }
        ],
        "invariants": [],
        "allow_tokens": [],
        "allow_routers": [],
        "allow_recipients": [],
        "approval_above_usd": None,
    }

    mock_client = MockLLMClient()
    mock_client.set_default_responses([p_b_json])
    llm_reader = LLMReader(mock_client)

    res = verify_policy("gas under 5%", DummyReader(p_a), llm_reader, lambda q, opts: opts[0].id)

    assert isinstance(res, Rejected)
    assert res.status == "REJECTED"


def test_scenario_5_reader_a_unreadable_engages_tier2():
    """Scenario 5: Reader A raises Unreadable on a paraphrase: Tier 2 mode engages and independence='llm-llm'."""
    p_valid = Policy(
        action="swap_buy",
        triggers=[Cmp("le", Var("gas"), Const(Fraction(20, 1), Sort.GWEI))],
    )

    failing_primary_a = DummyReader(should_fail=True)
    fallback_a = DummyReader(policy=p_valid)

    mock_client = MockLLMClient()
    mock_client.set_default_responses([
        {
            "node": "Policy",
            "action": "swap_buy",
            "triggers": [
                {
                    "node": "Cmp",
                    "op": "le",
                    "lhs": {"node": "Var", "name": "gas"},
                    "rhs": {"node": "Const", "value": "20/1", "sort": "GWEI", "unit_inferred": False},
                }
            ],
            "invariants": [],
            "allow_tokens": [],
            "allow_routers": [],
            "allow_recipients": [],
            "approval_above_usd": None,
        }
    ])
    llm_reader_b = LLMReader(mock_client)

    res = verify_policy(
        "paraphrase that rule reader cannot parse",
        failing_primary_a,
        llm_reader_b,
        lambda q, opts: opts[0].id,
        reader_a_fallback=fallback_a,
    )

    assert isinstance(res, VerifiedPolicy)
    assert res.status == "VERIFIED"
    assert res.independence == "llm-llm"


def test_scenario_6_p10_refused():
    """Scenario 6: P10: refused, no policy produced."""
    rule_reader = RuleReader()
    mock_client = MockLLMClient()
    # LLM reader also fails or is not called
    llm_reader = LLMReader(mock_client)

    res = verify_policy("Double my money.", rule_reader, llm_reader, lambda q, opts: opts[0].id)

    assert isinstance(res, Rejected)
    assert res.status == "REJECTED"
