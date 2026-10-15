"""Live Coinbase WebSocket Exchange Client for Autonomous Wallet Agent.

Streams real-time sub-second ETH-USD ticks directly from Coinbase Exchange.
Includes auto-reconnect and offline fallback simulation.
"""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
import random
import threading
import time
from typing import Any, Callable, Deque, Dict, List, Optional
import urllib.request

logger = logging.getLogger("exchange.client")

COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"


class CoinbaseWebSocketClient:
    """Real-time WebSocket client for Coinbase ETH-USD ticker."""

    def __init__(self, product_id: str = "ETH-USD", max_history: int = 120) -> None:
        self.product_id = product_id
        self.max_history = max_history
        self.current_price: float = 2345.50
        self.high_24h: float = 2390.00
        self.low_24h: float = 2310.00
        self.volume_24h: float = 45200.00
        self.last_tick_time: str = datetime.now(timezone.utc).isoformat()
        self.is_connected: bool = False
        self.history: Deque[Dict[str, Any]] = deque(maxlen=max_history)
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

        # Seed initial history buffer with realistic curve
        now = time.time()
        for i in range(30):
            ts = now - (30 - i) * 2
            p = round(self.current_price + (random.random() - 0.5) * 4.0, 2)
            self.history.append({
                "time": datetime.fromtimestamp(ts, timezone.utc).strftime("%H:%M:%S"),
                "price": p,
                "timestamp": ts,
            })

    def subscribe_tick(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def start(self) -> None:
        """Start WebSocket listener in a background daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_async_loop, daemon=True, name="CoinbaseWSThread")
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False

    def _run_async_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._listen_websocket())
        except Exception as e:
            logger.warning(f"WebSocket loop terminated: {e}. Starting fallback ticker.")
        finally:
            loop.close()

    async def _listen_websocket(self) -> None:
        import websockets

        retry_count = 0
        while self._running:
            try:
                async with websockets.connect(
                    COINBASE_WS_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    sub_msg = {
                        "type": "subscribe",
                        "product_ids": [self.product_id],
                        "channels": ["ticker"],
                    }
                    await ws.send(json.dumps(sub_msg))
                    with self._lock:
                        self.is_connected = True
                    retry_count = 0

                    while self._running:
                        msg = await asyncio.wait_for(ws.recv(), timeout=15)
                        data = json.loads(msg)
                        if data.get("type") == "ticker" and "price" in data:
                            self._process_tick(data)
            except Exception as e:
                with self._lock:
                    self.is_connected = False
                retry_count += 1
                wait_s = min(2 ** retry_count, 10)
                # Run simulated ticks while disconnected so UI never freezes
                for _ in range(wait_s * 2):
                    if not self._running:
                        break
                    self._generate_synthetic_tick()
                    await asyncio.sleep(0.5)

    def _process_tick(self, data: Dict[str, Any]) -> None:
        price = float(data["price"])
        high = float(data.get("high_24h", self.high_24h))
        low = float(data.get("low_24h", self.low_24h))
        vol = float(data.get("volume_24h", self.volume_24h))
        iso_time = data.get("time", datetime.now(timezone.utc).isoformat())

        # Extract HH:MM:SS for chart
        try:
            dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
            time_label = dt.strftime("%H:%M:%S")
        except Exception:
            time_label = datetime.now(timezone.utc).strftime("%H:%M:%S")

        tick = {
            "time": time_label,
            "price": price,
            "high_24h": high,
            "low_24h": low,
            "volume_24h": vol,
            "timestamp": time.time(),
            "source": "COINBASE_WS",
        }

        with self._lock:
            self.current_price = price
            self.high_24h = high
            self.low_24h = low
            self.volume_24h = vol
            self.last_tick_time = iso_time
            self.history.append(tick)
            subs = list(self._subscribers)

        for callback in subs:
            try:
                callback(tick)
            except Exception:
                pass

    def _generate_synthetic_tick(self) -> None:
        """Simulate micro-movement if internet connection drops."""
        delta = (random.random() - 0.49) * 0.85
        with self._lock:
            self.current_price = round(max(500.0, self.current_price + delta), 2)
            time_label = datetime.now(timezone.utc).strftime("%H:%M:%S")
            tick = {
                "time": time_label,
                "price": self.current_price,
                "high_24h": self.high_24h,
                "low_24h": self.low_24h,
                "volume_24h": self.volume_24h,
                "timestamp": time.time(),
                "source": "SYNTHETIC_SIM",
            }
            self.history.append(tick)
            subs = list(self._subscribers)

        for callback in subs:
            try:
                callback(tick)
            except Exception:
                pass

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "product_id": self.product_id,
                "price": self.current_price,
                "high_24h": self.high_24h,
                "low_24h": self.low_24h,
                "volume_24h": self.volume_24h,
                "is_connected": self.is_connected,
                "last_tick_time": self.last_tick_time,
                "history": list(self.history),
            }
