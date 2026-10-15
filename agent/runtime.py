"""Autonomous Agent Runtime — Always-Running Reactive Decision Loop.

Continuously monitors live market feeds (Coinbase WebSocket & Gas Oracle),
evaluates registered policy tasks, and executes guarded on-chain actions
when formal trigger and invariant conditions are satisfied.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Deque, Dict, List, Literal, Optional
import uuid

from agent.task import AgentTask, task_manager
from exchange import exchange_service
from reasoning import reasoning_engine
from user import user_db

logger = logging.getLogger("agent.runtime")

AgentState = Literal["IDLE", "MONITORING", "TRIGGER_MET", "GUARD_BLOCKED", "EXECUTING", "PAUSED", "ERROR"]


class AutonomousAgent:
    """Daemon worker running continuously in the background to execute autonomous tasks."""

    def __init__(self, check_interval_sec: float = 1.0) -> None:
        self.check_interval_sec = check_interval_sec
        self.state: AgentState = "IDLE"
        self._running = False
        self._paused = False
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self.thought_logs: Deque[Dict[str, Any]] = deque(maxlen=150)
        self.last_heartbeat = time.time()
        self._last_logged_gas: Optional[float] = None
        self._last_logged_price: Optional[float] = None

        # Add initial welcome thought
        self.add_thought("INFO", "Autonomous Wallet Agent initialized and listening for policy tasks.")

    def add_thought(self, log_type: str, message: str) -> None:
        """Append a structured thought to the agent's real-time reasoning trace."""
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "type": log_type.upper(),
            "message": message,
        }
        with self._lock:
            self.thought_logs.appendleft(entry)
        logger.info(f"[{entry['type']}] {message}")

    def start(self) -> None:
        """Start the autonomous agent daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AutonomousAgentDaemon")
            self._thread.start()
            self.add_thought("INFO", "Agent daemon thread started. Continuous observation loop active.")

    def pause(self) -> None:
        with self._lock:
            self._paused = True
            self.state = "PAUSED"
            self.add_thought("WARN", "Agent paused by user. Active task monitoring suspended.")

    def resume(self) -> None:
        with self._lock:
            self._paused = False
            self.state = "MONITORING" if task_manager.get_active_task() else "IDLE"
            self.add_thought("INFO", "Agent resumed by user. Re-evaluating active tasks.")

    def reset(self) -> None:
        """Reset agent state, clear all registered tasks, and reset thought stream."""
        with self._lock:
            task_manager.clear_all()
            self.state = "IDLE"
            self._paused = False
            self.thought_logs.clear()
            self.add_thought("INFO", "Simulation reset by user. All tasks cleared. Agent standing by.")

    def _run_loop(self) -> None:
        """Continuous execution loop running forever."""
        while self._running:
            try:
                if not self._paused:
                    self.step()
            except Exception as e:
                logger.error(f"Error in agent step: {e}", exc_info=True)
                self.add_thought("ERROR", f"Agent execution exception: {str(e)}")
            time.sleep(self.check_interval_sec)

    def step(self) -> None:
        """Single decision cycle: observe feeds -> evaluate active task -> gate -> act."""
        task = task_manager.get_active_task()
        current_task = task_manager.get_current_task()

        if not task or task.status != "RUNNING":
            if current_task and current_task.status == "FINISHED":
                with self._lock:
                    self.state = "FINISHED"
            elif current_task and current_task.status == "STOPPED":
                with self._lock:
                    self.state = "STOPPED"
            else:
                if self.state != "IDLE":
                    with self._lock:
                        self.state = "IDLE"
                    self.add_thought("IDLE", "No active tasks registered. Standing by for policy deployment.")
            return

        # Task is RUNNING -> state is MONITORING
        market = exchange_service.get_market_state()
        user_state = user_db.get_state()

        current_gas = market["gas_gwei"]
        current_price = market["eth_price_usd"]
        available_usdc = user_state.balances.USDC
        current_eth = user_state.balances.ETH

        # Check triggers
        trigger_passed, trigger_reason = self._evaluate_triggers(task, current_gas, market)

        if not trigger_passed:
            with self._lock:
                self.state = "MONITORING"
            task_manager.update_check(task.id, trigger_reason)

            # Log periodically if price or gas changed significantly
            now = time.time()
            if now - self.last_heartbeat > 5.0 or (self._last_logged_gas and abs(current_gas - self._last_logged_gas) >= 1.0):
                self.last_heartbeat = now
                self._last_logged_gas = current_gas
                self.add_thought(
                    "MONITOR",
                    f"Observing Market: Gas={current_gas} gwei, ETH=${current_price:,.2f}. {trigger_reason}"
                )
            return

        # Trigger condition is met!
        with self._lock:
            self.state = "TRIGGER_MET"
        self.add_thought(
            "TRIGGER",
            f"Trigger condition satisfied! Gas is {current_gas:.1f} gwei. Initiating fragmented cognitive reasoning pipeline...",
        )

        trade_usd = float(task.trade_action.get("amount_usd", 200.0))

        # Run cognitive pipeline: RAG -> Intent -> Dry Run -> Z3 Gate
        report = reasoning_engine.execute_reasoning_pipeline(
            prompt=task.prompt,
            current_usdc=available_usdc,
            current_eth=current_eth,
            eth_price=current_price,
            gas_gwei=current_gas,
            scenario=market.get("scenario", "REAL_MARKET"),
            trade_amount_usd=trade_usd,
            triggers=task.triggers,
            invariants=task.invariants,
            on_thought=lambda ltype, msg: self.add_thought(ltype, msg),
        )

        # Handle Dry-run Risk Abort
        if report.final_decision == "ABORTED_BY_RISK":
            with self._lock:
                self.state = "MONITORING"
            abort_reason = f"Action aborted: {report.dry_run.simulation_notes}"
            task_manager.update_check(task.id, abort_reason)
            user_db.add_transaction(
                actor="AGENT",
                action="SWAP",
                details=f"Aborted Autonomous Swap: ${trade_usd:.2f} USDC for ETH (High Risk)",
                amount=0.0,
                token="ETH",
                status="BLOCKED_BY_GUARD",
                price_usd=current_price,
                reason=report.dry_run.simulation_notes,
                reasoning_report=report.to_dict(),
            )
            time.sleep(2.0)
            return

        # Handle Formal Z3 Guard Block
        if report.final_decision == "BLOCKED_BY_GUARD":
            with self._lock:
                self.state = "GUARD_BLOCKED"
            block_reason = f"Guard Invariant Blocked: {report.gate_data.summary}"
            self.add_thought("BLOCKED", block_reason)
            task_manager.update_check(task.id, block_reason)
            user_db.add_transaction(
                actor="AGENT",
                action="SWAP",
                details=f"Blocked Autonomous Swap: ${trade_usd:.2f} USDC for ETH",
                amount=0.0,
                token="ETH",
                status="BLOCKED_BY_GUARD",
                price_usd=current_price,
                reason=report.gate_data.summary,
                reasoning_report=report.to_dict(),
            )
            time.sleep(2.0)
            return

        # Both RAG dry-run risk and Z3 invariant guards passed -> EXECUTE!
        with self._lock:
            self.state = "EXECUTING"

        eth_purchased = report.dry_run.estimated_eth_received
        new_usdc = report.dry_run.post_swap_usdc
        new_eth = report.dry_run.post_swap_eth

        # 1. Update persistent balances
        user_db.update_balances(eth=new_eth, usdc=new_usdc)

        # 2. Record on-chain transaction with full reasoning report attached
        tx = user_db.add_transaction(
            actor="AGENT",
            action="SWAP",
            details=f"Autonomous Guarded Swap: Sold ${trade_usd:.2f} USDC for +{eth_purchased:.5f} ETH @ ${current_price:,.2f}",
            amount=eth_purchased,
            token="ETH",
            status="CONFIRMED",
            price_usd=current_price,
            reason=f"RAG '{report.rag_context.regime_name}' favorable ({report.rag_context.historical_win_rate*100:.0f}% win-rate). Floor preserved (${new_usdc:.2f} >= $500).",
            reasoning_report=report.to_dict(),
        )

        # 3. Mark task as FINISHED with comprehensive reason
        finished_reason = (
            f"Finished successfully: Gas dropped to {current_gas:.1f} gwei (trigger <= 20 gwei passed). "
            f"RAG regime '{report.rag_context.regime_name}' validated (Risk: {report.dry_run.risk_level} {report.dry_run.risk_score}/10). "
            f"Floor preserved (${new_usdc:.2f} >= $500). "
            f"Swapped ${trade_usd:.2f} USDC for +{eth_purchased:.5f} ETH @ ${current_price:,.2f} on Base Sepolia. "
            f"Tx: {tx.tx_hash[:10]}...{tx.tx_hash[-6:]}"
        )
        task_manager.mark_finished(
            task.id,
            tx_hash=tx.tx_hash,
            reason=finished_reason,
        )

        with self._lock:
            self.state = "FINISHED"

        self.add_thought(
            "EXECUTE",
            f"SUCCESS! Autonomous swap executed: {eth_purchased} ETH bought for ${trade_usd:.2f} USDC on Base Sepolia. Hash: {tx.tx_hash[:14]}..."
        )

    def _evaluate_triggers(self, task: AgentTask, current_gas: float, market: Dict[str, Any]) -> tuple[bool, str]:
        """Check if market feed fulfills task trigger condition."""
        if not task.triggers:
            return False, "Active Invariant Guard: Monitoring wallet solvency. No trigger registered to initiate buy/swap."

        for trig in task.triggers:
            val = trig.get("val") or trig.get("value") or 20.0
            if trig.get("field") == "gas" or "gas" in str(trig):
                limit = float(val)
                if current_gas <= limit:
                    return True, f"Gas ({current_gas} gwei) is within target threshold (<= {limit} gwei)."
                else:
                    return False, f"Current gas ({current_gas} gwei) > target ({limit} gwei). Waiting for dip."

        return True, "Trigger conditions satisfied."

    def _evaluate_invariants(self, task: AgentTask, current_usdc: float, trade_usd: float) -> tuple[bool, str]:
        """Check if proposed trade preserves verified balance floor invariants."""
        balance_after = current_usdc - trade_usd

        for inv in task.invariants:
            floor = float(inv.get("val") or inv.get("value") or 500.0)
            if balance_after < floor:
                return False, f"Balance after trade (${balance_after:.2f}) falls below required floor (${floor:.2f})"

        return True, f"Balance floor preserved: ${balance_after:.2f} >= $500.00"

    def get_status(self) -> Dict[str, Any]:
        """Fetch current agent status, current task (RUNNING, FINISHED, STOPPED), and recent thoughts."""
        with self._lock:
            current_task = task_manager.get_current_task()
            return {
                "state": self.state,
                "is_running": self._running,
                "is_paused": self._paused,
                "active_task": current_task.to_dict() if current_task else None,
                "current_task": current_task.to_dict() if current_task else None,
                "thought_logs": list(self.thought_logs),
            }


# Global singleton agent
autonomous_agent = AutonomousAgent()
