"""Unit tests for user database, wallet balances, and transaction ledger."""
import os
import tempfile
import pytest

from user.db import UserDatabase
from user.models import TransactionRecord, UserState, WalletBalances


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    db = UserDatabase(db_path=tmp_path)
    yield db
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


def test_initial_state(temp_db):
    state = temp_db.get_state()
    assert state.balances.ETH == 1.50
    assert state.balances.USDC == 1500.00
    assert len(state.transactions) == 5
    assert state.transactions[0].actor == "AGENT"
    assert any(tx.actor == "USER" for tx in state.transactions)


def test_update_balances(temp_db):
    updated = temp_db.update_balances(eth=3.25, usdc=2500.0)
    assert updated.balances.ETH == 3.25
    assert updated.balances.USDC == 2500.0

    state = temp_db.get_state()
    assert state.balances.ETH == 3.25
    assert state.balances.USDC == 2500.0


def test_add_transactions_user_and_agent(temp_db):
    # Add user transaction
    tx_user = temp_db.add_transaction(
        actor="USER",
        action="DEPOSIT",
        details="Manual testnet topup",
        amount=0.5,
        token="ETH",
        status="CONFIRMED",
    )
    assert tx_user.actor == "USER"
    assert tx_user.status == "CONFIRMED"

    # Add agent transaction
    tx_agent = temp_db.add_transaction(
        actor="AGENT",
        action="SWAP",
        details="Guarded autonomous swap",
        amount=200.0,
        token="USDC",
        status="CONFIRMED",
        reason="Trigger satisfied",
    )
    assert tx_agent.actor == "AGENT"
    assert tx_agent.reason == "Trigger satisfied"

    # Verify order: newest first
    state = temp_db.get_state()
    assert state.transactions[0].id == tx_agent.id
    assert state.transactions[1].id == tx_user.id


def test_reset_db(temp_db):
    temp_db.update_balances(eth=10.0, usdc=10.0)
    temp_db.add_transaction(actor="AGENT", action="SWAP", details="foo", amount=1, token="ETH", status="CONFIRMED")
    assert len(temp_db.get_state().transactions) == 6

    # Reset
    reset_state = temp_db.reset_db()
    assert reset_state.balances.ETH == 1.50
    assert reset_state.balances.USDC == 1500.00
    assert len(reset_state.transactions) == 5
