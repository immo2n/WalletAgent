# WalletAgent (Orvilo) — Technical Documentation & Architecture Specification

> **2026 Shenzhen International FinTech Competition (FinTechathon) — International Track**  
> **Host:** Tsinghua PBC School of Finance with WeBank  
> **Theme:** *"AI as a Financial Participant"*  
> **Topic:** **Topic F — Agent Wallet (Autonomous On-Chain Wallet)**  
> **Target Network:** Base Sepolia (EVM Chain ID: `84532`)  
> **Test Suite:** **94 / 94 Passing** (`pytest tests/`) across 13 test files

---

## Document Control & System Metadata

| Parameter | Value | Notes |
| :--- | :--- | :--- |
| **Document Version** | `1.2 (Final)` | Current codebase — `main` branch |
| **Preparation Date** | 20 October 2026 | FinTechathon 2026 (Topic F) |
| **Organization** | Orvilo Engineering Team | Repository technical specification |
| **Repository** | `https://github.com/immo2n/WalletAgent` | Active submission repository |
| **Branch** | `main` | Production / submission baseline |
| **Execution Environment** | Python 3.14 · Linux · Web3 EVM Simulator | Base Sepolia `84532`; offline simulation by default |
| **Automated Tests** | **94 / 94 Passing** | 13 test files, all scorecard features + assistant |
| **Docker Smoke Test** | **11 / 11 Checks Passed** | Verified via `scripts/docker_smoke.py` |
| **Deployed Contract** | `0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E` | Live on Base Sepolia; 5 on-chain txs confirmed |

---

## 1. Executive Summary & Core Innovation

Autonomous on-chain agent wallets face a fundamental security dilemma: LLMs excel at parsing semantic human language and reasoning over volatile market regimes, yet they remain probabilistic, prone to hallucinations, and susceptible to prompt injection. Entrusting an LLM with direct private key access or unconstrained transaction authority is an unacceptable financial vulnerability.

**WalletAgent (Orvilo) resolves this with a tri-layer defense-in-depth architecture:**

1. **The LLM is Never the Security Boundary** — The LLM functions exclusively as an *untrusted proposer*. It translates conversational intents into formal draft structures but cannot authorize, execute, or loosen any limit.

2. **Dual-Reader Z3 SMT Formal Verification** — User instructions are parsed by two independent channels: a deterministic spaCy rule parser and a schema-constrained LLM synthesizer. Semantic equivalence is formally proved using the **Z3 SMT Solver** over physical domain bounds. Disagreements produce concrete counterexamples fed into an automated repair loop.

3. **Deterministic Multi-Stage Enforcement** — All proposed trades pass through deterministic local invariant gates and EVM pre-execution simulation before any state mutation. The Solidity contract (`contracts/PolicyWallet.sol`) and wallet client define the on-chain enforcement boundary deployed to Base Sepolia.

4. **Cognitive Conversational Co-Pilot** — A LangChain-powered assistant (`agent/assistant.py`) provides real-time transaction anomaly auditing, invariant explanations, and autonomous task introspection — accessible via the dashboard chat bubble.

---

## 2. FinTechathon 2026 Scorecard — Feature Coverage Matrix

WalletAgent implements all 9 evaluated scorecard requirements plus the conversational co-pilot:

