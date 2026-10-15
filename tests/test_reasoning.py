"""Comprehensive unit and integration tests for the Cognitive Reasoning & RAG Engine."""
import json
import os
import tempfile
import pytest

from reasoning.dry_run import RiskSimulator
from reasoning.engine import ReasoningEngine
from reasoning.llm_client import FragmentedReasoningLLM
from reasoning.models import ActionIntent, HistoricalRegime, RAGMatch
from reasoning.rag import RAGRetriever
from user.db import UserDatabase


@pytest.fixture
def sample_regimes():
    return [
        {
            "regime_id": "TEST-REG-01",
            "name": "Low Gas Dip Rebound",
            "description": "Favorable dip recovery with low gas fees.",
            "conditions": {
                "eth_price_min": 2000.0,
                "eth_price_max": 2500.0,
                "gas_gwei_max": 20.0,
                "market_trend": "DIP_REBOUND",
                "volatility": "LOW",
            },
            "historical_metrics": {
                "win_rate": 0.85,
                "expected_return_24h_pct": 5.0,
                "risk_level": "LOW",
                "risk_score": 2.0,
                "max_drawdown_pct": 1.5,
                "sample_size_trades": 100,
            },
            "strategy_recommendation": "ACCUMULATE",
            "profitability_assessment": "High probability accumulation zone.",
        },
        {
            "regime_id": "TEST-REG-02",
            "name": "Severe Gas Congestion Panic",
            "description": "Extreme gas spike with high slippage risk.",
            "conditions": {
                "eth_price_min": 1800.0,
                "eth_price_max": 3000.0,
                "gas_gwei_max": 80.0,
                "market_trend": "CONGESTION_PANIC",
                "volatility": "HIGH",
            },
            "historical_metrics": {
                "win_rate": 0.25,
                "expected_return_24h_pct": -6.0,
                "risk_level": "HIGH",
                "risk_score": 9.2,
                "max_drawdown_pct": 8.0,
                "sample_size_trades": 50,
            },
            "strategy_recommendation": "HALT_TRADING",
            "profitability_assessment": "Negative expected value.",
        },
    ]


@pytest.fixture
def temp_rag_retriever(sample_regimes):
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump(sample_regimes, f)
        tmp_path = f.name
    retriever = RAGRetriever(history_file=tmp_path)
    yield retriever
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


def test_rag_retrieval_favorable(temp_rag_retriever):
    match = temp_rag_retriever.retrieve(eth_price=2300.0, gas_gwei=15.0, scenario="GAS_DIP")
    assert match.regime_id == "TEST-REG-01"
    assert match.risk_level == "LOW"
    assert match.historical_win_rate == 0.85
    assert match.expected_return_24h_pct == 5.0
    assert match.similarity_score > 0.8


def test_rag_retrieval_high_gas(temp_rag_retriever):
    match = temp_rag_retriever.retrieve(eth_price=2400.0, gas_gwei=65.0, scenario="HIGH_GAS")
    assert match.regime_id == "TEST-REG-02"
    assert match.risk_level == "HIGH"
    assert match.strategy_recommendation == "HALT_TRADING"


def test_dry_run_simulation_favorable():
    simulator = RiskSimulator()
    intent = ActionIntent(
        intent_type="SWAP",
        target_token="ETH",
        amount_usd=200.0,
        thesis="Dip rebound accumulation",
        profitability_outlook="Favorable +5.0%",
        confidence_score=0.88,
    )
    rag_match = RAGMatch(
        regime_id="TEST-REG-01",
        regime_name="Low Gas Dip Rebound",
        similarity_score=0.92,
        historical_win_rate=0.85,
        expected_return_24h_pct=5.0,
        risk_level="LOW",
        risk_score=2.0,
        max_drawdown_pct=1.5,
        context_summary="Favorable recovery",
        strategy_recommendation="ACCUMULATE",
    )

    result = simulator.simulate(
        intent=intent,
        current_usdc=1500.0,
        current_eth=1.5,
        eth_price=2345.5,
        gas_gwei=16.0,
        rag_match=rag_match,
    )

    assert result.decision == "PROCEED_TO_GATES"
    assert result.risk_level == "LOW"
    assert result.estimated_eth_received > 0.08
    assert result.post_swap_usdc == 1300.0
    assert result.expected_24h_value_delta_usd == 10.0  # +5% of 200
    assert result.max_drawdown_risk_usd == 3.0          # 1.5% of 200


