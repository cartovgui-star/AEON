"""
Multi-exchange Orderbook Aggregator
Pulls public orderbook data from OKX + Binance + Bybit, aggregates into
price buckets, identifies "walls" (large concentrations), computes
bid/ask imbalance. Coinglass-style data without the price tag.
"""
from fastapi import APIRouter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

EXCHANGES = ["OKX", "Coinbase", "Kraken", "Bitget", "Gate.io", "KuCoin"]

# ──────────────────────────────────────────────────────────────────────────
# Per-exchange orderbook fetchers — public APIs, no auth required, no geo block.
# Each returns: (bids, asks) where each side is [(price, size_base), ...]
# size_base = size in the base asset (e.g. BTC for BTC/USDT).
# ──────────────────────────────────────────────────────────────────────────

async def _fetch_okx(session: aiohttp.ClientSession, sym: str) -> Tuple[List, List]:
    """OKX: BTC-USDT"""
    inst = f"{sym}-USDT"
    url = f"https://www.okx.com/api/v5/market/books?instId={inst}&sz=200"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200: return [], []
            data = await r.json()
            if data.get("code") != "0" or not data.get("data"): return [], []
            book = data["data"][0]
            return ([(float(b[0]), float(b[1])) for b in book.get("bids", [])],
                    [(float(a[0]), float(a[1])) for a in book.get("asks", [])])
    except Exception as e:
        logger.warning(f"OKX orderbook fetch failed: {e}")
        return [], []


async def _fetch_coinbase(session: aiohttp.ClientSession, sym: str) -> Tuple[List, List]:
    """Coinbase: BTC-USD. USD not USDT but liquid + closely correlated."""
    pair = f"{sym}-USD"
    url = f"https://api.exchange.coinbase.com/products/{pair}/book?level=2"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200: return [], []
            data = await r.json()
            return ([(float(b[0]), float(b[1])) for b in data.get("bids", [])[:200]],
                    [(float(a[0]), float(a[1])) for a in data.get("asks", [])[:200]])
    except Exception as e:
        logger.warning(f"Coinbase orderbook fetch failed: {e}")
        return [], []


async def _fetch_kraken(session: aiohttp.ClientSession, sym: str) -> Tuple[List, List]:
    """Kraken: XBTUSDT for BTC, otherwise <sym>USDT. Returns up to 500 levels."""
    # Kraken uses XBT for BTC and lists pairs as e.g. XBTUSDT, ETHUSDT, SOLUSDT
    k_sym = "XBT" if sym == "BTC" else sym
    pair = f"{k_sym}USDT"
    url = f"https://api.kraken.com/0/public/Depth?pair={pair}&count=200"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200: return [], []
            data = await r.json()
            if data.get("error") or not data.get("result"): return [], []
            # Kraken nests under the pair key — first key in result is the data
            book = next(iter(data["result"].values()))
            return ([(float(b[0]), float(b[1])) for b in book.get("bids", [])],
                    [(float(a[0]), float(a[1])) for a in book.get("asks", [])])
    except Exception as e:
        logger.warning(f"Kraken orderbook fetch failed: {e}")
        return [], []


async def _fetch_bitget(session: aiohttp.ClientSession, sym: str) -> Tuple[List, List]:
    """Bitget v2 spot: BTCUSDT"""
    pair = f"{sym}USDT"
    url = f"https://api.bitget.com/api/v2/spot/market/orderbook?symbol={pair}&limit=150"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200: return [], []
            data = await r.json()
            if data.get("code") != "00000" or not data.get("data"): return [], []
            d = data["data"]
            return ([(float(b[0]), float(b[1])) for b in d.get("bids", [])],
                    [(float(a[0]), float(a[1])) for a in d.get("asks", [])])
    except Exception as e:
        logger.warning(f"Bitget orderbook fetch failed: {e}")
        return [], []


