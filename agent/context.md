# Package Context: `agent/`

`agent/` owns the background task registry and autonomous decision loop. It is
used by the Flask application and depends on the exchange, reasoning, user,
and contract-model packages.

## Runtime flow

1. `flask.server.create_app()` starts the singleton `autonomous_agent`.
2. `AutonomousAgent` runs a daemon thread with a one-second interval.
3. The loop reads the current `AgentTask` from `TaskManager`.
4. It stops early when there is no `RUNNING` task, the agent is paused, or the
   contract-model pause flag is set.
5. It reads effective market state from `exchange_service` and wallet state
   from `user_db`.
6. It evaluates market and schedule triggers.
7. A satisfied trigger invokes `reasoning_engine.execute_reasoning_pipeline()`.
8. The reasoning pipeline performs RAG retrieval, intent generation, dry-run
   risk simulation, and programmatic trigger/invariant checks.
9. A failed gate or high-risk dry run records `BLOCKED_BY_GUARD`; a successful
   decision updates local balances and records a confirmed `AGENT` transaction.
10. The runtime does not submit a signed live transaction in the default path.

The runtime states include `IDLE`, `MONITORING`, `TRIGGER_MET`,
`GUARD_BLOCKED`, `EXECUTING`, `PAUSED`, and `ERROR`. The implementation also
uses `FINISHED` and `STOPPED` when a task reaches a terminal state.

## Task registry

`TaskManager` persists tasks to `agent/data/agent_tasks.json`, protects access
with a re-entrant lock, and enforces one running task. Registering a new task
marks an existing running task `STOPPED` with a supersession reason. Up to five
historical task records are retained in the file.

Supported task metadata includes:

- `MARKET_TRIGGER` tasks with gas or other trigger records.
- `ONE_TIME_SCHEDULE` transfers.
- `RECURRING_INTERVAL` transfers with `interval_seconds`.
- `RUNNING`, `FINISHED`, and `STOPPED` task statuses.
- execution count, next run time, last check reason, recipient, and policy hash.

Task persistence is local JSON, not a queue service or transactional database.
Malformed task JSON is currently treated as an empty registry.

## Safety boundary

The LLM used by the reasoning layer proposes intent and risk commentary only.
The runtime uses deterministic trigger checks, dry-run calculations, contract
model checks, and wallet state updates. The `PolicyWalletClient` pause flag is
checked before market evaluation. This is a local defense-in-depth demonstration,
not proof of a deployed contract or production key custody.

## Related implementation

| File | Responsibility |
|---|---|
| [`runtime.py`](runtime.py) | Daemon lifecycle, one tick, guard outcomes, audit writes |
| [`task.py`](task.py) | Task model, persistence, scheduling, lifecycle operations |
| [`../reasoning/engine.py`](../reasoning/engine.py) | RAG → intent → dry run → deterministic gates |
| [`../exchange/service.py`](../exchange/service.py) | Effective market snapshot |
| [`../user/db.py`](../user/db.py) | Wallet balances and transaction ledger |
| [`../contracts/wallet_client.py`](../contracts/wallet_client.py) | In-memory security controls |
