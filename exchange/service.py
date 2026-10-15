"""Exchange Service Orchestration for Live Market Perception.

Coordinates Coinbase WebSocket feeds, market scenario injections,
and provides clean state snapshots for the Wallet Agent and Web Dashboard.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from exchange.client import CoinbaseWebSocketClient
from exchange.emitter import MarketConditions, MarketScenarioEmitter, ScenarioMode
from exchange.gas_oracle import l1_gas_oracle

logger = logging.getLogger("exchange.service")


class ExchangeService:
    """Singleton service providing unified market state to agent and dashboard."""

    def __init__(self, product_id: str = "ETH-USD") -> None:
        self.ws_client = CoinbaseWebSocketClient(product_id=product_id)
        self.emitter = MarketScenarioEmitter()
        # Automatically start live feeds
        self.ws_client.start()
        l1_gas_oracle.start()

    def get_market_state(self) -> Dict[str, Any]:
        """Fetch current effective market state (price, gas, scenario metadata)."""
        snap = self.ws_client.get_snapshot()
        raw_price = snap["price"]
        cond = self.emitter.compute_effective_conditions(raw_price)

        return {
            "eth_price_usd": cond.eth_price_usd,
            "raw_coinbase_price": raw_price,
            "gas_gwei": cond.gas_gwei,
            "l1_base_fee": cond.l1_base_fee,
            "l1_priority_fee": cond.l1_priority_fee,
            "l1_block": cond.l1_block,
            "is_live_rpc": cond.is_live_rpc,
            "avg24h_gwei": cond.avg24h_gwei,
            "high_24h": snap["high_24h"],
            "low_24h": snap["low_24h"],
            "volume_24h": snap["volume_24h"],
            "is_connected": snap["is_connected"],
            "scenario": cond.scenario,
            "scenario_description": cond.scenario_description,
            "last_updated": snap["last_tick_time"],
        }

    def get_chart_history(self) -> List[Dict[str, Any]]:
        """Fetch rolling history for chart rendering with effective price adjustments."""
        raw_history = self.ws_client.get_snapshot()["history"]
        offset = self.emitter.price_offset_pct
        result = []
        for tick in raw_history:
            adjusted = dict(tick)
            if offset != 0.0:
                adjusted["price"] = round(tick["price"] * (1.0 + offset), 2)
            result.append(adjusted)
        return result

    def set_scenario(self, scenario: ScenarioMode) -> Dict[str, Any]:
        return self.emitter.set_scenario(scenario)

    def subscribe_tick(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        def _wrapper(tick: Dict[str, Any]) -> None:
            offset = self.emitter.price_offset_pct
            adjusted = dict(tick)
            if offset != 0.0:
                adjusted["price"] = round(tick["price"] * (1.0 + offset), 2)
            cond = self.emitter.compute_effective_conditions(tick["price"])
            adjusted["gas_gwei"] = cond.gas_gwei
            adjusted["scenario"] = cond.scenario
            callback(adjusted)

        self.ws_client.subscribe_tick(_wrapper)


# Global default exchange service singleton
exchange_service = ExchangeService()


if __name__ == "__main__":
    import sys

    print("Starting Exchange Service CLI monitor (Press Ctrl+C to stop)...")

    def print_tick(t: Dict[str, Any]) -> None:
        sys.stdout.write(
            f"\r[TICK] Time: {t.get('time')} | ETH: ${t.get('price'):,.2f} | Gas: {t.get('gas_gwei', 18)} gwei | Src: {t.get('source')}"
        )
        sys.stdout.flush()

    exchange_service.subscribe_tick(print_tick)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Exchange Service.")
