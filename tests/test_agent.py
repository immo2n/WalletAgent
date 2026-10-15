"""Unit tests for Autonomous Agent runtime, Task Manager, and execution gating."""
import os
import tempfile
import pytest

from agent.runtime import AutonomousAgent
from agent.task import AgentTask, TaskManager
from user.db import UserDatabase


@pytest.fixture
def temp_task_mgr():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    mgr = TaskManager(db_path=tmp_path)
    yield mgr
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


def test_task_registration_and_statuses(temp_task_mgr):
    # 1. Register first task (RUNNING)
    t1 = temp_task_mgr.register_task(
        prompt="Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.",
        policy_hash="hash-1",
        canonical_readback="Buy when gas <= 20. Keep balance >= $500.",
        triggers=[{"field": "gas", "op": "lte", "val": 20.0}],
        invariants=[{"field": "balance", "op": "sub", "val": 500.0}],
        trade_amount_usd=200.0,
    )
    assert t1.status == "RUNNING"
    assert temp_task_mgr.get_active_task().id == t1.id
    assert temp_task_mgr.get_current_task().id == t1.id

    # 2. Register second task: supersedes the first
    t2 = temp_task_mgr.register_task(
        prompt="Never let my balance go under 500 dollars.",
        policy_hash="hash-2",
        canonical_readback="Keep balance >= $500.",
        triggers=[],
        invariants=[{"field": "balance", "op": "sub", "val": 500.0}],
        trade_amount_usd=100.0,
    )
    assert t2.status == "RUNNING"
    assert temp_task_mgr.get_active_task().id == t2.id
    assert temp_task_mgr.get_current_task().id == t2.id

    # Verify t1 was marked STOPPED
    all_tasks = temp_task_mgr.get_all_tasks()
    old_t1 = next(t for t in all_tasks if t.id == t1.id)
    assert old_t1.status == "STOPPED"
    assert "Superseded" in old_t1.last_reason

    # 3. Test mark_finished preserves task in current_task with detailed reason
    finished_reason = "Finished successfully: Gas 16.5 <= 20 gwei. Swapped $100 USDC for ETH."
    temp_task_mgr.mark_finished(t2.id, tx_hash="0xabc123", reason=finished_reason)
    curr = temp_task_mgr.get_current_task()
    assert curr is not None
    assert curr.status == "FINISHED"
    assert curr.last_reason == finished_reason
    assert curr.execution_tx_hash == "0xabc123"

    # 4. Test re-running task
    rerun = temp_task_mgr.rerun_task(t2.id)
    assert rerun.status == "RUNNING"
    assert temp_task_mgr.get_active_task().id == t2.id

    # 5. Test stopping task
    temp_task_mgr.stop_task(t2.id, reason="Manually stopped by user")
    curr_stopped = temp_task_mgr.get_current_task()
    assert curr_stopped.status == "STOPPED"
    assert curr_stopped.last_reason == "Manually stopped by user"


def test_task_user_deletion(temp_task_mgr):
    t = temp_task_mgr.register_task(
        prompt="Buy ETH when gas <= 20",
        policy_hash="hash-abc",
        canonical_readback="Readback",
        triggers=[{"field": "gas", "op": "lte", "val": 20.0}],
        invariants=[],
    )
    assert temp_task_mgr.get_current_task() is not None

    # User deletes task
    deleted = temp_task_mgr.delete_task(t.id)
    assert deleted is True
    assert temp_task_mgr.get_current_task() is None


def test_agent_step_evaluation():
    agent = AutonomousAgent()
    agent.step()
    status = agent.get_status()
    assert "state" in status
    assert "thought_logs" in status
    assert "current_task" in status


def test_flask_agent_api():
    import importlib.util
    server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "flask", "server.py")
    spec = importlib.util.spec_from_file_location("wallet_flask_server", server_path)
    server_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_mod)
    app = server_mod.create_app()
    client = app.test_client()

    # 1. Register a task
    resp = client.post("/api/agent/task", json={
        "prompt": "Buy ETH when gas is under 18 gwei, and never let my balance drop below 500 dollars.",
        "trade_amount_usd": 150.0,
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == "RUNNING"
    task_id = data["id"]

    # 2. Check status endpoint retains task
    status_resp = client.get("/api/agent/status")
    status_data = status_resp.get_json()
    assert status_data["current_task"]["id"] == task_id
    assert status_data["current_task"]["status"] == "RUNNING"

    # 3. Stop task manually
    stop_resp = client.post("/api/agent/task/stop")
    assert stop_resp.status_code == 200
    stop_data = client.get("/api/agent/status").get_json()
    assert stop_data["current_task"]["status"] == "STOPPED"
    assert "stopped by user" in stop_data["current_task"]["last_reason"].lower()

    # 4. Rerun task
    rerun_resp = client.post("/api/agent/task/rerun")
    assert rerun_resp.status_code == 200
    rerun_data = client.get("/api/agent/status").get_json()
    assert rerun_data["current_task"]["status"] == "RUNNING"

    # 5. Simulate task completion with mark_finished
    from agent.task import task_manager
    finished_reason = "Finished successfully: Gas dropped to 15 gwei. Tx: 0x999999"
    task_manager.mark_finished(task_id, tx_hash="0x999999", reason=finished_reason)

    # 6. Verify task is NOT deleted and shows FINISHED status + reason
    fin_status = client.get("/api/agent/status").get_json()
    assert fin_status["current_task"] is not None
    assert fin_status["current_task"]["status"] == "FINISHED"
    assert fin_status["current_task"]["last_reason"] == finished_reason
    assert fin_status["current_task"]["execution_tx_hash"] == "0x999999"

    # 7. Verify index page renders without error when task is FINISHED
    index_resp = client.get("/")
    assert index_resp.status_code == 200
    html = index_resp.get_data(as_text=True)
    assert "FINISHED" in html
    assert "Finished Successfully:" in html

    # 8. Verify simulation reset clears all tasks and resets agent to IDLE
    reset_resp = client.post("/api/user/reset")
    assert reset_resp.status_code == 200
    reset_status = client.get("/api/agent/status").get_json()
    assert reset_status["current_task"] is None
    assert reset_status["active_task"] is None
    assert reset_status["state"] == "IDLE"
    assert task_manager.get_current_task() is None


