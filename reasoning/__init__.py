"""Autonomous Agent Cognitive Reasoning Package.

Provides RAG historical retrieval, fragmented LLM intent formulation,
dry-run risk simulation, and formal Z3 policy gate verification.
"""
from reasoning.dry_run import RiskSimulator, risk_simulator
from reasoning.engine import ReasoningEngine, reasoning_engine
from reasoning.llm_client import FragmentedReasoningLLM, reasoning_llm
from reasoning.models import (
    ActionIntent,
    DryRunResult,
    GateResult,
    HistoricalRegime,
    RAGMatch,
    ReasoningReport,
)
from reasoning.rag import RAGRetriever, rag_retriever

__all__ = [
    "ReasoningEngine",
    "reasoning_engine",
    "RAGRetriever",
    "rag_retriever",
    "RiskSimulator",
    "risk_simulator",
    "FragmentedReasoningLLM",
    "reasoning_llm",
    "HistoricalRegime",
    "RAGMatch",
    "ActionIntent",
    "DryRunResult",
    "GateResult",
    "ReasoningReport",
]
