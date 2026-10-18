# Package Context: `policy/`

> Package responsible for natural-language policy discovery, dual independent parsing, formal type-checking, ambiguity resolution, and Z3 mathematical equivalence verification.

## 1. What this package does

Converts untrusted natural-language user instructions into a verified, typed, and mathematically proven policy object before any on-chain wallet actions can be executed.

Security Principle: **The LLM is never the security boundary.**
- Dual formalization: Reader A (Deterministic dependency parser + typed lexicon) and Reader B (LLM JSON output) produce typed ASTs independently.
- Ambiguity detection: Typechecker detects sort mismatches (e.g. `gas < 5%`) and queries the user via concrete clarification options.
- Z3 Solver equivalence check: Proves whether readings A and B are logically equivalent over the domain bounds. Disagreements extract concrete counterexamples that are fed back to the LLM for self-repair (max 2 retries, then human review).
- Exact math: `fractions.Fraction` and Z3 `Real` are used exclusively. No floating-point arithmetic is permitted in policy math.

## 2. Module Layout

| Module | Purpose |
|---|---|
| `sorts.py` | `Sort` enum (`GWEI`, `USD`, `RATIO`, `TOKEN`, `ADDRESS`, `TIME`, `COUNT`, `BOOL`), state variable registry (`REGISTRY`), and canonical units. |
| `ast.py` | Immutable frozen AST dataclasses (`Const`, `Var`, `BinOp`, `Cmp`, `Coerced`, `Policy`), exact `Fraction` parsing and canonical JSON serialization. |
| `schema.py` | Draft-07 JSON Schema for strict LLM output constrained generation and validation. |
| `coercions.py` | Data-driven coercion table and option generators bridging mismatched sorts (e.g. `(GWEI, RATIO)` -> `pct_below_avg24h`, `lowest_pctile24h`, `absolute_reinterpret`). |
| `typecheck.py` | Static type checker detecting `SORT_MISMATCH`, `ASSUMED_PROVENANCE`, `UNKNOWN_VAR`, and `BAD_BOUND`; provides deterministic `resolve()`. |
| `z3_compile.py` | Compiles AST into named Z3 constraints over physical `DOMAIN` bounds. Provides unsat-core naming functions for guards. |
| `compare.py` | Z3-based two-way equivalence checker (`A and not B`, `B and not A`) with 5-second timeout and exact counterexample extraction. |
| `sanity.py` | Solver checks guaranteeing policy satisfiability, non-vacuousness, and non-redundancy. |
| `readback.py` | Controlled English sentence generator for user confirmation and round-trip parsing verification. |
| `hashing.py` | SHA-256 canonical JSON hash over verified AST excluding reader metadata and provenance. |
| `onchain.py` | Parameter extractor for smart contract limits (`minBalanceAfterUsd`, `perTxCapUsd`, `dailyCapUsd`, `allowTokens`). |
| `loop.py` | Core orchestration (`verify_policy`) managing dual readers, ambiguity clarification, repair loops, and tier fallbacks. |
| `errors.py` | Typed exceptions: `Unreadable`, `UnresolvedTypeIssues`, `SolverTimeout`, `SanityCheckFailed`. |
| `readers/base.py` | `Reader` protocol and common reader exceptions. |
| `readers/rule_reader.py` | Deterministic Reader A using spaCy dependency parse and typed lexicon. |
| `readers/lexicon.py` | Typed lexicon data table for comparators, state nouns, units, and compound constraints. |
| `readers/llm_reader.py` | Untrusted Reader B interfacing with LLMs under JSON schema constraints with counterexample feedback. |
| `readers/llm_client.py` | `LLMClient` protocol and environment-configurable adapter (`EnvLLMClient`). |
| `readers/mock.py` | Scripted `MockLLMClient` for offline testing and deterministic scenarios. |

## 3. Public API (`policy/__init__.py`)

```python
from policy import (
    verify_policy,
    VerifiedPolicy,
    NeedsHumanReview,
    Rejected,
    Policy,
    compile_policy,
    constraint_names,
    DOMAIN,
)
```

### Signature:
```python
def verify_policy(
    text: str,
    reader_a: Reader,
    reader_b: Reader,
    ask_user: Callable[[str, tuple[CoercionOption, ...]], str],
    log: Callable[[str, dict[str, Any]], None] | None = None,
    reader_a_fallback: Reader | None = None,
) -> VerifiedPolicy | NeedsHumanReview | Rejected: ...
```

## 4. Coercion Table

Keyed by `(lhs_sort, rhs_sort)`:
- `(Sort.GWEI, Sort.RATIO)`:
  - `pct_below_avg24h`: `gas <= avg24h * (1 - r)` ("gas is at least {pct} below its 24h average")
  - `pct_above_avg24h`: `gas >= avg24h * (1 + r)` ("gas is at least {pct} above its 24h average")
  - `lowest_pctile24h`: `pctile24h <= r` ("gas is within the lowest {pct} of the last 24h")
  - `absolute_reinterpret`: `gas <= {num}` ("{num} gwei, not a percentage")
- `(Sort.USD, Sort.RATIO)`:
  - `pct_of_balance`: `trade <= balance * r` ("{pct} of current balance")

## 5. Known Limitations & Scope
- Supports single-action swap/transfer execution policies.
- Multi-token portfolio optimization and stateful trailing stops are out of scope for the demo tier.
- Floating-point representations are forbidden; all numeric values are rational `Fraction` or Z3 `Real`.

## 6. Architecture Visual
The package flow is authored in Mermaid at
[`visuals/policy-verification.mmd`](../visuals/policy-verification.mmd) and
rendered to [`visuals/rendered/policy-verification.png`](../visuals/rendered/policy-verification.png).

## 7. Current runtime boundary

The policy package verifies and exports policy data; it does not itself sign or
broadcast transactions. The Flask application creates the default proposal at
startup and auto-promotes that startup proposal to `ACTIVE` for the demo. User
created proposals use the explicit review, approval, and deployment endpoints.
The exported parameters are copied into the in-memory `PolicyWalletClient`
security state and are not durable blockchain state in the default run.
