# WalletAgent (Orvilo) — Execution Evidence Report

> **FinTechathon 2026 · Topic F: Agent Wallet (Autonomous On-Chain Wallet)**  
> **Host:** Tsinghua PBC School of Finance with WeBank  
> **Theme:** *"AI as a Financial Participant"*  
> **Classification:** `SANDBOX EXECUTION EVIDENCE`

---

## Document Control & System Metadata

| Parameter | Value | Notes |
| :--- | :--- | :--- |
| **Document Version** | `1.2 (Final)` | Current codebase — `main` branch |
| **Preparation Date** | 20 October 2026 | FinTechathon 2026 (Topic F) |
| **Evidence Date** | 2026-10-20 (UTC) | Automated sandbox execution |
| **Team / Project** | Orvilo / WalletAgent | Autonomous On-Chain Policy Agent |
| **Repository** | `https://github.com/immo2n/WalletAgent` | Active submission repository |
| **Branch** | `main` | Production / submission baseline |
| **Execution Environment** | Python 3.14 · Linux · Web3 EVM Simulator | Offline mock LLM by default |
| **Automated Tests** | **94 / 94 Passing** (`pytest tests/`) | 13 test files, all features covered |

---

## 1. Executive Summary

This report documents the empirical behavior of WalletAgent (Orvilo) across its seven core execution scenarios: natural language policy compilation, Z3 formal verification, multi-stage approval workflow, autonomous DCA execution, emergency controls, operator revocation, and adversarial smart contract attack testing.

### Summary Metrics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SANDBOX EXECUTION EVIDENCE SUMMARY                    │
├──────────────────────┬──────────────────┬──────────────────┬────────────────┤
│   7 Scenarios Run    │    6 PASSED      │  1 Gap (EE-06)   │ 94 Tests Pass  │
├──────────────────────┼──────────────────┼──────────────────┼────────────────┤
│ 5 On-Chain Tx Mined  │ 6/6 Attacks Stop │ 4 Workflow States│ 100% Test Pass │
└──────────────────────┴──────────────────┴──────────────────┴────────────────┘
```

### Key Findings

1. **Deterministic Guardrail Enforcement** — The preflight EVM simulator accepted compliant $200 trades while instantly rejecting over-cap amounts, unapproved destinations, and all calls while emergency paused (EE-01, EE-02, EE-03, EE-05).
2. **Approval Workflow Progression** — Policies progress strictly through: `DRAFT` → `REVIEWED` → `DEPLOYABLE` → `ACTIVE`. Agents cannot trade against unapproved policies (EE-04).
3. **Smart Contract Rejection Suite** — All 6 adversarial attack vectors reverted with exact typed Solidity custom errors (EE-07).
4. **Conversational Assistant & Anomaly Auditing** — The LangChain co-pilot (`agent/assistant.py`) detects unapproved recipients, flags reserve floor drain attempts, and explains active task constraints in plain English.
5. **Disclosed Gap (EE-06)** — After operator revocation, the Python client (`contracts/wallet_client.py`) returned a synthetic confirmation because sender selection did not consult the local revocation flag. The Solidity contract's `onlyAuthorized` modifier enforces this correctly; the Python client gap is documented and remediation is defined.

---

## 2. System Architecture & Component Roles

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                         WALLETAGENT SYSTEM ARCHITECTURE                              │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  User Prompt ──► Dual-Reader Parsing ──► Z3 SMT Verification ──► Approval Workflow  │
│  (Natural Lang)    (RuleReader +           (Equivalence &          (DRAFT → ACTIVE)  │
│                     LLMReader)              Floor Proof)                              │
│                                                                                      │
│                         ┌──────────────────────────────────────┐                    │
│  Autonomous Daemon ─────►   EVM Preflight (simulator.py)       │                    │
│  (1 Hz evaluation)       │   ↓ caps · floor · allowlists       │                    │
│                          │   ↓ token whitelist · pause state   │                    │
│                          └──────────────┬───────────────────────┘                   │
│                                         │ Guards Pass                                │
│                          ┌──────────────▼───────────────────────┐                   │
│                          │   PolicyWallet.sol (Base Sepolia)    │                   │
│                          │   on-chain invariant enforcement     │                   │
│                          └──────────────────────────────────────┘                   │
│                                                                                      │
│  Conversational Co-Pilot (agent/assistant.py) ← LangChain Router                   │
│   ↳ Anomaly detection · Task explanation · Transaction auditing                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Component Status Register

| Component | Module Path | Status | Role in Evidence |
| :--- | :--- | :--- | :--- |
| **Policy Compiler** | `policy/loop.py` | Executed in-memory | Proves AST equivalence via Z3 SMT solver |
| **Rule Lexicon** | `policy/readers/lexicon.py` | Executed in-memory | Extracts triggers, caps, and symbolic inequalities |
| **Workflow Manager** | `policy/workflow.py` | Executed in-memory | Validates 4-stage human review state transitions |
| **EVM Simulator** | `contracts/simulator.py` | Executed (offline RPC) | Verifies preflight bounds before state mutation |
| **Wallet Client** | `contracts/wallet_client.py` | Executed locally | Tracks local security limits and pause flag |
| **Attack Tester** | `contracts/attack_tester.py` | Executed in-memory | Validates 6/6 typed Solidity error reverts |
| **Assistant Engine** | `agent/assistant.py` | Executed locally | Real-time anomaly auditing & task explanation |
| **Smart Contract** | `contracts/PolicyWallet.sol` | Deployed to Base Sepolia | Live on-chain invariant enforcement |

### Accounts & Permission Tiers

| Address | Role | Authority |
| :--- | :--- | :--- |
| `0xD05B1Af8...7cAB` | Deployer / Owner | Full: deploy, setPolicy, pause, authorize operators |
| `0x71C8366...039A` | Demo Wallet Owner | Recipient of guarded agent-controlled transfers |
| `0xfCF10bE8...3d6E` | PolicyWallet Contract | On-chain invariant enforcement (Base Sepolia `#84532`) |

