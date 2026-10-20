# WalletAgent (Orvilo): Technical Documentation & Architecture Specification

> **2026 Shenzhen International FinTech Competition (FinTechathon) — International Track**  
> **Host:** Tsinghua PBC School of Finance with WeBank  
> **Theme:** *"AI as a Financial Participant"*  
> **Topic:** **Topic F: Agent Wallet (Autonomous On-Chain Wallet)**  
> **Target Network:** Base Sepolia (EVM Chain ID: `84532`)  
> **Test Suite:** **94 / 94 Passing** (`pytest tests/`) across 13 test files  
> **Classification:** Technical Documentation & System Specification (Version 1.2)

---

## Document Control & System Metadata

| Parameter | Recorded Value | Notes |
| :--- | :--- | :--- |
| **Document Version** | `1.2 (Final Repository Alignment)` | Synchronized with active `main` codebase |
| **Preparation Date** | 20 October 2026 | FinTechathon 2026 (Topic F: Agent Wallet) |
| **Organization** | Orvilo Engineering Team | Repository technical specification |
| **Repository** | `https://github.com/immo2n/WalletAgent` | Active GitHub submission repository |
| **Branch Assessed** | `main` | Production / Submission baseline |
| **Assessed Code Commit** | `7b5139e` | Merged upstream CI, Docker, & Conversational Assistant |
| **Execution Environment** | Python 3.14 · Linux · Web3 EVM Simulator | Base Sepolia (84532); offline simulation by default |
| **Automated Tests** | **94 / 94 Passing** (17.09s) | Regression suite covering all 9 scorecard features + Assistant |
| **Docker Smoke Test** | **11 / 11 Checks Passed** | Verified via `scripts/docker_smoke.py` |

> [!IMPORTANT]
> **Implementation Boundary**: This repository provides a local simulation, formal verification environment, and reactive web dashboard. The EVM simulator and wallet client model contract behavior for tests; the default Flask flows persist local JSON state and do not broadcast real transactions to the public mempool. Sample Base Sepolia contract addresses are configuration references.

---

## 1. Executive Summary & Core Innovation

Autonomous on-chain agent wallets face a fundamental security dilemma: Large Language Models (LLMs) are uniquely adept at parsing semantic human language and reasoning over volatile market regimes, yet they remain inherently probabilistic, prone to hallucinations, and susceptible to prompt injection attacks. Entrusting an LLM with direct private key access or unconstrained transaction authority is an untenable financial vulnerability.

**WalletAgent (Orvilo) resolves this dilemma through a tri-layer defense-in-depth architecture:**
1. **The LLM is Never the Security Boundary**: The LLM functions exclusively as an *untrusted proposer*. It translates conversational intents into formal draft structures, but cannot authorize, execute, or loosen limits.
2. **Dual-Reader Z3 SMT Formal Verification**: User instructions are parsed across two independent channels (a deterministic spaCy rule parser and a schema-constrained LLM synthesizer). Semantic equivalence is formally proved using the **Z3 SMT Solver** over physical domain bounds. Disagreements automatically generate concrete counterexamples fed into an automated feedback repair loop.
3. **Deterministic Multi-Stage Enforcement**: All proposed trades pass through deterministic local invariant gates and EVM pre-execution simulation. The Solidity contract and wallet client define the intended Base Sepolia enforcement boundary.
4. **Cognitive Conversational Assistant**: A LangChain-powered conversational co-pilot (`agent/assistant.py`) provides real-time transaction anomaly auditing, policy invariant explanations, and system telemetry introspection.

---

## 2. FinTechathon 2026 Scorecard: Feature Coverage Matrix

