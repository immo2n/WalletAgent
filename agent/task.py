"""Agent Task Models and Single-Task Registry.

Manages autonomous tasks registered by the verified policy engine,
enforcing a maximum of 1 active task, showing FINISHED, RUNNING, or STOPPED
statuses along with clear execution and blocking reasons.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
import threading
from typing import Any, Dict, List, Literal, Optional
import uuid

TaskStatus = Literal["RUNNING", "FINISHED", "STOPPED"]

DEFAULT_TASK_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "agent_tasks.json")


@dataclass
class AgentTask:
    id: str
    prompt: str
    policy_hash: str
    status: TaskStatus
    created_at: str
    triggers: List[Dict[str, Any]]
    invariants: List[Dict[str, Any]]
    trade_action: Dict[str, Any]
    canonical_readback: str
    last_checked_at: Optional[str] = None
    last_reason: Optional[str] = None
    execution_tx_hash: Optional[str] = None
    executed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentTask:
        # Backward compatibility for old statuses
        raw_status = data.get("status", "RUNNING")
        if raw_status in ("ACTIVE", "MONITORING"):
            status = "RUNNING"
        elif raw_status in ("EXECUTED", "COMPLETED"):
            status = "FINISHED"
        elif raw_status in ("CANCELLED", "PAUSED"):
            status = "STOPPED"
        else:
            status = raw_status

        data_copy = dict(data)
        data_copy["status"] = status
        return cls(**data_copy)


class TaskManager:
    """Thread-safe task registry enforcing single active task constraint."""

    MAX_TASKS = 1

    def __init__(self, db_path: str = DEFAULT_TASK_DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._tasks: List[AgentTask] = []
        self._load()

    def _load(self) -> None:
        with self._lock:
            if os.path.exists(self.db_path) and os.path.getsize(self.db_path) > 0:
                try:
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._tasks = [AgentTask.from_dict(t) for t in data]
                        return
                except Exception:
                    pass
            self._tasks = []

    def _save(self) -> None:
        with self._lock:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self._tasks], f, indent=2)

    def get_current_task(self) -> Optional[AgentTask]:
        """Fetch the current task regardless of whether it is RUNNING, FINISHED, or STOPPED."""
        with self._lock:
            return self._tasks[0] if self._tasks else None

    def get_active_task(self) -> Optional[AgentTask]:
        """Fetch active task only if it is currently RUNNING."""
        with self._lock:
            for t in self._tasks:
                if t.status == "RUNNING":
                    return t
            return None

    def get_all_tasks(self) -> List[AgentTask]:
        with self._lock:
            return list(self._tasks)

    def register_task(
        self,
        prompt: str,
        policy_hash: str,
        canonical_readback: str,
        triggers: List[Dict[str, Any]],
        invariants: List[Dict[str, Any]],
        trade_amount_usd: float = 200.0,
    ) -> AgentTask:
        """Register a new autonomous task (replaces any previous task)."""
        with self._lock:
            for t in self._tasks:
                if t.status == "RUNNING":
                    t.status = "STOPPED"
                    t.last_reason = "Superseded by new policy deployment"

            now_iso = datetime.now(timezone.utc).isoformat()
            new_task = AgentTask(
                id=f"task-{uuid.uuid4().hex[:6]}",
                prompt=prompt,
                policy_hash=policy_hash,
                status="RUNNING",
                created_at=now_iso,
                triggers=triggers,
                invariants=invariants,
                trade_action={
                    "type": "SWAP",
                    "from_token": "USDC",
                    "to_token": "ETH",
                    "amount_usd": float(trade_amount_usd),
                },
                canonical_readback=canonical_readback,
                last_checked_at=now_iso,
                last_reason="Task started. Watching market feed for trigger conditions.",
            )
            # Insert at top (current task)
            self._tasks.insert(0, new_task)
            self._tasks = self._tasks[:5]
            self._save()
            return new_task

    def stop_task(self, task_id: str, reason: str = "Manually stopped by user") -> bool:
        """User manual stopping/pausing of the task."""
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    t.status = "STOPPED"
                    t.last_reason = reason
                    self._save()
                    return True
            return False

    def rerun_task(self, task_id: str) -> Optional[AgentTask]:
        """Re-activate a finished or stopped task."""
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    t.status = "RUNNING"
                    t.last_reason = "Re-activated by user. Watching market feed for trigger conditions."
                    t.executed_at = None
                    t.execution_tx_hash = None
                    self._save()
                    return t
            return None

    def delete_task(self, task_id: str) -> bool:
        """User manual dismissal/deletion of the task."""
        with self._lock:
            initial_len = len(self._tasks)
            self._tasks = [t for t in self._tasks if t.id != task_id]
            if len(self._tasks) < initial_len:
                self._save()
                return True
            return False

    def clear_all(self) -> None:
        """Clear all registered tasks from memory and persistent disk database."""
        with self._lock:
            self._tasks = []
            self._save()

    def mark_finished(self, task_id: str, tx_hash: str, reason: str) -> bool:
        """Mark task as FINISHED with execution transaction hash and detailed reason."""
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    t.status = "FINISHED"
                    t.executed_at = datetime.now(timezone.utc).isoformat()
                    t.execution_tx_hash = tx_hash
                    t.last_reason = reason
                    self._save()
                    return True
            return False

    def mark_executed(self, task_id: str, tx_hash: str, reason: str) -> bool:
        """Alias for backward compatibility."""
        return self.mark_finished(task_id, tx_hash, reason)

    def update_check(self, task_id: str, reason: str) -> None:
        with self._lock:
            for t in self._tasks:
                if t.id == task_id:
                    t.last_checked_at = datetime.now(timezone.utc).isoformat()
                    t.last_reason = reason
                    self._save()
                    break


# Global singleton
task_manager = TaskManager()
