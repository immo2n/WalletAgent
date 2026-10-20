#!/usr/bin/env python3
"""Deploy PolicyWallet to Base Sepolia and execute verified on-chain transactions.

This script:
1. Generates or loads an ephemeral agent keypair from .env.
2. Checks wallet balance on Base Sepolia (chain ID 84532).
3. If unfunded, prints instructions and faucet links.
4. Once funded, compiles contracts/PolicyWallet.sol via solcx (Solidity 0.8.20).
5. Deploys PolicyWallet to Base Sepolia.
6. Executes 4 state-changing transactions:
   - setPolicy(...)
   - pause()
   - unpause()
   - setOperator(...)
7. Saves transaction hashes and BaseScan explorer links to docs/evidence/basescan_transactions.json.
8. Updates .env with WALLET_CONTRACT_ADDRESS.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import solcx
from eth_account import Account
from web3 import Web3

ENV_FILE = ROOT_DIR / ".env"
EVIDENCE_DIR = ROOT_DIR / "docs" / "evidence"
EVIDENCE_FILE = EVIDENCE_DIR / "basescan_transactions.json"

CHAIN_ID = 84532
DEFAULT_RPC_URL = "https://sepolia.base.org"
EXPLORER_BASE = "https://sepolia.basescan.org"


def update_env_variable(key: str, value: str) -> None:
    """Safely append or update a key-value pair in .env file."""
    lines = []
    found = False
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}=") or stripped.startswith(f"# {key}="):
                lines[idx] = f"{key}={value}"
                found = True
                break

    if not found:
        lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_or_create_wallet() -> tuple[Account, bool]:
    """Retrieve existing private key from .env or generate a fresh ephemeral one."""
    load_dotenv(ENV_FILE, override=True)
    pk = os.environ.get("AGENT_PRIVATE_KEY", "").strip()

    is_new = False
    if not pk or pk.startswith("0x_your_"):
        new_account = Account.create()
        pk = new_account.key.hex()
        update_env_variable("AGENT_PRIVATE_KEY", pk)
        is_new = True
        account = new_account
    else:
        account = Account.from_key(pk)

    return account, is_new


def check_balance_and_guide(w3: Web3, account: Account) -> int:
    """Check balance on Base Sepolia and print instructions if unfunded."""
    balance_wei = w3.eth.get_balance(account.address)
    balance_eth = w3.from_wei(balance_wei, "ether")

    print("\n" + "=" * 70)
    print(" BASE SEPOLIA ON-CHAIN DEPLOYMENT & TRANSACTION RUNNER")
    print("=" * 70)
    print(f"Network:        Base Sepolia (Chain ID: {CHAIN_ID})")
    print(f"RPC Endpoint:   {w3.provider.endpoint_uri}")
    print(f"Wallet Address: {account.address}")
    print(f"Balance:        {balance_eth:.6f} ETH")
    print(f"Explorer URL:   {EXPLORER_BASE}/address/{account.address}")
    print("=" * 70)

    # Minimum recommended balance: 0.0005 ETH
    min_required_wei = w3.to_wei(0.0005, "ether")
    if balance_wei < min_required_wei:
        print("\n [!] ACTION REQUIRED: WALLET NEEDS TESTNET ETH [!]")
        print("Your wallet currently has 0.000000 ETH (or below minimum gas requirements).")
        print("Please fund this address using free testnet faucets:\n")
        print("Option A (Fastest direct Base Sepolia faucet):")
        print(f"  👉 QuickNode Faucet: https://faucet.quicknode.com/base/sepolia")
        print(f"     (Paste address: {account.address})\n")
        print("Option B (Coinbase Base Faucet):")
        print(f"  👉 Coinbase Faucet:  https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet\n")
        print("Option C (Superchain Faucet):")
        print(f"  👉 Superchain:       https://console.optimism.io/faucet\n")
        print("Option D (Google Cloud Ethereum Sepolia + Bridge to Base):")
        print(f"  1. Claim at:         https://cloud.google.com/web3 (Ethereum Sepolia ETH)")
        print(f"  2. Bridge to Base:   https://bridge.base.org/deposit\n")
        print("After requesting faucet funds, run this script again:")
        print("  python scripts/deploy_and_transact.py\n")
        return balance_wei

    print(f"\n [✓] Wallet is funded with {balance_eth:.6f} ETH. Proceeding to execution!\n")
    return balance_wei


def compile_policy_wallet() -> tuple[list, str]:
    """Compile contracts/PolicyWallet.sol using solcx."""
    contract_path = ROOT_DIR / "contracts" / "PolicyWallet.sol"
    print(f"[*] Compiling {contract_path.name} with Solidity 0.8.20...")

    installed = solcx.get_installed_solc_versions()
    if not any(str(v).startswith("0.8.20") for v in installed):
        print("[*] Installing solc 0.8.20...")
        solcx.install_solc("0.8.20")

    solcx.set_solc_version("0.8.20")
    source = contract_path.read_text(encoding="utf-8")
    compiled = solcx.compile_source(source, solc_version="0.8.20", output_values=["abi", "bin"])

    contract_data = compiled["<stdin>:PolicyWallet"]
    abi = contract_data["abi"]
    bytecode = contract_data["bin"]
    print(f"[✓] Compilation successful. Bytecode size: {len(bytecode) // 2} bytes.")
    return abi, bytecode


def send_signed_transaction(w3: Web3, account: Account, tx_dict: dict, description: str) -> dict:
    """Build, sign, broadcast and wait for a transaction."""
    print(f"\n[*] Broadcasting Tx: {description}...")
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    tx_dict["nonce"] = nonce
    tx_dict["from"] = account.address
    tx_dict["chainId"] = CHAIN_ID

    # Estimate gas if not provided
    if "gas" not in tx_dict:
        try:
            estimated_gas = w3.eth.estimate_gas(tx_dict)
            tx_dict["gas"] = int(estimated_gas * 1.3)
        except Exception as e:
            print(f"    Notice: gas estimation fallback (1,500,000): {e}")
            tx_dict["gas"] = 1_500_000

    # Handle EIP-1559 or legacy gas
    latest_block = w3.eth.get_block("latest")
    if "baseFeePerGas" in latest_block and latest_block["baseFeePerGas"] is not None:
        base_fee = latest_block["baseFeePerGas"]
        priority_fee = w3.eth.max_priority_fee or w3.to_wei(0.1, "gwei")
        tx_dict["maxPriorityFeePerGas"] = priority_fee
        tx_dict["maxFeePerGas"] = int(base_fee * 1.5) + priority_fee
    else:
        tx_dict["gasPrice"] = w3.eth.gas_price

    signed_tx = account.sign_transaction(tx_dict)
    raw_tx = getattr(signed_tx, "raw_transaction", None) or getattr(signed_tx, "rawTransaction")
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    tx_hash_hex = tx_hash.hex()
    print(f"    Tx Hash: {tx_hash_hex}")
    print(f"    Explorer: {EXPLORER_BASE}/tx/{tx_hash_hex}")
    print("    Waiting for confirmation on Base Sepolia...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180, poll_latency=2)
    status_str = "SUCCESS" if receipt["status"] == 1 else "REVERTED"
    print(f"    Confirmed in Block #{receipt['blockNumber']} — Status: {status_str} (Gas Used: {receipt['gasUsed']})")

    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction {description} reverted on-chain!")

    return {
        "action": description,
        "tx_hash": tx_hash_hex,
        "block_number": receipt["blockNumber"],
        "gas_used": receipt["gasUsed"],
        "explorer_url": f"{EXPLORER_BASE}/tx/{tx_hash_hex}",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> None:
    load_dotenv(ENV_FILE, override=True)
    rpc_url = os.environ.get("BASE_SEPOLIA_RPC", os.environ.get("RPC_URL", DEFAULT_RPC_URL))
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print(f"[!] Error: Could not connect to RPC endpoint {rpc_url}")
        sys.exit(1)

    account, is_new = get_or_create_wallet()
    if is_new:
        print(f"[*] Generated new ephemeral keypair and saved to .env")

    balance = check_balance_and_guide(w3, account)
    if balance < w3.to_wei(0.0005, "ether"):
        sys.exit(0)

    # Compile contract
    abi, bytecode = compile_policy_wallet()

    executed_records: list[dict] = []

    # 1. Deploy Contract
    contract_factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    deploy_tx_data = contract_factory.constructor(account.address, account.address).build_transaction({
        "from": account.address,
        "chainId": CHAIN_ID,
    })
    deploy_record = send_signed_transaction(w3, account, deploy_tx_data, "1_Deploy_PolicyWallet")
    
    # Get deployed contract address from receipt
    receipt = w3.eth.get_transaction_receipt(deploy_record["tx_hash"])
    contract_address = receipt["contractAddress"]
    deploy_record["contract_address"] = contract_address
    print(f"\n[✓] PolicyWallet deployed at: {contract_address}")
    print(f"    Explorer: {EXPLORER_BASE}/address/{contract_address}")
    update_env_variable("WALLET_CONTRACT_ADDRESS", contract_address)
    executed_records.append(deploy_record)

    contract = w3.eth.contract(address=contract_address, abi=abi)

    # 2. setPolicy
    policy_hash = Web3.keccak(text="Orvilo Policy v1.0 - FinTechathon 2026")
    min_floor_usd = 500
    per_tx_cap = 1000
    daily_cap = 2000
    allowed_tokens: list[str] = []
    allowed_recipients: list[str] = [account.address]

    set_policy_tx = contract.functions.setPolicy(
        policy_hash,
        min_floor_usd,
        per_tx_cap,
        daily_cap,
        allowed_tokens,
        allowed_recipients,
    ).build_transaction({"from": account.address, "chainId": CHAIN_ID})
    rec_policy = send_signed_transaction(w3, account, set_policy_tx, "2_setPolicy_Guards")
    executed_records.append(rec_policy)

    # 3. pause
    pause_tx = contract.functions.pause().build_transaction({"from": account.address, "chainId": CHAIN_ID})
    rec_pause = send_signed_transaction(w3, account, pause_tx, "3_Emergency_Pause")
    executed_records.append(rec_pause)

    # 4. unpause
    unpause_tx = contract.functions.unpause().build_transaction({"from": account.address, "chainId": CHAIN_ID})
    rec_unpause = send_signed_transaction(w3, account, unpause_tx, "4_Emergency_Unpause")
    executed_records.append(rec_unpause)

    # 5. setOperator (Autonomous Agent key authorization)
    agent_operator_addr = "0x2B5AD5c4795c026514f8317c7a215E218DcCD6cF"
    set_operator_tx = contract.functions.setOperator(
        Web3.to_checksum_address(agent_operator_addr), True
    ).build_transaction({"from": account.address, "chainId": CHAIN_ID})
    rec_operator = send_signed_transaction(w3, account, set_operator_tx, "5_Authorize_Agent_Operator")
    executed_records.append(rec_operator)

    # Write evidence file
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "network": "Base Sepolia",
        "chain_id": CHAIN_ID,
        "contract_address": contract_address,
        "contract_explorer_url": f"{EXPLORER_BASE}/address/{contract_address}",
        "deployer_address": account.address,
        "transactions_count": len(executed_records),
        "executed_transactions": executed_records,
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[✓] Evidence successfully written to {EVIDENCE_FILE.relative_to(ROOT_DIR)}")

    print("\n" + "=" * 75)
    print(" SUMMARY OF REAL ON-CHAIN BASE SEPOLIA TRANSACTIONS")
    print("=" * 75)
    for rec in executed_records:
        print(f"Action: {rec['action']:<30} | Block: #{rec['block_number']} | Gas: {rec['gas_used']}")
        print(f"Explorer: {rec['explorer_url']}\n")
    print("=" * 75)


if __name__ == "__main__":
    main()
