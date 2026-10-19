"""Exercise the supported Flask API surface against a running container."""
from __future__ import annotations

import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:5000"


def request(path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, object]:
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urlopen(req, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                raw = response.readline()
            else:
                raw = response.read()
            if "json" in content_type:
                return response.status, json.loads(raw)
            return response.status, raw.decode(errors="replace")
    except (HTTPError, URLError) as exc:
        raise AssertionError(f"{method} {path} failed: {exc}") from exc


def expect(path: str, method: str = "GET", payload: dict | None = None, status: int = 200) -> object:
    actual_status, result = request(path, method, payload)
    assert actual_status == status, f"{method} {path}: expected {status}, got {actual_status}: {result}"
    return result


def main() -> None:
    dashboard = expect("/", status=200)
    assert "WalletAgent" in dashboard
    market = expect("/api/market/live")
    assert "market" in market and "history" in market
    expect("/api/market/scenario", "POST", {"scenario": "GAS_DIP"})
    expect("/api/market/stream", status=200)

    wallet = expect("/api/user/wallet")
    assert "balances" in wallet and "transactions" in wallet
    expect("/api/wallet/balances")
    expect("/api/user/transactions")
    created_tx = expect(
        "/api/user/transactions",
        "POST",
        {"action": "TRANSFER", "details": "container smoke test", "amount": 1, "token": "USDC"},
        status=201,
    )
    expect(f"/api/user/transaction/{created_tx['id']}/reasoning")
    expect(f"/api/reasoning/report/{created_tx['tx_hash']}")

    verification = expect(
        "/api/verify",
        "POST",
        {"prompt": "Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars."},
    )
    assert verification["status"] == "VERIFIED"
    proposal_id = verification["proposal_id"]
    expect("/api/policy/workflow")
    expect("/api/policy/review", "POST", {"proposal_id": proposal_id})
    expect("/api/policy/approve", "POST", {"proposal_id": proposal_id})
    deployed = expect("/api/policy/deploy", "POST", {"proposal_id": proposal_id})
    assert deployed["success"] is True

    expect("/api/agent/status")
    expect("/api/agent/task")
    expect("/api/validate_intent", "POST", {"trade_usd": 100, "gas_gwei": 10, "execute": False})
    expect("/api/simulation/simulate", "POST", {"trade_usd": 100, "token": "ETH"})
    expect("/api/agent/schedule", "POST", {"amount_usd": 10, "token": "USDC"}, status=201)
    expect("/api/agent/pause", "POST")
    expect("/api/agent/resume", "POST")

    security = expect("/api/contract/security-status")
    assert security["network"] == "Base Sepolia (84532)"
    expect("/api/contract/pause", "POST")
    expect("/api/contract/unpause", "POST")
    expect("/api/contract/revoke-operator", "POST", {"operator": security["operator"]})
    expect(
        "/api/contract/revoke-allowance",
        "POST",
        {"token": "0x0000000000000000000000000000000000000001", "spender": security["operator"]},
    )
    expect("/api/contract/invalidate-policy", "POST")

    vectors = expect("/api/contract/attack-test/vectors")
    assert len(vectors) == 6
    for vector in vectors:
        result = expect("/api/contract/attack-test/run", "POST", {"attack_id": vector["id"]})
        assert result["status"] == "PASSED", result

    assistant = expect("/api/assistant/chat", "POST", {"message": "What is my current wallet balance?"})
    assert assistant.get("reply")
    expect("/api/reasoning/history")
    expect("/api/agent/task/delete", "POST")
    expect("/api/simulation/reset", "POST")
    print("Docker smoke test passed: dashboard, market, wallet, policy, agent, simulation, contract, attacks, assistant.")


if __name__ == "__main__":
    for attempt in range(30):
        try:
            main()
            break
        except (URLError, ConnectionError):
            if attempt == 29:
                raise
            time.sleep(2)
    else:
        raise AssertionError("Docker smoke test did not complete")