| # | Scorecard Feature | Primary Modules | Evidence |
| :---: | :--- | :--- | :--- |
| **1** | Natural-Language Instruction Parsing & AST Compilation | `policy/readers/rule_reader.py`, `policy/readers/llm_reader.py`, `policy/ast.py` | 100% AST paraphrase hash equivalence |
| **2** | Policy Review & Explicit User Approval Workflow | `policy/workflow.py`, `flask/server.py` | 4-stage stepper; state invariants verified |
| **3** | On-Chain Rules: Tokens, Recipients, Caps & Balance Floors | `contracts/PolicyWallet.sol`, `policy/onchain.py` | Invariant bounds in Solidity + Z3 SMT |
| **4** | Scheduled Transfers & Recurring DCA Execution Queue | `agent/task.py`, `agent/runtime.py` | Recurring interval background daemon |
| **5** | Pre-Execution EVM Simulation & Gas Estimation Preflight | `contracts/simulator.py`, `reasoning/dry_run.py` | `eth_call` revert trace + dynamic buffer |
| **6** | Smart Contract On-Chain Policy Invariant Enforcement | `contracts/PolicyWallet.sol`, `contracts/wallet_client.py` | Base Sepolia live deployment; custom Solidity errors |
| **7** | Transaction History, Explanations & Reasoning Audit Reports | `user/db.py`, `reasoning/engine.py` | Full RAG + solver introspection modal |
| **8** | Emergency Pause, Allowance & Operator Key Revocation | `contracts/wallet_client.py`, `contracts/PolicyWallet.sol` | Instant killswitch; access control drops |
| **9** | Adversarial Attack Testing Suite | `contracts/attack_tester.py`, `tests/test_scorecard_features.py` | 6/6 exploits blocked — 100% modeled reverts |
| **10** | Conversational Assistant & Anomaly Auditor Co-Pilot | `agent/assistant.py`, `tests/test_assistant.py` | LangChain co-pilot; 4/4 tests passing |

---

## 3. System Architecture

### Master Pipeline

```
Natural Language Prompt
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    DUAL-READER PARSING LAYER                  │
│  ┌──────────────────────┐   ┌──────────────────────────────┐  │
│  │  Rule Reader (spaCy) │   │  LLM Reader (Schema-Bound)   │  │
│  │  Deterministic AST   │   │  Untrusted Proposer          │  │
│  └──────────┬───────────┘   └─────────────┬────────────────┘  │
│             └────────────────────┬─────────┘                   │
└──────────────────────────────────│────────────────────────────┘
                                   ▼
┌───────────────────────────────────────────────────────────────┐
│              Z3 SMT FORMAL VERIFICATION GATE                  │
│  ∀x ∈ Domain: Φ_RuleReader(x) ⟺ Φ_LLMReader(x)              │
│  UNSAT → Equivalent (SAT) | SAT → Counterexample → Repair    │
└──────────────────────────────────┬────────────────────────────┘
                                   ▼
┌───────────────────────────────────────────────────────────────┐
│             MULTI-STAGE APPROVAL WORKFLOW                     │
│  DRAFT → REVIEWED → DEPLOYABLE → ACTIVE                      │
│  (Agent cannot trade against DRAFT or REVIEWED policy)       │
└──────────────────────────────────┬────────────────────────────┘
                                   ▼
┌───────────────────────────────────────────────────────────────┐
│            AUTONOMOUS AGENT RUNTIME DAEMON (1 Hz)             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  EVM Preflight Simulator (contracts/simulator.py)       │  │
│  │  • Token allowlist  • Recipient allowlist               │  │
│  │  • Per-tx cap       • Daily rolling cap                 │  │
│  │  • Balance floor    • Emergency pause state             │  │
│  └────────────────────────┬────────────────────────────────┘  │
│                            │ Guards Pass                       │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  PolicyWallet.sol — Base Sepolia (Chain ID 84532)       │  │
│  │  Deployed: 0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E  │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘

Conversational Co-Pilot (agent/assistant.py)
  └─► Anomaly detection · Invariant explanation · Task Q&A
```

### Module Index

