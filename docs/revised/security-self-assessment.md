# WalletAgent (Orvilo) — Security Self-Assessment Report

> **User-Defined On-Chain Guardrails for Autonomous AI Wallets**  
> **FinTechathon 2026 · Topic F — Agent Wallet**  
> **Classification:** `FINAL SELF-ASSESSMENT · NOT AN INDEPENDENT AUDIT`

---

## Document Control & System Metadata

| Parameter | Value | Notes |
| :--- | :--- | :--- |
| **Document Version** | `1.2 (Final)` | Current codebase — `main` branch |
| **Preparation Date** | 20 October 2026 | FinTechathon 2026 (Topic F) |
| **Report Status** | Final self-assessment | Prepared by Orvilo Engineering Team |
| **Repository** | `https://github.com/immo2n/WalletAgent` | Active submission repository |
| **Branch** | `main` | Production / submission baseline |
| **Environment** | Python 3.14 · Linux venv · Docker | Base Sepolia `84532`; offline simulation by default |
| **Automated Tests** | **94 / 94 Passing** (`pytest tests/`) | 100% pass across 13 test files |
| **Docker Smoke Test** | **11 / 11 Checks Passed** | Verified via `scripts/docker_smoke.py` |
| **Deployed Contract** | `0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E` | Live on Base Sepolia — 5 on-chain txs confirmed |
| **Open Findings** | 10 Recorded (2 Critical, 6 High, 2 Medium) | Pre-production sandbox boundaries disclosed |

> **Evidence Convention:**
> - **Designed:** Described as an intended control in code comments or documentation.
> - **Implemented:** Present and inspectable in the current source code.
> - **Verified:** Exercised and confirmed by the 94-test automated suite or Docker smoke test.  
> A control is not treated as verified merely because a comment, UI label, or simulated response claims it is active.

---

## 1. Executive Summary

WalletAgent (Orvilo) is a simulation-first Flask application that:
- Converts natural-language trading constraints into a typed policy AST
- Formally proves semantic equivalence between deterministic and LLM-derived interpretations using Z3 SMT
- Enforces a human multi-stage review and approval workflow before any autonomous execution
- Runs a background autonomous DCA agent loop that evaluates policies at 1 Hz
- Provides real-time anomaly auditing via a LangChain conversational co-pilot

The reference smart contract `PolicyWallet.sol` is deployed live to **Base Sepolia** (`Chain ID 84532`) with owner/operator authorization, policy hashes, token and recipient allowlists, spending caps, reserve floors, pause, and allowance-revocation functions. Five genuine on-chain transactions confirm its deployment and functional lifecycle.

The application defaults to **local simulation mode**: the Docker image uses `LLM_PROVIDER=mock`, and the Python wallet client generates simulation receipts rather than broadcasting signed transactions for routine agent evaluations. The five verified on-chain transactions in `docs/evidence/basescan_transactions.json` represent the complete smart contract lifecycle (deploy, setPolicy, pause, unpause, setOperator).

### Outcome Summary by Area

| Area | Status | Basis |
| :--- | :---: | :--- |
| Policy parsing & deterministic guard logic | `Verified` | 94/94 tests pass; Docker smoke test |
| Human-review workflow | `Partial` | Implemented; happy-path API transitions verified |
| Solidity access modifiers & guards | `Source Reviewed + Live` | Deployed and confirmed on Base Sepolia |
| Permission tiers | `Partial` | Owner/operator modeled; HTTP layer unauthenticated |
| Authentication & account isolation | `Not Implemented` | All Flask routes reachable without identity proof |
| Real signing & on-chain execution | `Partial` | 5 lifecycle txs on-chain; routine evaluations simulated |
| Conversational Co-Pilot | `Verified` | `tests/test_assistant.py` — 4/4 passing |
| Production readiness | `Not Ready` | 2 Critical, 6 High findings must be remediated before handling real funds |

### Principal Risks
1. **Unauthenticated Administrative Routes (K-01):** Wallet-mutating and policy-administering routes are callable by any client that reaches the server.
2. **Unsafe Contract Execution Design (K-02):** `executeTransfer` accepts caller-supplied USD and post-balance values, and performs arbitrary router calls.
3. **Synthetic Approvals & Hashes (K-03, K-04):** Default signing and approval are generated strings; deployment can proceed before review in local flows.
4. **Fallbacks that Look Like Success (K-06):** Simulated execution can appear successful when RPC or deployment state is unavailable.

