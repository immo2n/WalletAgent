"""Market Scenario Emitter for Testing Agent Decision Capabilities.

Enables instant injection of targeted market scenarios (gas dips, price drops)
to test agent policy triggers during live hackathon presentations and demos.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import random
import threading
import time
from typing import Any, Dict, Literal, Optional

from exchange.gas_oracle import l1_gas_oracle

ScenarioMode = Literal["REAL_MARKET", "GAS_DIP", "ETH_DIP", "HIGH_GAS"]


@dataclass
class MarketConditions:
    eth_price_usd: float
    gas_gwei: float
    avg24h_gwei: float
    scenario: ScenarioMode
    scenario_description: str
    last_updated: float
    l1_base_fee: float = 1.0
    l1_priority_fee: float = 1.5
    l1_block: int = 0
    is_live_rpc: bool = True


class MarketScenarioEmitter:
    """Manages active market conditions, gas oracle feeds, and test scenario injections."""

    def __init__(self) -> None:
        self.scenario: ScenarioMode = "REAL_MARKET"
        self.base_gas: float = 18.0
        self.avg24h_gas: float = 22.0
        self.price_offset_pct: float = 0.0
        self._lock = threading.RLock()
        self.last_update = time.time()

    def set_scenario(self, scenario: ScenarioMode) -> Dict[str, Any]:
        """Activate a specific test scenario."""
        with self._lock:
            self.scenario = scenario
            if scenario == "REAL_MARKET":
                self.base_gas = 18.0
                self.price_offset_pct = 0.0
                desc = "Real-time market feed directly from Coinbase WebSocket."
            elif scenario == "GAS_DIP":
                self.base_gas = 16.5  # Below 20 gwei threshold
                self.price_offset_pct = 0.0
                desc = "Simulated Gas Dip to 16.5 gwei. Triggers 'gas <= 20' policies!"
            elif scenario == "ETH_DIP":
                self.base_gas = 19.0
                self.price_offset_pct = -0.035  # -3.5% price dip
                desc = "Simulated -3.5% Flash Dip on ETH to test buy-the-dip policies."
            elif scenario == "HIGH_GAS":
                self.base_gas = 36.0  # Above 20 gwei threshold
                self.price_offset_pct = 0.0
                desc = "Simulated Gas Spike to 36 gwei. Guards will intercept trades!"
            else:
                self.scenario = "REAL_MARKET"
                self.base_gas = 18.0
                self.price_offset_pct = 0.0
                desc = "Reset to real-time market feed."

            self.last_update = time.time()
            return {
                "scenario": self.scenario,
                "description": desc,
                "gas_gwei": self.base_gas,
                "price_offset_pct": self.price_offset_pct,
            }

    def compute_effective_conditions(self, raw_coinbase_price: float) -> MarketConditions:
        """Calculate effective price and gas given active scenario and live L1 oracle."""
        with self._lock:
            # Fetch live L1 gas oracle state
            oracle_snap = l1_gas_oracle.get_gas_snapshot()
            live_l1_gas = oracle_snap["total_gas_gwei"]
            base_fee = oracle_snap["base_fee_gwei"]
            tip = oracle_snap["priority_fee_gwei"]
            block = oracle_snap["latest_block"]
            is_live = oracle_snap["is_connected"]

            if self.scenario == "REAL_MARKET":
                effective_gas = round(live_l1_gas, 2)
                is_live_rpc = is_live
                desc = f"Live Ethereum L1 RPC ({oracle_snap['active_rpc']})"
            elif self.scenario == "GAS_DIP":
                effective_gas = round(min(16.5, live_l1_gas), 2)
                is_live_rpc = False
                desc = "Active Scenario: Gas Dip (16.5 gwei) [Trigger Condition Active]"
            elif self.scenario == "ETH_DIP":
                effective_gas = round(live_l1_gas, 2)
                is_live_rpc = is_live
                desc = "Active Scenario: -3.5% ETH Price Dip"
            elif self.scenario == "HIGH_GAS":
                effective_gas = 36.0
                is_live_rpc = False
                desc = "Active Scenario: High Gas Spike (36 gwei) [Guard Blocking Active]"
            else:
                effective_gas = round(live_l1_gas, 2)
                is_live_rpc = is_live
                desc = "Live Ethereum L1 Feed"

            # Apply price offset if scenario active
            effective_price = round(raw_coinbase_price * (1.0 + self.price_offset_pct), 2)

            return MarketConditions(
                eth_price_usd=effective_price,
                gas_gwei=effective_gas,
                avg24h_gwei=self.avg24h_gas,
                scenario=self.scenario,
                scenario_description=desc,
                last_updated=time.time(),
                l1_base_fee=base_fee,
                l1_priority_fee=tip,
                l1_block=block,
                is_live_rpc=is_live_rpc,
            )
