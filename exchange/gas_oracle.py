"""Live Ethereum L1 Mainnet Gas Oracle.

Fetches real-world base fees, priority tips, and latest block numbers directly
from Ethereum Mainnet JSON-RPC nodes with multi-endpoint failover and background sync.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional
import urllib.request

logger = logging.getLogger("exchange.gas_oracle")


class EthereumL1GasOracle:
    """Thread-safe live Ethereum Mainnet gas oracle with automatic RPC failover."""

    DEFAULT_RPCS: List[str] = [
        "https://ethereum.publicnode.com",
        "https://1rpc.io/eth",
        "https://mainnet.gateway.tenderly.co",
        "https://eth.drpc.org",
    ]

    def __init__(
        self,
        rpc_endpoints: Optional[List[str]] = None,
        poll_interval_sec: float = 8.0,
    ) -> None:
        self.rpc_endpoints = list(rpc_endpoints or self.DEFAULT_RPCS)
        self.poll_interval_sec = poll_interval_sec
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Cached state
        self.total_gas_gwei: float = 18.0
        self.base_fee_gwei: float = 1.0
        self.priority_fee_gwei: float = 1.5
        self.latest_block: int = 0
        self.active_rpc: str = self.rpc_endpoints[0]
        self.is_connected: bool = False
        self.last_sync_time: float = 0.0

        # Perform initial sync synchronously
        self._fetch_live_gas()

    def start(self) -> None:
        """Start background polling thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._poll_loop,
                daemon=True,
                name="EthereumL1GasOraclePoll",
            )
            self._thread.start()
            logger.info("Ethereum L1 Gas Oracle background sync active.")

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._fetch_live_gas()
            except Exception as e:
                logger.error(f"Error in L1 gas oracle poll loop: {e}")
            time.sleep(self.poll_interval_sec)

    def _rpc_call(self, endpoint: str, method: str, params: List[Any]) -> Dict[str, Any]:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "AutonomousWalletAgent/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _fetch_live_gas(self) -> bool:
        """Attempt to fetch live base fee and gas price across candidate RPCs."""
        for rpc in self.rpc_endpoints:
            try:
                # 1. Fetch latest fee history (base fees and priority tips for last 4 blocks)
                fee_resp = self._rpc_call(
                    rpc,
                    "eth_feeHistory",
                    [4, "latest", [25, 50, 75]],
                )

                if "result" in fee_resp and fee_resp["result"]:
                    res = fee_resp["result"]
                    base_fees = res.get("baseFeePerGas", [])
                    oldest_block_hex = res.get("oldestBlock", "0x0")
                    oldest_block = int(oldest_block_hex, 16)
                    latest_block = oldest_block + len(base_fees) - 1

                    # Latest block base fee in gwei
                    latest_base_wei = int(base_fees[-1], 16) if base_fees else 1000000000
                    base_gwei = round(latest_base_wei / 1e9, 3)

                    # Median priority tip estimate
                    rewards = res.get("reward", [])
                    tip_wei = 1500000000  # Default 1.5 gwei tip
                    if rewards and rewards[-1]:
                        tip_wei = int(rewards[-1][1], 16)  # 50th percentile reward
                    priority_gwei = round(tip_wei / 1e9, 2)

                    total_gwei = round(base_gwei + priority_gwei, 2)

                    with self._lock:
                        self.base_fee_gwei = base_gwei
                        self.priority_fee_gwei = priority_gwei
                        self.total_gas_gwei = max(0.5, total_gwei)
                        self.latest_block = latest_block
                        self.active_rpc = rpc
                        self.is_connected = True
                        self.last_sync_time = time.time()

                    logger.debug(
                        f"Synced Ethereum L1 Gas: Base={base_gwei} gwei, Tip={priority_gwei} gwei, "
                        f"Total={total_gwei} gwei (Block #{latest_block} via {rpc})"
                    )
                    return True

                # Fallback to simple eth_gasPrice if eth_feeHistory unsupported
                gas_resp = self._rpc_call(rpc, "eth_gasPrice", [])
                if "result" in gas_resp:
                    gas_wei = int(gas_resp["result"], 16)
                    total_gwei = round(gas_wei / 1e9, 2)
                    with self._lock:
                        self.total_gas_gwei = max(0.5, total_gwei)
                        self.base_fee_gwei = round(total_gwei * 0.6, 2)
                        self.priority_fee_gwei = round(total_gwei * 0.4, 2)
                        self.active_rpc = rpc
                        self.is_connected = True
                        self.last_sync_time = time.time()
                    return True

            except Exception as e:
                logger.warning(f"L1 RPC {rpc} failed: {e}. Trying next failover endpoint...")
                continue

        logger.error("All Ethereum L1 RPC endpoints failed to respond. Retaining previous gas cache.")
        return False

    def get_gas_snapshot(self) -> Dict[str, Any]:
        """Fetch current live gas metrics."""
        with self._lock:
            return {
                "total_gas_gwei": self.total_gas_gwei,
                "base_fee_gwei": self.base_fee_gwei,
                "priority_fee_gwei": self.priority_fee_gwei,
                "latest_block": self.latest_block,
                "active_rpc": self.active_rpc,
                "is_connected": self.is_connected,
                "last_sync_time": self.last_sync_time,
            }


# Global singleton instance
l1_gas_oracle = EthereumL1GasOracle()
