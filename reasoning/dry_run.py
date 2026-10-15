"""Dry-Run Risk and Outcome Simulator.

Simulates action outcomes, slippage, and portfolio risk based on live feeds
and retrieved historical regime parameters before passing to formal policy gates.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Literal

from reasoning.models import ActionIntent, DryRunResult, RAGMatch

logger = logging.getLogger("reasoning.dry_run")


class RiskSimulator:
    """Simulates financial outcomes and evaluates risk thresholds."""

    BASE_SLIPPAGE_PCT = 0.05  # 0.05% standard pool slippage on Base

    def simulate(
        self,
        intent: ActionIntent,
        current_usdc: float,
        current_eth: float,
        eth_price: float,
        gas_gwei: float,
        rag_match: RAGMatch,
    ) -> DryRunResult:
        """Simulate trade execution, portfolio balance impact, and 24h risk exposure."""
        amount_usd = intent.amount_usd
        slippage_pct = self.BASE_SLIPPAGE_PCT

        # Dynamic slippage factor if gas is unusually high
        if gas_gwei > 40.0:
            slippage_pct += 0.15

        effective_price = eth_price * (1.0 + (slippage_pct / 100.0))
        estimated_eth = round(amount_usd / effective_price, 5) if effective_price > 0 else 0.0

        post_swap_usdc = round(current_usdc - amount_usd, 2)
        post_swap_eth = round(current_eth + estimated_eth, 5)

        # Projected 24h delta based on historical regime performance
        exp_return_pct = rag_match.expected_return_24h_pct
        expected_24h_delta_usd = round(amount_usd * (exp_return_pct / 100.0), 2)

        # Max drawdown exposure based on historical regime
        max_drawdown_pct = rag_match.max_drawdown_pct
        max_drawdown_usd = round(amount_usd * (max_drawdown_pct / 100.0), 2)

        # Evaluate risk score & decision
        # High risk if historical risk score is >= 7.0, expected return is negative, or strategy is HALT/CAUTION
        regime_risk_score = rag_match.risk_score
        regime_risk_level = rag_match.risk_level.upper()

        if regime_risk_score >= 7.0 or exp_return_pct < -2.0 or regime_risk_level == "HIGH" or rag_match.strategy_recommendation == "HALT_TRADING":
            risk_level: Literal["LOW", "MEDIUM", "HIGH"] = "HIGH"
            risk_score = max(7.0, regime_risk_score)
            decision: Literal["PROCEED_TO_GATES", "ABORT_HIGH_RISK"] = "ABORT_HIGH_RISK"
            notes = (
                f"Dry-run simulation rejected: High risk score ({risk_score}/10) in '{rag_match.regime_name}'. "
                f"Historical expected 24h return ({exp_return_pct:+.1f}%) and max drawdown (-{max_drawdown_usd:.2f}) "
                f"indicate unfavorable risk-reward. Strategy recommendation: {rag_match.strategy_recommendation}."
            )
        elif regime_risk_score >= 4.5 or regime_risk_level == "MEDIUM":
            risk_level = "MEDIUM"
            risk_score = regime_risk_score
            decision = "PROCEED_TO_GATES"
            notes = (
                f"Dry-run simulation acceptable with moderate risk ({risk_score}/10). "
                f"Simulated swap: +{estimated_eth:.5f} ETH. Expected 24h delta: {expected_24h_delta_usd:+.2f} USD. "
                f"Post-trade USDC: ${post_swap_usdc:,.2f}."
            )
        else:
            risk_level = "LOW"
            risk_score = regime_risk_score
            decision = "PROCEED_TO_GATES"
            notes = (
                f"Dry-run simulation favorable: Low risk ({risk_score}/10) in '{rag_match.regime_name}'. "
                f"Simulated swap: +{estimated_eth:.5f} ETH at ${eth_price:,.2f}. "
                f"Historical win-rate: {rag_match.historical_win_rate * 100:.0f}%, "
                f"Expected 24h gain: {expected_24h_delta_usd:+.2f} USD."
            )

        return DryRunResult(
            estimated_eth_received=estimated_eth,
            estimated_slippage_pct=round(slippage_pct, 3),
            post_swap_usdc=post_swap_usdc,
            post_swap_eth=post_swap_eth,
            expected_24h_value_delta_usd=expected_24h_delta_usd,
            max_drawdown_risk_usd=max_drawdown_usd,
            risk_score=round(risk_score, 1),
            risk_level=risk_level,
            decision=decision,
            simulation_notes=notes,
        )


risk_simulator = RiskSimulator()
