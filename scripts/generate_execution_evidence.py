"""Generate isolated, reproducible sandbox evidence for the Orvilo report.

This script intentionally avoids Flask routes and repository JSON stores. It uses
fresh in-memory workflow/client objects and an offline Web3 stub so that evidence
generation cannot be mistaken for a broadcast blockchain transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.attack_tester import AttackSimulator
from contracts.simulator import EVMSimulator, evm_simulator
from contracts.wallet_client import PolicyWalletClient
from policy.workflow import PolicyWorkflowManager


class OfflineWeb3:
    """Minimal deterministic Web3 substitute: RPC is explicitly unavailable."""

    def is_connected(self) -> bool:
        return False


OUT_DIR = ROOT / "docs" / "evidence" / "execution-report"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record(scenario_id: str, feature: str, preconditions: dict, inputs: dict,
           expected: str, observed: dict, outcome: str, before: dict, after: dict) -> dict:
    return {
        "scenario_id": scenario_id,
        "timestamp_utc": utc_now(),
        "feature": feature,
        "preconditions": preconditions,
        "inputs": inputs,
        "expected_result": expected,
        "observed_result": observed,
        "outcome": outcome,
        "before_state": before,
        "after_state": after,
        "evidence_classification": "LOCAL_SANDBOX_SIMULATION",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_started = utc_now()
    original_w3 = evm_simulator.w3
    evm_simulator.w3 = OfflineWeb3()
    scenarios: list[dict] = []

    try:
        # EE-01: authorized operation accepted by deterministic local guards.
        sim = EVMSimulator(w3=OfflineWeb3())
        guards_ok = {
            "trade_amount_usd": 200.0,
            "balance_after_usd": 1300.0,
            "min_balance_floor_usd": 500.0,
            "per_tx_cap_usd": 500.0,
            "daily_cap_usd": 1000.0,
            "spent_today_usd": 0.0,
            "token": "ETH",
            "allowed_tokens": ["ETH", "WETH", "USDC"],
            "recipient": "0x71C8366420A096207E90B01D252431792349039A",
            "allowed_recipients": ["0x71C8366420A096207E90B01D252431792349039A"],
            "is_paused": False,
        }
        ok = sim.simulate_transaction(
            "0x71C8366420A096207E90B01D252431792349039A",
            "0x89D24A6b4CcB1B6fAA2625fE562bDD9a23260359",
            guards=guards_ok,
        )
        scenarios.append(record(
            "EE-01", "Authorized guarded operation", {"rpc": "offline", "mode": "simulation"},
            guards_ok, "SIMULATED_SUCCESS with no chain mutation", ok,
            "PASSED" if ok.get("status") == "SIMULATED_SUCCESS" else "FAILED",
            {"spent_today_usd": 0.0, "balance_after_usd": 1500.0},
            {"spent_today_usd": 0.0, "projected_balance_after_usd": 1300.0, "chain_mutated": False},
        ))

        # EE-02 and EE-03: explicit guard rejections.
        for scenario_id, feature, changes, expected_error in [
            ("EE-02", "Per-transaction spending limit rejection",
             {"trade_amount_usd": 700.0}, "ExceedsPerTxCap"),
            ("EE-03", "Restricted destination rejection",
             {"recipient": "0x9999999999999999999999999999999999999999"}, "RecipientNotAllowed"),
        ]:
            guards = dict(guards_ok)
            guards.update(changes)
            result = sim.simulate_transaction(
                "0x71C8366420A096207E90B01D252431792349039A",
                "0x89D24A6b4CcB1B6fAA2625fE562bDD9a23260359",
                guards=guards,
            )
            passed = (not result.get("success")) and result.get("custom_error_name") == expected_error
            scenarios.append(record(
                scenario_id, feature, {"rpc": "offline", "mode": "simulation"}, guards,
                f"SIMULATED_REVERT with {expected_error}", result,
                "PASSED" if passed else "FAILED", {"chain_mutated": False}, {"chain_mutated": False},
            ))

        # EE-04: workflow transitions. Signatures and transaction IDs are synthetic.
        workflow = PolicyWorkflowManager()
        proposal = workflow.create_proposal(
            prompt="Buy ETH when gas < 20 gwei. Keep balance at least $500.",
            policy_obj=None,
            canonical_readback="Buy ETH when gas <= 20 gwei; preserve a $500 floor.",
            hash_val="0xabcdef1234567890",
        )
        states = [proposal.status]
        workflow.review_policy(proposal.proposal_id, reviewer="Sandbox Reviewer")
        states.append(proposal.status)
        workflow.approve_policy(proposal.proposal_id, approver="Sandbox Owner")
        states.append(proposal.status)
        workflow.deploy_policy(proposal.proposal_id)
        states.append(proposal.status)
        workflow_obs = {
            "states": states,
            "signature_kind": "synthetic_uuid_string",
            "deployment_identifier_kind": "synthetic_uuid_hash",
            "reported_tx_hash": proposal.onchain_tx_hash,
        }
        scenarios.append(record(
            "EE-04", "Policy review, approval, and activation", {"identity": "unverified sandbox labels"},
            {"proposal_id": proposal.proposal_id}, "DRAFT -> REVIEWED -> DEPLOYABLE -> ACTIVE",
            workflow_obs, "PASSED" if states == ["DRAFT", "REVIEWED", "DEPLOYABLE", "ACTIVE"] else "FAILED",
            {"proposal_status": "DRAFT"}, {"proposal_status": proposal.status, "chain_mutated": False},
        ))

        # EE-05: pause blocks a simulated operation.
        paused = dict(guards_ok)
        paused["is_paused"] = True
        pause_result = sim.simulate_transaction(
            "0x71C8366420A096207E90B01D252431792349039A",
            "0x89D24A6b4CcB1B6fAA2625fE562bDD9a23260359",
            guards=paused,
        )
        scenarios.append(record(
            "EE-05", "Emergency pause rejection", {"mode": "simulation"}, paused,
            "SIMULATED_REVERT with WalletPaused", pause_result,
            "PASSED" if pause_result.get("custom_error_name") == "WalletPaused" else "FAILED",
            {"is_paused": True}, {"is_paused": True, "chain_mutated": False},
        ))

        # EE-06: execute after local operator revocation. This intentionally exposes
        # that the Python client records revocation but does not enforce it locally.
        client = PolicyWalletClient(rpc_url="http://127.0.0.1:1")
        agent = "0x2B5AD5c4795c026514f8317c7a215E218DcCD6cF"
        before = client.get_security_status()
        revoke = client.revoke_operator(agent)
        execution = client.execute_onchain_transaction(
            action="SWAP", token="ETH", amount=0.05, price_usd=2000.0,
            balance_after_usd=1400.0, policy_hash=client.active_policy_hash,
        )
        after = client.get_security_status()
        revocation_obs = {
            "revoke_response": revoke,
            "post_revocation_execution_response": execution,
            "interpretation": "Execution still reported CONFIRMED locally; revocation is not enforced by the Python client.",
        }
        scenarios.append(record(
            "EE-06", "Operation attempted after permission revocation",
            {"mode": "local client simulation", "operator": agent}, {"amount_usd": 100.0},
            "Operation rejected after operator revocation", revocation_obs, "FAILED",
            {"authorized": before["authorized_operators"].get(agent)},
            {"authorized": after["authorized_operators"].get(agent), "chain_mutated": False},
        ))

        # EE-07: execute all modeled attack vectors.
        attacks = AttackSimulator().run_all_attacks()
        scenarios.append(record(
            "EE-07", "Modeled adversarial guard checks", {"mode": "simulation", "vector_count": 6},
            {"vector_ids": [item["vector_id"] for item in attacks]},
            "All modeled vectors return expected simulated revert",
            {"results": attacks},
            "PASSED" if all(item["status"] == "PASSED" for item in attacks) else "FAILED",
            {"chain_mutated": False}, {"chain_mutated": False},
        ))
    finally:
        evm_simulator.w3 = original_w3

    payload = {
        "report": "Orvilo Execution Evidence",
        "run_started_utc": run_started,
        "run_completed_utc": utc_now(),
        "classification": "NON_ON_CHAIN_SANDBOX_EVIDENCE",
        "network_label_in_application": "Base Sepolia (84532)",
        "rpc_used_for_this_run": False,
        "genuine_transactions_broadcast": 0,
        "scenarios": scenarios,
    }
    evidence_path = OUT_DIR / "execution-evidence.json"
    evidence_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    (OUT_DIR / "execution-evidence.sha256").write_text(
        f"{digest}  {evidence_path.name}\n", encoding="utf-8"
    )
    print(json.dumps({"evidence": str(evidence_path), "sha256": digest,
                      "scenarios": len(scenarios)}, indent=2))


if __name__ == "__main__":
    main()
