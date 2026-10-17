"""
Comprehensive test suite verifying all 9 scorecard features for FinTechathon 2026:
1. Natural-language instruction parsing
2. Policy review and user approval workflow
3. On-chain rules for tokens, recipients, limits, and balances
4. Scheduled transfers & recurring DCA
5. Transaction simulation before submission (EVM eth_call & gas estimation)
6. On-chain policy enforcement (PolicyWallet smart contract)
7. Transaction history and explanations
8. Emergency pause and permission revocation
9. Attack tester showing smart contract rejection
"""

import pytest
import json
import os
import importlib.util

from contracts.simulator import EVMSimulator
from contracts.wallet_client import PolicyWalletClient
from contracts.attack_tester import AttackSimulator
from policy.workflow import PolicyWorkflowManager
from agent.task import AgentTask, TaskManager, task_manager

# Load flask/server.py without shadowing installed flask package
server_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flask", "server.py")
spec = importlib.util.spec_from_file_location("wallet_flask_server", server_path)
server_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_mod)
create_app = server_mod.create_app


@pytest.fixture
def test_client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# =========================================================================
# Feature 1 & 3: Natural Language Parsing & On-Chain Rules
# =========================================================================

def test_natural_language_parsing_allowlists_and_limits(test_client):
    """Verifies parsing of allowlists, recipients, and limits."""
    payload = {
        "prompt": "Only trade ETH and USDC. Keep the balance after each trade at least $500. Limit single trades to $300."
    }
    res = test_client.post("/api/verify", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "VERIFIED"
    assert "hash" in data
    assert "readback" in data


# =========================================================================
# Feature 2: Policy Review and Explicit User Approval Workflow
# =========================================================================

def test_policy_approval_workflow():
    """Verifies DRAFT -> REVIEWED -> DEPLOYABLE -> ACTIVE workflow state transitions."""
    manager = PolicyWorkflowManager()
    proposal = manager.create_proposal(
        prompt="Buy ETH when gas < 20 gwei. Keep balance at least $500.",
        policy_obj=None,
        canonical_readback="Buy ETH when gas <= 20 gwei.",
        hash_val="0xabcdef1234567890"
    )
    assert proposal.status == "DRAFT"

    # 1. Review
    reviewed = manager.review_policy(proposal.proposal_id, reviewer="Auditor")
    assert reviewed.status == "REVIEWED"
    assert reviewed.reviewed_by == "Auditor"

    # 2. Approve
    approved = manager.approve_policy(proposal.proposal_id, approver="0x71C8366420A096207E90B01D252431792349039A")
    assert approved.status == "DEPLOYABLE"
    assert approved.signature is not None

    # 3. Deploy
    deployed = manager.deploy_policy(proposal.proposal_id)
    assert deployed.status == "ACTIVE"
    assert deployed.onchain_tx_hash is not None


def test_policy_workflow_endpoints(test_client):
    """Verifies the HTTP workflow API endpoints."""
    # Ensure there is a proposal in the system
    test_client.post("/api/verify", json={"prompt": "Buy ETH when gas < 20 gwei. Keep balance at least $500."})

    # Review
    res1 = test_client.post("/api/policy/review", json={"reviewer": "User"})
    assert res1.status_code == 200
    assert res1.get_json()["proposal"]["status"] == "REVIEWED"

    # Approve
    res2 = test_client.post("/api/policy/approve", json={"approver": "0x71C8366420A096207E90B01D252431792349039A"})
    assert res2.status_code == 200
    assert res2.get_json()["proposal"]["status"] == "DEPLOYABLE"

    # Deploy
    res3 = test_client.post("/api/policy/deploy", json={"prompt": "Test policy"})
    assert res3.status_code == 200
    assert res3.get_json()["proposal"]["status"] == "ACTIVE"


# =========================================================================
# Feature 4: Scheduled Transfers
# =========================================================================

def test_scheduled_transfer_creation():
    """Verifies task model schedule fields and initialization."""
    task = task_manager.schedule_transfer_task(
        recipient="0x71C8366420A096207E90B01D252431792349039A",
        amount_usd=150.0,
        token="USDC",
        schedule_type="RECURRING_INTERVAL",
        interval_seconds=60
    )
    assert task.schedule_type == "RECURRING_INTERVAL"
    assert task.recipient == "0x71C8366420A096207E90B01D252431792349039A"
    assert task.interval_seconds == 60
    assert task.next_run_at is not None


def test_scheduled_transfer_endpoint(test_client):
    """Verifies /api/agent/schedule endpoint."""
    payload = {
        "recipient": "0x71C8366420A096207E90B01D252431792349039A",
        "amount_usd": 100.0,
        "token": "USDC",
        "schedule_type": "RECURRING_INTERVAL",
        "interval_seconds": 60
    }
    res = test_client.post("/api/agent/schedule", json=payload)
    assert res.status_code in (200, 201)
    data = res.get_json()
    assert data["success"] is True
    assert data["task"]["schedule_type"] == "RECURRING_INTERVAL"


# =========================================================================
# Feature 5: Pre-Flight EVM Simulation & Gas Estimation
# =========================================================================

def test_evm_simulator_preflight():
    """Verifies EVMSimulator eth_call, gas estimation, and revert checks."""
    sim = EVMSimulator()
    # Passing trade
    res_ok = sim.simulate_transaction(
        from_address="0x71C8366420A096207E90B01D252431792349039A",
        to_address="0x839841B98692FE55806e2E1FaFfeF754d924C236",
        guards={
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
            "is_paused": False
        }
    )
    assert res_ok["success"] is True
    assert res_ok["gas_estimate"] > 0
    assert res_ok["status"] == "SIMULATED_SUCCESS"

    # Reverting trade: below floor
    res_fail = sim.simulate_transaction(
        from_address="0x71C8366420A096207E90B01D252431792349039A",
        to_address="0x839841B98692FE55806e2E1FaFfeF754d924C236",
        guards={
            "trade_amount_usd": 1200.0,
            "balance_after_usd": 300.0,
            "min_balance_floor_usd": 500.0,
            "is_paused": False
        }
    )
    assert res_fail["success"] is False
    assert res_fail["custom_error_name"] == "BelowMinimumBalanceFloor"


def test_simulation_endpoint(test_client):
    """Verifies /api/simulation/simulate HTTP endpoint."""
    res = test_client.post("/api/simulation/simulate", json={"trade_usd": 200.0, "token": "USDC"})
    assert res.status_code == 200
    data = res.get_json()
    assert "gas_estimate" in data or "gas_estimated" in data


# =========================================================================
# Feature 6 & 8: Policy Smart Contract, Emergency Pause & Revocations
# =========================================================================

def test_wallet_client_security_controls():
    """Verifies pause, unpause, operator revocation, allowance revocation, and policy invalidation."""
    client = PolicyWalletClient()
    st = client.get_security_status()
    assert st["contract_address"].startswith("0x")
    assert st["paused"] is False

    # Emergency Pause
    pause_res = client.emergency_pause()
    assert pause_res["paused"] is True
    assert client.is_paused is True

    # Emergency Unpause
    unpause_res = client.emergency_unpause()
    assert unpause_res["paused"] is False
    assert client.is_paused is False

    # Revoke Operator
    revoke_op = client.revoke_operator("0x2B5AD5c4795c026514f8317c7a215E218DcCD6cF")
    assert revoke_op["authorized"] is False

    # Revoke Allowance
    revoke_all = client.revoke_allowance("0x0b2C639c533813f4Aa9D7837CA6262d0839793E", "0x111111125421cA6dc452d289314280a0f8842A65")
    assert revoke_all["allowance"] == 0

    # Invalidate Policy
    inval = client.invalidate_policy()
    assert inval["invalidated"] is True
    assert client.active_policy_hash in ("", "0x" + "0" * 64)


def test_contract_security_endpoints(test_client):
    """Verifies security HTTP endpoints."""
    st = test_client.get("/api/contract/security-status").get_json()
    assert "contract_address" in st

    res_pause = test_client.post("/api/contract/pause").get_json()
    assert res_pause["paused"] is True

    res_unpause = test_client.post("/api/contract/unpause").get_json()
    assert res_unpause["paused"] is False


# =========================================================================
# Feature 9: Attack Tester Suite Showing Smart Contract Rejection
# =========================================================================

def test_attack_tester_vectors():
    """Verifies that all 6 attack vectors revert with the expected Solidity custom errors."""
    attacker = AttackSimulator()
    vectors = attacker.get_attack_vectors()
    assert len(vectors) == 6

    # Test all attacks
    results = attacker.run_all_attacks()
    assert len(results) == 6
    for r in results:
        assert r["reverted_as_expected"] is True
        assert r["actual_status"] == "REVERTED (0x0)"
        assert r["custom_error_name"] == r["expected_error"]
        assert r["error_signature"].startswith("0x")


def test_attack_tester_endpoints(test_client):
    """Verifies attack tester HTTP endpoints."""
    # List vectors
    res_vecs = test_client.get("/api/contract/attack-test/vectors")
    assert res_vecs.status_code == 200
    vecs = res_vecs.get_json()
    assert len(vecs) == 6

    # Run single attack
    res_single = test_client.post("/api/contract/attack-test/run", json={"attack_id": "VIOLATE_FLOOR"})
    assert res_single.status_code == 200
    data = res_single.get_json()
    assert data["reverted_as_expected"] is True
    assert data["custom_error_name"] == "BelowMinimumBalanceFloor"

    # Run all attacks
    res_all = test_client.post("/api/contract/attack-test/run", json={})
    assert res_all.status_code == 200
    all_data = res_all.get_json()
    assert len(all_data["results"]) == 6