### What is Working Well
- Deterministic policy parsing, dimensional type-checking, and Z3 equivalence comparison are proven across **94 passing tests**.
- The Solidity contract contains robust access modifiers (`onlyOwner`, `onlyAuthorized`, `whenNotPaused`), custom typed errors, and invariant checks — deployed and confirmed on Base Sepolia.
- Docker image runs as a non-root user (`orvilo`), excludes `.env` from build context, and defines an active health check.
- The conversational assistant (`agent/assistant.py`) provides real-time auditability via LangChain structured tool routing.

---

## 2. Assessment Scope & System Identification

### In-Scope Components

| Component | Repository Path | Role |
| :--- | :--- | :--- |
| **Flask Dashboard & API** | `flask/server.py` | UI, REST API, SSE telemetry streaming |
| **Policy AST, Readers & Parser** | `policy/` | Dual-reader grammar, Z3 solver, AST hashing |
| **Rule Lexicon & Comparators** | `policy/readers/lexicon.py` | Triggers, caps, symbolic inequalities (`<`, `<=`, `>`, `>=`, `=`, `==`) |
| **Approval Workflow** | `policy/workflow.py` | Governance stepper (`DRAFT` → `ACTIVE`) |
| **Autonomous Agent Runtime** | `agent/runtime.py`, `agent/task.py` | 1 Hz daemon evaluation loop, task state machine |
| **Conversational Co-Pilot** | `agent/assistant.py` | LangChain assistant for anomaly auditing and task explanation |
| **Wallet & Transaction Store** | `user/db.py`, `user/models.py` | Balance tracking and transaction logging |
| **EVM Simulator & Attack Suite** | `contracts/simulator.py`, `contracts/attack_tester.py` | Preflight simulation, 6/6 adversarial exploit checks |
| **Solidity Reference Contract** | `contracts/PolicyWallet.sol`, `contracts/abi.py` | Invariant defense — deployed live on Base Sepolia |
| **Client, Docker & CI** | `contracts/wallet_client.py`, `Dockerfile`, `.github/workflows/ci.yml` | Containerization, simulation client, automated CI |
| **Market & Gas Integration** | `exchange/` | Coinbase WebSocket feed, simulated gas estimation |

### Excluded Evidence
- Private keys and production secrets
- Live Base Sepolia mainnet transaction receipts beyond the 5 documented contract lifecycle transactions
- Independent third-party smart contract audit

---

## 3. Assessment Methodology & Rating Criteria

1. **Source Code Review:** Exhaustive analysis of Flask routes, state management, policy loop, Z3 verification, task runtime, contract client, Solidity code, Docker, and CI.
2. **Automated Test Suite:** `PYTHONPATH=. pytest -q` → **94 passed** across 13 test files.
3. **Docker Smoke Test:** `scripts/docker_smoke.py` → **11/11 checks passed**.
4. **Live On-Chain Verification:** 5 Base Sepolia transactions confirmed via RPC (`eth_getTransactionByHash`) and BaseScan explorer.
5. **Adversarial Attack Simulation:** 6 scorecard exploit vectors tested — all confirmed reverting with typed Solidity errors.

### Rating Definitions

| Dimension | Meaning |
| :--- | :--- |
| **Likelihood** | **Low:** constrained · **Medium:** plausible with access · **High:** directly reachable |
| **Impact** | **Low:** limited integrity effect · **Medium:** material application effect · **High:** fund-control effect |
| **Severity** | **Critical:** direct path to unauthorized value movement · **High:** serious control gap · **Medium:** defense-in-depth gap |
| **Confidence** | Evidence confidence 1/10–10/10 based on empirical verification |

---

## 4. Security Architecture & Threat Model

### Key Assets
- **Wallet balances and transaction history** — Direct financial value; basis for audit reconciliation
- **Active policy hash, caps, allowlists, reserve floor, and pause state** — Define what the autonomous agent may do
- **Owner/operator authority and signing credentials** — Compromise gives control over funds
- **Policy proposals, reviews, approvals, and deployment records** — Proof of human governance

### Threat Scenarios

