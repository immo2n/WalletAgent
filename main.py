"""Autonomous Wallet Agent — Main Orchestration & Policy Discovery Engine.

Initializes the verified policy engine, prints out the active guard set,
and launches the interactive Flask monitoring dashboard.

Run:
    python main.py
    python main.py --port 5000
    python main.py --cli-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time

# Ensure root directory is in sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from policy import (
    DOMAIN,
    Policy,
    VerifiedPolicy,
    compile_policy,
    constraint_names,
    verify_policy,
)
from policy.hashing import policy_hash
from policy.onchain import params as onchain_params
from policy.readback import readback
from policy.readers.llm_client import EnvLLMClient
from policy.readers.llm_reader import LLMReader
from policy.readers.mock import MockLLMClient
from policy.readers.rule_reader import RuleReader

# Terminal Color Codes
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


def print_banner() -> None:
    banner = f"""
{BOLD}{CYAN}╔═════════════════════════════════════════════════════════════════════════════╗
║                                                                             ║
║   {GREEN}VERIFIED-POLICY AUTONOMOUS ON-CHAIN WALLET AGENT{CYAN}                          ║
║   {DIM}FinTechathon 2026 — Topic F : Autonomous On-chain Wallet Agent{CYAN}             ║
║                                                                             ║
║   {YELLOW}• Layer 1: Dual Mathematical Intent Verification (Z3 Solver){CYAN}              ║
║   {BLUE}• Layer 2: Deterministic Off-Chain Guard Layer{CYAN}                            ║
║   {MAGENTA}• Layer 3: Solidity Smart Contract Limits (Base Sepolia){CYAN}                    ║
║                                                                             ║
╚═════════════════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)


def discover_and_print_policy(prompt: str) -> VerifiedPolicy:
    """Run formal policy discovery and print active guard set to terminal."""
    print(f"{BOLD}[1/2] INITIALIZING POLICY DISCOVERY ENGINE...{RESET}")
    print(f"  • Reading Natural Language Intent: {YELLOW}\"{prompt}\"{RESET}")

    rule_reader = RuleReader()
    env_client = EnvLLMClient()
    if env_client.api_key and env_client.provider != "mock":
        llm_reader = LLMReader(env_client)
        print(f"  • Reader B (Untrusted LLM): {GREEN}Live Provider ({env_client.provider}: {env_client.model}){RESET}")
    else:
        mock_client = MockLLMClient()
        llm_reader = LLMReader(mock_client)
        parsed_a = rule_reader.read(prompt)
        mock_client.set_default_responses([parsed_a.to_json(), parsed_a.to_json()])
        print(f"  • Reader B (Untrusted LLM): {YELLOW}Mock Client (Offline){RESET}")

    # Run dual verification
    result = verify_policy(prompt, rule_reader, llm_reader, lambda q, opts: opts[0].id)

    if not isinstance(result, VerifiedPolicy):
        print(f"\n{BOLD}\033[31m[ERROR] Policy verification failed with status: {result.status}{RESET}")
        sys.exit(1)

    print(f"  • Dual Formalization: {GREEN}Reader A (Deterministic) ≡ Reader B (Untrusted LLM){RESET}")
    print(f"  • Z3 Equivalence Proof: {GREEN}PROVEN LOGICAL MATCH (0 counterexamples){RESET}")
    print(f"  • Sanity Checks: {GREEN}Satisfiable, Non-vacuous, Non-redundant{RESET}")

    # Print out discovered policy set
    print(f"\n{BOLD}{CYAN}{'='*77}{RESET}")
    print(f"{BOLD}{CYAN}  DISCOVERED POLICY SET (ACTIVE INTENT VALIDATION GUARDS){RESET}")
    print(f"{BOLD}{CYAN}{'='*77}{RESET}\n")

    print(f"  {BOLD}Status:{RESET}            {GREEN}{BOLD}{result.status}{RESET}")
    print(f"  {BOLD}Independence:{RESET}      {CYAN}{result.independence}{RESET}")
    print(f"  {BOLD}Attempts:{RESET}          {YELLOW}{result.attempts}{RESET}")
    print(f"  {BOLD}Canonical Readback:{RESET}{BOLD} {result.readback}{RESET}")
    print(f"  {BOLD}Policy SHA-256:{RESET}     {MAGENTA}{result.hash}{RESET}\n")

    print(f"  {BOLD}Active Guard Constraints (Z3 Unsat-Core Names):{RESET}")
    constraints = constraint_names(result.policy)
    for i, c in enumerate(constraints, 1):
        if "gas" in c or "avg24h" in c or "pctile" in c:
            print(f"    [{i}] {YELLOW}[TRIGGER]{RESET}   {BOLD}{c}{RESET}")
        else:
            print(f"    [{i}] {CYAN}[INVARIANT]{RESET} {BOLD}{c}{RESET}")

    print(f"\n  {BOLD}Exported On-Chain Smart Contract Parameters:{RESET}")
    print(f"  {DIM}{json.dumps(result.onchain, indent=4)}{RESET}\n")

    print(f"{BOLD}{CYAN}{'='*77}{RESET}\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Wallet Agent Engine")
    parser.add_argument(
        "--prompt",
        type=str,
        default="Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.",
        help="Natural language policy to verify on startup",
    )
    parser.add_argument("--port", type=int, default=5000, help="Port for Flask web dashboard (default: 5000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    parser.add_argument("--cli-only", action="store_true", help="Run policy discovery in CLI without starting web server")

    args = parser.parse_args()

    print_banner()

    # 1. Discover and print policy set
    verified = discover_and_print_policy(args.prompt)

    if args.cli_only:
        print(f"{GREEN}Policy discovery complete. CLI-only mode exiting.{RESET}")
        return

    # 2. Launch Flask web interface
    print(f"{BOLD}[2/2] STARTING FLASK WALLET DASHBOARD...{RESET}")
    try:
        import importlib.util

        server_path = os.path.join(WORKSPACE_ROOT, "flask", "server.py")
        spec = importlib.util.spec_from_file_location("wallet_flask_server", server_path)
        server_mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(server_mod)

        # Initialize engine state with verified policy
        server_mod.set_default_policy(args.prompt)
        app = server_mod.create_app()

        from exchange import exchange_service
        from user import user_db

        market = exchange_service.get_market_state()
        user_state = user_db.get_state()

        print(f"  • Live Market (Coinbase WS): {GREEN}${market['eth_price_usd']:,.2f} USD{RESET} | Gas: {YELLOW}{market['gas_gwei']} gwei{RESET}")
        print(f"  • Wallet Balances (Base Sepolia): {CYAN}{user_state.balances.ETH} ETH{RESET} | {GREEN}${user_state.balances.USDC:,.2f} USDC{RESET}")
        print(f"  • Transaction Ledger: {BOLD}{len(user_state.transactions)} records{RESET} (USER vs AGENT tracked)")

        url = f"http://{args.host}:{args.port}"
        print(f"\n  • Web Dashboard URL: {BOLD}{GREEN}{url}{RESET}")
        print(f"  • Real-time Live Chart, Editable Balances & Autonomous Guard Gate\n")
        print(f"{DIM}Press Ctrl+C to terminate the engine.{RESET}\n")

        app.run(host=args.host, port=args.port, debug=False)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down Wallet Agent Engine.{RESET}")
    except Exception as e:
        print(f"\n{BOLD}\033[31m[ERROR] Failed to start web dashboard: {e}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
