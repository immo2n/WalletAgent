"""Unit tests for LLMReader with MockLLMClient."""
from fractions import Fraction
import pytest

from policy.ast import BinOp, Cmp, Coerced, Const, Policy, Var
from policy.compare import Finding
from policy.errors import Unreadable
from policy.readers.llm_reader import LLMReader
from policy.readers.mock import MockLLMClient
from policy.sorts import Sort


def test_schema_invalid_output_becomes_unreadable():
    mock_client = MockLLMClient()
    mock_client.set_default_responses([{"invalid": "schema", "no": "action"}])
    reader = LLMReader(mock_client)

    with pytest.raises(Unreadable, match="does not conform to Policy schema"):
        reader.read("Buy ETH when gas is under 20 gwei.")


def test_feedback_text_contains_counterexample_numbers():
    mock_client = MockLLMClient()
    mock_client.set_default_responses([
        {
            "node": "Policy",
            "action": "swap_buy",
            "triggers": [],
            "invariants": [
                {
                    "node": "Cmp",
                    "op": "ge",
                    "lhs": {"node": "Var", "name": "balance"},
                    "rhs": {"node": "Const", "value": "500/1", "sort": "USD", "unit_inferred": False},
                }
            ],
            "allow_tokens": [],
            "allow_routers": [],
            "allow_recipients": [],
            "approval_above_usd": None,
        }
    ])
    reader = LLMReader(mock_client)

    finding = Finding(
        direction="B_looser",
        state={"balance": Fraction(600, 1), "trade": Fraction(300, 1)},
        explanation="violates stated minimum of 500 after the trade",
    )

    reader.read("Never let balance drop below 500", feedback=finding)

    assert len(mock_client.call_history) == 1
    last_user_prompt = mock_client.call_history[0]["user"]
    # Verify counterexample numbers appear verbatim
    assert "balance=600" in last_user_prompt
    assert "trade=300" in last_user_prompt


def test_llm_reader_never_emits_confirmed_provenance():
    mock_client = MockLLMClient()
    # Script an output with provenance="confirmed"
    mock_client.set_default_responses([
        {
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
                        "provenance": "confirmed",  # Untrusted LLM claims confirmed
                    },
                }
            ],
            "invariants": [],
            "allow_tokens": [],
            "allow_routers": [],
            "allow_recipients": [],
            "approval_above_usd": None,
        }
    ])
    reader = LLMReader(mock_client)
    p = reader.read("gas under 5%")

    # LLMReader must have sanitized provenance to 'assumed'
    assert isinstance(p.triggers[0].rhs, Coerced)
    assert p.triggers[0].rhs.provenance == "assumed"