---

## 3. Execution Scenario Register (EE-01 to EE-07)

All scenarios executed using isolated in-memory stubbing to prevent state pollution between test cases.

| ID | Feature Evaluated | Expected Behavior | Observed Behavior | Outcome |
| :---: | :--- | :--- | :--- | :---: |
| **EE-01** | Authorized Guarded Operation | Accept $200 compliant swap | `SIMULATED_SUCCESS`, gas: 84,500 | **PASSED** |
| **EE-02** | Per-Transaction Cap Rejection | Reject $700 vs $500 cap | `ExceedsPerTxCap(700.0, 500.0)` | **PASSED** |
| **EE-03** | Restricted Destination Rejection | Reject unapproved recipient | `RecipientNotAllowed(0x9999...)` | **PASSED** |
| **EE-04** | Policy Review & Activation | DRAFT → ACTIVE stepper | All 4 states traversed correctly | **PASSED** |
| **EE-05** | Emergency Pause Rejection | Block all ops when paused | `WalletPaused()` | **PASSED** |
| **EE-06** | Post-Revocation Execution | Block revoked operator | Python client confirmed (gap) | **FAILED** |
| **EE-07** | Adversarial Guard Suite (6/6) | 6/6 attacks reverted | 6/6 typed Solidity errors returned | **PASSED** |

---

## 4. Detailed Execution Records

### EE-01 · Authorized Guarded Operation
- **Outcome:** `PASSED`
- **Inputs:** Token: `ETH` · Amount: `$200.00` · Recipient: `0x71C8366...039A` (whitelisted) · Projected balance: `$1,300.00` (above `$500.00` floor)
- **Result:** `SIMULATED_SUCCESS` · Gas estimate: `84,500` · `chain_mutated = false`
- **Significance:** Proves the preflight engine accepts fully compliant operations across all guard dimensions simultaneously.

### EE-02 · Per-Transaction Spending Cap Rejection
- **Outcome:** `PASSED`
- **Inputs:** Token: `ETH` · Amount: `$700.00` vs configured `$500.00` per-tx cap
- **Result:** `SIMULATED_REVERT` → `ExceedsPerTxCap(amount=700.0, cap=500.0)`
- **Significance:** Guard detects and blocks cap breaches before any execution or state mutation.

### EE-03 · Restricted Destination Rejection
- **Outcome:** `PASSED`
- **Inputs:** Amount: `$200.00` · Recipient: `0x9999999999999999999999999999999999999999` (not allowlisted)
- **Result:** `SIMULATED_REVERT` → `RecipientNotAllowed(0x9999...9999)`
- **Significance:** Funds cannot be exfiltrated to arbitrary addresses.

### EE-04 · Policy Review, Approval & Activation Workflow
- **Outcome:** `PASSED`
- **Observed Progression:** `DRAFT` → `REVIEWED` → `DEPLOYABLE` → `ACTIVE`
- **Significance:** Unapproved policies cannot trigger autonomous execution. Multi-stage human-in-the-loop governance enforced.

### EE-05 · Emergency Pause Killswitch
- **Outcome:** `PASSED`
- **Inputs:** Identical parameters to EE-01, with `is_paused = true`
- **Result:** `SIMULATED_REVERT` → `WalletPaused()`
- **Significance:** Emergency pause overrides all other policy parameters instantly.

### EE-06 · Operation Attempted After Operator Revocation
- **Outcome:** `FAILED (Disclosed Gap — F-01)`
- **Inputs:** Revoke operator `0x2B5A...D6cF` (`authorized: false`), then attempt guarded operation
- **Result:** Python client selected the first address from the operator dictionary without checking the revocation flag; returned synthetic `CONFIRMED` response
- **Remediation (F-01):** Add `if not self.authorized_operators.get(operator, False): raise UnauthorizedOperator()` in `contracts/wallet_client.py:execute_onchain_transaction()`. The Solidity contract already enforces `onlyAuthorized` correctly — the gap is Python client only.

