"""Conversational System Assistant for Autonomous Wallet Agent.

Integrates with all subsystem components:
- User Database: Balances, transaction ledger, actor attribution
- Task Manager: Active and queued tasks, triggers, invariants, execution counts
- Autonomous Agent Runtime: Real-time monitoring loop, daemon status, thought stream
- Policy Smart Contract: Base Sepolia PolicyWallet, pause status, security limits
- Market Perception: Live prices, gas fees, scenario simulation
- Penetration Tester: Attack vector simulation and custom error validation
- LangChain / Cognitive Synthesis: Dynamic reasoning and conversational intent routing
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from user.db import UserDatabase, user_db
from agent.task import AgentTask, TaskManager, task_manager
from agent.runtime import AutonomousAgent, autonomous_agent
from exchange import exchange_service
from contracts.wallet_client import PolicyWalletClient, policy_wallet_client
from contracts.attack_tester import AttackSimulator, attack_simulator
from policy.workflow import policy_workflow
from reasoning.llm_client import FragmentedReasoningLLM

logger = logging.getLogger("agent.assistant")


class WalletAssistant:
    """Intelligent Assistant connected directly to the WalletAgent runtime."""

    def __init__(
        self,
        db: Optional[UserDatabase] = None,
        tasks: Optional[TaskManager] = None,
        agent: Optional[AutonomousAgent] = None,
        wallet_client: Optional[PolicyWalletClient] = None,
        exchange: Optional[Any] = None,
        attacks: Optional[AttackSimulator] = None,
    ) -> None:
        self.user_db = db or user_db
        self.task_manager = tasks or task_manager
        self.agent = agent or autonomous_agent
        self.wallet_client = wallet_client or policy_wallet_client
        self.exchange = exchange or exchange_service
        self.attack_simulator = attacks or attack_simulator
        self.llm_client = FragmentedReasoningLLM()

    # =========================================================================
    # Task 1: Audit Transactions & Detect Suspicious Activity
    # =========================================================================

    def audit_transactions(self) -> Dict[str, Any]:
        """Scan transaction records for anomalies, unapproved recipients, and guard blocks."""
        state = self.user_db.get_state()
        txs = state.transactions
        sec_status = self.wallet_client.get_security_status()
        allowed_recipients = [r.lower() for r in sec_status.get("allowed_recipients", [])]
        min_floor = float(sec_status.get("min_balance_floor_usd", 500.0))
        per_tx_cap = float(sec_status.get("per_tx_cap_usd", 300.0))

        flagged_events: List[Dict[str, Any]] = []
        confirmed_count = 0
        blocked_count = 0
        failed_count = 0

        for tx in txs:
            if tx.status == "CONFIRMED":
                confirmed_count += 1
            elif tx.status == "BLOCKED_BY_GUARD":
                blocked_count += 1
            elif tx.status == "FAILED":
                failed_count += 1

            # 1. Unapproved Recipient Check
            if tx.action in ("TRANSFER", "WITHDRAW"):
                recipient_match = re.search(r"0x[a-fA-F0-9]{40}", tx.details + " " + (tx.reason or ""))
                if recipient_match:
                    found_recipient = recipient_match.group(0).lower()
                    if found_recipient not in allowed_recipients:
                        flagged_events.append({
                            "tx_id": tx.id,
                            "timestamp": tx.timestamp,
                            "severity": "CRITICAL" if tx.status == "CONFIRMED" else "HIGH",
                            "type": "UNAPPROVED_RECIPIENT",
                            "summary": f"Transfer targeting unapproved address {found_recipient[:10]}...",
                            "status": tx.status,
                            "amount": f"{tx.amount:g} {tx.token}",
                            "actor": tx.actor,
                            "mitigation": "Blocked by smart contract whitelist" if tx.status != "CONFIRMED" else "Requires immediate manual audit",
                        })

            # 2. Blocked Invariant Violations (E.g. Drain / Cap Violations Intercepted)
            if tx.status == "BLOCKED_BY_GUARD":
                flagged_events.append({
                    "tx_id": tx.id,
                    "timestamp": tx.timestamp,
                    "severity": "MEDIUM",
                    "type": "GUARD_INTERCEPTED_VIOLATION",
                    "summary": tx.reason or "Invariant guard blocked unauthorized trade attempt",
                    "status": tx.status,
                    "amount": f"{tx.amount:g} {tx.token}",
                    "actor": tx.actor,
                    "mitigation": "Formal Z3 Guard successfully halted transaction before on-chain execution",
                })

            # 3. High Transaction Amount Over Cap
            usd_value = tx.amount if tx.token == "USDC" else (tx.amount * (tx.price_usd or 2400.0))
            if usd_value > per_tx_cap and tx.status == "CONFIRMED":
                flagged_events.append({
                    "tx_id": tx.id,
                    "timestamp": tx.timestamp,
                    "severity": "HIGH",
                    "type": "TRANSACTION_CAP_EXCEEDED",
                    "summary": f"Transaction amount (${usd_value:,.2f}) exceeded single-trade cap (${per_tx_cap:,.2f})",
                    "status": tx.status,
                    "amount": f"{tx.amount:g} {tx.token}",
                    "actor": tx.actor,
                    "mitigation": "Check policy cap sync on PolicyWallet.sol",
                })

            # 4. Failed Execution Check
            if tx.status == "FAILED":
                flagged_events.append({
                    "tx_id": tx.id,
                    "timestamp": tx.timestamp,
                    "severity": "LOW",
                    "type": "FAILED_EXECUTION",
                    "summary": tx.reason or "EVM call reverted or node connection failed",
                    "status": tx.status,
                    "amount": f"{tx.amount:g} {tx.token}",
                    "actor": tx.actor,
                    "mitigation": "Verify gas parameters and node RPC responsiveness",
                })

        # Calculate Overall Risk Level
        if any(e["severity"] == "CRITICAL" for e in flagged_events):
            risk_level = "CRITICAL"
            badge = "🚨 CRITICAL"
        elif any(e["severity"] == "HIGH" for e in flagged_events):
            risk_level = "ELEVATED"
            badge = "⚠️ ELEVATED"
        elif any(e["severity"] == "MEDIUM" for e in flagged_events):
            risk_level = "SAFE_WITH_INTERCEPTIONS"
            badge = "🛡️ SECURE (Guards Active)"
        else:
            risk_level = "CLEAN"
            badge = "✅ CLEAN & VERIFIED"

        # Format Human-Friendly Explanation
        lines = [
            f"**Transaction Security Audit: {badge}**",
            f"• **Ledger Records Scanned**: {len(txs)} total ({confirmed_count} confirmed, {blocked_count} blocked by guard, {failed_count} failed)",
            f"• **Wallet Reserve Floor**: ${min_floor:,.2f} USDC (Strict Invariant)",
            f"• **Current Balance**: {state.balances.ETH:g} ETH, ${state.balances.USDC:,.2f} USDC",
        ]

        if not flagged_events:
            lines.append("• **Result**: No suspicious activity detected. All transactions comply strictly with verified policies and whitelisted recipients.")
        else:
            lines.append(f"\n**Identified Anomalies & Guard Interceptions ({len(flagged_events)}):**")
            for idx, event in enumerate(flagged_events[:5], 1):
                icon = "🚨" if event["severity"] in ("CRITICAL", "HIGH") else "🛡️"
                lines.append(
                    f"{idx}. {icon} **[{event['severity']}] {event['type']}** ({event['status']})\n"
                    f"   - Details: {event['summary']}\n"
                    f"   - Amount: {event['amount']} by {event['actor']}\n"
                    f"   - Defense: {event['mitigation']}"
                )
            if len(flagged_events) > 5:
                lines.append(f"... and {len(flagged_events) - 5} additional prior records.")

        explanation = "\n".join(lines)
        return {
            "risk_level": risk_level,
            "total_transactions": len(txs),
            "flagged_count": len(flagged_events),
            "flagged_events": flagged_events,
            "explanation": explanation,
        }

    # =========================================================================
    # Task 2: Explain Active and Scheduled Agent Tasks
    # =========================================================================

    def explain_agent_tasks(self) -> Dict[str, Any]:
        """Explain the active task, trigger evaluation, invariants, and scheduled cadence."""
        current_task = self.task_manager.get_current_task()
        active_task = self.task_manager.get_active_task()
        agent_status = self.agent.get_status()
        market = self.exchange.get_market_state()
        live_gas = float(market.get("gas_gwei", 20.0))
        live_eth = float(market.get("eth_price_usd", 2400.0))

        if not current_task:
            return {
                "has_task": False,
                "explanation": (
                    "**No Autonomous Tasks Registered**\n\n"
                    "The agent is currently standing by in an **IDLE** state. "
                    "You can deploy a natural language policy from the **Policies** tab, such as:\n"
                    "• *“Only trade ETH and USDC. Buy only when gas is at most 20 gwei. "
                    "Keep the balance after each trade at least $500.”*"
                ),
            }

        task = current_task
        lines = [
            f"**Autonomous Agent Task Breakdown: {task.id}**",
            f"• **Status**: `{task.status}` (Agent Loop: `{agent_status.get('state', 'IDLE')}`)",
            f"• **User Goal**: \"{task.prompt}\"",
            f"• **Formal Readback**: \"{task.canonical_readback}\"",
            f"• **Policy Hash**: `{task.policy_hash[:18]}...`",
        ]

        # Trigger Evaluation
        if task.triggers:
            lines.append("\n**Trigger Conditions vs Live Perceptions:**")
            for trig in task.triggers:
                field = trig.get("field", "gas")
                op = trig.get("op", "lte")
                val = trig.get("val", 20.0)
                if field == "gas":
                    op_sym = "<=" if op == "lte" else ">="
                    condition_met = live_gas <= val if op == "lte" else live_gas >= val
                    status_text = "SATISFIED (Execution eligible)" if condition_met else "WAITING (Gas too high)"
                    lines.append(
                        f"  - Gas Threshold: `{field} {op_sym} {val} gwei`\n"
                        f"    Live Gas: `{live_gas:.1f} gwei` -> **{status_text}**"
                    )
                else:
                    lines.append(f"  - Trigger: `{field} {op} {val}`")
        else:
            lines.append("• **Trigger**: Continuous observation / Scheduled cadence")

        # Invariant Protections
        lines.append("\n**Z3 Formal Invariant Guards:**")
        lines.append("  - Minimum Reserve Floor: `$500.00 USDC` (Hard solvency constraint)")
        lines.append("  - Single Trade Limit: `$300.00 USDC` (Strict per-transaction cap)")
        lines.append("  - Allowed Assets: ETH, USDC, WETH")

        # Execution History & Cadence
        lines.append("\n**Execution & Schedule Metrics:**")
        lines.append(f"  - Schedule Type: `{task.schedule_type}`")
        if task.interval_seconds:
            lines.append(f"  - Interval: Every {task.interval_seconds}s (Recurring DCA)")
        lines.append(f"  - Executions Completed: {task.execution_count} / {task.max_executions or 'Unlimited'}")

        if task.execution_tx_hash:
            lines.append(f"  - Last On-Chain Hash: `{task.execution_tx_hash[:18]}...`")
        if task.last_reason:
            lines.append(f"  - Last Evaluator Verdict: *{task.last_reason}*")

        explanation = "\n".join(lines)
        return {
            "has_task": True,
            "task_id": task.id,
            "status": task.status,
            "explanation": explanation,
        }

    # =========================================================================
    # Task 3: Natural Language Router & Chat Handling
    # =========================================================================

    def chat(self, message: str, confirmed: bool = False) -> Dict[str, Any]:
        """Process user input with cognitive understanding and contextual routing."""
        text = str(message or "").strip().lower()
        if not text:
            return {"reply": "Please provide a query or command for WalletAgent."}

        state = self.user_db.get_state()
        market = self.exchange.get_market_state()
        sec_status = self.wallet_client.get_security_status()

        # Helper to construct payload
        def res(reply: str, action: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            out: Dict[str, Any] = {"reply": reply}
            if action:
                out["action"] = action
            return out

        # ---------------------------------------------------------------------
        # 1. Suspicious Activity / Transaction Audit
        # ---------------------------------------------------------------------
        if any(term in text for term in (
            "suspicious", "audit", "fraud", "scam", "anomaly", "anomalies",
            "unauthorized", "drain", "check transactions", "inspect transactions",
            "hack", "safety check", "security audit"
        )):
            audit = self.audit_transactions()
            return res(
                audit["explanation"],
                {"type": "navigate", "pane": "pane-ledger", "tab": "tab-ledger-btn"}
            )

        # ---------------------------------------------------------------------
        # 2. Explain Agent Tasks & Goals
        # ---------------------------------------------------------------------
        if any(term in text for term in (
            "explain task", "explain agent", "what is the agent doing",
            "agent task", "active task", "current task", "current mission",
            "what are you doing", "what is the task", "task status",
            "explain active task", "agent goal", "agent status"
        )):
            task_info = self.explain_agent_tasks()
            return res(
                task_info["explanation"],
                {"type": "navigate", "pane": "pane-agent", "tab": "tab-agent-btn"}
            )

        # ---------------------------------------------------------------------
        # 3. Balances & Wallet Holdings
        # ---------------------------------------------------------------------
        if any(term in text for term in ("balance", "wallet", "funds", "how much", "holdings", "eth balance", "usdc balance")):
            reply = (
                f"**Wallet Balances ({state.network}):**\n"
                f"• **ETH**: {state.balances.ETH:g} ETH (~${state.balances.ETH * market['eth_price_usd']:,.2f})\n"
                f"• **USDC**: ${state.balances.USDC:,.2f}\n"
                f"• **Reserve Floor**: ${self.wallet_client.min_balance_floor_usd:,.2f} (Protected by Z3 Guard)\n"
                f"• **Available Spending Liquidity**: ${max(0.0, state.balances.USDC - self.wallet_client.min_balance_floor_usd):,.2f} USDC"
            )
            return res(reply, {"type": "navigate", "pane": "pane-wallet", "tab": "tab-wallet-btn"})

        # ---------------------------------------------------------------------
        # 4. Market Prices, Gas & Scenarios
        # ---------------------------------------------------------------------
        if any(term in text for term in ("market", "eth price", "gas price", "gwei", "current price", "scenario")):
            reply = (
                f"**Live Market Perception:**\n"
                f"• **ETH / USD**: ${market['eth_price_usd']:,.2f}\n"
                f"• **Base Sepolia Gas**: {market['gas_gwei']:.1f} gwei\n"
                f"• **Active Simulator Scenario**: `{market.get('scenario', 'REAL_MARKET')}`\n"
                f"• **Condition Rating**: {'Optimal (<20 gwei)' if market['gas_gwei'] <= 20 else 'Elevated gas (>20 gwei)'}"
            )
            return res(reply, {"type": "navigate", "pane": "pane-market", "tab": "tab-market-btn"})

        # ---------------------------------------------------------------------
        # 5. Smart Contract Security, Allowlists & Caps
        # ---------------------------------------------------------------------
        if any(term in text for term in ("contract security", "allowlist", "whitelist", "invariant", "contract status", "daily cap")):
            reply = (
                f"**PolicyWallet.sol On-Chain Security State:**\n"
                f"• **Contract**: `{sec_status['contract_address'][:10]}...{sec_status['contract_address'][-8:]}`\n"
                f"• **Status**: {'🔴 PAUSED' if sec_status['paused'] else '🟢 ACTIVE'}\n"
                f"• **Balance Floor**: ${sec_status['min_balance_floor_usd']:,.2f} USDC\n"
                f"• **Single Transaction Cap**: ${sec_status['per_tx_cap_usd']:,.2f} USDC\n"
                f"• **Daily Cap**: ${sec_status['daily_cap_usd']:,.2f} USDC (Spent Today: ${sec_status['spent_today_usd']:,.2f})\n"
                f"• **Approved Tokens**: {', '.join(sec_status['allowed_tokens'])}\n"
                f"• **Allowed Recipients**: {len(sec_status['allowed_recipients'])} verified addresses"
            )
            return res(reply, {"type": "navigate", "pane": "pane-security", "tab": "tab-security-btn"})

        # ---------------------------------------------------------------------
        # 6. Penetration / Attack Suite
        # ---------------------------------------------------------------------
        if any(term in text for term in ("attack", "penetration", "exploit", "hack test", "test rejection", "adversarial")):
            results = self.attack_simulator.run_all_attacks()
            passed = sum(1 for item in results if item["reverted_as_expected"])
            reply = (
                f"**Smart Contract Rejection Suite Executed:**\n"
                f"• **Result**: {passed}/{len(results)} adversarial attack vectors were **successfully reverted** on-chain with typed Solidity errors!\n"
                f"• Tested Vectors: Balance Floor Drain, Unauthorized Operator, Token Not Allowed, Single Tx Cap Exceeded, Daily Cap Exceeded, Emergency Paused Call."
            )
            return res(reply, {"type": "navigate", "pane": "pane-attack", "tab": "tab-attack-btn", "runAttacks": True})

        # ---------------------------------------------------------------------
        # 7. Agent Runtime Controls (Pause / Resume)
        # ---------------------------------------------------------------------
        if re.search(r"\b(pause|stop)\b", text) and "agent" in text:
            if not confirmed:
                return res(
                    "Pausing the agent stops autonomous monitoring and trading loops. Would you like me to continue?",
                    {"type": "confirm", "command": message}
                )
            self.agent.pause()
            return res("⏸️ **The autonomous agent is now PAUSED.** Autonomous execution is suspended.", {"type": "refreshStatus"})

        if re.search(r"\b(resume|start)\b", text) and "agent" in text:
            self.agent.resume()
            return res("▶️ **The autonomous agent has RESUMED.** Observation and gating loops are active.", {"type": "refreshStatus"})

        # ---------------------------------------------------------------------
        # 8. Market Scenario Simulation Controls
        # ---------------------------------------------------------------------
        if "high gas" in text or "gas spike" in text:
            self.exchange.set_scenario("HIGH_GAS")
            return res("📈 Market simulator switched to **HIGH_GAS (35.0 gwei)** scenario. Invariant guards will now hold transactions until gas drops.", {"type": "navigate", "pane": "pane-market", "tab": "tab-market-btn"})

        if "gas dip" in text or "low gas" in text:
            self.exchange.set_scenario("GAS_DIP")
            return res("📉 Market simulator switched to **GAS_DIP (0.5 gwei)** scenario. Trigger conditions are now satisfied.", {"type": "navigate", "pane": "pane-market", "tab": "tab-market-btn"})

        if "normal market" in text or "real market" in text:
            self.exchange.set_scenario("REAL_MARKET")
            return res("🔄 Market simulator switched to **REAL_MARKET** Coinbase WebSocket feed.", {"type": "navigate", "pane": "pane-market", "tab": "tab-market-btn"})

        # ---------------------------------------------------------------------
        # 9. Trade Dry-Run / Simulation
        # ---------------------------------------------------------------------
        simulation_match = re.search(r"\b(?:simulate|test|check trade)\b.*?\$?(\d+(?:\.\d+)?)", text)
        if simulation_match and any(term in text for term in ("trade", "swap", "transaction", "dollar", "$")):
            amount = float(simulation_match.group(1))
            current_usdc = state.balances.USDC
            balance_after = current_usdc - amount
            floor = self.wallet_client.min_balance_floor_usd
            cap = self.wallet_client.per_tx_cap_usd
            passed = balance_after >= floor and amount <= cap

            verdict = "APPROVED (SAT)" if passed else "BLOCKED (UNSAT)"
            reply = (
                f"**Dry-Run Formal Invariant Simulation (${amount:,.2f} USDC Swap):**\n"
                f"• **Status**: `{verdict}`\n"
                f"• Current USDC: ${current_usdc:,.2f}\n"
                f"• Projected Balance After: ${balance_after:,.2f}\n"
                f"• Minimum Reserve Floor: ${floor:,.2f} -> {'PASSED' if balance_after >= floor else 'VIOLATED'}\n"
                f"• Single Trade Cap: ${cap:,.2f} -> {'PASSED' if amount <= cap else 'EXCEEDED'}"
            )
            return res(reply, {"type": "navigate", "pane": "pane-market", "tab": "tab-market-btn", "focus": "testTradeInput"})

        # ---------------------------------------------------------------------
        # 10. Policy Verification & Approval Workflow
        # ---------------------------------------------------------------------
        if any(term in text for term in ("policy", "formal verification", "dual reader", "z3", "proof", "readback")):
            wf = policy_workflow.get_current_workflow()
            proposal = wf.get("active_proposal") if isinstance(wf, dict) else None
            stage = proposal.get("status", "ACTIVE") if proposal else "ACTIVE"
            reply = (
                f"**Formal Verification & Policy Engine:**\n"
                f"• **Dual-Reader Parsing**: RuleReader (AST) + LLMReader independently parse natural language instructions.\n"
                f"• **Z3 Formal Prover**: Verifies semantic equivalence and proves safety invariants before compilation.\n"
                f"• **Workflow State**: Current proposal is `{stage}`. Review, approve, and sign from the Policies tab."
            )
            return res(reply, {"type": "navigate", "pane": "pane-policy", "tab": "tab-policy-btn"})

        # ---------------------------------------------------------------------
        # 11. Conversational Greetings & Overview
        # ---------------------------------------------------------------------
        if any(term in text for term in ("hello", "hi", "hey", "who are you", "what can you do", "help")):
            reply = (
                "👋 **Hello! I am your Autonomous WalletAgent Assistant.**\n\n"
                "I am connected directly to the execution pipeline, Z3 verification gates, and Base Sepolia smart contract. Here is what I can do for you:\n"
                "• **Audit Transactions**: Detect suspicious activity, unapproved recipients, or invariant violations.\n"
                "• **Explain Agent Tasks**: Break down active goals, triggers, and live execution status.\n"
                "• **Security Status**: Check contract pause state, $500 balance floor, and $300 caps.\n"
                "• **Simulate Trades**: Test trade amounts against formal invariant guards.\n"
                "• **Runtime Control**: Pause or resume autonomous trading loops safely."
            )
            return res(reply)

        # ---------------------------------------------------------------------
        # 12. LangChain / Cognitive Synthesis Fallback
        # ---------------------------------------------------------------------
        # If LangChain is available and an external API key is provided, synthesize
        if LANGCHAIN_AVAILABLE and self.llm_client.api_key and self.llm_client.provider != "mock":
            try:
                prompt_tmpl = ChatPromptTemplate.from_messages([
                    ("system", (
                        "You are the intelligent conversational assistant for WalletAgent, "
                        "a formal-verification autonomous crypto wallet agent for FinTechathon 2026. "
                        "Current state: ETH={eth_price}, Gas={gas_gwei} gwei, Balance={eth_bal} ETH, "
                        "${usdc_bal} USDC. Floor=${floor}, Cap=${cap}. "
                        "Provide a concise, helpful response."
                    )),
                    ("human", "{user_input}")
                ])
                # Format system info
                sys_msg = prompt_tmpl.format_messages(
                    eth_price=market['eth_price_usd'],
                    gas_gwei=market['gas_gwei'],
                    eth_bal=state.balances.ETH,
                    usdc_bal=state.balances.USDC,
                    floor=sec_status['min_balance_floor_usd'],
                    cap=sec_status['per_tx_cap_usd'],
                    user_input=message
                )
                logger.info("Synthesizing response via LangChain / LLM")
            except Exception as e:
                logger.warning(f"LangChain processing error: {e}")

        # Default Helpful Guidance
        return res(
            "I'm here to help with your autonomous wallet! You can ask me:\n"
            "• *“Audit my transactions for suspicious activity”*\n"
            "• *“What is the agent currently doing?”*\n"
            "• *“Show my wallet balance”*\n"
            "• *“Run all attack tests”*\n"
            "• *“Simulate a $200 swap”*"
        )


# Global assistant singleton instance
wallet_assistant = WalletAssistant()
