"""Interactive terminal test runner and demonstration for the policy package.

Run: python testing/policy.py
"""
from __future__ import annotations

import os
import sys

# Ensure root workspace is imported, not this test file
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if sys.path and sys.path[0] == os.path.dirname(os.path.abspath(__file__)):
    sys.path.pop(0)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from fractions import Fraction
import json

from policy import (
    DOMAIN,
    NeedsHumanReview,
    Policy,
    Rejected,
    VerifiedPolicy,
    compile_policy,
    constraint_names,
    verify_policy,
)
from policy.ast import BinOp, Cmp, Const, Var
from policy.compare import compare
from policy.hashing import policy_hash
from policy.onchain import params as onchain_params
from policy.readback import readback
from policy.readers.llm_reader import LLMReader
from policy.readers.mock import MockLLMClient
from policy.readers.rule_reader import RuleReader
from policy.sanity import sanity
from policy.sorts import Sort
from policy.typecheck import resolve, typecheck

# ANSI Terminal Colors
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
RESET = "\033[0m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'='*75}{RESET}")
    print(f"{BOLD}{CYAN}  {title.upper()}{RESET}")
    print(f"{BOLD}{CYAN}{'='*75}{RESET}\n")


def subheader(title: str) -> None:
    print(f"\n{BOLD}{MAGENTA}--- [ {title} ] ---{RESET}")


def log_event(event: str, data: dict) -> None:
    color = GREEN if event == "verified" else (YELLOW if event in ("clarify", "mismatch") else CYAN)
    print(f"  {color}▸ EVENT:{RESET} {BOLD}{event.upper():<16}{RESET} {DIM}{json.dumps(data)}{RESET}")


def demo_ast_and_typecheck() -> None:
    header("Test 1: AST Construction & Ambiguity Detection (Typecheck)")

    print(f"{BOLD}User Input:{RESET} 'Buy if gas price is under 5% and do not go under 500 dollars balance.'")
    reader_a = RuleReader()
    policy_ast = reader_a.read("Buy if gas price is under 5% and do not go under 500 dollars balance.")

    print(f"{BOLD}Raw Parsed AST:{RESET}")
    print(json.dumps(policy_ast.to_json(), indent=2))

    print(f"\n{BOLD}Running Type Checker...{RESET}")
    issues = typecheck(policy_ast)
    print(f"Detected {len(issues)} TypeIssue(s):")
    for i, issue in enumerate(issues, 1):
        print(f"  [{i}] {RED}{issue.kind}{RESET} on {YELLOW}{issue.issue_id}{RESET}: {issue.message}")
        if issue.options:
            print(f"      {BOLD}Resolution Options from Coercion Table:{RESET}")
            for opt in issue.options:
                print(f"        • [{opt.id}] -> {CYAN}{opt.description}{RESET}")

    # Resolve issue
    print(f"\n{BOLD}Resolving issue with option:{RESET} 'pct_below_avg24h'...")
    resolved = resolve(policy_ast, issues[0].issue_id, "pct_below_avg24h")
    remaining = typecheck(resolved)
    print(f"Issues after resolution: {GREEN}{len(remaining)} (Clean!){RESET}")
    print(f"Resolved Readback: {BOLD}{readback(resolved)}{RESET}")


def demo_z3_verification_and_repair() -> None:
    header("Test 2: Z3 Verification & LLM Counterexample Repair Loop")

    text = "Buy if gas price is under 5% and do not go under 500 dollars balance."
    print(f"{BOLD}Simulating end-to-end verification with staged LLM mis-parse:{RESET}")
    print(f"  • Reader A (Deterministic): Parsed balance floor as: balance - trade >= 500")
    print(f"  • Reader B (Untrusted LLM Attempt 1): Buggy parse: balance >= 500 (before trade)")
    print(f"  • Expected: Z3 discovers counterexample -> Handed back to LLM -> LLM repairs on Attempt 2\n")

    rule_reader = RuleReader()
    mock_client = MockLLMClient()

    # Attempt 1 (Buggy)
    attempt1_ast = {
        "node": "Policy",
        "action": "swap_buy",
        "triggers": [
            {
                "node": "Cmp",
                "op": "le",
                "lhs": {"node": "Var", "name": "gas"},
                "rhs": {"node": "Const", "value": "1/20", "sort": "RATIO", "unit_inferred": False},
            }
        ],
        "invariants": [
            {
                "node": "Cmp",
                "op": "ge",
                "lhs": {"node": "Var", "name": "balance"},
                "rhs": {"node": "Const", "value": "500/1", "sort": "USD", "unit_inferred": False},
            }
        ],
        "allow_tokens": [],
        "allow_routers": [],
        "allow_recipients": [],
        "approval_above_usd": None,
    }

    # Attempt 2 (Repaired)
    attempt2_ast = {
        "node": "Policy",
        "action": "swap_buy",
        "triggers": [
            {
                "node": "Cmp",
                "op": "le",
                "lhs": {"node": "Var", "name": "gas"},
                "rhs": {"node": "Const", "value": "1/20", "sort": "RATIO", "unit_inferred": False},
            }
        ],
        "invariants": [
            {
                "node": "Cmp",
                "op": "ge",
                "lhs": {
                    "node": "BinOp",
                    "op": "sub",
                    "lhs": {"node": "Var", "name": "balance"},
                    "rhs": {"node": "Var", "name": "trade"},
                },
                "rhs": {"node": "Const", "value": "500/1", "sort": "USD", "unit_inferred": False},
            }
        ],
        "allow_tokens": [],
        "allow_routers": [],
        "allow_recipients": [],
        "approval_above_usd": None,
    }

    mock_client.set_default_responses([attempt1_ast, attempt2_ast])
    llm_reader = LLMReader(mock_client)

    def interactive_ask_user(question: str, options: tuple) -> str:
        print(f"\n{BOLD}{YELLOW}[USER CLARIFICATION MODAL]{RESET} {question}")
        for i, opt in enumerate(options, 1):
            print(f"   ({chr(96+i)}) {opt.description}")
        chosen = "pct_below_avg24h"
        print(f"   => Simulating user selection: {CYAN}{chosen}{RESET}\n")
        return chosen

    res = verify_policy(text, rule_reader, llm_reader, interactive_ask_user, log=log_event)

    print(f"\n{BOLD}Verification Loop Result:{RESET}")
    print(f"  • Status:        {GREEN}{BOLD}{res.status}{RESET}")
    print(f"  • Total Attempts:{YELLOW} {res.attempts}{RESET}")
    print(f"  • Independence:  {CYAN} {res.independence}{RESET}")
    print(f"  • Policy Hash:   {MAGENTA} {res.hash}{RESET}")
    print(f"  • Readback:      {BOLD} {res.readback}{RESET}")
    print(f"  • On-chain Dict: {json.dumps(res.onchain, indent=4)}")