def test_dry_run_simulation_high_risk_aborts():
    simulator = RiskSimulator()
    intent = ActionIntent(
        intent_type="SWAP",
        target_token="ETH",
        amount_usd=200.0,
        thesis="Attempting swap in volatile market",
        profitability_outlook="Unfavorable",
        confidence_score=0.40,
    )
    rag_match = RAGMatch(
        regime_id="TEST-REG-02",
        regime_name="Severe Gas Congestion Panic",
        similarity_score=0.88,
        historical_win_rate=0.25,
        expected_return_24h_pct=-6.0,
        risk_level="HIGH",
        risk_score=9.2,
        max_drawdown_pct=8.0,
        context_summary="Severe congestion",
        strategy_recommendation="HALT_TRADING",
    )

    result = simulator.simulate(
        intent=intent,
        current_usdc=1500.0,
        current_eth=1.5,
        eth_price=2345.5,
        gas_gwei=65.0,
        rag_match=rag_match,
    )

    assert result.decision == "ABORT_HIGH_RISK"
    assert result.risk_level == "HIGH"
    assert "rejected" in result.simulation_notes.lower()


def test_end_to_end_reasoning_pipeline_execution():
    engine = ReasoningEngine()
    thoughts = []

    report = engine.execute_reasoning_pipeline(
        prompt="Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.",
        current_usdc=1500.0,
        current_eth=1.5,
        eth_price=2345.5,
        gas_gwei=16.0,
        scenario="GAS_DIP",
        trade_amount_usd=200.0,
        triggers=[{"field": "gas", "op": "lte", "val": 20.0}],
        invariants=[{"field": "balance", "op": "sub", "val": 500.0}],
        on_thought=lambda ltype, msg: thoughts.append((ltype, msg)),
    )

    assert report.final_decision == "EXECUTED"
    assert report.dry_run.decision == "PROCEED_TO_GATES"
    assert report.gate_data.solver_status == "SAT"
    assert report.gate_data.passed is True
    assert len(thoughts) >= 4  # RAG, INTENT, DRY_RUN, GATE thoughts logged


def test_end_to_end_reasoning_pipeline_gate_block():
    engine = ReasoningEngine()

    # User balance is 600 USDC, proposed trade is 200 USDC -> balance_after is 400 USDC (< 500 floor)
    report = engine.execute_reasoning_pipeline(
        prompt="Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.",
        current_usdc=600.0,
        current_eth=1.5,
        eth_price=2345.5,
        gas_gwei=16.0,
        scenario="GAS_DIP",
        trade_amount_usd=200.0,
        triggers=[{"field": "gas", "op": "lte", "val": 20.0}],
        invariants=[{"field": "balance", "op": "sub", "val": 500.0}],
    )

    assert report.final_decision == "BLOCKED_BY_GUARD"
    assert report.gate_data.solver_status == "UNSAT"
    assert report.gate_data.passed is False


def test_user_json_manipulation_affects_decisions(temp_rag_retriever):
    """Test user's requirement: modifying market_history.json manipulates agent decisions."""
    # 1. Modify regime to simulate high risk on gas <= 20
    custom_regimes = [
        {
            "regime_id": "MODIFIED-USER-REGIME",
            "name": "User Manipulated Bear Trap",
            "description": "User deliberately manipulated regime to test high-risk abort behavior.",
            "conditions": {
                "eth_price_min": 1000.0,
                "eth_price_max": 5000.0,
                "gas_gwei_max": 25.0,
                "market_trend": "BEAR_TRAP",
                "volatility": "EXTREME",
            },
            "historical_metrics": {
                "win_rate": 0.15,
                "expected_return_24h_pct": -12.5,
                "risk_level": "HIGH",
                "risk_score": 9.8,
                "max_drawdown_pct": 15.0,
                "sample_size_trades": 200,
            },
            "strategy_recommendation": "HALT_TRADING",
            "profitability_assessment": "Extreme risk crash probability.",
        }
    ]
    temp_rag_retriever.save_regimes(custom_regimes)

    engine = ReasoningEngine()
    engine.rag = temp_rag_retriever

    report = engine.execute_reasoning_pipeline(
        prompt="Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.",
        current_usdc=1500.0,
        current_eth=1.5,
        eth_price=2345.5,
        gas_gwei=16.0,
        scenario="REAL_MARKET",
        trade_amount_usd=200.0,
    )

    # Because user manipulated JSON to high risk, dry-run rejects action before gates
    assert report.final_decision == "ABORTED_BY_RISK"
    assert report.dry_run.decision == "ABORT_HIGH_RISK"
    assert "aborted" in report.executive_summary.lower()


def test_transaction_reasoning_endpoint():
    import importlib.util
    server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flask", "server.py")
    spec = importlib.util.spec_from_file_location("wallet_flask_server_test", server_path)
    server_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_mod)
    app = server_mod.create_app()
    client = app.test_client()

    # Query transaction reasoning endpoint
    from user.db import user_db
    tx = user_db.get_state().transactions[0]
    resp = client.get(f"/api/user/transaction/{tx.id}/reasoning")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tx_id"] == tx.id
    assert "actor" in data
    assert "status" in data

    # Query reasoning history endpoint
    hist_resp = client.get("/api/reasoning/history")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.get_json()
    assert isinstance(hist_data, list)
    assert len(hist_data) >= 1
