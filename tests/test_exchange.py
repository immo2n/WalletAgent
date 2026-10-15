"""Unit tests for Exchange package (WebSocket client, Scenario Emitter, ExchangeService)."""
import time
import pytest

from exchange.client import CoinbaseWebSocketClient
from exchange.emitter import MarketScenarioEmitter
from exchange.service import ExchangeService


def test_scenario_emitter():
    emitter = MarketScenarioEmitter()
    assert emitter.scenario == "REAL_MARKET"

    # Test GAS_DIP scenario
    res = emitter.set_scenario("GAS_DIP")
    assert res["scenario"] == "GAS_DIP"
    cond = emitter.compute_effective_conditions(2300.0)
    assert cond.gas_gwei < 20.0
    assert cond.scenario == "GAS_DIP"

    # Test ETH_DIP scenario
    emitter.set_scenario("ETH_DIP")
    cond_dip = emitter.compute_effective_conditions(2000.0)
    assert cond_dip.eth_price_usd < 2000.0  # Discounted by 3.5%

    # Reset
    emitter.set_scenario("REAL_MARKET")
    cond_real = emitter.compute_effective_conditions(2000.0)
    assert cond_real.eth_price_usd == 2000.0


def test_exchange_service_snapshot():
    svc = ExchangeService()
    state = svc.get_market_state()
    assert "eth_price_usd" in state
    assert "gas_gwei" in state
    assert "is_connected" in state
    assert state["eth_price_usd"] > 0

    history = svc.get_chart_history()
    assert isinstance(history, list)
    assert len(history) > 0
    assert "time" in history[0]
    assert "price" in history[0]


def test_l1_gas_oracle():
    from exchange.gas_oracle import l1_gas_oracle
    snap = l1_gas_oracle.get_gas_snapshot()
    assert "total_gas_gwei" in snap
    assert "base_fee_gwei" in snap
    assert "priority_fee_gwei" in snap
    assert "latest_block" in snap
    assert snap["total_gas_gwei"] > 0

