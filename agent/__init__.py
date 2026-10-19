"""Agent package for Autonomous Wallet Agent.

Provides always-running reactive agent runtime, task manager,
and real-time decision loop.
"""
from agent.assistant import WalletAssistant, wallet_assistant
from agent.runtime import AutonomousAgent, autonomous_agent
from agent.task import AgentTask, TaskManager, task_manager

__all__ = [
    "AutonomousAgent",
    "autonomous_agent",
    "AgentTask",
    "TaskManager",
    "task_manager",
    "WalletAssistant",
    "wallet_assistant",
]

