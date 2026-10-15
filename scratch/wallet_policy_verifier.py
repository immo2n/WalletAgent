"""
Verified-policy layer for an LLM wallet agent (demo).

Pipeline
  user text
    -> (A) deterministic rule parser           (independent formalization #1)
    -> (B) LLM proposes typed JSON policy      (independent formalization #2, UNTRUSTED)
    -> Z3 compares A and B over the same state space
         equivalent  -> accept, read back in plain English, hash, export on-chain params
         different   -> hand the LLM a concrete counterexample, retry (max 2), then human review
    -> Guard: every proposed trade is checked against the verified policy with Z3
              (no LLM involved; unsat core says exactly which rule blocked it)

Run:  python wallet_policy_verifier.py
Needs: pip install z3-solver
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable, Optional, Protocol

from z3 import And, BoolVal, Not, Real, RealVal, Solver, sat, unsat

MAX_REPAIRS = 2

# ----------------------------------------------------------------------------
# 1. State space. Everything the policy can talk about, as exact Z3 reals.
#    These values come from TRUSTED feeds (node, oracle) -- never from the LLM.
# ----------------------------------------------------------------------------
V = {n: Real(n) for n in ("gas", "avg24h", "pctile24h", "balance", "trade")}
DOMAIN = [
    V["gas"] >= 1,      # gwei
    V["avg24h"] >= 1,
    V["pctile24h"] >= 0,
    V["pctile24h"] <= 100,
    V["balance"] >= 0,
    V["trade"] >= 1,    # USD
    V["trade"] <= V["balance"],  # cannot spend more than you hold
]

# "under 5%" is genuinely ambiguous. The DSL refuses to guess: basis is required.
TRIGGER_BASES = {
    "pct_below_avg24h": "gas is at least {v}% below its 24h average",
    "lowest_pctile24h": "gas is within the lowest {v}% of the last 24h",
    "absolute_gwei": "gas is at most {v} gwei",
}

CLARIFY_OPTIONS = {
    "a": "pct_below_avg24h",
    "b": "lowest_pctile24h",
    "c": "absolute_gwei",
}

INVARIANT_TYPES = {
    "min_balance_after": "balance after the trade stays >= ${usd}",
    "min_balance_before": "balance before the trade is >= ${usd}",
    "max_trade": "a single trade is <= ${usd}",
}


class NeedsClarification(Exception):
    def __init__(self, question: str, options: dict[str, str]):
        super().__init__(question)
        self.question, self.options = question, options


# ----------------------------------------------------------------------------
# 2. Typed policy -> Z3 constraints (each one named, so cores are readable)
# ----------------------------------------------------------------------------
def validate(p: dict) -> None:
    t = p.get("trigger") or {}
    if t.get("basis") not in TRIGGER_BASES:
        raise NeedsClarification(
            f"What does the {t.get('value')} in your gas condition refer to?",
            {k: TRIGGER_BASES[v].format(v=t.get("value")) for k, v in CLARIFY_OPTIONS.items()},
        )
    for inv in p.get("invariants", []):
        if inv.get("type") not in INVARIANT_TYPES:
            raise ValueError(f"unknown invariant type: {inv.get('type')}")


def constraints(p: dict) -> dict[str, object]:
    validate(p)
    t = p["trigger"]
    val = RealVal(str(t["value"]))
    out: dict[str, object] = {}
    if t["basis"] == "pct_below_avg24h":
        out[f"gas<=avg24h*(1-{t['value']}%)"] = V["gas"] <= V["avg24h"] * (RealVal(1) - val / 100)
    elif t["basis"] == "lowest_pctile24h":
        out[f"gas_pctile24h<={t['value']}"] = V["pctile24h"] <= val
    else:
        out[f"gas<={t['value']}gwei"] = V["gas"] <= val
    for inv in p.get("invariants", []):
        usd = RealVal(str(inv["usd"]))
        if inv["type"] == "min_balance_after":
            out[f"balance-trade>={inv['usd']}"] = V["balance"] - V["trade"] >= usd
        elif inv["type"] == "min_balance_before":
            out[f"balance>={inv['usd']}"] = V["balance"] >= usd
        elif inv["type"] == "max_trade":
            out[f"trade<={inv['usd']}"] = V["trade"] <= usd
    return out


def conj(exprs) -> object:
    return And(BoolVal(True), *list(exprs))


def _val(model, name: str) -> float:
    return round(float(model.eval(V[name], model_completion=True).as_fraction()), 4)


# ----------------------------------------------------------------------------
# 3. Formalization A: deterministic rule parser (small controlled grammar).
#    Plays the role APE/ACE would play; swap it in later if time allows.
# ----------------------------------------------------------------------------
def parse_rules(text: str) -> dict:
    t = text.lower()
    policy: dict = {"version": 1, "action": "swap_buy", "trigger": {}, "invariants": []}
    m = re.search(r"gas(?: price)? (?:is )?(?:under|below) (\d+(?:\.\d+)?)\s*gwei", t)
    if m:
        policy["trigger"] = {"basis": "absolute_gwei", "value": float(m.group(1))}
    else:
        m = re.search(r"gas(?: price)? (?:is )?(?:under|below) (\d+(?:\.\d+)?)\s*%", t)
        if m:  # percentage with no stated reference: do NOT guess
            policy["trigger"] = {"basis": None, "value": float(m.group(1))}
    m = re.search(
        r"(?:do not|don't|never) go (?:under|below) \$?(\d+(?:\.\d+)?)\s*(?:dollars?|usd)?(?: balance)?", t
    )
    if m:
        policy["invariants"].append({"type": "min_balance_after", "usd": float(m.group(1))})
    if not policy["trigger"] and not policy["invariants"]:
        raise ValueError("rule parser could not understand the instruction")
    return policy


# ----------------------------------------------------------------------------
# 4. Formalization B: the LLM (untrusted). Protocol + a scripted mock for demos.
# ----------------------------------------------------------------------------
class PolicyLLM(Protocol):
    def propose(self, text: str, clarification: Optional[str], feedback: Optional[dict]) -> dict: ...


class MockLLM:
    """Scripted stand-in. `fixes_after_feedback=False` simulates a model that never gets it right."""

    def __init__(self, fixes_after_feedback: bool = True):
        self.fixes = fixes_after_feedback
        self.calls = 0

    def propose(self, text, clarification, feedback):
        self.calls += 1
        basis = clarification or "pct_below_avg24h"
        good = {
            "version": 1, "action": "swap_buy",
            "trigger": {"basis": basis, "value": 5.0},
            "invariants": [{"type": "min_balance_after", "usd": 500.0}],
        }
        bad = json.loads(json.dumps(good))
        # classic slip: floor checked on the balance BEFORE the trade
        bad["invariants"] = [{"type": "min_balance_before", "usd": 500.0}]
        return good if (feedback and self.fixes) else bad


# ----------------------------------------------------------------------------
# 5. Z3 equivalence check with counterexamples
# ----------------------------------------------------------------------------
def compare(pa: dict, pb: dict) -> list[dict]:
    ca, cb = conj(constraints(pa).values()), conj(constraints(pb).values())
    findings = []
    for label, left, right in (
        ("LLM policy is LOOSER (allows what the rules forbid)", cb, ca),
        ("LLM policy is STRICTER (forbids what the rules allow)", ca, cb),
    ):
        s = Solver()
        s.add(*DOMAIN)
        s.add(And(left, Not(right)))
        if s.check() == sat:
            m = s.model()
            findings.append({"kind": label, "state": {n: _val(m, n) for n in V}})
    return findings


def sanity(p: dict) -> list[str]:
    """Is the verified policy satisfiable, and does each rule actually bind?"""
    cs = constraints(p)
    problems = []
    s = Solver()
    s.add(*DOMAIN)
    s.add(*cs.values())
    if s.check() != sat:
        problems.append("policy is contradictory: no trade could ever pass")
    for name, c in cs.items():
        s2 = Solver()
        s2.add(*DOMAIN)
        s2.add(Not(c))
        if s2.check() != sat:
            problems.append(f"rule '{name}' can never be violated (vacuous)")
    return problems


# ----------------------------------------------------------------------------
# 6. Verification loop
# ----------------------------------------------------------------------------
def readback(p: dict) -> str:
    t = p["trigger"]
    lines = [f"Buy only when {TRIGGER_BASES[t['basis']].format(v=t['value'])}."]
    for inv in p["invariants"]:
        lines.append(INVARIANT_TYPES[inv["type"]].format(usd=inv["usd"]).capitalize() + ".")
    return " ".join(lines)


def policy_hash(p: dict) -> str:
    return "0x" + hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def onchain_params(p: dict) -> dict:
    """What the wallet contract enforces independently of every off-chain layer."""
    params = {"policyHash": policy_hash(p)}
    for inv in p["invariants"]:
        if inv["type"] == "min_balance_after":
            params["minBalanceAfterUsd"] = inv["usd"]
        if inv["type"] == "max_trade":
            params["perTxCapUsd"] = inv["usd"]
    return params


def verify_policy(
    text: str, llm: PolicyLLM, ask_user: Callable[[str, dict], str], log=print
) -> dict:
    clarification = None
    pa = parse_rules(text)
    if pa["trigger"].get("basis") is None:
        q = f"What does the {pa['trigger']['value']}% in your gas condition refer to?"
        opts = {k: TRIGGER_BASES[v].format(v=pa["trigger"]["value"]) for k, v in CLARIFY_OPTIONS.items()}
        log(f"  [clarify] {q}")
        for k, o in opts.items():
            log(f"            {k}) {o}")
        choice = ask_user(q, opts)
        clarification = CLARIFY_OPTIONS[choice]
        pa["trigger"]["basis"] = clarification
        log(f"  [clarify] user chose {choice}) -> {clarification}")

    feedback = None
    for attempt in range(MAX_REPAIRS + 1):
        pb = llm.propose(text, clarification, feedback)
        findings = compare(pa, pb)
        if not findings:
            problems = sanity(pa)
            if problems:
                return {"status": "REJECTED", "reasons": problems}
            log(f"  [z3] attempt {attempt + 1}: LLM policy == rule policy  (equivalent over all states)")
            return {
                "status": "VERIFIED", "policy": pa, "readback": readback(pa),
                "hash": policy_hash(pa), "onchain": onchain_params(pa), "attempts": attempt + 1,
            }
        f = findings[0]
        log(f"  [z3] attempt {attempt + 1}: MISMATCH -> {f['kind']}")
        log(f"       counterexample: {f['state']}")
        feedback = f
    log(f"  [z3] still different after {MAX_REPAIRS} repairs -> human review")
    return {"status": "NEEDS_HUMAN_REVIEW", "last_counterexample": feedback}


# ----------------------------------------------------------------------------
# 7. Guard: deterministic gate on every proposed action (no LLM anywhere)
# ----------------------------------------------------------------------------
def guard(policy: dict, allow: dict, state: dict, tx: dict) -> dict:
    """state: trusted feed values. tx: what the agent proposed."""
    if tx["token"] not in allow["tokens"]:
        return {"allow": False, "blocked_by": [f"token {tx['token']} not allowlisted"]}
    if tx["router"] not in allow["routers"]:
        return {"allow": False, "blocked_by": [f"router {tx['router']} not allowlisted"]}
    s = Solver()
    s.set(unsat_core=True)
    for i, (name, c) in enumerate(constraints(policy).items()):
        s.assert_and_track(c, f"rule::{name}")
    concrete = {**state, "trade": tx["amount_usd"]}
    for n, v in concrete.items():
        s.add(V[n] == RealVal(str(v)))
    if s.check() == sat:
        return {"allow": True, "blocked_by": []}
    return {"allow": False, "blocked_by": [str(c).replace("rule::", "") for c in s.unsat_core()]}


# ----------------------------------------------------------------------------
# Demo
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    PROMPT = "Buy if gas price is under 5% and do not go under 500 dollars balance."
    ALLOW = {"tokens": {"WETH", "USDC"}, "routers": {"0xRouterGood"}}

    print("=" * 78)
    print("SCENARIO 1  ambiguous prompt + LLM mis-parse, fixed by counterexample")
    print("=" * 78)
    print(f'  prompt: "{PROMPT}"')
    res = verify_policy(PROMPT, MockLLM(fixes_after_feedback=True), ask_user=lambda q, o: "a")
    print(f"  status: {res['status']}  (attempts: {res['attempts']})")
    print(f"  read back to user: {res['readback']}")
    print(f"  policy hash: {res['hash'][:18]}...   on-chain params: {res['onchain']}")
    policy = res["policy"]

    print()
    print("=" * 78)
    print("SCENARIO 2  guard on proposed trades (state comes from trusted feeds)")
    print("=" * 78)
    cheap = {"gas": 18, "avg24h": 30, "pctile24h": 40, "balance": 1000}  # 40% below avg
    pricey = {"gas": 29, "avg24h": 30, "pctile24h": 80, "balance": 1000}
    cases = [
        ("cheap gas, trade 300 (leaves 700)", cheap, {"token": "WETH", "router": "0xRouterGood", "amount_usd": 300}, True),
        ("cheap gas, trade 600 (leaves 400)", cheap, {"token": "WETH", "router": "0xRouterGood", "amount_usd": 600}, False),
        ("gas not cheap enough", pricey, {"token": "WETH", "router": "0xRouterGood", "amount_usd": 100}, False),
        ("injected: poisoned token name asks for attacker router", cheap,
         {"token": "WETH", "router": "0xAttacker", "amount_usd": 100}, False),
        ("injected: unknown airdrop token", cheap,
         {"token": "FREE-ETH.claim", "router": "0xRouterGood", "amount_usd": 100}, False),
    ]
    ok = True
    for label, st, tx, expect in cases:
        r = guard(policy, ALLOW, st, tx)
        flag = "ALLOW" if r["allow"] else "BLOCK"
        print(f"  {flag:5} {label:55} {r['blocked_by'] or ''}")
        ok &= r["allow"] == expect
    print(f"  all guard expectations met: {ok}")

    print()
    print("=" * 78)
    print("SCENARIO 3  LLM never converges -> escalate to human, nothing executes")
    print("=" * 78)
    res3 = verify_policy(PROMPT, MockLLM(fixes_after_feedback=False), ask_user=lambda q, o: "a")
    print(f"  status: {res3['status']}")

    print()
    print("=" * 78)
    print("SCENARIO 4  user clarifies differently (percentile) -> different verified policy")
    print("=" * 78)
    res4 = verify_policy(PROMPT, MockLLM(), ask_user=lambda q, o: "b", log=lambda *_: None)
    print(f"  read back: {res4['readback']}")
    print(f"  hash differs from scenario 1: {res4['hash'] != res['hash']}")