async def _fetch_gateio(session: aiohttp.ClientSession, sym: str) -> Tuple[List, List]:
    """Gate.io spot: BTC_USDT"""
    pair = f"{sym}_USDT"
    url = f"https://api.gateio.ws/api/v4/spot/order_book?currency_pair={pair}&limit=100"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200: return [], []
            data = await r.json()
            return ([(float(b[0]), float(b[1])) for b in data.get("bids", [])],
                    [(float(a[0]), float(a[1])) for a in data.get("asks", [])])
    except Exception as e:
        logger.warning(f"Gate.io orderbook fetch failed: {e}")
        return [], []


async def _fetch_kucoin(session: aiohttp.ClientSession, sym: str) -> Tuple[List, List]:
    """KuCoin: BTC-USDT, level2_100 = top 100 levels"""
    pair = f"{sym}-USDT"
    url = f"https://api.kucoin.com/api/v1/market/orderbook/level2_100?symbol={pair}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status != 200: return [], []
            data = await r.json()
            if data.get("code") != "200000" or not data.get("data"): return [], []
            d = data["data"]
            return ([(float(b[0]), float(b[1])) for b in d.get("bids", [])],
                    [(float(a[0]), float(a[1])) for a in d.get("asks", [])])
    except Exception as e:
        logger.warning(f"KuCoin orderbook fetch failed: {e}")
        return [], []


FETCHERS = {
    "OKX":      _fetch_okx,
    "Coinbase": _fetch_coinbase,
    "Kraken":   _fetch_kraken,
    "Bitget":   _fetch_bitget,
    "Gate.io":  _fetch_gateio,
    "KuCoin":   _fetch_kucoin,
}


# ──────────────────────────────────────────────────────────────────────────
# Aggregation logic
# ──────────────────────────────────────────────────────────────────────────

def _pick_bucket_size(mark_price: float) -> float:
    """Choose a reasonable bucket size based on price magnitude."""
    if mark_price >= 10000:  return 100.0   # BTC: $100 buckets
    if mark_price >= 1000:   return 10.0    # ETH: $10 buckets
    if mark_price >= 100:    return 1.0     # SOL: $1 buckets
    if mark_price >= 10:     return 0.10
    if mark_price >= 1:      return 0.01
    return 0.001


def _bucket(price: float, bucket: float) -> float:
    """Round price down to nearest bucket."""
    return round(int(price / bucket) * bucket, 8)


