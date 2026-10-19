# WalletAgent (Orvilo): Security Self-Assessment Report

> **User-Defined On-Chain Guardrails for Autonomous AI Wallets**  
> **Classification:** `FINAL SELF-ASSESSMENT · NOT AN INDEPENDENT AUDIT`

---

## Document Control & System Metadata

| Parameter | Recorded Value | Notes |
| :--- | :--- | :--- |
| **Document Version** | `1.1 (Final Repository Alignment)` | Synchronized with active `main` codebase |
| **Preparation Date** | 20 October 2026 | FinTechathon 2026 (Topic F: Agent Wallet) |
| **Report Status** | Final self-assessment | Repository self-assessment by engineering team |
| **Repository** | `https://github.com/immo2n/WalletAgent` | Active GitHub submission repository |
| **Branch Assessed** | `main` | Production / Submission baseline |
| **Assessed Code Commit** | `f81167f` | Merged upstream CI, Docker, & Conversational Assistant |
| **Environment** | Local Docker & Python 3.14 virtual environment | Base Sepolia (84532) configured; offline simulation by default |
| **Automated Tests** | **94 / 94 Passing** (`pytest tests/`) | 100% pass across all 13 test files |
| **Docker Smoke Test** | **11 / 11 Checks Passed** | Verified via `scripts/docker_smoke.py` |
| **Open Findings** | 10 Recorded (2 Critical, 6 High, 2 Medium) | Pre-production sandbox boundaries disclosed |

> [!IMPORTANT]
> **Evidence Convention**:
> - **Designed:** Described as an intended control in documentation or comments.
> - **Implemented:** Present and inspectable in the current source code.
> - **Verified:** Exercised and confirmed by the 94-test automated suite or Docker smoke test.
> *A control is not treated as verified merely because a comment, UI label, generated hash, or simulated response claims it is active.*

---

## 1. Executive Summary

Orvilo is a simulation-first Flask application that converts natural-language trading constraints into a typed policy, compares deterministic and LLM-derived interpretations, applies Z3-backed formal proofs, records a human-review workflow, and runs a local autonomous task loop. It includes a Solidity reference contract named `PolicyWallet` with owner/operator authorization, policy hashes, token and recipient allowlists, spending caps, reserve floors, pause, and allowance-revocation functions.

The assessed deployment is **local simulation by default**. The Docker image sets `LLM_PROVIDER=mock`; the application uses JSON state stores and the contract client returns generated transaction identifiers instead of signing and broadcasting transactions. The configured network is Base Sepolia (`84532`), but no genuine on-chain transaction hash, receipt, signer operation, or deployed-contract state was verified in this assessment.

### Outcome Summary by Area

| Area | Status | Basis |
| :--- | :---: | :--- |
| **Policy parsing & deterministic guard logic** | `Verified` | Implemented and verified by the 94-test suite and Docker smoke test. |
| **Human-review workflow** | `Partial` | Implemented in application memory; verified for happy-path API transitions only. |
| **Solidity access modifiers & guards** | `Source Reviewed` | Present in reviewed source; not verified against a deployed bytecode address. |
| **Permission tiers** | `Partial` | Owner/operator modeled; HTTP/API identity enforcement is absent. |
| **Authentication & account isolation** | `Not Implemented` | All Flask routes are reachable without identity proof. |
| **Real signing & blockchain execution** | `Not Implemented` | Generated hashes are simulation identifiers; no broadcast to Base Sepolia. |
| **Conversational Co-Pilot (agent/assistant.py)**| `Verified` | LangChain assistant tests pass (4/4); anomaly audit and task explanation active. |
| **Production readiness** | `Not Ready` | 2 Critical and 6 High findings must be remediated prior to handling real funds. |

### Principal Risks
1. **Unauthenticated Administrative Routes (K-01):** Wallet-mutating and policy-administering routes can be called by any client that reaches the server.
2. **Unsafe Contract Execution Design (K-02):** Execution accepts caller-supplied USD and post-balance values and performs arbitrary router calls.
3. **Synthetic Approvals and Hashes (K-03, K-04):** Default signing and approval are generated strings, and deployment can proceed before review.
4. **Fallbacks that Look Like Success (K-06):** Simulated execution can appear successful when RPC or deployment state is unavailable.

### What is Working Well
- Deterministic policy parsing, type-checking, and Z3 equivalence comparison are proven across 94 passing tests.
- The Solidity reference contract contains robust access modifiers (`onlyOwner`, `onlyAuthorized`, `whenNotPaused`), custom typed errors, and invariant checks.
- Docker image runs as a non-root user (`orvilo`), excludes `.env` from build context, and defines an active health check.
- Simulation boundaries are clearly documented, and the conversational assistant (`agent/assistant.py`) provides real-time auditability.