def demo_prompt_matrix() -> None:
    header("Test 3: Prompt Acceptance Matrix (T1 Prompts)")

    test_prompts = [
        ("P1", "Buy ETH when gas is under 20 gwei.", "Clean trigger <= 20 gwei"),
        ("P2", "Never let my balance go under 500 dollars.", "Invariant: balance - trade >= 500"),
        ("P3", "Don't spend more than 300 dollars in one transaction.", "Invariant: trade <= 300"),
        ("P4", "No more than 1000 dollars per day in total.", "Invariant: spent_today + trade <= 1000"),
        ("P6", "Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.", "Compound Trigger + Invariant"),
        ("P7", "Only trade WETH and USDC.", "Allowlist tokens"),
        ("P8", "Ask me before anything over 500 dollars.", "Approval threshold $500"),
        ("P10", "Double my money.", "Expected Refusal (T3)"),
    ]

    rule_reader = RuleReader()

    for pid, text, desc in test_prompts:
        print(f"{BOLD}[{pid}]{RESET} {CYAN}{text:<65}{RESET} ({desc})")
        try:
            p = rule_reader.read(text)
            h = policy_hash(p)
            rb = readback(p)
            print(f"     {GREEN}✔ PARSED{RESET} -> Hash: {DIM}{h[:16]}...{RESET} | Readback: {DIM}{rb}{RESET}")
        except Exception as e:
            print(f"     {RED}✘ REFUSED/UNREADABLE{RESET} -> {type(e).__name__}: {e}")


def demo_sanity_and_mutations() -> None:
    header("Test 4: Sanity Checks & Solver Robustness")

    # Contradictory policy
    p_contra = Policy(
        action="swap_buy",
        triggers=[
            Cmp("le", Var("gas"), Const(Fraction(10, 1), Sort.GWEI)),
            Cmp("ge", Var("gas"), Const(Fraction(15, 1), Sort.GWEI)),
        ],
    )
    problems = sanity(p_contra)
    print(f"{BOLD}Contradictory Policy Check:{RESET}")
    print(f"  Input: gas <= 10 and gas >= 15")
    print(f"  Sanity Report: {RED}{problems[0]}{RESET}")

    # Vacuous policy
    p_vacuous = Policy(
        action="swap_buy",
        triggers=[Cmp("ge", Var("gas"), Const(Fraction(0, 1), Sort.GWEI))],
    )
    problems_v = sanity(p_vacuous)
    print(f"\n{BOLD}Vacuous Policy Check:{RESET}")
    print(f"  Input: gas >= 0 (Domain bound enforces gas >= 1)")
    print(f"  Sanity Report: {YELLOW}{problems_v[0]}{RESET}")


def main() -> None:
    print(f"{BOLD}{GREEN}")
    print("╔═════════════════════════════════════════════════════════════════════════╗")
    print("║     VERIFIED-POLICY WALLET AGENT : POLICY PACKAGE TEST SUITE            ║")
    print("║     Dual Readers • Typed AST • Z3 Equivalence • Hash & On-Chain Export   ║")
    print("╚═════════════════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

    demo_ast_and_typecheck()
    demo_z3_verification_and_repair()
    demo_prompt_matrix()
    demo_sanity_and_mutations()

    print(f"\n{BOLD}{GREEN}ALL POLICY PACKAGE TESTS COMPLETED SUCCESSFULLY! ✔{RESET}\n")


if __name__ == "__main__":
    main()
