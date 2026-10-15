# Project Context: Verified-Policy Wallet Agent

> Read this first. It tells any engineer or coding agent what is being built, why, how the pieces fit, and what must never be violated. Keep it updated as decisions change.

## 1. What we are building

An autonomous on-chain wallet agent where **the user's natural-language instructions are converted into a mathematically verified policy before the agent may act**, and where **every action the agent proposes is gated by deterministic code, never by an LLM**.

The LLM is useful (it understands language, reasons about swaps) but it can hallucinate and be prompt-injected. So it is treated as an **untrusted proposer**. Security comes from verification and gates around it.

**One-line principle: the LLM is never the security boundary.**

### Competition target

- Event: 2026 Shenzhen International FinTech Competition (FinTechathon), International Track, hosted by Tsinghua PBC School of Finance with WeBank. Theme: "AI as a Financial Participant".
- Our topic: **Topic F, Agent Wallet (Autonomous On-chain Wallet)**. This topic includes an optional 0 to 5 point challenge bonus (details unknown, see section 9).
- Submission deadline: **20 October 2026, 23:59 Beijing Time (UTC+8)**. Submission and registration are by email to the organizer.
- Expected evaluation themes (from secondary sources, not the official PDF): permission hierarchy, hallucination prevention, injection defense, intent understanding, task planning. For the on-chain topic, evidence must be real on-chain transaction hashes.
- **We are building a demo, not a production system.** Goal: the demo scenarios work end to end and clearly show the verification idea. Cut anything that does not serve a demo scenario.

### What makes us different

Most agent-wallet designs gate actions after the LLM decides (policy engine plus smart-contract limits). We additionally verify **intent**: the policy itself is formalized two independent ways, compared with Z3, and any disagreement produces a concrete counterexample that is fed back to the LLM. Ambiguous instructions are never guessed; the user is asked.

## 2. Architecture

```
user text
  |
  v
[policy]  A) deterministic rule parser  --\
          B) LLM -> typed JSON policy   ---+--> Z3 equivalence check
                                              |  mismatch: counterexample -> LLM retry (max 2) -> human review
                                              |  ambiguous: ask the user (never guess)
                                              v
                                    VERIFIED POLICY (typed object)
                                    + plain-English readback (user confirms)
                                    + sha256 policy hash
                                    + on-chain params (floor, caps, hash)

[monitor] trusted market state: gas, price, RSI/APY, DEX pool (parallel loops, sockets)
     |
     v
[agent]   LLM reasoning (UNTRUSTED): optimal swap, ABI call, min-out, final intent
     |
     v
[guard]   deterministic, no LLM:
          allowlist checks -> Z3 check of concrete trade vs verified policy
          -> dry-run simulation -> tier decision T1 auto / T2 owner approval / T3 blocked
     |
     v
[chain]   wallet contract enforces allowlist, caps, balance floor, pause, policy hash
          INDEPENDENTLY of every off-chain layer; real tx hashes are the evidence
```

Defense in depth, three independent layers: (1) verified policy, (2) deterministic guard, (3) on-chain contract. A compromise of one must not defeat the others.

## 3. Hard invariants (do not violate, even if it makes something easier)

1. **LLM output is untrusted.** It may propose policies and trades. It never decides whether something is allowed.
2. **Trusted state comes from feeds, never from the LLM.** Gas, prices, balances, averages, oracle values are produced by deterministic code. The LLM supplies only the proposed action (token, router, amount).
3. **Fail closed.** Unknown intent, parse failure, solver timeout, missing data, ambiguity: do not execute. Escalate or ask.
4. **Never guess ambiguous instructions.** Example: "gas under 5%" has no stated reference (percent below 24h average? lowest percentile? gwei?). Ask the user. The chosen meaning changes the policy hash.
5. **The agent can never loosen policy.** Raising limits, editing allowlists, unpausing: owner-only, outside the agent's toolset.
6. **Untrusted external text** (token names, pool metadata, invoices, emails, news) is labeled untrusted wherever it enters an LLM prompt and can never authorize an action by itself.
7. **Use exact arithmetic.** Z3 `Real`, not floats, for policy math. Money is never a Python float in the guard path.
8. **The verified policy is the single source of truth.** Guard parameters and on-chain parameters are derived from it and carry its hash.
9. **Every decision is logged** with its reasons (which rule blocked, counterexample, tx hash).

