"""JSON-based Database System for User Wallet State and Transactions.

Provides persistent storage, easy reset mechanism for simulations,
and transaction logging partitioned by actor (USER manual vs AGENT autonomous).
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import threading
from typing import Any, Dict, List, Literal, Optional
import uuid

from user.models import TransactionRecord, UserState, WalletBalances

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "wallet_db.json")


class UserDatabase:
    """Thread-safe JSON file database for wallet balances and transaction history."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        self.db_path = os.path.abspath(db_path)
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Create or initialize the database with default state if empty."""
        with self._lock:
            if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
                self._write_default_state()

    def _write_default_state(self) -> UserState:
        now_iso = datetime.now(timezone.utc).isoformat()
        initial_txs = [
            TransactionRecord(
                id="tx-onchain-operator",
                timestamp=now_iso,
                actor="AGENT",
                action="POLICY_ENFORCEMENT",
                details="Autonomous Operator Authorization on Base Sepolia (Block #48349787)",
                amount=0.00,
                token="ETH",
                status="CONFIRMED",
                tx_hash="0xe7da3881004d6b7cd14fae51a6900c5904c1039e608a3fd2f8057fe1635f690f",
                price_usd=2409.37,
                reason="EVM Operator authorized via on-chain PolicyWallet.sol call",
                is_onchain=True,
            ),
            TransactionRecord(
                id="tx-onchain-unpause",
                timestamp=now_iso,
                actor="AGENT",
                action="POLICY_ENFORCEMENT",
                details="Emergency Unpause Restored Execution on Base Sepolia (Block #48349785)",
                amount=0.00,
                token="ETH",
                status="CONFIRMED",
                tx_hash="0x38fca19438151fe9f56f206cd285c8a23a365fae771650f659232e53cc738822",
                price_usd=2409.37,
                reason="Verified unpause state broadcasted and mined",
                is_onchain=True,
            ),
            TransactionRecord(
                id="tx-onchain-pause",
                timestamp=now_iso,
                actor="AGENT",
                action="POLICY_ENFORCEMENT",
                details="Emergency Pause Killswitch Verification on Base Sepolia (Block #48349783)",
                amount=0.00,
                token="ETH",
                status="CONFIRMED",
                tx_hash="0xdd853edcaa73408046a2aff4c5b0f92d94d8ae805a433d66c3eb210bf67bd9a3",
                price_usd=2409.37,
                reason="On-chain emergency pause validated",
                is_onchain=True,
            ),
            TransactionRecord(
                id="tx-onchain-policy",
                timestamp=now_iso,
                actor="USER",
                action="POLICY_ENFORCEMENT",
                details="Configured Formal Invariant Floor ($500) & Daily Cap on Base Sepolia (Block #48349781)",
                amount=0.00,
                token="ETH",
                status="CONFIRMED",
                tx_hash="0x42a5e6e3140a3954e118cc8961a322a65cded9dd60e64a0538805d704e6c6400",
                price_usd=2409.37,
                reason="Policy rules set on smart contract PolicyWallet.sol",
                is_onchain=True,
            ),
            TransactionRecord(
                id="tx-onchain-deploy",
                timestamp=now_iso,
                actor="USER",
                action="POLICY_ENFORCEMENT",
                details="Deployed PolicyWallet Smart Contract to Base Sepolia (Block #48349779)",
                amount=0.00,
                token="ETH",
                status="CONFIRMED",
                tx_hash="0xb3a5e3044fa1ed5f0b40da4573bd1a6f68e2dd6290bfb17f7693b7a705624a40",
                price_usd=2409.37,
                reason="Contract Address: 0xfCF10bE8546981b2645A7BAE6a5Efe41C08E3d6E",
                is_onchain=True,
            ),
        ]
        state = UserState(
            wallet_address="0x71C8366420A096207E90B01D252431792349039A",
            network="Base Sepolia (84532)",
            balances=WalletBalances(ETH=1.50, USDC=1500.00, WETH=0.00),
            transactions=initial_txs,
            created_at=now_iso,
            last_reset=now_iso,
        )
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)
        return state

    def get_state(self) -> UserState:
        """Fetch current user state from database."""
        with self._lock:
            if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
                return self._write_default_state()
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return UserState.from_dict(data)
            except Exception:
                return self._write_default_state()

    def update_balances(
        self,
        eth: Optional[float] = None,
        usdc: Optional[float] = None,
        weth: Optional[float] = None,
    ) -> UserState:
        """Update wallet balances and persist to database."""
        with self._lock:
            state = self.get_state()
            if eth is not None:
                state.balances.ETH = max(0.0, float(eth))
            if usdc is not None:
                state.balances.USDC = max(0.0, float(usdc))
            if weth is not None:
                state.balances.WETH = max(0.0, float(weth))

            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)
            return state

    def add_transaction(
        self,
        actor: Literal["USER", "AGENT"],
        action: Literal["DEPOSIT", "WITHDRAW", "SWAP", "TRANSFER", "POLICY_ENFORCEMENT"],
        details: str,
        amount: float,
        token: str,
        status: Literal["CONFIRMED", "BLOCKED_BY_GUARD", "FAILED"],
        tx_hash: Optional[str] = None,
        price_usd: Optional[float] = None,
        reason: Optional[str] = None,
        reasoning_report: Optional[Dict[str, Any]] = None,
        is_onchain: bool = False,
    ) -> TransactionRecord:
        """Append a new transaction record to ledger."""
        if not tx_hash:
            tx_hash = "0x" + uuid.uuid4().hex + uuid.uuid4().hex

        record = TransactionRecord(
            id=f"tx-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:4]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=actor,
            action=action,
            details=details,
            amount=float(amount),
            token=token.upper(),
            status=status,
            tx_hash=tx_hash,
            price_usd=price_usd,
            reason=reason,
            reasoning_report=reasoning_report,
            is_onchain=is_onchain,
        )

        with self._lock:
            state = self.get_state()
            # Prepend newest transactions
            state.transactions.insert(0, record)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)
            return record

    def get_transaction(self, tx_id: str) -> Optional[TransactionRecord]:
        """Find transaction record by ID or hash."""
        with self._lock:
            state = self.get_state()
            for tx in state.transactions:
                if tx.id == tx_id or tx.tx_hash == tx_id:
                    return tx
            return None

    def reset_db(self) -> UserState:
        """Reset database to initial clean state with fresh simulation funds."""
        with self._lock:
            return self._write_default_state()


# Global default database singleton
user_db = UserDatabase()