---

## 2. Assessment Scope & System Identification

### In-Scope Components

| Component | Repository Path | Evidence & Role |
| :--- | :--- | :--- |
| **Flask Dashboard & API** | `flask/server.py` | UI, REST API, SSE telemetry streaming |
| **Policy AST, Readers & Parser** | `policy/` | Dual-reader grammar, Z3 solver, AST hashing |
| **Rule Lexicon & Comparators** | `policy/readers/lexicon.py` | Extracts triggers, caps, and symbolic inequalities (`<`, `<=`, `>`, `>=`, `=`, `==`) |
| **Approval Workflow** | `policy/workflow.py` | Governance stepper (`DRAFT` $\to$ `ACTIVE`) |
| **Autonomous Agent Runtime** | `agent/runtime.py`, `agent/task.py` | 1 Hz daemon evaluation loop, task state machine |
| **Conversational Co-Pilot** | `agent/assistant.py` | LangChain assistant for anomaly auditing and task explanation |
| **Wallet & Transaction Store** | `user/db.py`, `user/models.py` | In-memory balance tracking and transaction logging |
| **EVM Simulator & Attack Suite** | `contracts/simulator.py`, `contracts/attack_tester.py` | Preflight simulation and 6/6 adversarial exploit checks |
| **Solidity Reference Contract** | `contracts/PolicyWallet.sol`, `contracts/abi.py` | Invariant defense contract for Base Sepolia |
| **Client, Docker & CI** | `contracts/wallet_client.py`, `Dockerfile`, `.github/workflows/ci.yml` | Containerization, client simulation, and automated CI |
| **Market & Gas Integration** | `exchange/` | Coinbase WebSocket feed and simulated gas estimation |

### Excluded Evidence
The following were not available and are therefore outside the assessment:
- Private keys and production secrets.
- Deployed owner configuration and live on-chain owner/operator state.
- Live Base Sepolia transaction receipts and any mainnet activity.
- Independent external third-party smart-contract audit.

---

## 3. Assessment Methodology & Rating Criteria

1. **Source Code Review:** Exhaustive analysis of Flask routes, state management, policy loop, Z3 verification, task runtime, contract client, Solidity code, Docker, and CI configurations.
2. **Automated Test Suite Execution:** `PYTHONPATH=. pytest -q` $\to$ **94 passed in 17.09s** across 13 test files.
3. **Docker Smoke Testing:** `scripts/docker_smoke.py` verified against running container (`11/11 checks passed`).
4. **Adversarial Attack Simulation:** 6 scorecard exploit vectors tested and confirmed reverting with typed Solidity errors.
5. **Architectural Gap Analysis:** Comparing documented claims against observable sandbox runtime behavior.

### Rating Definitions

| Dimension | Meaning |
| :--- | :--- |
| **Likelihood** | **Low:** difficult or constrained · **Medium:** plausible with access · **High:** directly reachable or reproducible |
| **Impact** | **Low:** limited integrity effect · **Medium:** material application effect · **High:** policy, identity, or fund-control effect |
| **Severity** | **Critical:** direct path to unauthorized value movement · **High:** serious control gap · **Medium:** defense-in-depth gap |
| **Confidence** | Evidence confidence rating from 1/10 to 10/10 based on empirical verification |

---

## 4. Security Architecture & Threat Model

![Security trust boundaries](../visuals/rendered/security-trust-boundaries.png)

### Key Assets
- **Wallet balances and transaction history:** Direct financial value and basis for audit reconciliation.
- **Active policy hash, caps, allowlists, reserve floor, and pause state:** Define what an autonomous agent may do.
- **Owner/operator authority and signing credentials:** Compromise gives control over funds.
- **Policy proposals, reviews, approvals, and deployment records:** Proof of human governance.
- **Market and gas data:** Inputs to execution decisions; manipulation or staleness distorts them.

### Threat Scenarios

| ID | Threat Scenario | Consequence | Finding |
| :--- | :--- | :--- | :--- |
| **T-1** | Remote client calls pause, reset, wallet-mutation, or approval routes directly | Policy and wallet state altered without identity proof | **K-01** |
| **T-2** | Operator supplies misleading USD value or post-balance, or arbitrary router calldata | Spending caps and reserve floor bypassed on-chain | **K-02** |
| **T-3** | Generated simulation identifier presented as confirmed transaction | False assurance; distorted accounting and audit trail | **K-03, K-06** |
| **T-4** | Proposal deployed from `DRAFT` or approved with arbitrary string name | Human-in-the-loop guarantee defeated | **K-04** |
| **T-5** | Stale approval or execution replayed after deadline | Outdated authority reused | **K-07** |
| **T-6** | Concurrent access to shared JSON store | Lost updates; cross-user state pollution | **K-05** |