## 4. Package layout (proposed; `main.py` orchestrates, packages stay independent)

```
wallet-agent/
  context.md          this file
  main.py             entry point; wires packages together; demo scenarios
  policy/             NL -> verified policy (built first, see section 5)
  guard/              deterministic gate + tiers (T1/T2/T3)
  monitor/            trusted market feeds (gas, price, RSI/APY, DEX pool)
  agent/              LLM reasoning (swap choice, ABI call, min-out); untrusted
  chain/              wallet contract client, tx build/send, simulation
  contracts/          Solidity wallet (allowlist, caps, balance floor, pause, policy hash) + tests
  tests/              prompt eval set (50 prompts + paraphrases), red-team/injection cases
  visuals/            architecture & flow diagrams (Graphviz .dot files only)
  docs/               architecture, evidence (tx hashes, screenshots), demo script
```

Rules for packages: no cross-package imports except through the small interfaces in section 6. `main.py` is the only place that composes them. Each package gets its own `context` note (like `policy/context.md`) when it is built. For package diagrams/flowcharts, create only Graphviz `.dot` files under `visuals/` (`visuals/<package>.dot`).

Language: Python for the off-chain system (the `main.py` entry point implies this). Solidity for contracts. Confirm chain/testnet choice in section 9.

## 5. Current status

**Done:**
- `policy/` package fully implemented, tested, and passing all acceptance and mutation criteria:
  - Typed AST (`policy/ast.py`) with frozen dataclasses, exact `Fraction` parsing, and draft-07 JSON Schema validation (`policy/schema.py`).
  - Sorts registry and canonical units (`policy/sorts.py`).
  - Data-driven coercion table (`policy/coercions.py`) and static typechecker (`policy/typecheck.py`) with stable issue keys and clarification options.
  - Z3 compilation (`policy/z3_compile.py`) over physical `DOMAIN` bounds with human-readable unsat-core naming.
  - Z3 equivalence checker (`policy/compare.py`) with 5s timeout and exact counterexample extraction (100% mutation test coverage).
  - Sanity verification (`policy/sanity.py`) detecting contradictory, vacuous, and redundant constraints.
  - Controlled English readback (`policy/readback.py`) with Reader A round-trip property.
  - Canonical SHA-256 policy hashing (`policy/hashing.py`) and on-chain parameter export (`policy/onchain.py`).
  - Dual readers: Deterministic spaCy Reader A (`policy/readers/rule_reader.py`, `policy/readers/lexicon.py`) and schema-constrained LLM Reader B (`policy/readers/llm_reader.py`, `policy/readers/mock.py`).
  - Verification loop orchestration (`policy/loop.py`) with Tier 1 and Tier 2 independence modes, feedback repair loop, and human review fallback.
  - Test suite (`tests/policy/`): 60 tests covering AST, typecheck, mutations, readers, loop scenarios 1-6, T1 prompts, and paraphrase hash stability.
  - Interactive terminal test runner with colorful I/O logging (`testing/policy.py`).

**Not done:**
- `guard/` package (deterministic trade check against verified policy and state feeds)
- Solidity wallet contract (`contracts/`), deployment, and real transaction hashes
- Monitor feeds (`monitor/`) and agent reasoning (`agent/`)
- Dry-run simulation and bypass demo (guard off, contract reverts)
- Injection tests (poisoned token name, malicious invoice)
- Submission package and registration

## 6. Interfaces between packages (keep stable)

```python
# policy
verify_policy(text, llm, ask_user, log) -> {
    "status": "VERIFIED" | "NEEDS_HUMAN_REVIEW" | "REJECTED",
    "policy": dict, "readback": str, "hash": str, "onchain": dict, "attempts": int
}

# guard
guard(policy: dict, allow: dict, state: dict, tx: dict) -> {"allow": bool, "blocked_by": [str]}
# state = trusted feed values; tx = what the agent proposed (token, router, amount_usd)

# monitor  -> produces `state` dicts (gas, avg24h, pctile24h, balance, ...) from trusted sources
# agent    -> produces `tx` proposals (untrusted); never touches policy or guard internals
# chain    -> submit(tx, policy_hash) -> tx_hash ; contract may still revert
```

