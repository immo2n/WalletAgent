"""Data models for RAG-driven autonomous reasoning, dry-run simulations, and formal gate reports."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


@dataclass
class HistoricalRegime:
    regime_id: str
    name: str
    description: str
    conditions: Dict[str, Any]
    historical_metrics: Dict[str, Any]
    strategy_recommendation: str
    profitability_assessment: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HistoricalRegime:
        return cls(**data)


@dataclass
class RAGMatch:
    regime_id: str
    regime_name: str
    similarity_score: float
    historical_win_rate: float
    expected_return_24h_pct: float
    risk_level: str
    risk_score: float
    max_drawdown_pct: float
    context_summary: str
    strategy_recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionIntent:
    intent_type: str
    target_token: str
    amount_usd: float
    thesis: str
    profitability_outlook: str
    confidence_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DryRunResult:
    estimated_eth_received: float
    estimated_slippage_pct: float
    post_swap_usdc: float
    post_swap_eth: float
    expected_24h_value_delta_usd: float
    max_drawdown_risk_usd: float
    risk_score: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    decision: Literal["PROCEED_TO_GATES", "ABORT_HIGH_RISK"]
    simulation_notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GateResult:
    solver_status: Literal["SAT", "UNSAT", "UNKNOWN"]
    is_formally_verified: bool
    invariant_checks: List[Dict[str, Any]]
    trigger_checks: List[Dict[str, Any]]
    passed: bool
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReasoningReport:
    report_id: str
    timestamp: str
    prompt: str
    live_market: Dict[str, Any]
    rag_context: RAGMatch
    intent: ActionIntent
    dry_run: DryRunResult
    gate_data: GateResult
    final_decision: Literal["EXECUTED", "BLOCKED_BY_GUARD", "ABORTED_BY_RISK"]
    executive_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "prompt": self.prompt,
            "live_market": self.live_market,
            "rag_context": self.rag_context.to_dict(),
            "intent": self.intent.to_dict(),
            "dry_run": self.dry_run.to_dict(),
            "gate_data": self.gate_data.to_dict(),
            "final_decision": self.final_decision,
            "executive_summary": self.executive_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReasoningReport:
        return cls(
            report_id=data["report_id"],
            timestamp=data["timestamp"],
            prompt=data["prompt"],
            live_market=data["live_market"],
            rag_context=RAGMatch(**data["rag_context"]),
            intent=ActionIntent(**data["intent"]),
            dry_run=DryRunResult(**data["dry_run"]),
            gate_data=GateResult(**data["gate_data"]),
            final_decision=data["final_decision"],
            executive_summary=data["executive_summary"],
        )