@router.get("/orderbook/aggregate/{symbol}")
async def aggregate_orderbook(symbol: str, levels: int = 30, range_pct: float = 2.0):
    """
    Aggregate orderbook across OKX + Binance + Bybit.

    Args:
      symbol: BTC, ETH, SOL, etc. (USDT pair implied)
      levels: how many price buckets to return on each side (max 50)
      range_pct: ±% from mark price to include (default 2%)

    Returns:
      mark_price, bids[], asks[], totals, imbalance, walls, exchanges_used
    """
    levels = max(5, min(int(levels), 50))
    range_pct = max(0.5, min(float(range_pct), 10.0))

    sym_clean = symbol.upper().replace("/USDT", "").replace("USDT", "").replace("/", "")

    async with aiohttp.ClientSession() as session:
        # Fetch all exchanges in parallel
        tasks = [FETCHERS[ex](session, sym_clean) for ex in EXCHANGES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    exchanges_used = []
    all_bids: List[Tuple[float, float, str]] = []  # (price, size, exchange)
    all_asks: List[Tuple[float, float, str]] = []
    for ex_name, res in zip(EXCHANGES, results):
        if isinstance(res, Exception) or not isinstance(res, tuple):
            continue
        bids, asks = res
        if not bids or not asks:
            continue
        exchanges_used.append(ex_name)
        for p, sz in bids:
            all_bids.append((p, sz, ex_name))
        for p, sz in asks:
            all_asks.append((p, sz, ex_name))

    if not exchanges_used or not all_bids or not all_asks:
        return {
            "symbol": f"{sym_clean}/USDT",
            "error": "No exchange data available",
            "exchanges_attempted": EXCHANGES,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Mark price = mid of best bid/ask averaged across exchanges
    best_bid = max(p for p, _, _ in all_bids)
    best_ask = min(p for p, _, _ in all_asks)
    mark_price = (best_bid + best_ask) / 2.0

    # Filter to range
    lo = mark_price * (1 - range_pct / 100.0)
    hi = mark_price * (1 + range_pct / 100.0)
    filtered_bids = [(p, sz, ex) for p, sz, ex in all_bids if p >= lo]
    filtered_asks = [(p, sz, ex) for p, sz, ex in all_asks if p <= hi]

    bucket = _pick_bucket_size(mark_price)

    # Aggregate into buckets: {price_bucket: {"size": total_base, "size_usd": total_usd, "exchanges": set}}
    def aggregate(orders, side):
        buckets: Dict[float, Dict] = {}
        for p, sz, ex in orders:
            b = _bucket(p, bucket)
            if b not in buckets:
                buckets[b] = {"size": 0.0, "exchanges": set()}
            buckets[b]["size"] += sz
            buckets[b]["exchanges"].add(ex)
        out = []
        for b, info in buckets.items():
            size_usd = info["size"] * b
            out.append({
                "price": b,
                "size": round(info["size"], 6),
                "size_usd": round(size_usd, 2),
                "exchanges": sorted(info["exchanges"]),
            })
        # Sort: bids descending (closest to mark first), asks ascending
        out.sort(key=lambda x: x["price"], reverse=(side == "bid"))
        return out[:levels]

    bid_buckets = aggregate(filtered_bids, "bid")
    ask_buckets = aggregate(filtered_asks, "ask")

    # Compute walls = top 20% by size_usd within each side
    def find_walls(buckets, top_pct=0.20):
        if not buckets:
            return []
        sorted_by_size = sorted(buckets, key=lambda x: x["size_usd"], reverse=True)
        # threshold = size of the (top_pct * len) bucket
        n = max(1, int(len(sorted_by_size) * top_pct))
        threshold = sorted_by_size[n - 1]["size_usd"] if sorted_by_size else 0
        # Also require at least 1.5× the median
        sizes = [b["size_usd"] for b in buckets]
        median = sorted(sizes)[len(sizes) // 2] if sizes else 0
        min_wall = max(threshold, median * 2.0)
        walls = [b for b in buckets if b["size_usd"] >= min_wall]
        return walls

    bid_walls = find_walls(bid_buckets)
    ask_walls = find_walls(ask_buckets)

    # Mark walls in bid/ask arrays
    wall_bid_prices = {w["price"] for w in bid_walls}
    wall_ask_prices = {w["price"] for w in ask_walls}
    for b in bid_buckets: b["is_wall"] = b["price"] in wall_bid_prices
    for a in ask_buckets: a["is_wall"] = a["price"] in wall_ask_prices

    total_bid_usd = sum(b["size_usd"] for b in bid_buckets)
    total_ask_usd = sum(a["size_usd"] for a in ask_buckets)
    ratio = (total_bid_usd / total_ask_usd) if total_ask_usd > 0 else 1.0

    if ratio > 1.15:
        imbalance = "BID HEAVY"
        imbalance_dir = "LONG"
    elif ratio < 0.87:
        imbalance = "ASK HEAVY"
        imbalance_dir = "SHORT"
    else:
        imbalance = "BALANCED"
        imbalance_dir = "NEUTRAL"

    return {
        "symbol": f"{sym_clean}/USDT",
        "mark_price": round(mark_price, 8),
        "best_bid": round(best_bid, 8),
        "best_ask": round(best_ask, 8),
        "spread_pct": round((best_ask - best_bid) / mark_price * 100, 4),
        "bucket_size": bucket,
        "range_pct": range_pct,
        "bids": bid_buckets,
        "asks": ask_buckets,
        "total_bid_usd": round(total_bid_usd, 2),
        "total_ask_usd": round(total_ask_usd, 2),
        "bid_ask_ratio": round(ratio, 3),
        "imbalance": imbalance,
        "imbalance_direction": imbalance_dir,
        "walls": {
            "bids": sorted(bid_walls, key=lambda x: x["size_usd"], reverse=True)[:5],
            "asks": sorted(ask_walls, key=lambda x: x["size_usd"], reverse=True)[:5],
        },
        "exchanges_used": exchanges_used,
        "exchanges_attempted": EXCHANGES,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
