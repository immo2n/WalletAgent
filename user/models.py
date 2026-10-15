"""User Wallet and Transaction Models for Autonomous Wallet Agent.

Defines schemas for wallet balances, transaction ledgers, and actor attribution
(USER manual operations vs AGENT autonomous operations).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Literal, Optional
import uuid


@dataclass
class WalletBalances:
    ETH: float = 1.50
    USDC: float = 1500.00
    WETH: float = 0.00

    def to_dict(self) -> Dict[str, float]:
        return {
            "ETH": round(self.ETH, 6),
            "USDC": round(self.USDC, 2),
            "WETH": round(self.WETH, 6),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WalletBalances:
        return cls(
            ETH=float(data.get("ETH", 1.50)),
            USDC=float(data.get("USDC", 1500.00)),
            WETH=float(data.get("WETH", 0.00)),
        )


@dataclass
class TransactionRecord:
    id: str
    timestamp: str
    actor: Literal["USER", "AGENT"]
    action: Literal["DEPOSIT", "WITHDRAW", "SWAP", "TRANSFER", "POLICY_ENFORCEMENT"]
    details: str
    amount: float
    token: str
    status: Literal["CONFIRMED", "BLOCKED_BY_GUARD", "FAILED"]
    tx_hash: str
    price_usd: Optional[float] = None
    reason: Optional[str] = None
    reasoning_report: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TransactionRecord:
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            actor=data["actor"],
            action=data["action"],
            details=data["details"],
            amount=float(data["amount"]),
            token=data["token"],
            status=data["status"],
            tx_hash=data["tx_hash"],
            price_usd=data.get("price_usd"),
            reason=data.get("reason"),
            reasoning_report=data.get("reasoning_report"),
        )


@dataclass
class UserState:
    wallet_address: str = "0x71C8366420A096207E90B01D252431792349039A"
    network: str = "Base Sepolia (84532)"
    balances: WalletBalances = field(default_factory=WalletBalances)
    transactions: List[TransactionRecord] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_reset: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_address": self.wallet_address,
            "network": self.network,
            "balances": self.balances.to_dict(),
            "transactions": [tx.to_dict() for tx in self.transactions],
            "created_at": self.created_at,
            "last_reset": self.last_reset,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserState:
        balances_data = data.get("balances", {})
        txs_data = data.get("transactions", [])
        return cls(
            wallet_address=data.get("wallet_address", "0x71C8366420A096207E90B01D252431792349039A"),
            network=data.get("network", "Base Sepolia (84532)"),
            balances=WalletBalances.from_dict(balances_data),
            transactions=[TransactionRecord.from_dict(tx) for tx in txs_data],
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_reset=data.get("last_reset", datetime.now(timezone.utc).isoformat()),
        )