| ID | Threat | Consequence | Finding |
| :--- | :--- | :--- | :--- |
| **T-1** | Remote client calls pause, reset, or approval routes directly | Policy and wallet state altered without identity proof | K-01 |
| **T-2** | Operator supplies misleading USD value or arbitrary router calldata | Spending caps and reserve floor bypassed on-chain | K-02 |
| **T-3** | Generated simulation identifier presented as confirmed transaction | False assurance; distorted audit trail | K-03, K-06 |
| **T-4** | Proposal deployed from `DRAFT` with arbitrary string name | Human-in-the-loop guarantee defeated | K-04 |
| **T-5** | Stale approval or execution replayed after deadline | Outdated authority reused | K-07 |
| **T-6** | Concurrent access to shared JSON store | Lost updates; cross-user state pollution | K-05 |

---

## 5. Security Requirements & Verification Matrix

| ID | Security Requirement | Implementation Evidence | Result |
| :--- | :--- | :--- | :---: |
| **SR-01** | Only owner can change policy or emergency state | Solidity `onlyOwner` in `PolicyWallet.sol` | `Source Reviewed + Live` |
| **SR-02** | Operator actions bounded by policy invariants | `_verifyGuards`, caps, allowlists, floor, pause | `Verified (Local)` |
| **SR-03** | Policy interpretation independently checked | Rule reader, LLM reader, Z3 SMT proof | **`Verified (94/94)`** |
| **SR-04** | Human approval precedes deployment | `PolicyWorkflowManager` multi-stage stepper | `Partial` |
| **SR-05** | Unauthorized HTTP callers cannot mutate state | Not implemented in current release | **`FAILED`** |
| **SR-06** | Execution values derived from trusted chain state | Not implemented in current release | **`FAILED`** |
| **SR-07** | Revocation immediately blocks future execution | Contract `revokeOperator`; local flag gap noted (EE-06) | `Partial` |
| **SR-08** | Contract lifecycle verified on-chain | 5 txs confirmed on Base Sepolia | **`Verified (On-Chain)`** |
| **SR-09** | Account data isolated by authenticated owner | Not implemented — single shared JSON store | **`Not Implemented`** |
| **SR-10** | Secrets not baked into image or repository | `.dockerignore`, `.env.example`, mock defaults | `Verified` |

---

## 6. Key Custody, Signing Authority & Permissions

### Implemented / Modeled Permission Tiers

| Tier | Holder | Allowed Actions | Restrictions | Enforcement | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Owner** | Human wallet owner | Set/invalidate policy, manage operators, pause/unpause, revoke allowances | Highest privilege | Solidity `onlyOwner` | Implemented in contract; API layer unauthenticated |
| **Authorized Operator** | Autonomous agent | Guarded swap/transfer | Policy hash, caps, allowlists, floor, pause | Solidity `onlyAuthorized` + `_verifyGuards` | Implemented in contract; Python client gap (EE-06) |
| **Reviewer** | Security reviewer | Mark proposal reviewed | Precondition for approval | String field `reviewed_by` | Modeled; not authenticated |
| **Approver** | Owner / Approver | Mark proposal deployable | Human approval signature | String field `approved_by` | Modeled; no cryptographic check |
| **Public HTTP Caller** | Any network client | Actual caller of exposed routes | None in Flask layer | No auth middleware | **Unrestricted (Critical Gap)** |

---

## 7. Security Test Register & Evidence

| ID | Requirement | Procedure | Result | Evidence |
| :--- | :--- | :--- | :---: | :--- |
| **ST-01** | SR-03 | Run full Python test suite | **PASSED** | **94 passed** across 13 test files |
| **ST-02** | SR-03/SR-04 | Build Docker image; run policy verification | **PASSED** | Docker smoke test — 11/11 checks |
| **ST-03** | SR-04 | Review, approve, and deploy policy proposal | **PASSED** | Workflow stepper transitions verified |
| **ST-04** | SR-02 | Execute 6 modeled adversarial penetration checks | **PASSED** | 6/6 reverted with typed Solidity errors |
| **ST-05** | SR-07 | Pause/unpause, revoke operator, invalidate policy | **PASSED** | Local client state transitions verified |
| **ST-06** | SR-08 | Confirm genuine on-chain contract lifecycle | **PASSED** | 5 txs confirmed on Base Sepolia via RPC + BaseScan |
| **ST-07** | SR-05 | Attempt unauthenticated administrative API calls | **FAILED** | Mutating routes accept unauthenticated JSON |
| **ST-08** | SR-06 | Prove contract derives values from trusted on-chain state | **FAILED** | Caller-supplied arguments in `PolicyWallet.sol` |
| **ST-09** | SR-09 | Verify multi-account isolation | **NOT TESTED** | Single shared JSON state architecture |
| **ST-10** | SR-10 | Build image with `.env` present; inspect context | **PASSED** | Excluded via `.dockerignore` |
| **ST-11** | SR-02 | Concurrent execution race test | **NOT TESTED** | Single-threaded runner excluded concurrency |
| **ST-12** | SR-03 | Conversational assistant anomaly auditing | **PASSED** | `tests/test_assistant.py` — 4/4 passing |

