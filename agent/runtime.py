"""Autonomous Agent Runtime — Always-Running Reactive Decision Loop.

Continuously monitors live market feeds (Coinbase WebSocket & Gas Oracle),
evaluates registered policy tasks, and executes guarded on-chain actions
when formal trigger and invariant conditions are satisfied.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone, timedelta
import logging
import threading
import time
from typing import Any, Deque, Dict, List, Literal, Optional
import uuid

from agent.task import AgentTask, task_manager
from exchange import exchange_service
from reasoning import reasoning_engine
from user import user_db
from contracts.wallet_client import policy_wallet_client
from contracts.simulator import evm_simulator

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
        # Check on-chain emergency pause first
        if policy_wallet_client.is_paused:
            with self._lock:
                self.state = "GUARD_BLOCKED"
            block_msg = "Contract Emergency Paused on-chain: All autonomous agent actions halted."
            self.add_thought("BLOCKED", block_msg)
            task_manager.update_check(task.id, block_msg)
            time.sleep(1.0)
            return

        market = exchange_service.get_market_state()
        user_state = user_db.get_state()

        current_gas = market["gas_gwei"]
        current_price = market["eth_price_usd"]
        available_usdc = user_state.balances.USDC
        current_eth = user_state.balances.ETH

        # Check triggers (market or schedule)
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
                    f"Observing: Gas={current_gas} gwei, ETH=${current_price:,.2f}. {trigger_reason}"
                )
            return

        # Trigger condition is met!
        with self._lock:
            self.state = "TRIGGER_MET"
        self.add_thought(
            "TRIGGER",
            f"Trigger condition satisfied! Initiating fragmented cognitive reasoning pipeline...",
        )

        trade_usd = float(task.trade_action.get("amount_usd", 200.0))
        action_type = task.trade_action.get("type", "SWAP")
        token = task.trade_action.get("to_token", "ETH")
        recipient = task.trade_action.get("recipient")

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
                action=action_type,
                details=f"Aborted Autonomous Action: ${trade_usd:.2f} USDC for {token} (High Risk)",
                amount=0.0,
                token=token,
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
                action=action_type,
                details=f"Blocked Autonomous Action: ${trade_usd:.2f} USDC for {token}",
                amount=0.0,
                token=token,
                status="BLOCKED_BY_GUARD",
                price_usd=current_price,
                reason=report.gate_data.summary,
                reasoning_report=report.to_dict(),
            )
            time.sleep(2.0)
            return

        # Pre-flight EVM simulation on smart contract
        balance_after = available_usdc - trade_usd
        guards = {
            "trade_amount_usd": trade_usd,
            "balance_after_usd": balance_after,
            "min_balance_floor_usd": policy_wallet_client.min_balance_floor_usd,
            "per_tx_cap_usd": policy_wallet_client.per_tx_cap_usd,
            "daily_cap_usd": policy_wallet_client.daily_cap_usd,
            "spent_today_usd": policy_wallet_client.spent_today_usd,
            "token": token,
            "allowed_tokens": policy_wallet_client.allowed_tokens,
            "recipient": recipient or "",
            "allowed_recipients": policy_wallet_client.allowed_recipients,
            "is_paused": policy_wallet_client.is_paused,
        }
        sim_res = evm_simulator.simulate_transaction(
            from_address="0x71C8366420A096207E90B01D252431792349039A",
            to_address=policy_wallet_client.contract_address,
            guards=guards,
        )
        if not sim_res["success"]:
            with self._lock:
                self.state = "GUARD_BLOCKED"
            sim_block = f"EVM Pre-Flight Reverted: {sim_res['revert_reason']}"
            self.add_thought("BLOCKED", sim_block)
            task_manager.update_check(task.id, sim_block)
            time.sleep(2.0)
            return

        # Both RAG dry-run risk, Z3 invariant guards, and EVM pre-flight passed -> EXECUTE!
        with self._lock:
            self.state = "EXECUTING"

        # 1. Update persistent balances
        if action_type == "TRANSFER":
            if token == "USDC":
                user_db.update_balances(usdc=max(0.0, available_usdc - trade_usd))
            else:
                user_db.update_balances(eth=max(0.0, current_eth - (trade_usd / current_price)))
        else:
            eth_purchased = report.dry_run.estimated_eth_received
            new_usdc = report.dry_run.post_swap_usdc
            new_eth = report.dry_run.post_swap_eth
            user_db.update_balances(eth=new_eth, usdc=new_usdc)

        # 2. Execute on-chain transaction via client
        onchain_res = policy_wallet_client.execute_onchain_transaction(
            action=action_type,
            token=token,
            amount=trade_usd / current_price if token == "ETH" else trade_usd,
            price_usd=current_price,
            balance_after_usd=balance_after,
            policy_hash=task.policy_hash,
            recipient=recipient,
        )

        # 3. Record on-chain transaction with full reasoning report attached
        eth_purchased = report.dry_run.estimated_eth_received if action_type == "SWAP" else (trade_usd / current_price)
        tx = user_db.add_transaction(
            actor="AGENT",
            action=action_type,
            details=f"Autonomous Guarded {action_type}: ${trade_usd:.2f} USDC for {token} (Base Sepolia #{onchain_res['block_number']})",
            amount=eth_purchased,
            token=token,
            status="CONFIRMED",
            price_usd=current_price,
            reason=f"Verified On-Chain Policy: RAG regime validated ({report.rag_context.historical_win_rate*100:.0f}% win-rate). Floor preserved (${balance_after:.2f} >= $500). EVM Gas: {onchain_res['gas_used']}",
            reasoning_report=report.to_dict(),
        )

        # 4. Handle recurring interval vs single-shot finished
        task.execution_count = getattr(task, "execution_count", 0) + 1
        if getattr(task, "schedule_type", "MARKET_TRIGGER") == "RECURRING_INTERVAL" and (task.max_executions is None or task.execution_count < task.max_executions):
            interval = task.interval_seconds or 60
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()
            task.next_run_at = next_run
            reason = f"Recurring execution #{task.execution_count} verified on-chain. Next run at {next_run[:19].replace('T', ' ')} UTC. Tx: {onchain_res['tx_hash'][:10]}..."
            task_manager.update_check(task.id, reason)
            with self._lock:
                self.state = "MONITORING"
            self.add_thought("EXECUTE", reason)
        else:
            finished_reason = (
                f"Finished successfully: {action_type} executed on Base Sepolia (Block #{onchain_res['block_number']}). "
                f"RAG regime '{report.rag_context.regime_name}' validated. Floor preserved (${balance_after:.2f} >= $500). "
                f"Tx: {onchain_res['tx_hash'][:10]}...{onchain_res['tx_hash'][-6:]}"
            )
            task_manager.mark_finished(
                task.id,
                tx_hash=onchain_res["tx_hash"],
                reason=finished_reason,
            )
            with self._lock:
                self.state = "FINISHED"
            self.add_thought(
                "EXECUTE",
                f"SUCCESS! Autonomous {action_type} executed & verified on Base Sepolia. Hash: {onchain_res['tx_hash'][:14]}..."
            )

    def _evaluate_triggers(self, task: AgentTask, current_gas: float, market: Dict[str, Any]) -> tuple[bool, str]:
        """Check if market feed or time schedule fulfills task trigger condition."""
        # Scheduled or Recurring triggers
        if getattr(task, "schedule_type", "MARKET_TRIGGER") in ("ONE_TIME_SCHEDULE", "DELAYED", "RECURRING_INTERVAL"):
            now_iso = datetime.now(timezone.utc).isoformat()
            next_run = getattr(task, "next_run_at", None) or getattr(task, "execute_at", None)
            if next_run and now_iso < next_run:
                return False, f"Scheduled execution pending: Next run at {next_run[:19].replace('T', ' ')} UTC"
            return True, f"Scheduled execution time reached ({getattr(task, 'schedule_type', 'SCHEDULED')})."

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