WalletAgent implements all 9 evaluated scorecard requirements plus the conversational co-pilot:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               FINTECHATHON 2026 COMPETITION SCORECARD                                   │
├────┬──────────────────────────────────────┬────────────────────────────────────┬──────────────────────┤
│ #  │ Scorecard Evaluated Feature          │ Primary Implementation Module      │ Verification Evidence│
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 1  │ Natural-Language Instruction Parsing │ policy/readers/rule_reader.py      │ 100% AST Paraphrase  │
│    │ & AST Semantic Compilation           │ policy/readers/llm_reader.py       │ Hash Equivalence     │
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 2  │ Policy Review & Explicit User        │ policy/workflow.py                 │ Multi-Step Stepper   │
│    │ Approval Workflow Pipeline           │ flask/server.py                    │ State Invariants     │
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 3  │ On-Chain Rules: Tokens, Recipients,  │ contracts/PolicyWallet.sol         │ Invariant Bounds in  │
│    │ Spend Caps & Balance Floors          │ policy/onchain.py                  │ Solidity & Z3 SMT    │
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 4  │ Scheduled Transfers & Recurring DCA  │ agent/task.py                      │ Recurring Interval   │
│    │ Execution Queue                      │ agent/runtime.py                   │ Background Daemon    │
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 5  │ Pre-Execution EVM Simulation &       │ contracts/simulator.py             │ eth_call Revert Trace│
│    │ Gas Estimation Preflight             │ reasoning/dry_run.py               │ & Dynamic Buffer     │
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 6  │ Smart Contract On-Chain Policy       │ contracts/PolicyWallet.sol         │ Base Sepolia Tests   │
│    │ Invariant Enforcement                │ contracts/wallet_client.py         │ Custom Solidity Errors│
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 7  │ Transaction History, Explanations    │ user/db.py                         │ Full RAG & Solver    │
│    │ & Reasoning Audit Reports            │ reasoning/engine.py                │ Introspection Modal  │
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 8  │ Emergency Pause, Allowance &         │ contracts/wallet_client.py         │ Instant Killswitch & │
│    │ Operator Key Revocation              │ contracts/PolicyWallet.sol         │ Access Control Drops │
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 9  │ Adversarial Attack Testing Suite     │ contracts/attack_tester.py         │ 6/6 Exploits Blocked │
│    │ (Smart Contract Rejection Evidence)  │ tests/test_scorecard_features.py   │ 100% Modeled Reverts│
├────┼──────────────────────────────────────┼────────────────────────────────────┼──────────────────────┤
│ 10 │ Conversational Assistant & Anomaly   │ agent/assistant.py                 │ LangChain Co-Pilot,  │
│    │ Auditor Co-Pilot                     │ tests/test_assistant.py            │ 4/4 Tests Passing    │
└────┴──────────────────────────────────────┴────────────────────────────────────┴──────────────────────┘
```

---

## 3. Master Architecture & Subsystem Index

WalletAgent is architected into modular, decoupled subsystems:

| Subsystem Specification | Core Topics & Modules | Primary Visual Flowchart |
| :--- | :--- | :--- |
| **Policy Engine & Formal Verification** | Dual readers, AST, dimensional sorts, Z3 SMT solver, counterexamples, hashing | [`visuals/rendered/policy-verification.png`](../visuals/rendered/policy-verification.png) |
| **Agent Runtime & Cognitive Reasoning** | Daemon loop, scheduled DCA queue, market perception, RAG historical regimes, dry-run | [`visuals/rendered/runtime-safety.png`](../visuals/rendered/runtime-safety.png) |
| **EVM Smart Contracts & Security Controls** | `PolicyWallet.sol`, custom typed errors, preflight `eth_call`, killswitches, attack tester | [`visuals/rendered/security-controls.png`](../visuals/rendered/security-controls.png) |
| **User Approval Workflow & Audit Trail** | `DRAFT` $\to$ `ACTIVE` stepper, approval signatures, in-memory ledger, Flask UI | [`visuals/rendered/data-model.png`](../visuals/rendered/data-model.png) |
| **Security Trust & Permission Model** | Role boundaries, owner/operator tiers, simulation boundary, attack vectors | [`visuals/rendered/permission-enforcement.png`](../visuals/rendered/permission-enforcement.png) |
| **Conversational Co-Pilot Subsystem** | `agent/assistant.py`, LangChain router, transaction anomaly auditing, prompt Q&A | [`visuals/rendered/system-context.png`](../visuals/rendered/system-context.png) |

---

## 4. System Architecture Visualizations

### 1. Master Pipeline Topology
Below is the system-wide architecture flow rendered from [`visuals/rendered/policy-verification.png`](../visuals/rendered/policy-verification.png):

![Policy Verification Architecture](../visuals/rendered/policy-verification.png)

### 2. Autonomous Agent & Perception Loop
Rendered from [`visuals/rendered/runtime-safety.png`](../visuals/rendered/runtime-safety.png) and [`visuals/rendered/security-controls.png`](../visuals/rendered/security-controls.png):

![Agent Runtime Safety](../visuals/rendered/runtime-safety.png)

### 3. Permission Enforcement & Trust Boundaries
Rendered from [`visuals/rendered/permission-enforcement.png`](../visuals/rendered/permission-enforcement.png) and [`visuals/rendered/security-trust-boundaries.png`](../visuals/rendered/security-trust-boundaries.png):

![Permission Enforcement](../visuals/rendered/permission-enforcement.png)

---

## 5. Detailed Technical Walkthrough of Core Subsystems

### 5.1 Natural-Language Instruction Parsing & Dual-Channel Synthesis
- **Modules**: `policy/readers/rule_reader.py`, `policy/readers/llm_reader.py`, `policy/ast.py`, `policy/readers/lexicon.py`
- **Core Functionality**:
  - **Deterministic Rule Reader**: Uses `spaCy` dependency tree grammars and explicit keyword registries to extract trigger predicates, action clauses, numeric thresholds, and asset symbols. Operates deterministically without network calls.
  - **Symbolic Inequality Parser**: Recognizes both colloquial phrases (*under*, *less than*, *no more than*, *at least*) and symbolic mathematical operators (`<`, `<=`, `>`, `>=`, `=`, `==`).
  - **Untrusted LLM Synthesizer**: Parses colloquial phrasings, synonyms, and conversational variations into a typed Draft-07 JSON Schema.
  - **Dimensional Type Checking**: Enforces physical sorts (`Sort.USD`, `Sort.GWEI`, `Sort.PERCENT`, `Sort.TOKEN`). Rejects nonsensical mathematical comparisons (e.g. comparing Gwei to USD) at compile time via `policy/typecheck.py`.

### 5.2 Formal Verification & Z3 Mathematical Formulation
The Z3 SMT solver mathematically checks semantic equivalence over physical domain bounds:
$$\forall \vec{x} \in \mathcal{D}_{\text{physical}}, \quad \Phi_{\text{RuleReader}}(\vec{x}) \iff \Phi_{\text{LLMReader}}(\vec{x})$$

Where $\vec{x} = \langle \text{gas}, \text{trade}, \text{balance after}, \text{daily spent} \rangle$ represents physical blockchain state variables.

To verify equivalence, the solver searches for satisfiability of the refutation predicate:
$$\Psi_{\text{refute}} = \mathcal{D}_{\text{physical}} \land \neg \left( \Phi_A \iff \Phi_B \right)$$

- **`UNSAT` (Unsatisfiable)**: No counterexample exists. The two ASTs are provably equivalent under all possible market conditions.
- **`SAT` (Satisfiable)**: Z3 extracts a concrete counterexample $\vec{x}^*$ (e.g. $\text{trade} = \$250, \text{balance after} = \$450$). This counterexample is fed back into Channel B for automated repair (max 2 attempts) before human escalation.

### 5.3 Policy Review & Multi-Stage Approval Stepper
- **Modules**: `policy/workflow.py`, `flask/server.py`
- **Lifecycle Pipeline**:
  $$\text{User Prompt} \xrightarrow{\text{Z3 SMT}} \text{DRAFT} \xrightarrow{\text{Review}} \text{REVIEWED} \xrightarrow{\text{Owner Sign}} \text{DEPLOYABLE} \xrightarrow{\text{Base Sepolia}} \text{ACTIVE}$$
- **Key Guarantees**:
  - Autonomous agents cannot trade against a `DRAFT` or `REVIEWED` policy.
  - Explicit owner signature binds the canonical SHA-256 policy hash.
  - Deployment updates the in-memory `PolicyWalletClient` guard state and registers the agent daemon task.

### 5.4 On-Chain Invariants & Smart Contract Guardrails
- **Modules**: `contracts/PolicyWallet.sol`, `contracts/wallet_client.py`, `contracts/simulator.py`
- **Enforced Invariants**:
  1. **Token Allowlist**: Only whitelisted ERC-20 tokens (`ETH`, `WETH`, `USDC`) can be traded. All other tokens revert with `TokenNotAllowed(address)`.
  2. **Recipient Allowlist**: Outgoing transfers are restricted to approved counterparty addresses.
  3. **Per-Transaction Cap**: Bounds single-trade exposure (e.g., $300 max per trade).
  4. **24-Hour Rolling Daily Cap**: Tracks daily expenditure; reverts with `ExceedsDailyLimit` if $\sum A_{\text{USD}} > \text{DailyCap}$.
  5. **Minimum Balance Reserve Floor**: Reverts with `BelowMinimumBalanceFloor` if projected post-execution balance drops below the verified floor (e.g., $500).
  6. **Emergency Killswitch**: `pause()` immediately locks all outgoing transactions; `revokeOperator()` drops autonomous execution rights.

### 5.5 Autonomous Agent Runtime & DCA Task Queue
- **Modules**: `agent/task.py`, `agent/runtime.py`
- **Core Functionality**:
  - Supports `IMMEDIATE`, `CONDITIONAL_TRIGGER`, and `RECURRING_INTERVAL` schedules.
  - Enables recurring Dollar-Cost Averaging (e.g., *Buy $100 USDC of ETH every 60 seconds while gas $\le$ 20 gwei*).
  - Background daemon checks the schedule queue at 1 Hz, automatically executing swaps as interval timestamps mature while strictly honoring all policy caps.

### 5.6 Conversational Assistant & Anomaly Auditor Co-Pilot
- **Modules**: `agent/assistant.py`, `tests/test_assistant.py`
- **Core Functionality**:
  - **Transaction Anomaly Auditing**: Inspects historical and pending transactions, identifying transfers to unwhitelisted addresses, spending spikes, or reserve floor breaches.
  - **Task Explanation**: Breaks down active autonomous DCA tasks, explaining remaining intervals, gas triggers, and invariant constraints in plain English.
  - **Interactive Web Interface**: Accessible via the responsive floating chat bubble on the web dashboard.
  - **LangChain Integration**: Leverages structured tool routing with automatic fallback to offline deterministic analysis when external LLM endpoints are unreachable.

---

## 6. Complete REST API Reference

The Flask application (`flask/server.py`) exposes 23 endpoints:

| Endpoint | Method | Role / Description | Status |
| :--- | :---: | :--- | :---: |
| `/` | `GET` | Responsive web dashboard UI | `Verified` |
| `/api/market/stream` | `GET` | Server-Sent Events (SSE) telemetry stream | `Verified` |
| `/api/market/state` | `GET` | Snapshot of live Coinbase prices & gas oracle | `Verified` |
| `/api/wallet/state` | `GET` | Wallet balances, active policy, & guard state | `Verified` |
| `/api/wallet/simulate-trade` | `POST` | Preflight EVM simulation & dry-run execution | `Verified` |
| `/api/reasoning/audit` | `GET` | Complete transaction reasoning proof traces | `Verified` |
| `/api/wallet/reset` | `POST` | Reinitializes simulation state to defaults | `Verified` |
| `/api/verify` | `POST` | Natural-language policy compilation & Z3 proof | `Verified` |
| `/api/policy/workflow` | `GET` | Current governance proposal status | `Verified` |
| `/api/policy/review` | `POST` | Moves policy proposal from DRAFT to REVIEWED | `Verified` |
| `/api/policy/approve` | `POST` | Generates approval signature (DEPLOYABLE) | `Verified` |
| `/api/policy/deploy` | `POST` | Activates policy and registers autonomous task | `Verified` |
| `/api/agent/task` | `POST` | Manually configures or updates agent DCA task | `Verified` |
| `/api/agent/pause` | `POST` | Pauses autonomous agent daemon loop | `Verified` |
| `/api/agent/resume` | `POST` | Resumes autonomous agent daemon loop | `Verified` |
| `/api/contract/pause` | `POST` | Activates smart contract emergency pause | `Verified` |
| `/api/contract/unpause` | `POST` | Deactivates emergency pause | `Verified` |
| `/api/contract/revoke-operator` | `POST` | Revokes agent operator authorization | `Verified` |
| `/api/contract/revoke-allowance` | `POST` | Resets DEX router token allowances to zero | `Verified` |
| `/api/contract/invalidate-policy`| `POST` | Invalidates active policy hash | `Verified` |
| `/api/contract/test-attacks` | `POST` | Executes 6-vector adversarial attack suite | `Verified` |
| `/api/assistant/chat` | `POST` | Conversational assistant Q&A and task explanation | `Verified` |
| `/api/assistant/audit` | `POST` | Anomaly transaction analysis & risk report | `Verified` |

---

## 7. Automated Test Suite Evidence

The complete test suite contains **94 automated unit and integration tests** across 13 test files:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

```text
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0
rootdir: /home/immo2n/Moon/WalletAgent
plugins: anyio-4.15.1, langsmith-0.14.11
collected 94 items

