"""Fragmented LLM prompt handler for RAG intent generation and dry-run evaluation.

Avoids monolithic prompts by segmenting cognitive duties into discrete, manageable chunks:
- Chunk 1: Strategy intent generation and profitability analysis from RAG context.
- Chunk 2: Dry-run risk evaluation and execution clearance before formal policy gates.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from reasoning.models import ActionIntent, DryRunResult, RAGMatch

logger = logging.getLogger("reasoning.llm")


class FragmentedReasoningLLM:
    """Handles structured, multi-stage reasoning queries with optional API integration."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.provider = (provider or os.environ.get("LLM_PROVIDER", "mock")).lower()
        self.api_key = (
            api_key
            or os.environ.get("LLM_API_KEY")
            or os.environ.get(f"{self.provider.upper()}_API_KEY", "")
            or os.environ.get("GROQ_API_KEY", "")
        )
        self.model = model or os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")

    def generate_intent(
        self,
        user_prompt: str,
        eth_price: float,
        gas_gwei: float,
        rag_match: RAGMatch,
        trade_amount_usd: float = 200.0,
    ) -> ActionIntent:
        """Chunk 1: Derive action intent, strategic thesis, and profitability outlook from RAG."""
        system_prompt = (
            "You are an autonomous algorithmic financial agent. "
            "Given a concise RAG historical context and live market prices, formulate a structured "
            "trade action intent and evaluate profitability. Output strictly valid JSON."
        )

        user_content = (
            f"GOAL: {user_prompt}\n"
            f"CURRENT MARKET: ETH = ${eth_price:,.2f}, Gas = {gas_gwei:.1f} gwei\n"
            f"RETRIEVED HISTORICAL REGIME:\n"
            f"- Matched Regime: {rag_match.regime_name} (Similarity: {rag_match.similarity_score * 100:.1f}%)\n"
            f"- Historical Win-Rate: {rag_match.historical_win_rate * 100:.1f}%\n"
            f"- Expected 24h Return: {rag_match.expected_return_24h_pct:+.1f}%\n"
            f"- Recommendation: {rag_match.strategy_recommendation}\n"
            f"- Context: {rag_match.context_summary}\n\n"
            f"TASK: Propose a trade intent of ${trade_amount_usd:.2f} USDC for ETH if favorable."
        )

        # If live external API is configured, invoke it; otherwise use native cognitive synthesis
        is_profitable = rag_match.expected_return_24h_pct > 0 and rag_match.historical_win_rate >= 0.55
        confidence = min(0.95, round(rag_match.similarity_score * rag_match.historical_win_rate + 0.1, 2))

        if is_profitable:
            profitability_outlook = (
                f"Favorable: Historical regime '{rag_match.regime_name}' demonstrates {rag_match.historical_win_rate * 100:.0f}% win-rate "
                f"with {rag_match.expected_return_24h_pct:+.1f}% expected 24h return. Low gas ({gas_gwei:.1f} gwei) minimizes overhead."
            )
            thesis = (
                f"Accumulate ETH: Gas at {gas_gwei:.1f} gwei satisfies entry trigger. "
                f"RAG pattern matches historical {rag_match.strategy_recommendation} regime."
            )
        else:
            profitability_outlook = (
                f"Cautionary/Unfavorable: Historical regime shows negative expected return ({rag_match.expected_return_24h_pct:+.1f}%) "
                f"or low win-rate ({rag_match.historical_win_rate * 100:.0f}%)."
            )
            thesis = (
                f"Cautious proposal: Market conditions resemble '{rag_match.regime_name}'. "
                f"RAG recommendation: {rag_match.strategy_recommendation}."
            )

        # If Groq live API is configured and key is present, invoke it for live model synthesis
        if self.provider == "groq" and self.api_key:
            try:
                import urllib.request
                url = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"{system_prompt}\nReturn JSON with keys: "
                                f"'intent_type' (str), 'target_token' (str), 'amount_usd' (float), "
                                f"'thesis' (str), 'profitability_outlook' (str), 'confidence_score' (float 0.0-1.0)."
                            ),
                        },
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                res_json = json.loads(data["choices"][0]["message"]["content"])
                return ActionIntent(
                    intent_type=str(res_json.get("intent_type", "SWAP")),
                    target_token=str(res_json.get("target_token", "ETH")),
                    amount_usd=float(res_json.get("amount_usd", trade_amount_usd)),
                    thesis=str(res_json.get("thesis", thesis)),
                    profitability_outlook=str(res_json.get("profitability_outlook", profitability_outlook)),
                    confidence_score=float(res_json.get("confidence_score", confidence)),
                )
            except Exception as e:
                logger.warning(f"Groq API call failed or timed out: {e}. Using deterministic synthesis.")

        return ActionIntent(
            intent_type="SWAP",
            target_token="ETH",
            amount_usd=float(trade_amount_usd),
            thesis=thesis,
            profitability_outlook=profitability_outlook,
            confidence_score=confidence,
        )

    def evaluate_risk_chunk(
        self,
        intent: ActionIntent,
        dry_run: DryRunResult,
        rag_match: RAGMatch,
    ) -> Dict[str, Any]:
        """Chunk 2: Evaluate simulation numbers and decide clearance to formal policy gates."""
        system_prompt = (
            "You are a risk management evaluator for an autonomous wallet agent. "
            "Review the simulated trade outcome and historical drawdown risk. "
            "Output strictly valid JSON with risk assessment and clearance decision."
        )

        user_content = (
            f"PROPOSED ACTION: {intent.intent_type} ${intent.amount_usd:.2f} USDC -> {intent.target_token}\n"
            f"SIMULATED OUTCOME:\n"
            f"- Estimated Received: +{dry_run.estimated_eth_received:.5f} ETH\n"
            f"- Post-Trade USDC: ${dry_run.post_swap_usdc:,.2f}\n"
            f"- Expected 24h Delta: ${dry_run.expected_24h_value_delta_usd:+.2f}\n"
            f"- Max Historical Drawdown: -${dry_run.max_drawdown_risk_usd:.2f}\n"
            f"- Historical Risk Score: {dry_run.risk_score} / 10 ({dry_run.risk_level})\n\n"
            f"TASK: Determine whether risk is within acceptable parameters to proceed to formal Z3 policy gates."
        )

        # If Groq live API is configured and key is present, invoke it for live risk clearance
        if self.provider == "groq" and self.api_key:
            try:
                import urllib.request
                url = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"{system_prompt}\nReturn JSON with keys: 'decision' ('PROCEED_TO_GATES' or 'ABORT_HIGH_RISK'), "
                                f"'risk_level' ('LOW', 'MEDIUM', 'HIGH'), 'risk_score' (float 0-10), 'reasoning' (str)."
                            ),
                        },
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                res_json = json.loads(data["choices"][0]["message"]["content"])
                return {
                    "decision": str(res_json.get("decision", "PROCEED_TO_GATES" if dry_run.decision != "ABORT_HIGH_RISK" else "ABORT_HIGH_RISK")),
                    "risk_level": str(res_json.get("risk_level", dry_run.risk_level)),
                    "risk_score": float(res_json.get("risk_score", dry_run.risk_score)),
                    "reasoning": str(res_json.get("reasoning", "Live Groq model risk clearance evaluation.")),
                }
            except Exception as e:
                logger.warning(f"Groq API risk evaluation failed: {e}. Using deterministic evaluation.")

        # Clear, auditable assessment
        if dry_run.decision == "ABORT_HIGH_RISK":
            return {
                "decision": "ABORT_HIGH_RISK",
                "risk_level": "HIGH",
                "risk_score": dry_run.risk_score,
                "reasoning": f"Risk evaluation rejected trade: High risk score ({dry_run.risk_score}/10) exceeds threshold. {dry_run.simulation_notes}",
            }
        else:
            return {
                "decision": "PROCEED_TO_GATES",
                "risk_level": dry_run.risk_level,
                "risk_score": dry_run.risk_score,
                "reasoning": (
                    f"Risk clearance granted: Risk level is {dry_run.risk_level} (Score {dry_run.risk_score}/10). "
                    f"Expected 24h return is positive (${dry_run.expected_24h_value_delta_usd:+.2f}) with controlled drawdown (-${dry_run.max_drawdown_risk_usd:.2f}). "
                    f"Proceeding to formal Z3 invariant gate."
                ),
            }


reasoning_llm = FragmentedReasoningLLM()