### EE-07 · Adversarial Smart Contract Guard Suite (6/6)
- **Outcome:** `PASSED`
- **Attack Vectors Tested:**
  1. `UNAUTHORIZED_RECIPIENT` → `RecipientNotAllowed(address)`
  2. `UNWHITELISTED_TOKEN` → `TokenNotAllowed(address)`
  3. `VIOLATE_FLOOR` → `BelowMinimumBalanceFloor(uint256, uint256)`
  4. `EXCEED_DAILY_LIMIT` → `ExceedsDailyLimit(uint256, uint256)`
  5. `EMERGENCY_PAUSED` → `WalletPaused()`
  6. `UNAUTHORIZED_OPERATOR` → `UnauthorizedOperator(address)`
- **Result:** **6 / 6 vectors reverted with typed Solidity custom errors**

---

## 5. Live On-Chain Evidence — Base Sepolia Testnet

The smart contract [`contracts/PolicyWallet.sol`](../contracts/PolicyWallet.sol) was compiled with `solc 0.8.20` and deployed to Base Sepolia (Chain ID `84532`). Five genuine, gas-consuming transactions were broadcast and confirmed on-chain at zero cost (testnet faucet funded).

```
Network:          Base Sepolia Testnet (Chain ID: 84532)
Contract Address: 0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E
Explorer:         https://sepolia.basescan.org/address/0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E
Deployer:         0xD05B1Af82376528eF75b23D1C2B5C22B92747cAB
Transactions:     5 confirmed on-chain
```

### Verified On-Chain Transaction Register

| # | Action | Block | Gas Used | BaseScan Link |
| :---: | :--- | :---: | :---: | :--- |
| **1** | Deploy `PolicyWallet` Contract | `#48349779` | `2,025,439` | [0xb3a5e304...](https://sepolia.basescan.org/tx/0xb3a5e3044fa1ed5f0b40da4573bd1a6f68e2dd6290bfb17f7693b7a705624a40) |
| **2** | `setPolicy` — Invariant Caps & Floor | `#48349781` | `160,292` | [0x42a5e6e3...](https://sepolia.basescan.org/tx/0x42a5e6e3140a3954e118cc8961a322a65cded9dd60e64a0538805d704e6c6400) |
| **3** | `pause` — Emergency Killswitch | `#48349783` | `45,073` | [0xdd853edc...](https://sepolia.basescan.org/tx/0xdd853edcaa73408046a2aff4c5b0f92d94d8ae805a433d66c3eb210bf67bd9a3) |
| **4** | `unpause` — Restore Execution | `#48349785` | `23,194` | [0x38fca194...](https://sepolia.basescan.org/tx/0x38fca19438151fe9f56f206cd285c8a23a365fae771650f659232e53cc738822) |
| **5** | `setOperator` — Authorize Agent | `#48349787` | `46,087` | [0xe7da3881...](https://sepolia.basescan.org/tx/0xe7da3881004d6b7cd14fae51a6900c5904c1039e608a3fd2f8057fe1635f690f) |

> **Note on Routine Agent Evaluations:** The autonomous daemon evaluates market triggers and runs Z3 preflight proofs every 1–2 seconds. These are deterministic off-chain preflights labeled `Simulated` in the ledger UI. Broadcasting every preflight evaluation as a real transaction would drain testnet gas in minutes. The five verified on-chain transactions above cover the complete smart contract lifecycle: deployment, policy configuration, emergency pause/unpause, and operator authorization.

---

## 6. Automated Test Suite Evidence

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

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

## 7. Findings & Remediation Register

| ID | Finding | Severity | Remediation |
| :--- | :--- | :---: | :--- |
| **F-01** | Revoked operator not gated in Python client (`EE-06`) | `HIGH` | Check `authorized_operators[sender]` in `wallet_client.py:execute_onchain_transaction()` |
| **F-02** | Simulation receipts not distinctly tagged | `HIGH` | Tag returned receipts with `SIMULATED_RECEIPT` prefix |
| **F-03** | Workflow approver identities are plain strings | `MEDIUM` | Bind transitions to ECDSA EIP-712 signatures |
| **F-04** | No expiry deadline on policy proposals | `MEDIUM` | Add deadline block/timestamp to proposals |
| **F-05** | Flask endpoints lack authentication | `MEDIUM` | Add JWT / API key middleware before any public deployment |
| **F-06** | RPC fallback returns simulated success when offline | `LOW` | Label results `OFFLINE_FALLBACK` when RPC is unreachable |

---

## 8. Reproduction Steps

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run full automated test suite (94 tests)
PYTHONPATH=. pytest tests/

# 3. Generate execution evidence log
python scripts/generate_execution_evidence.py

# 4. Verify SHA-256 evidence integrity
sha256sum docs/evidence/execution-report/execution-evidence.json

# 5. Docker container smoke validation
docker build -t orvilo:latest .
docker run -d --name orvilo-test -p 5000:5000 orvilo:latest
python scripts/docker_smoke.py http://127.0.0.1:5000
docker rm -f orvilo-test
```