---

## 8. Known Risks, Findings & Residual Exposure

| ID | Finding | Component | Likelihood | Impact | Severity | Confidence | Status |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **K-01** | Unauthenticated administrative & wallet mutation routes | `flask/server.py` | High | High | **CRITICAL** | 10/10 | Open |
| **K-02** | Contract trusts caller-supplied financial values; arbitrary router call | `PolicyWallet.sol` | Medium | Critical | **CRITICAL** | 10/10 | Open |
| **K-03** | Default client fabricates simulation receipts and confirmations | `contracts/wallet_client.py` | High | High | **HIGH** | 10/10 | Open |
| **K-04** | Workflow accepts unauthenticated reviewer strings; premature deployment possible | `policy/workflow.py` | High | High | **HIGH** | 10/10 | Open |
| **K-05** | Single shared JSON state — no account isolation or ACID semantics | `user/db.py`, `agent/task.py` | High | High | **HIGH** | 9/10 | Open |
| **K-06** | Simulator RPC fallback returns simulated success when offline | `contracts/simulator.py` | Medium | High | **HIGH** | 9/10 | Open |
| **K-07** | No nonce, replay protection, or expiry deadline in contract or workflow | `PolicyWallet.sol`, `workflow.py` | Medium | High | **HIGH** | 8/10 | Open |
| **K-08** | No rate limiting, CSRF protection, TLS, or production WSGI boundary | `Dockerfile`, `flask/server.py` | High* | Medium | **HIGH** | 9/10 | Open |
| **K-09** | External market/RPC fallback and static addresses not proof of live state | `exchange/`, `wallet_client.py` | Medium | Medium | **MEDIUM** | 9/10 | Open |
| **K-10** | No verified dependency scan, deployed bytecode match, or independent receipt | Repository-wide | Medium | Medium | **MEDIUM** | 10/10 | Open |

*K-08 rated High likelihood under internet exposure.*

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

1. **Block Public Deployment** — Add authentication middleware, session tokens, CSRF protection, TLS termination, and rate limits before any exposure outside `localhost`.
2. **Replace Simulated Signing** — Implement EIP-712 cryptographic signing with domain separation, chain ID binding, account nonces, and verifiable receipt polling via RPC.
3. **Harden Contract Execution** — Constrain swap routers to an approved immutable allowlist; attest token prices via signed Chainlink oracles; enforce `minAmountOut`; validate token decimals.
4. **Enforce Cryptographic Workflow Governance** — Require ECDSA signatures from authorized keys for review/approval; reject deployments from `DRAFT` state.
5. **Migrate to Transactional Database** — Replace flat JSON files with PostgreSQL / SQLite with row-level account isolation and ACID locking.
6. **Fail-Closed on RPC Uncertainty** — Never report `CONFIRMED` for local synthetic receipts. Explicitly distinguish: offline simulation / pending / confirmed / reverted.

---

## 10. Conclusion & Limitations

WalletAgent (Orvilo) establishes a powerful natural-language policy compilation and formal verification framework. Its local deterministic tests (**94/94 passed**), Docker smoke test, five live on-chain Base Sepolia transactions, and conversational co-pilot demonstrate strong preflight safety and auditability capabilities.

The empirical evidence shows that **the application is a pre-production sandbox system**. It must not be deployed to handle real funds or exposed to the public internet without remediating findings K-01 through K-08. This report constitutes a transparent engineering self-assessment, not an independent commercial security audit.
