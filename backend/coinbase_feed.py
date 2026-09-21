"""
AEON Coinbase Advanced Trade WebSocket Feed
Real-time price feed replacing MEXC REST polling for spot prices.

- Subscribes to `ticker` channel (public, no auth required)
- Maps Coinbase product IDs (BTC-USD) ↔ internal symbols (BTC/USDT)
- Auto-reconnects with exponential backoff on disconnect
- Falls back gracefully: callers check .covers(symbol) before using
- OHLCV / candle data still comes from MEXC REST (unchanged)
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

_WS_URL = "wss://advanced-trade-ws.coinbase.com"

# All symbols the rest of the system tracks, in internal format (BTC/USDT)
_TRACKED = [
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "SHIB/USDT", "DOT/USDT",
    "LINK/USDT", "TRX/USDT", "BCH/USDT", "LTC/USDT", "NEAR/USDT",
    "UNI/USDT", "APT/USDT", "ICP/USDT", "ETC/USDT", "FIL/USDT",
    "ATOM/USDT", "XLM/USDT", "ARB/USDT", "OP/USDT", "INJ/USDT",
    "HBAR/USDT", "VET/USDT", "GRT/USDT", "AAVE/USDT", "ALGO/USDT",
    "SAND/USDT", "AXS/USDT", "MANA/USDT", "XTZ/USDT", "FLOW/USDT",
    "NEO/USDT", "SNX/USDT", "CRV/USDT", "RUNE/USDT", "ZEC/USDT",
    "DASH/USDT", "COMP/USDT", "ENJ/USDT", "CHZ/USDT",
]


def _to_cb_id(symbol: str) -> str:
    """BTC/USDT  →  BTC-USD"""
    base = symbol.split("/")[0]
    return f"{base}-USD"


def _from_cb_id(product_id: str) -> str:
    """BTC-USD  →  BTC/USDT"""
    base = product_id.split("-")[0]
    return f"{base}/USDT"


class CoinbasePriceFeed:
    """
    Singleton async WebSocket client for Coinbase Advanced Trade ticker feed.

    Usage:
        price = coinbase_feed.get_price("BTC/USDT")   # None if not yet received
        ticker = coinbase_feed.get_ticker("ETH/USDT")  # dict or None
        if coinbase_feed.covers("SOL/USDT"):
            ...
    """

    def __init__(self):
        # Cache: internal_symbol → {price, change_24h, high_24h, low_24h, volume_24h, ts}
        self._cache: Dict[str, Dict] = {}
        self._active = False
        self._connected = False
        self._reconnect_delay = 2.0   # seconds, doubles on each failure up to _max_delay
        self._max_delay = 60.0
        self._product_ids = [_to_cb_id(s) for s in _TRACKED]
        self._last_heartbeat_ts: float = 0.0  # unix timestamp of last health heartbeat

    # ── Public API ────────────────────────────────────────────────────────────

    def covers(self, symbol: str) -> bool:
        """True if we have at least one live tick for this symbol."""
        return symbol in self._cache

    def get_price(self, symbol: str) -> Optional[float]:
        entry = self._cache.get(symbol)
        return entry["price"] if entry else None

    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Returns a dict compatible with MarketIntelligence.get_ticker_sync():
        {symbol, price, change_24h, high_24h, low_24h, volume_24h}
        Returns None if we have no data yet.
        """
        return self._cache.get(symbol)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_stats(self) -> Dict:
        return {
            "connected": self._connected,
            "symbols_live": len(self._cache),
            "sample": {s: v["price"] for s, v in list(self._cache.items())[:5]},
        }

    # ── Background task ───────────────────────────────────────────────────────

    async def run_forever(self):
        """Start the feed. Call once as an asyncio background task."""
        self._active = True
        delay = self._reconnect_delay
        while self._active:
            try:
                await self._connect_and_stream()
                delay = self._reconnect_delay  # reset on clean exit
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"CoinbaseFeed: disconnected ({e}), reconnecting in {delay:.0f}s")
            finally:
                self._connected = False
            if not self._active:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._max_delay)

    def stop(self):
        self._active = False

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _connect_and_stream(self):
        logger.info("CoinbaseFeed: connecting to %s", _WS_URL)
        async with websockets.connect(
            _WS_URL,
            ping_interval=20,
            ping_timeout=30,
            close_timeout=10,
        ) as ws:
            self._connected = True
            logger.info("CoinbaseFeed: connected — subscribing to %d symbols", len(self._product_ids))

            await ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": self._product_ids,
                "channel": "ticker",
            }))

            async for raw in ws:
                if not self._active:
                    break
                try:
                    self._handle_message(raw)
                except Exception as e:
                    logger.debug("CoinbaseFeed: message parse error: %s", e)

    def _handle_message(self, raw: str):
        msg = json.loads(raw)
        channel = msg.get("channel")
        if channel != "ticker":
            return

        for event in msg.get("events", []):
            for tick in event.get("tickers", []):
                product_id = tick.get("product_id", "")
                if not product_id:
                    continue
                try:
                    price = float(tick["price"])
                except (KeyError, ValueError, TypeError):
                    continue

                # Heartbeat for health monitor (throttled to once per 30s)
                now_ts = time.time()
                if now_ts - self._last_heartbeat_ts >= 30:
                    self._last_heartbeat_ts = now_ts
                    try:
                        from self_healer import self_healer
                        self_healer.heartbeat("coinbase_feed")
                    except Exception:
                        pass

                symbol = _from_cb_id(product_id)
                change = _safe_float(tick.get("price_percent_chg_24_h"))
                self._cache[symbol] = {
                    "symbol": symbol,
                    "price": price,
                    "last": price,           # ccxt-compat alias used by paper_trading, routes, engines
                    "change_24h": change,
                    "percentage": change,    # ccxt-compat alias used by telegram handlers
                    "high_24h": _safe_float(tick.get("high_52_w")) or _safe_float(tick.get("high_24_h")) or price,
                    "low_24h": _safe_float(tick.get("low_52_w")) or _safe_float(tick.get("low_24_h")) or price,
                    "volume_24h": _safe_float(tick.get("volume_24_h")),
                    "ts": time.time(),
                }


def _safe_float(val) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


# Singleton — imported everywhere
coinbase_feed = CoinbasePriceFeed()