| Subsystem | Core Modules | Role |
| :--- | :--- | :--- |
| **Policy Engine & Formal Verification** | `policy/loop.py`, `policy/ast.py`, `policy/typecheck.py` | Dual readers, AST, dimensional sorts, Z3 SMT solver |
| **Agent Runtime & DCA Queue** | `agent/runtime.py`, `agent/task.py`, `agent/reasoning.py` | 1 Hz daemon, scheduled tasks, RAG regime matching |
| **EVM Contracts & Security** | `contracts/PolicyWallet.sol`, `contracts/simulator.py`, `contracts/attack_tester.py` | On-chain guards, preflight simulation, attack vectors |
| **User Approval & Audit Trail** | `policy/workflow.py`, `user/db.py`, `user/models.py` | DRAFT→ACTIVE stepper, transaction ledger |
| **Market & Gas Integration** | `exchange/feed.py`, `exchange/gas.py` | Coinbase WebSocket feed, simulated gas oracle |
| **Conversational Co-Pilot** | `agent/assistant.py` | LangChain router, anomaly auditing, task explanation |
| **Flask Dashboard & API** | `flask/server.py`, `flask/templates/index.html` | Responsive web UI, 23 REST endpoints, SSE stream |

---

## 4. Technical Walkthrough of Core Subsystems

### 4.1 Natural-Language Instruction Parsing & Dual-Channel Synthesis

**Modules:** `policy/readers/rule_reader.py`, `policy/readers/llm_reader.py`, `policy/ast.py`, `policy/readers/lexicon.py`

- **Deterministic Rule Reader:** Uses `spaCy` dependency tree grammars and explicit keyword registries to extract trigger predicates, action clauses, numeric thresholds, and asset symbols — fully offline, no network calls.
- **Symbolic Inequality Parser:** Recognizes both colloquial phrases (*under*, *less than*, *no more than*, *at least*) and symbolic mathematical operators (`<`, `<=`, `>`, `>=`, `=`, `==`).
- **Untrusted LLM Synthesizer:** Parses phrasings and synonyms into a Draft-07 JSON Schema. Treated as untrusted — output must survive Z3 equivalence check.
- **Dimensional Type Checking:** Enforces physical sorts (`Sort.USD`, `Sort.GWEI`, `Sort.PERCENT`, `Sort.TOKEN`) via `policy/typecheck.py`. Nonsensical comparisons (e.g., Gwei vs USD) are rejected at compile time.

### 4.2 Formal Verification — Z3 SMT Formulation

The Z3 SMT solver formally proves semantic equivalence between both readers over physical blockchain state variables:

```
State vector:  x = ⟨ gas_gwei, trade_usd, balance_after_usd, daily_spent_usd ⟩
Physical domain: D = { gas ∈ [0, 5000], trade ∈ [0, 10⁶], balance ∈ [0, 10⁶], spent ∈ [0, 10⁶] }

Equivalence:   ∀x ∈ D:  Φ_RuleReader(x) ⟺ Φ_LLMReader(x)

Refutation:    Ψ_refute = D ∧ ¬(Φ_A ⟺ Φ_B)
  • UNSAT → No counterexample. Proofs complete. Policy deployable.
  • SAT   → Z3 extracts concrete x* (e.g., trade=$250, balance_after=$450).
             Counterexample feeds into automatic Channel B repair loop (max 2 attempts).
```

### 4.3 Policy Review & Multi-Stage Approval Stepper

**Modules:** `policy/workflow.py`, `flask/server.py`

```
User Prompt ──(Z3 SMT)──► DRAFT ──(Review)──► REVIEWED ──(Owner Sign)──► DEPLOYABLE ──(Base Sepolia)──► ACTIVE
```

- Autonomous agents **cannot trade** against a `DRAFT` or `REVIEWED` policy.
- Explicit owner signature binds the canonical SHA-256 policy hash.
- Deployment updates the `PolicyWalletClient` guard state and registers the agent daemon task.

### 4.4 On-Chain Invariants & Smart Contract Guards

**Modules:** `contracts/PolicyWallet.sol`, `contracts/wallet_client.py`, `contracts/simulator.py`

Six invariants are enforced both in the local Python preflight and in the deployed Solidity contract:

| Invariant | Guard Mechanism | Revert Error |
| :--- | :--- | :--- |
| Token allowlist | Only `ETH`, `WETH`, `USDC` permitted | `TokenNotAllowed(address)` |
| Recipient allowlist | Outgoing transfers restricted to approved addresses | `RecipientNotAllowed(address)` |
| Per-transaction cap | Single-trade max (e.g., $500) | `ExceedsPerTxCap(uint256, uint256)` |
| Daily rolling cap | 24h expenditure tracked; reverts on breach | `ExceedsDailyLimit(uint256, uint256)` |
| Minimum balance floor | Post-execution projected balance must exceed floor (e.g., $500) | `BelowMinimumBalanceFloor(uint256, uint256)` |
| Emergency killswitch | `pause()` instantly locks all outgoing transactions; `revokeOperator()` drops agent rights | `WalletPaused()` / `UnauthorizedOperator(address)` |

### 4.5 Autonomous Agent Runtime & DCA Task Queue

**Modules:** `agent/task.py`, `agent/runtime.py`

- Supports `IMMEDIATE`, `CONDITIONAL_TRIGGER`, and `RECURRING_INTERVAL` schedules.
- Enables recurring Dollar-Cost Averaging (e.g., *Buy $100 USDC of ETH every 60 seconds while gas ≤ 20 gwei*).
- Background daemon evaluates the schedule queue at 1 Hz, executing swaps as interval timestamps mature while strictly honoring all caps.
- Each execution produces a full **Reasoning Report** capturing: live market data, RAG regime match, dry-run simulation, Z3 gate result, and final decision — all surfaced in the UI Reasoning Modal.

### 4.6 RAG-Driven Market Regime Matching & Dry-Run Simulation

**Modules:** `reasoning/engine.py`, `reasoning/rag.py`, `reasoning/dry_run.py`

Before any trade executes:
1. **RAG Regime Lookup:** Matches current market conditions against a historical regime registry using vector similarity. Returns `historical_win_rate`, `expected_return_24h_pct`, and `risk_level`.
2. **Dry-Run Simulation:** Estimates post-swap ETH received, slippage, and projected 24h value delta. Aborts if `risk_score > 7.0 / 10.0`.
3. **Z3 Gate:** Formally verifies that projected `balance_after >= min_floor` and `trade_amount <= per_tx_cap`.

### 4.7 Conversational Assistant & Anomaly Auditor Co-Pilot

**Modules:** `agent/assistant.py`, `tests/test_assistant.py`

- **Anomaly Detection:** Inspects historical and pending transactions for transfers to unwhitelisted addresses, spending spikes, or reserve floor breaches.
- **Task Explanation:** Breaks down active DCA tasks — remaining intervals, gas triggers, invariant constraints — in plain English.
- **Interactive Chat Bubble:** Accessible on the main dashboard via LangChain structured tool routing.
- **Offline Fallback:** Automatic fallback to deterministic analysis when external LLM endpoints are unreachable.

---

## 5. Complete REST API Reference

The Flask application (`flask/server.py`) exposes 23 endpoints:

| Endpoint | Method | Description | Status |
| :--- | :---: | :--- | :---: |
| `/` | `GET` | Responsive web dashboard UI | Verified |
| `/api/market/stream` | `GET` | SSE telemetry stream (prices + gas) | Verified |
| `/api/market/state` | `GET` | Snapshot of live Coinbase prices & gas oracle | Verified |
| `/api/wallet/state` | `GET` | Wallet balances, active policy & guard state | Verified |
| `/api/wallet/simulate-trade` | `POST` | Preflight EVM simulation & dry-run execution | Verified |
| `/api/reasoning/audit` | `GET` | Full transaction reasoning proof traces | Verified |
| `/api/wallet/reset` | `POST` | Reinitialize simulation state to defaults | Verified |
| `/api/verify` | `POST` | Natural-language policy compilation & Z3 proof | Verified |
| `/api/policy/workflow` | `GET` | Current governance proposal status | Verified |
| `/api/policy/review` | `POST` | Move policy proposal DRAFT → REVIEWED | Verified |
| `/api/policy/approve` | `POST` | Generate approval signature (DEPLOYABLE) | Verified |
| `/api/policy/deploy` | `POST` | Activate policy and register autonomous task | Verified |
| `/api/agent/task` | `POST` | Configure or update agent DCA task | Verified |
| `/api/agent/pause` | `POST` | Pause autonomous agent daemon loop | Verified |
| `/api/agent/resume` | `POST` | Resume autonomous agent daemon loop | Verified |
| `/api/contract/pause` | `POST` | Activate smart contract emergency pause | Verified |
| `/api/contract/unpause` | `POST` | Deactivate emergency pause | Verified |
| `/api/contract/revoke-operator` | `POST` | Revoke agent operator authorization | Verified |
| `/api/contract/revoke-allowance` | `POST` | Reset DEX router token allowances to zero | Verified |
| `/api/contract/invalidate-policy` | `POST` | Invalidate active policy hash on-chain | Verified |
| `/api/contract/test-attacks` | `POST` | Execute 6-vector adversarial attack suite | Verified |
| `/api/assistant/chat` | `POST` | Conversational assistant Q&A and task explanation | Verified |
| `/api/assistant/audit` | `POST` | Anomaly transaction analysis & risk report | Verified |

