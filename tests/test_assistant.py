"""Unit and integration tests for WalletAssistant and assistant API endpoints."""
import os
import importlib.util
import pytest

from agent.assistant import WalletAssistant, wallet_assistant
from user.db import UserDatabase
from agent.task import TaskManager
from contracts.wallet_client import PolicyWalletClient

# Load flask/server.py
server_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "flask", "server.py")
spec = importlib.util.spec_from_file_location("wallet_flask_server_assistant", server_path)
server_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_mod)
create_app = server_mod.create_app


@pytest.fixture
def app_client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_assistant_audit_transactions():
    """Verify transaction auditing and anomaly detection logic."""
    audit = wallet_assistant.audit_transactions()
    assert "risk_level" in audit
    assert "total_transactions" in audit
    assert "flagged_count" in audit
    assert "explanation" in audit
    assert audit["total_transactions"] >= 0
    assert "Transaction Security Audit" in audit["explanation"]


def test_assistant_explain_tasks():
    """Verify agent task explanation and live trigger evaluation."""
    task_info = wallet_assistant.explain_agent_tasks()
    assert "has_task" in task_info
    assert "explanation" in task_info
    if task_info["has_task"]:
        assert "Autonomous Agent Task Breakdown" in task_info["explanation"]
        assert "Z3 Formal Invariant Guards" in task_info["explanation"]


def test_assistant_chat_intents():
    """Verify natural-language conversational queries and action routing."""
    # 1. Suspicious Activity
    res_audit = wallet_assistant.chat("Are there any suspicious transactions?")
    assert "reply" in res_audit
    assert "Security Audit" in res_audit["reply"]
    assert res_audit["action"]["type"] == "navigate"
    assert res_audit["action"]["pane"] == "pane-ledger"

    # 2. Explain Task
    res_task = wallet_assistant.chat("Explain the active agent task")
    assert "reply" in res_task
    assert res_task["action"]["type"] == "navigate"
    assert res_task["action"]["pane"] == "pane-agent"

    # 3. Balance Query
    res_bal = wallet_assistant.chat("What is my current wallet balance?")
    assert "reply" in res_bal
    assert "ETH" in res_bal["reply"]
    assert "USDC" in res_bal["reply"]
    assert res_bal["action"]["type"] == "navigate"
    assert res_bal["action"]["pane"] == "pane-wallet"

    # 4. Security Status
    res_sec = wallet_assistant.chat("What is the contract security status?")
    assert "reply" in res_sec
    assert "PolicyWallet.sol" in res_sec["reply"]
    assert res_sec["action"]["pane"] == "pane-security"

    # 5. Attack Tests
    res_atk = wallet_assistant.chat("Run all attack tests")
    assert "reply" in res_atk
    assert "rejection suite" in res_atk["reply"].lower()
    assert res_atk["action"]["runAttacks"] is True

    # 6. Trade Simulation
    res_sim = wallet_assistant.chat("Simulate a $200 swap")
    assert "reply" in res_sim
    assert "Dry-Run" in res_sim["reply"]

    # 7. Conversational Greeting
    res_hi = wallet_assistant.chat("Hello, who are you?")
    assert "reply" in res_hi
    assert "WalletAgent" in res_hi["reply"]


def test_assistant_http_endpoints(app_client):
    """Verify Flask HTTP endpoints for assistant chat, audit, and task explanation."""
    # Test POST /api/assistant/chat
    chat_res = app_client.post(
        "/api/assistant/chat",
        json={"message": "Audit transactions for any suspicious ones"}
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.get_json()
    assert "reply" in chat_data
    assert "action" in chat_data
    assert chat_data["action"]["pane"] == "pane-ledger"

    # Test GET /api/assistant/audit
    audit_res = app_client.get("/api/assistant/audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.get_json()
    assert "risk_level" in audit_data
    assert "explanation" in audit_data

    # Test GET /api/assistant/tasks
    tasks_res = app_client.get("/api/assistant/tasks")
    assert tasks_res.status_code == 200
    tasks_data = tasks_res.get_json()
    assert "has_task" in tasks_data
    assert "explanation" in tasks_data