tests/policy/test_compile_compare.py ...                                 [  3%]
tests/policy/test_loop.py ......                                         [  9%]
tests/policy/test_mutations.py ...........                               [ 21%]
tests/policy/test_paraphrase_hash.py ...                                 [ 24%]
tests/policy/test_prompts_t1.py ..........                               [ 35%]
tests/policy/test_readback.py ..                                         [ 37%]
tests/policy/test_readers_llm_mock.py ...                                [ 40%]
tests/policy/test_readers_rule.py .........                              [ 50%]
tests/policy/test_sanity.py ....                                         [ 54%]
tests/policy/test_sorts_ast.py ....                                      [ 58%]
tests/policy/test_typecheck.py .....                                     [ 63%]
tests/test_agent.py ....                                                 [ 68%]
tests/test_assistant.py ....                                             [ 72%]
tests/test_exchange.py ...                                               [ 75%]
tests/test_reasoning.py ........                                         [ 84%]
tests/test_scorecard_features.py ...........                             [ 95%]
tests/test_user_db.py ....                                               [100%]

============================= 94 passed in 17.09s ==============================
```

---

## 8. Deployment & Reproduction Instructions

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.11 – 3.14)
- Docker & Docker Compose (optional for containerized deployment)
- Node.js & Mermaid CLI (only required if re-rendering documentation diagrams)

### 2. Environment Configuration (`.env`)
```dotenv
# LLM Provider Configuration (mock for offline evaluation, groq for live inference)
LLM_PROVIDER=mock
LLM_MODEL=llama-3.3-70b-versatile

# Base Sepolia Network Details
CHAIN_ID=84532
RPC_URL=https://sepolia.base.org
EXPLORER_URL=https://sepolia.basescan.org

# Smart Contract Deployment
POLICY_WALLET_ADDRESS=0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E
WALLET_OWNER_ADDRESS=0xD05B1Af82376528eF75b23D1C2B5C22B92747cAB
EXPLORER_URL=https://sepolia.basescan.org/address/0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E
```

### 3. Launching Locally
```bash
source .venv/bin/activate
PYTHONPATH=. python main.py --host 127.0.0.1 --port 5000
```
Open your browser to `http://localhost:5000` to interact with the responsive dashboard, test natural language policies, simulate market spikes, and inspect the real-time reasoning and verification pipeline.

### 4. Docker Container Smoke Validation
```bash
docker build -t orvilo:latest .
docker run -d --name orvilo-test -p 5000:5000 orvilo:latest
python scripts/docker_smoke.py http://127.0.0.1:5000
docker rm -f orvilo-test
```
