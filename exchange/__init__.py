"""Exchange package for Autonomous Wallet Agent.

Provides live market feed (Coinbase WebSocket), scenario injections,
and trusted market state for the agent and web interface.
"""
from exchange.client import CoinbaseWebSocketClient
from exchange.emitter import MarketConditions, MarketScenarioEmitter
from exchange.service import ExchangeService, exchange_service

__all__ = [
    "CoinbaseWebSocketClient",
    "MarketScenarioEmitter",
    "MarketConditions",
    "ExchangeService",
    "exchange_service",
]
