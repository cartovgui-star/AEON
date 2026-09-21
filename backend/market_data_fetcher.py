"""
market_data_fetcher.py — Multi-Asset OHLCV & Weight Fetcher
============================================================
Provides candle data for BTC, ETH, SOL, BNB, XRP used by
OracleEntropyGate to compute H_market.

Data priority:
  1. Coinbase Advanced Trade (ccxt coinbasepro)
  2. MEXC REST (ccxt mexc) — fallback

Weight priority:
  1. CoinGecko /coins/markets (weekly cache)
  2. Static fallback weights if API fails
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)

# ── Asset definitions ──────────────────────────────────────────────────────────

ASSETS: List[str] = ["BTC", "ETH", "SOL", "BNB", "XRP"]

# CoinGecko IDs for each asset
_COINGECKO_IDS: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
}

# Symbol suffixes for each exchange
_MEXC_SYMBOLS: Dict[str, str] = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "SOL": "SOL/USDT",
    "BNB": "BNB/USDT",
    "XRP": "XRP/USDT",
}

# Static fallback weights (sum = 1.0)
STATIC_WEIGHTS: Dict[str, float] = {
    "BTC": 0.50,
    "ETH": 0.20,
    "SOL": 0.10,
    "BNB": 0.10,
    "XRP": 0.10,
}

_COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=10"
)

# ── Weight cache ───────────────────────────────────────────────────────────────

class _WeightCache:
    TTL = 7 * 24 * 3600  # 1 week

    def __init__(self) -> None:
        self._weights: Dict[str, float] = {}
        self._fetched_at: float = 0.0

    def is_fresh(self) -> bool:
        return bool(self._weights) and (time.time() - self._fetched_at) < self.TTL

    def get(self) -> Dict[str, float]:
        return self._weights if self._weights else STATIC_WEIGHTS

    def set(self, weights: Dict[str, float]) -> None:
        self._weights = weights
        self._fetched_at = time.time()


_weight_cache = _WeightCache()


async def fetch_market_cap_weights() -> Dict[str, float]:
    """
    Fetch top-10 coins from CoinGecko and return normalised weights
    for the 5 monitored assets.  Falls back to static weights on any error.
    """
    if _weight_cache.is_fresh():
        return _weight_cache.get()

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(_COINGECKO_URL) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"[MarketDataFetcher] CoinGecko returned HTTP {resp.status} — using static weights"
                    )
                    return STATIC_WEIGHTS
                data = await resp.json()

        # Build market-cap map for our assets
        id_to_asset = {v: k for k, v in _COINGECKO_IDS.items()}
        caps: Dict[str, float] = {}
        for coin in data:
            asset = id_to_asset.get(coin.get("id", ""))
            if asset:
                caps[asset] = float(coin.get("market_cap") or 0)

        total = sum(caps.values())
        if total <= 0:
            logger.warning("[MarketDataFetcher] CoinGecko: zero total market cap — using static weights")
            return STATIC_WEIGHTS

        weights = {a: caps.get(a, 0) / total for a in ASSETS}
        _weight_cache.set(weights)
        logger.info(f"[MarketDataFetcher] Weights refreshed from CoinGecko: {weights}")
        return weights

    except Exception as exc:
        logger.warning(f"[MarketDataFetcher] Weight fetch failed ({exc}) — using static weights")
        return STATIC_WEIGHTS


# ── OHLCV fetching ─────────────────────────────────────────────────────────────

def _fetch_ohlcv_sync(symbol_map: Dict[str, str], limit: int) -> Dict[str, List]:
    """
    Synchronous OHLCV fetch via CCXT (runs in executor thread).
    Tries Coinbase first, then MEXC per asset.
    Returns {asset: [[ts, o, h, l, c, v], ...]}
    """
    import ccxt

    results: Dict[str, List] = {}

    # Attempt Coinbase for BTC and ETH (most liquid, always on CB)
    try:
        cb = ccxt.coinbase({"enableRateLimit": True})
        cb_symbols = {
            "BTC": "BTC-USDT",
            "ETH": "ETH-USDT",
            "SOL": "SOL-USDT",
            "BNB": "BNB-USDT",
            "XRP": "XRP-USDT",
        }
        for asset in ASSETS:
            try:
                candles = cb.fetch_ohlcv(cb_symbols[asset], "1h", limit=limit)
                if candles and len(candles) >= 21:
                    results[asset] = candles
            except Exception:
                pass  # Will be covered by MEXC fallback
    except Exception:
        pass

    # MEXC fallback for any asset not yet fetched
    missing = [a for a in ASSETS if a not in results]
    if missing:
        try:
            mexc = ccxt.mexc({"enableRateLimit": True})
            for asset in missing:
                try:
                    sym = symbol_map.get(asset, f"{asset}/USDT")
                    candles = mexc.fetch_ohlcv(sym, "1h", limit=limit)
                    if candles and len(candles) >= 21:
                        results[asset] = candles
                except Exception as exc:
                    logger.warning(f"[MarketDataFetcher] MEXC {asset} failed: {exc}")
        except Exception as exc:
            logger.warning(f"[MarketDataFetcher] MEXC init failed: {exc}")

    return results


async def fetch_ohlcv_all(limit: int = 252) -> Dict[str, List]:
    """
    Async wrapper — fetches `limit` 1h candles for all 5 assets.
    Returns {asset: [[ts, o, h, l, c, v], ...]}
    """
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None,
            _fetch_ohlcv_sync,
            _MEXC_SYMBOLS,
            limit,
        )
        fetched = list(results.keys())
        missing = [a for a in ASSETS if a not in results]
        if fetched:
            logger.info(f"[MarketDataFetcher] OHLCV fetched for: {fetched}")
        if missing:
            logger.warning(f"[MarketDataFetcher] OHLCV missing for: {missing}")
        return results
    except Exception as exc:
        logger.error(f"[MarketDataFetcher] fetch_ohlcv_all failed: {exc}")
        return {}
