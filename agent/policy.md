# Agent implementation reference

This file records how the current `agent/` package consumes verified policy
data. It is not a separate policy engine and it must not be read as a promise
of live-chain execution.

## Inputs

`TaskManager.register_task()` receives:

- the natural-language prompt;
- the verified policy hash and canonical readback;
- normalized trigger and invariant dictionaries;
- trade amount, token, recipient, and schedule metadata.

The Flask policy routes create these inputs from the active verified result.
`set_default_policy()` also registers a default market-trigger task when no
current task exists.

## Decision sequence

For a running task, `AutonomousAgent.step()`:

1. checks the local `PolicyWalletClient.is_paused` flag;
2. reads market and wallet snapshots;
3. evaluates task triggers and schedule maturity;
4. calls the reasoning engine;
5. handles `ABORTED_BY_RISK` as a blocked action;
6. applies deterministic guard outcomes;
7. updates the local wallet ledger only when the action is allowed;
8. writes a structured reasoning report to the transaction record.

The agent never receives private-key signing authority in this repository.
Successful runtime actions are local simulation state changes.

## Failure behavior

- No running task: state becomes `IDLE`.
- Trigger not satisfied: state remains `MONITORING`; the task receives a
  human-readable last-check reason.
- Contract-model pause: state becomes `GUARD_BLOCKED`.
- Dry-run high risk: a blocked transaction is recorded.
- Formal trigger or invariant failure: a blocked transaction is recorded.
- Unexpected loop errors: the exception is logged and the agent emits an
  `ERROR` thought without silently treating the action as successful.

## Verification

The agent package is covered by the repository test suite. Run:

```bash
.venv/bin/python -m pytest -q
```

The current working tree has 90 passing tests. Test results demonstrate local
behavior only; they do not certify a deployed wallet contract.