---

## 6. Smart Contract — `PolicyWallet.sol`

**Deployed Address:** `0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E` (Base Sepolia)  
**Compiler:** `solc 0.8.20` · **License:** MIT

### Key Functions

| Function | Access | Description |
| :--- | :--- | :--- |
| `setPolicy(bytes32, uint256, uint256, uint256, address[], address[])` | `onlyOwner` | Set policy hash, per-tx cap, daily cap, floor, token & recipient allowlists |
| `executeTransfer(address, address, uint256, uint256, uint256, bytes32)` | `onlyAuthorized` · `whenNotPaused` | Execute guarded transfer enforcing all invariants |
| `pause()` / `unpause()` | `onlyOwner` | Instant emergency killswitch |
| `setOperator(address, bool)` | `onlyOwner` | Grant / revoke autonomous agent authorization |
| `revokeAllowance(address, address)` | `onlyOwner` | Reset ERC-20 DEX router allowance to zero |
| `invalidatePolicy()` | `onlyOwner` | Zero the active policy hash; blocks all agent execution |

### Custom Typed Errors (Solidity)

```solidity
error TokenNotAllowed(address token);
error RecipientNotAllowed(address recipient);
error ExceedsPerTxCap(uint256 amount, uint256 cap);
error ExceedsDailyLimit(uint256 total, uint256 limit);
error BelowMinimumBalanceFloor(uint256 projected, uint256 floor);
error WalletPaused();
error UnauthorizedOperator(address caller);
error InvalidPolicyHash(bytes32 provided, bytes32 active);
```

---

## 7. Automated Test Suite

```
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

========================== 94 passed in 179.81s ================================
```

---

## 8. Deployment & Reproduction

### Prerequisites
- Python 3.10+ (tested 3.11–3.14)
- Docker & Docker Compose (optional)
- Node.js + Mermaid CLI (only for diagram re-rendering)

### Environment Configuration (`.env`)

```dotenv
# LLM Provider (mock = fully offline; groq = live inference)
LLM_PROVIDER=mock
LLM_MODEL=llama-3.3-70b-versatile

# Base Sepolia Network
CHAIN_ID=84532
RPC_URL=https://sepolia.base.org
EXPLORER_URL=https://sepolia.basescan.org

# Deployed Smart Contract
WALLET_CONTRACT_ADDRESS=0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E
WALLET_OWNER_ADDRESS=0xD05B1Af82376528eF75b23D1C2B5C22B92747cAB
```

### Run Locally

```bash
source .venv/bin/activate
PYTHONPATH=. python main.py --host 127.0.0.1 --port 5000
# Open http://localhost:5000
```

### Docker

```bash
docker build -t orvilo:latest .
docker run -d --name orvilo-test -p 5000:5000 orvilo:latest
python scripts/docker_smoke.py http://127.0.0.1:5000
docker rm -f orvilo-test
```