---

## 5. Security Requirements & Verification Matrix

| ID | Security Requirement | Implementation Evidence | Verification Result |
| :--- | :--- | :--- | :---: |
| **SR-01** | Only owner can change policy or emergency state | Solidity `onlyOwner` in `PolicyWallet.sol` | `Source Reviewed` |
| **SR-02** | Operator actions are bounded by policy invariants | `_verifyGuards`, caps, allowlists, floor, pause | `Verified (Local)` |
| **SR-03** | Policy interpretation is independently checked | Rule reader, LLM reader, Z3 SMT solver proof | **`Verified (94/94)`** |
| **SR-04** | Human approval precedes deployment | `PolicyWorkflowManager` multi-stage stepper | `Partial` |
| **SR-05** | Unauthorized HTTP callers cannot mutate state | Required for production | **`FAILED`** |
| **SR-06** | Execution values derived from trusted chain state | Required for financial safety | **`FAILED`** |
| **SR-07** | Revocation immediately blocks future execution | Contract `revokeOperator` / local flag | `Partial (EE-06 Gap)` |
| **SR-08** | Transaction hashes represent real chain execution | Required for on-chain auditability | **`Not Implemented`** |
| **SR-09** | Account data is isolated by authenticated owner | Required for multi-user service | **`Not Implemented`** |
| **SR-10** | Secrets are not baked into image or repository | `.dockerignore`, `.env.example`, mock defaults | `Verified` |

---

## 6. Key Custody, Signing Authority, & Permissions

![Permission enforcement flow](../visuals/rendered/permission-enforcement.png)

### Implemented / Modeled Tiers

| Tier | Intended Holder | Allowed Actions | Restrictions | Enforcement Location | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Owner** | Human wallet owner | Set/invalidate policy, manage operators, pause/unpause, revoke allowances | Highest privilege | Solidity `onlyOwner` | Implemented in contract source; API enforcement failed |
| **Authorized Operator** | Autonomous agent | Guarded swap/transfer | Policy hash, caps, allowlists, floor, pause | Solidity `onlyAuthorized` + `_verifyGuards` | Implemented in contract; Python client gap noted (EE-06) |
| **Reviewer** | Security reviewer | Mark proposal reviewed | Precondition for approval | String field `reviewed_by` | Modeled; not authenticated |
| **Approver** | Owner / Approver | Mark proposal deployable | Human approval signature | String field `approved_by` | Modeled; cryptographic signature not verified |
| **Public HTTP Caller** | Any network client | Actual caller of exposed routes | None in Flask layer | No auth middleware | **Unrestricted (Critical Gap)** |

---

## 7. Security Test Register & Evidence

| ID | Requirement | Procedure | Result | Evidence Detail |
| :--- | :--- | :--- | :---: | :--- |
| **ST-01** | SR-03 | Run full Python test suite | **`PASSED`** | **94 passed in 17.09s** (13 test files) |
| **ST-02** | SR-03/SR-04 | Build Docker image and run policy verification | **`PASSED`** | Docker smoke test (`scripts/docker_smoke.py`) |
| **ST-03** | SR-04 | Review, approve, and deploy policy proposal | **`PASSED`** | Workflow stepper transitions verified |
| **ST-04** | SR-02 | Execute six modeled adversarial penetration checks | **`PASSED`** | 6/6 Reverted with typed Solidity errors |
| **ST-05** | SR-07 | Pause/unpause, revoke operator, invalidate policy | **`PASSED`** | Local client state transitions verified |
| **ST-06** | SR-08 | Confirm genuine on-chain transaction hash & receipt | **`NOT TESTED`** | No broadcast transactions (Sandbox mode) |
| **ST-07** | SR-05 | Attempt unauthenticated administrative API calls | **`FAILED`** | Mutating routes accept unauthenticated JSON |
| **ST-08** | SR-06 | Prove contract derives value from trusted on-chain state | **`FAILED`** | Caller-supplied arguments in `PolicyWallet.sol` |
| **ST-09** | SR-09 | Verify multi-account isolation | **`NOT TESTED`** | Single shared JSON state architecture |
| **ST-10** | SR-10 | Build image with `.env` present and inspect context | **`PASSED`** | Excluded via `.dockerignore` |
| **ST-11** | SR-02 | Concurrent execution & pending transaction race test | **`NOT TESTED`** | Single-threaded runner excluded concurrency |
| **ST-12** | SR-03 | Conversational assistant anomaly auditing & explanation | **`PASSED`** | `tests/test_assistant.py` (4/4 tests passed) |