## 7. Policy primitives (the unit we support, not individual sentences)

Natural language has unlimited phrasings. We do not map sentences; we map them onto a small set of typed primitives and test against a fixed prompt set.

- **Triggers:** gas (absolute gwei / percent below 24h average / lowest percentile), token price, indicator (RSI, APY), time or schedule
- **Constraints:** min balance after trade, max per trade, period (daily) cap, allowlist (tokens, routers, recipients), slippage, approval threshold
- **Controls:** pause, resume (owner only), policy change (owner only)
- **Actions:** swap, transfer, deposit or stake, read-only query

Paraphrase handling is the LLM's job. Verification operates on the typed object, so it is independent of phrasing.

### Demo tiers

- **T1: full pipeline** (rule parser, LLM, Z3 compare, guard, on-chain). About 10 core prompts. Headline: "Buy if gas price is under 5% and do not go under 500 dollars balance."
- **T2: LLM extraction + user readback confirmation + guard.** Used when the rule parser cannot parse a paraphrase; independence then comes from a second LLM extraction compared in Z3 plus user confirmation.
- **T3: deliberately refused or escalated.** Vague ("double my money"), out of scope (bridge, loans), open-ended ("best APY pool"). Clean refusal is a feature to demo.

### Core T1 prompts (full list of 50 lives in `tests/`)

Transfer to saved contact; transfer to unknown address (escalates to owner); pay all bills in inbox (injection surface); send all ETH (blocked); swap with slippage cap; buy when gas under 5 gwei; buy when gas under 5% (ambiguous, flagship); buy when price below X; never let balance go under 500; max 300 per transaction; max 1,000 per day; ask me before anything over 500; only trade WETH and USDC; only send to saved contacts; never approve unlimited allowances; pause; resume (owner only); jailbreak ("ignore your rules"); injected invoice text; unknown airdrop token; raise my daily limit (owner step-up only); add address to allowlist then send (allowlist change needs owner approval first).

## 8. Demo scenarios to make work (acceptance criteria)

1. Clean policy verifies, trade passes the guard, contract executes, real tx hash recorded.
2. Ambiguous prompt: system asks a clarifying question; different answers give different verified policies (different hashes).
3. LLM mis-parse (e.g. balance floor checked before the trade instead of after): Z3 shows a concrete counterexample, LLM repairs, policy verifies.
4. LLM never converges after 2 repairs: escalates to human, nothing executes.
5. Trade that breaches the floor or gas condition: blocked, with the exact rule named.
6. Prompt injection (poisoned token name, malicious invoice): agent may propose a bad action, guard blocks it.
7. Bypass attempt: guard disabled, raw malicious transaction from the agent key, **contract reverts** with a typed error (visible on a block explorer).

## 9. Open questions and unknowns

- The official Topic F problem statement (PDF) and the bonus-challenge definition have **not been read** (access was blocked). Read them and update this file; they override anything inferred here.
- Chain and testnet choice, and whether testnet transactions satisfy "real on-chain transaction hashes". Other public Topic F projects used Base Sepolia; unconfirmed for the rules.
- Which stablecoin and DEX/router to use for the demo. If the wallet holds a stablecoin, the balance floor can be token-denominated and needs no price oracle.
- Real LLM provider/model for the adapter.
- Team size and roles.

## 10. Conventions for agents working on this repo

- Read this file and the relevant package's own context note before changing anything.
- Do not weaken a hard invariant (section 3) to make a test pass. If an invariant seems wrong, say so and ask.
- Keep the demo small: prefer fewer primitives that work over many that half work.
- Add or update tests for every behavior change; the prompt eval set is the regression suite.
- Z3 and guard code paths must stay deterministic and LLM-free.
- **For visuals, only make Graphviz `.dot` files** in `visuals/` (`visuals/<package>.dot`) when documenting or updating package flows. Do not generate other visual formats.
- When you make a decision that changes scope, interfaces, or invariants, update this file in the same change.
