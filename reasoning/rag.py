"""RAG Retriever: Indexes historical market regimes and retrieves matched patterns."""
from __future__ import annotations

import json
import logging
import math
import os
import threading
from typing import Any, Dict, List, Optional

from reasoning.models import HistoricalRegime, RAGMatch

logger = logging.getLogger("reasoning.rag")

DEFAULT_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "market_history.json")


class RAGRetriever:
    """Thread-safe RAG retriever matching live market state against historical regimes."""

    def __init__(self, history_file: str = DEFAULT_HISTORY_FILE) -> None:
        self.history_file = os.path.abspath(history_file)
        self._lock = threading.RLock()
        self._regimes: List[HistoricalRegime] = []
        self._load()

    def _load(self) -> None:
        with self._lock:
            if os.path.exists(self.history_file) and os.path.getsize(self.history_file) > 0:
                try:
                    with open(self.history_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._regimes = [HistoricalRegime.from_dict(r) for r in data]
                        return
                except Exception as e:
                    logger.error(f"Error loading market history JSON: {e}")
            self._regimes = []

    def get_all_regimes(self) -> List[HistoricalRegime]:
        """Fetch all regimes (reloads from disk if modified)."""
        with self._lock:
            self._load()
            return list(self._regimes)

    def save_regimes(self, regimes_data: List[Dict[str, Any]]) -> None:
        """Overwrite historical regimes (allows user experimentation)."""
        with self._lock:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(regimes_data, f, indent=2)
            self._regimes = [HistoricalRegime.from_dict(r) for r in regimes_data]

    def retrieve(
        self,
        eth_price: float,
        gas_gwei: float,
        scenario: str = "REAL_MARKET",
        market_trend: Optional[str] = None,
    ) -> RAGMatch:
        """Retrieve the closest historical regime for the given live market parameters."""
        with self._lock:
            self._load()

            if not self._regimes:
                # Fallback regime if file was empty
                return RAGMatch(
                    regime_id="FALLBACK-DEFAULT",
                    regime_name="Standard Baseline Market",
                    similarity_score=0.75,
                    historical_win_rate=0.70,
                    expected_return_24h_pct=2.0,
                    risk_level="LOW",
                    risk_score=3.0,
                    max_drawdown_pct=2.0,
                    context_summary="No custom historical regimes found. Utilizing neutral baseline expectations.",
                    strategy_recommendation="ACCUMULATE",
                )

            # Score each regime based on gas compatibility, price range, and trend
            best_regime: Optional[HistoricalRegime] = None
            best_score = -1.0

            for regime in self._regimes:
                cond = regime.conditions
                score = 0.0

                # 1. Gas compatibility (weight: 0.45)
                gas_min = float(cond.get("gas_gwei_min", 0.0))
                gas_max = float(cond.get("gas_gwei_max", 30.0))
                if gas_min <= gas_gwei <= gas_max:
                    gas_score = 1.0
                elif gas_gwei < gas_min:
                    under = (gas_min - gas_gwei) / max(1.0, gas_min)
                    gas_score = max(0.0, 1.0 - under * 2.0)
                else:
                    overage = (gas_gwei - gas_max) / max(1.0, gas_max)
                    gas_score = max(0.0, 1.0 - overage * 2.0)
                score += 0.45 * gas_score

                # 2. Price range overlap (weight: 0.35)
                p_min = float(cond.get("eth_price_min", 1000.0))
                p_max = float(cond.get("eth_price_max", 5000.0))
                if p_min <= eth_price <= p_max:
                    price_score = 1.0
                else:
                    dist = min(abs(eth_price - p_min), abs(eth_price - p_max))
                    price_score = max(0.2, 1.0 - (dist / 2000.0))
                score += 0.35 * price_score

                # 3. Scenario & Trend match (weight: 0.20)
                regime_trend = cond.get("market_trend", "").upper()
                if scenario == "GAS_DIP" and ("DIP" in regime_trend or "LOW_GAS" in regime.name.upper()):
                    trend_score = 1.0
                elif scenario == "HIGH_GAS" and ("CONGESTION" in regime_trend or "PANIC" in regime_trend):
                    trend_score = 1.0
                elif scenario == "ETH_DIP" and ("DIP" in regime_trend or "CAPITULATION" in regime_trend):
                    trend_score = 1.0
                elif market_trend and market_trend.upper() in regime_trend:
                    trend_score = 1.0
                else:
                    trend_score = 0.7
                score += 0.20 * trend_score

                if score > best_score:
                    best_score = score
                    best_regime = regime

            assert best_regime is not None
            metrics = best_regime.historical_metrics

            return RAGMatch(
                regime_id=best_regime.regime_id,
                regime_name=best_regime.name,
                similarity_score=round(best_score, 3),
                historical_win_rate=float(metrics.get("win_rate", 0.75)),
                expected_return_24h_pct=float(metrics.get("expected_return_24h_pct", 3.0)),
                risk_level=str(metrics.get("risk_level", "LOW")),
                risk_score=float(metrics.get("risk_score", 3.0)),
                max_drawdown_pct=float(metrics.get("max_drawdown_pct", 2.5)),
                context_summary=best_regime.description,
                strategy_recommendation=best_regime.strategy_recommendation,
            )


rag_retriever = RAGRetriever()