---

## 8. Known Risks, Findings, & Residual Exposure

| ID | Finding Description | Affected Component | Likelihood | Impact | Severity | Confidence | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **K-01** | Unauthenticated HTTP administrative & wallet mutation routes | `flask/server.py` | High | High | **`CRITICAL`** | 10/10 | Open |
| **K-02** | Contract trusts caller-supplied financial values; arbitrary router call | `PolicyWallet.sol` | Medium | Critical | **`CRITICAL`** | 10/10 | Open |
| **K-03** | Default client fabricates transaction hashes and confirmations | `contracts/wallet_client.py` | High | High | **`HIGH`** | 10/10 | Open |
| **K-04** | Workflow accepts unauthenticated reviewer strings; premature deployment | `policy/workflow.py` | High | High | **`HIGH`** | 10/10 | Open |
| **K-05** | Single shared JSON state lacks account isolation or ACID semantics | `user/db.py`, `agent/task.py` | High | High | **`HIGH`** | 9/10 | Open |
| **K-06** | Simulator RPC fallback can return simulated success when offline | `contracts/simulator.py` | Medium | High | **`HIGH`** | 9/10 | Open |
| **K-07** | No nonce, replay protection, or expiry deadline in contract/workflow | `PolicyWallet.sol`, `workflow.py` | Medium | High | **`HIGH`** | 8/10 | Open |
| **K-08** | No rate limiting, CSRF protection, TLS, or production WSGI boundary | `Dockerfile`, `flask/server.py` | High* | Medium | **`HIGH`** | 9/10 | Open |
| **K-09** | External market/RPC fallback and static addresses are not proof of live state | `exchange/`, `wallet_client.py` | Medium | Medium | **`MEDIUM`** | 9/10 | Open |
| **K-10** | No verified dependency scan, deployed bytecode match, or live receipt | Repository-wide | Medium | Medium | **`MEDIUM`** | 10/10 | Open |

*\*K-08 rated High likelihood under internet exposure.*

### Risk Heat Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RISK SEVERITY MATRIX                              │
├─────────────────────┬───────────────────┬───────────────────┬───────────────┤
│ LIKELIHOOD \ IMPACT │        LOW        │       MEDIUM      │  HIGH / CRIT  │
├─────────────────────┼───────────────────┼───────────────────┼───────────────┤
│ HIGH                │                   │                   │ K-01, K-03,   │
│                     │                   │                   │ K-04, K-05,   │
│                     │                   │                   │ K-08          │
├─────────────────────┼───────────────────┼───────────────────┼───────────────┤
│ MEDIUM              │                   │ K-09, K-10        │ K-02, K-06,   │
│                     │                   │                   │ K-07          │
├─────────────────────┼───────────────────┼───────────────────┼───────────────┤
│ LOW                 │                   │                   │               │
└─────────────────────┴───────────────────┴───────────────────┴───────────────┘
```

---

## 9. Remediation & Prioritized Action Plan

1. **Block Public Deployment:** Add authentication middleware, session tokens, CSRF protection, TLS termination, and rate limits prior to any exposure outside `localhost`.
2. **Replace Simulated Signing:** Implement an EIP-712 cryptographic signing boundary with domain separation, chain ID binding, account nonces, and verifiable receipt polling.
3. **Harden Contract Execution:** Constrain swap routers to an approved immutable allowlist, attest token prices via signed Chainlink oracles, validate token decimals, and enforce `minAmountOut`.
4. **Enforce Cryptographic Workflow Governance:** Require cryptographic ECDSA signatures from authorized keys for review/approval; strictly reject deployments from `DRAFT`.
5. **Migrate to a Transactional Database:** Replace flat JSON files with PostgreSQL / SQLite with row-level account isolation and ACID transaction locking.
6. **Fail-Closed on RPC Uncertainty:** Explicitly distinguish offline simulation from pending, confirmed, and reverted transactions; never report `CONFIRMED` for local synthetic receipts.

---

## 10. Conclusion & Limitations

WalletAgent (Orvilo) successfully establishes a powerful natural-language policy compilation and formal verification framework. Its local deterministic tests (**94/94 passed**), Docker smoke test, and conversational co-pilot demonstrate strong preflight safety capabilities.

However, the empirical evidence demonstrates that **the application is currently a pre-production sandbox system**. It must not be deployed to handle real funds or exposed to the public internet without remediating findings K-01 through K-08. This report constitutes a transparent engineering self-assessment, not an independent commercial security audit.
