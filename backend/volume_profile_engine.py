"""
HYPER ACCURACY ENGINE
=====================
Volume Profile + Liquidation Heatmap + Orderbook + BTC Macro Gate
Three-layer analysis engine for institutional-grade signal generation:

1. VOLUME SESSION PROFILE (Volume at Price)
   - POC (Point of Control) = price with highest volume = strongest S/R
   - Value Area High/Low (70% of total volume)
   - HVN (High Volume Nodes) = congestion = support/resistance zones
   - LVN (Low Volume Nodes) = thin zones = price accelerates through
   - Naked POC = unvisited POC = price magnet

2. LIQUIDATION HEATMAP
   - Estimates where leveraged longs/shorts get liquidated at 5x/10x/20x/50x
   - Maps open interest distribution to price levels
   - Identifies "liquidity clusters" = dense liq zones price hunts
   - Long liq cluster above = bearish sweep target (market makers push up, rekt longs, reverse)
   - Short liq cluster below = bullish sweep target

3. ORDERBOOK DEPTH ANALYSIS
   - Bid/ask walls (large stacked limit orders)
   - Real-time bid/ask imbalance ratio
   - Sweep detection (wall was absorbed/eaten = momentum)
   - Iceberg detection (wall keeps refilling = institutional accumulation)

SIGNAL LOGIC:
- Price enters LVN + liq cluster ahead → SWEEP HUNT signal (direction toward cluster)
- Price bounces at HVN + CVD confirms + bid/ask wall holds → CONTINUATION
- Naked POC untouched → MAGNET signal (price will revisit)
- Large wall swept + CVD spike → MOMENTUM continuation
- Liq cluster swept + price reverses + CVD diverges → REVERSAL

DATA SOURCES:
- MEXC (OHLCV, trades, orderbook - no geo-restrictions)
- MEXC contract API (OI data, funding rates, tickers for liq estimates)
"""

import asyncio
import aiohttp
import logging
import traceback
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import ccxt
from okx_rate_limiter import OKX_SEM

logger = logging.getLogger(__name__)


def _to_ccxt_symbol(symbol: str) -> str:
    """Normalize any symbol format to CCXT BTC/USDT format.
    Handles: BTC/USDT, BTCUSDT, BTC-USDT, btcusdt
    """
    s = symbol.upper().replace("-", "").replace("/", "")
    if "USDT" in s:
        coin = s.replace("USDT", "")
        return f"{coin}/USDT"
    return f"{s}/USDT"


def _to_okx_futures_symbol(symbol: str) -> str:
    """Normalize to OKX swap format: BTC-USDT-SWAP"""
    base = symbol.upper().replace("_USDT", "").replace("/USDT", "").replace("-USDT", "").replace("USDT", "")
    return f"{base}-USDT-SWAP"


# ══════════════════════════════════════════════════════════════════════════════
# VOLUME SESSION PROFILE
# ══════════════════════════════════════════════════════════════════════════════

class VolumeSessionProfile:
    """
    Builds a Volume at Price (VAP) profile from OHLCV data.

    Each candle's volume is distributed across its price range proportionally.
    Identifies key levels: POC, Value Area, HVN, LVN, Naked POC.
    """

    def __init__(self, num_buckets: int = 100):
        self.num_buckets = num_buckets
        self.cache: Dict[str, Tuple[Dict, datetime]] = {}
        self.cache_ttl = 120  # 2 min cache

    def _cache_get(self, key: str) -> Optional[Dict]:
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None

    def _cache_set(self, key: str, data: Dict):
        self.cache[key] = (data, datetime.now())

    def build_profile(self, ohlcv_data: List[List]) -> Dict:
        """
        Build volume profile from OHLCV candles.
        ohlcv_data: list of [timestamp, open, high, low, close, volume]

        Returns:
          - poc_price: price with max volume
          - vah: Value Area High (top of 70% zone)
          - val: Value Area Low (bottom of 70% zone)
          - hvn_levels: list of High Volume Node prices
          - lvn_levels: list of Low Volume Node prices
          - profile: {price_bucket: volume} dict
          - total_volume: total volume in session
        """
        if not ohlcv_data or len(ohlcv_data) < 3:
            return {"error": "Insufficient OHLCV data"}

        prices = []
        for candle in ohlcv_data:
            prices.extend([candle[2], candle[3]])  # high, low

        price_min = min(prices)
        price_max = max(prices)

        if price_max <= price_min:
            return {"error": "Invalid price range"}

        bucket_size = (price_max - price_min) / self.num_buckets
        if bucket_size == 0:
            return {"error": "Zero bucket size"}

        # Volume distribution: for each candle, distribute volume uniformly
        # across its [low, high] range
        volume_at_price = defaultdict(float)

        for candle in ohlcv_data:
            _, open_, high, low, close, volume = candle
            candle_range = high - low
            if candle_range == 0:
                # Point candle — all volume at close
                bucket_idx = int((close - price_min) / bucket_size)
                bucket_idx = min(bucket_idx, self.num_buckets - 1)
                volume_at_price[bucket_idx] += volume
                continue

            # Number of buckets this candle spans
            low_idx = int((low - price_min) / bucket_size)
            high_idx = int((high - price_min) / bucket_size)
            low_idx = max(0, min(low_idx, self.num_buckets - 1))
            high_idx = max(0, min(high_idx, self.num_buckets - 1))

            span = high_idx - low_idx + 1
            vol_per_bucket = volume / span

            # Weight: more volume near close (where price spent time)
            close_idx = int((close - price_min) / bucket_size)
            close_idx = max(low_idx, min(close_idx, high_idx))

            for idx in range(low_idx, high_idx + 1):
                # Closer to close = more weight (1.5x at close, 0.75x at extremes)
                dist = abs(idx - close_idx)
                weight = max(0.5, 1.5 - dist * 0.1)
                volume_at_price[idx] += vol_per_bucket * weight

        if not volume_at_price:
            return {"error": "No volume data built"}

        # Normalize bucket index → price
        def idx_to_price(idx: int) -> float:
            return round(price_min + (idx + 0.5) * bucket_size, 8)

        total_volume = sum(volume_at_price.values())

        # POC = bucket with max volume
        poc_idx = max(volume_at_price, key=volume_at_price.get)
        poc_price = idx_to_price(poc_idx)

        # Value Area = 70% of total volume, expanding from POC outward
        target_va_volume = total_volume * 0.70
        va_volume = volume_at_price[poc_idx]
        va_low_idx = poc_idx
        va_high_idx = poc_idx

        while va_volume < target_va_volume:
            expand_up_vol = volume_at_price.get(va_high_idx + 1, 0)
            expand_down_vol = volume_at_price.get(va_low_idx - 1, 0)

            if expand_up_vol == 0 and expand_down_vol == 0:
                break
            if expand_up_vol >= expand_down_vol:
                va_high_idx += 1
                va_volume += expand_up_vol
            else:
                va_low_idx -= 1
                va_volume += expand_down_vol

        vah = idx_to_price(va_high_idx)
        val = idx_to_price(va_low_idx)

        # HVN = buckets with volume > 1.5x mean (support/resistance)
        mean_vol = total_volume / self.num_buckets
        hvn_threshold = mean_vol * 1.5
        lvn_threshold = mean_vol * 0.4

        hvn_levels = []
        lvn_levels = []

        for idx in range(self.num_buckets):
            vol = volume_at_price.get(idx, 0)
            price = idx_to_price(idx)
            if vol > hvn_threshold:
                hvn_levels.append({"price": price, "volume": round(vol, 2)})
            elif vol < lvn_threshold and vol > 0:
                lvn_levels.append({"price": price, "volume": round(vol, 2)})

        # Sort by price
        hvn_levels.sort(key=lambda x: x["price"])
        lvn_levels.sort(key=lambda x: x["price"])

        # Build profile dict for frontend heatmap rendering
        profile_buckets = []
        max_vol = max(volume_at_price.values()) if volume_at_price else 1
        for idx in range(self.num_buckets):
            vol = volume_at_price.get(idx, 0)
            profile_buckets.append({
                "price": idx_to_price(idx),
                "volume": round(vol, 2),
                "intensity": round(vol / max_vol, 4),  # 0-1 for heatmap coloring
            })

        return {
            "poc_price": poc_price,
            "poc_volume": round(volume_at_price[poc_idx], 2),
            "vah": vah,
            "val": val,
            "va_volume_pct": round(va_volume / total_volume * 100, 1),
            "hvn_levels": hvn_levels[:10],   # top 10
            "lvn_levels": lvn_levels[:10],
            "total_volume": round(total_volume, 2),
            "price_min": price_min,
            "price_max": price_max,
            "bucket_size": round(bucket_size, 8),
            "profile_buckets": profile_buckets,
        }

    async def get_session_profile(
        self, symbol: str, exchange, timeframe: str = "1h", limit: int = 96
    ) -> Dict:
        """
        Fetch OHLCV and build profile for the last N candles (e.g. 96h = 4 days).
        """
        cache_key = f"vsp_{symbol}_{timeframe}_{limit}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            loop = asyncio.get_running_loop()
            full_symbol = _to_ccxt_symbol(symbol)

            ohlcv = await loop.run_in_executor(
                None,
                lambda: exchange.fetch_ohlcv(full_symbol, timeframe, limit=limit)
            )

            profile = self.build_profile(ohlcv)
            profile["symbol"] = symbol
            profile["timeframe"] = timeframe
            profile["candles_used"] = len(ohlcv)
            profile["timestamp"] = datetime.now(timezone.utc).isoformat()

            self._cache_set(cache_key, profile)
            return profile

        except Exception as e:
            logger.error(f"VolumeSessionProfile error for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def find_naked_poc(
        self, profile: Dict, current_price: float, previous_profiles: List[Dict]
    ) -> Optional[Dict]:
        """
        Naked POC = a prior session's POC that current price has NOT returned to.
        These act as strong magnets — price almost always revisits them.
        """
        naked_pocs = []
        for prev in previous_profiles:
            poc = prev.get("poc_price")
            if poc is None:
                continue
            # Check if current session's price range visited this POC
            pmin = profile.get("price_min", 0)
            pmax = profile.get("price_max", 0)
            if not (pmin <= poc <= pmax):
                direction = "ABOVE" if poc > current_price else "BELOW"
                dist_pct = abs(poc - current_price) / current_price * 100
                naked_pocs.append({
                    "poc_price": poc,
                    "direction": direction,
                    "distance_pct": round(dist_pct, 2),
                    "session": prev.get("timeframe", ""),
                })

        naked_pocs.sort(key=lambda x: x["distance_pct"])
        return naked_pocs[:3] if naked_pocs else []

    def classify_price_location(self, profile: Dict, current_price: float) -> Dict:
        """
        Given current price, classify where it sits in the volume profile.
        Returns location context for signal logic.
        """
        poc = profile.get("poc_price", 0)
        vah = profile.get("vah", 0)
        val = profile.get("val", 0)
        hvn_levels = profile.get("hvn_levels", [])
        lvn_levels = profile.get("lvn_levels", [])

        # Find nearest HVN and LVN
        nearest_hvn_above = None
        nearest_hvn_below = None
        nearest_lvn_above = None
        nearest_lvn_below = None

        for h in hvn_levels:
            p = h["price"]
            if p > current_price:
                if nearest_hvn_above is None or p < nearest_hvn_above["price"]:
                    nearest_hvn_above = h
            elif p < current_price:
                if nearest_hvn_below is None or p > nearest_hvn_below["price"]:
                    nearest_hvn_below = h

        for l in lvn_levels:
            p = l["price"]
            if p > current_price:
                if nearest_lvn_above is None or p < nearest_lvn_above["price"]:
                    nearest_lvn_above = l
            elif p < current_price:
                if nearest_lvn_below is None or p > nearest_lvn_below["price"]:
                    nearest_lvn_below = l

        # Zone classification
        if val <= current_price <= vah:
            zone = "INSIDE_VALUE_AREA"
            zone_signal = "NEUTRAL"
            zone_desc = "Price inside value area — choppy, mean reversion likely"
        elif current_price > vah:
            zone = "ABOVE_VALUE_AREA"
            zone_signal = "BULLISH_BREAKOUT" if current_price > poc * 1.005 else "AT_VAH_RESISTANCE"
            zone_desc = "Price above value area — bullish breakout or VAH rejection"
        else:
            zone = "BELOW_VALUE_AREA"
            zone_signal = "BEARISH_BREAKDOWN" if current_price < poc * 0.995 else "AT_VAL_SUPPORT"
            zone_desc = "Price below value area — bearish breakdown or VAL support"

        # POC proximity
        poc_dist_pct = abs(current_price - poc) / current_price * 100

        # Is price in LVN? (thin air = fast move territory)
        in_lvn = any(
            abs(current_price - l["price"]) / current_price < 0.003
            for l in lvn_levels
        )
        # Is price at HVN? (congestion = slow / reversal territory)
        at_hvn = any(
            abs(current_price - h["price"]) / current_price < 0.003
            for h in hvn_levels
        )

        return {
            "zone": zone,
            "zone_signal": zone_signal,
            "zone_desc": zone_desc,
            "in_lvn": in_lvn,
            "at_hvn": at_hvn,
            "poc_distance_pct": round(poc_dist_pct, 2),
            "nearest_hvn_above": nearest_hvn_above,
            "nearest_hvn_below": nearest_hvn_below,
            "nearest_lvn_above": nearest_lvn_above,
            "nearest_lvn_below": nearest_lvn_below,
        }


# ══════════════════════════════════════════════════════════════════════════════
# LIQUIDATION HEATMAP
# ══════════════════════════════════════════════════════════════════════════════

class LiquidationHeatmap:
    """
    Estimates where leveraged long/short positions get liquidated.

    Uses:
    - MEXC Open Interest data (real, via contract API)
    - Price level history to model where positions were opened
    - Standard leverage tiers (5x, 10x, 20x, 50x)

    A "liquidation cluster" is a price zone where many positions would be
    force-closed simultaneously — this creates massive stop-loss cascades
    and is a prime target for market makers / large players.

    Long liquidation levels (price DROPS to here → longs rekt):
      liq_price = entry_price * (1 - maintenance_margin / leverage)
      With ~0.9 maintenance: liq = entry * (1 - 0.9/lev)

    Short liquidation levels (price RISES to here → shorts rekt):
      liq_price = entry * (1 + 0.9/lev)
    """

    LEVERAGE_TIERS = [3, 5, 10, 20, 50]  # 100x removed — paper trading capped at 20x, 100x adds noise
    MAINTENANCE_MARGIN = 0.9  # approximate

    def __init__(self):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.cache_ttl = 60

    def _cache_get(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None

    def _cache_set(self, key: str, data):
        self.cache[key] = (data, datetime.now())

    async def get_oi_data(self, symbol: str) -> Optional[Dict]:
        """Fetch Open Interest from OKX."""
        cache_key = f"oi_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            inst_id = _to_okx_futures_symbol(symbol)
            url = "https://www.okx.com/api/v5/public/open-interest"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"instType": "SWAP", "instId": inst_id},
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()

            items = data.get("data") or []
            if items:
                oi_value = float(items[0].get("oiCcy", 0))
                result = {
                    "symbol": symbol,
                    "oi_data": items,
                    "current_oi": oi_value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self._cache_set(cache_key, result)
                return result

        except Exception as e:
            logger.debug(f"LiqHeatmap OI fetch error for {symbol}: {e}")

        return None

    async def get_current_price(self, symbol: str) -> float:
        """Fetch current price from OKX ticker."""
        try:
            inst_id = _to_okx_futures_symbol(symbol)
            url = "https://www.okx.com/api/v5/market/ticker"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"instId": inst_id},
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
            items = data.get("data") or []
            if items:
                return float(items[0].get("last", 0))
        except Exception as e:
            logger.debug(f"LiqHeatmap price fetch error: {e}")
        return 0.0

    def calculate_liq_levels(
        self, entry_price: float, current_price: float
    ) -> Dict:
        """
        For a given entry price, compute liquidation levels at each leverage tier.
        Returns long_liqs and short_liqs for each leverage.
        """
        long_liqs = []
        short_liqs = []

        for lev in self.LEVERAGE_TIERS:
            # Long liq: price drops to liq_price = entry * (1 - 0.9/lev)
            long_liq_price = entry_price * (1 - self.MAINTENANCE_MARGIN / lev)
            # Short liq: price rises to liq_price = entry * (1 + 0.9/lev)
            short_liq_price = entry_price * (1 + self.MAINTENANCE_MARGIN / lev)

            dist_from_current_long = (long_liq_price - current_price) / current_price * 100
            dist_from_current_short = (short_liq_price - current_price) / current_price * 100

            long_liqs.append({
                "leverage": lev,
                "liq_price": round(long_liq_price, 6),
                "dist_pct": round(dist_from_current_long, 2),
            })
            short_liqs.append({
                "leverage": lev,
                "liq_price": round(short_liq_price, 6),
                "dist_pct": round(dist_from_current_short, 2),
            })

        return {"long_liqs": long_liqs, "short_liqs": short_liqs}

    def build_heatmap(
        self, ohlcv_data: List[List], current_price: float, num_buckets: int = 80
    ) -> Dict:
        """
        Build a liquidation heatmap from historical OHLCV data.

        The idea: each historical close price represents where positions were opened.
        We calculate where those positions get liquidated and sum up the
        liquidation density at each price bucket.

        Returns:
          - long_liq_clusters: zones below current price with high long liq density
          - short_liq_clusters: zones above current price with high short liq density
          - nearest_long_cluster: closest long liq zone (most dangerous drop target)
          - nearest_short_cluster: closest short liq zone (most dangerous pump target)
        """
        if not ohlcv_data or current_price <= 0:
            return {"error": "Insufficient data"}

        price_range_pct = 0.30  # look ±30% from current price
        price_min = current_price * (1 - price_range_pct)
        price_max = current_price * (1 + price_range_pct)
        bucket_size = (price_max - price_min) / num_buckets

        long_liq_map = defaultdict(float)   # price_bucket → liq density
        short_liq_map = defaultdict(float)

        # Weight recent candles more (positions opened recently are still open)
        n = len(ohlcv_data)
        for i, candle in enumerate(ohlcv_data):
            recency_weight = (i + 1) / n  # newer = higher weight
            entry_price = candle[4]  # close price
            volume = candle[5]       # candle volume as proxy for OI

            for lev in self.LEVERAGE_TIERS:
                lev_weight = 1.0 / (lev ** 0.5)  # lower lev = more common = higher weight

                # Long liq from this entry
                long_liq = entry_price * (1 - self.MAINTENANCE_MARGIN / lev)
                if price_min <= long_liq <= current_price:
                    bucket = int((long_liq - price_min) / bucket_size)
                    bucket = max(0, min(bucket, num_buckets - 1))
                    long_liq_map[bucket] += volume * recency_weight * lev_weight

                # Short liq from this entry
                short_liq = entry_price * (1 + self.MAINTENANCE_MARGIN / lev)
                if current_price <= short_liq <= price_max:
                    bucket = int((short_liq - price_min) / bucket_size)
                    bucket = max(0, min(bucket, num_buckets - 1))
                    short_liq_map[bucket] += volume * recency_weight * lev_weight

        def idx_to_price(idx):
            return round(price_min + (idx + 0.5) * bucket_size, 6)

        # Find clusters = density ratio (2.5x mean OR 15% of peak — whichever is selective)
        def find_clusters(liq_map: Dict, direction: str) -> List[Dict]:
            if not liq_map:
                return []
            values = list(liq_map.values())
            max_density = max(values)
            mean_density = sum(values) / len(values)
            threshold = max(mean_density * 2.5, max_density * 0.15)
            clusters = []
            for idx, density in liq_map.items():
                if density >= threshold:
                    price = idx_to_price(idx)
                    dist_pct = (price - current_price) / current_price * 100
                    clusters.append({
                        "price": price,
                        "density": round(density, 2),
                        "intensity": round(density / max(values), 4),
                        "dist_pct": round(dist_pct, 2),
                        "direction": direction,
                    })
            # Sort by distance from current price
            clusters.sort(key=lambda x: abs(x["dist_pct"]))
            return clusters[:8]

        long_clusters = find_clusters(long_liq_map, "LONG_LIQ")
        short_clusters = find_clusters(short_liq_map, "SHORT_LIQ")

        # Build full heatmap buckets for frontend
        max_long = max(long_liq_map.values()) if long_liq_map else 1
        max_short = max(short_liq_map.values()) if short_liq_map else 1

        heatmap_buckets = []
        for idx in range(num_buckets):
            p = idx_to_price(idx)
            long_d = long_liq_map.get(idx, 0)
            short_d = short_liq_map.get(idx, 0)
            if long_d > 0 or short_d > 0:
                heatmap_buckets.append({
                    "price": p,
                    "long_intensity": round(long_d / max_long, 4),
                    "short_intensity": round(short_d / max_short, 4),
                })

        # Nearest clusters (most immediate threat)
        nearest_long = long_clusters[0] if long_clusters else None
        nearest_short = short_clusters[0] if short_clusters else None

        # Detect if price is approaching a cluster (within 2%)
        approaching_long_liq = (
            nearest_long is not None and abs(nearest_long["dist_pct"]) < 2.5
        )
        approaching_short_liq = (
            nearest_short is not None and abs(nearest_short["dist_pct"]) < 2.5
        )

        return {
            "current_price": current_price,
            "long_liq_clusters": long_clusters,
            "short_liq_clusters": short_clusters,
            "nearest_long_cluster": nearest_long,
            "nearest_short_cluster": nearest_short,
            "approaching_long_liq": approaching_long_liq,
            "approaching_short_liq": approaching_short_liq,
            "heatmap_buckets": heatmap_buckets,
            "price_range": {"min": round(price_min, 6), "max": round(price_max, 6)},
        }

    async def analyze(self, symbol: str, ohlcv_data: List[List]) -> Dict:
        """Full liquidation heatmap analysis."""
        cache_key = f"liq_{symbol}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        # Use OHLCV last close as primary anchor — same source as all entry prices
        # fed into build_heatmap(), so liq buckets are self-consistent.
        # Fall back to the MEXC futures ticker only if OHLCV is empty.
        if ohlcv_data:
            current_price = float(ohlcv_data[-1][4])
        else:
            current_price = await self.get_current_price(symbol)

        heatmap = self.build_heatmap(ohlcv_data, current_price)
        heatmap["symbol"] = symbol
        heatmap["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Fetch real OI for context
        oi_data = await self.get_oi_data(symbol)
        if oi_data:
            heatmap["open_interest"] = oi_data.get("current_oi", 0)
            heatmap["oi_source"] = "okx"

        self._cache_set(cache_key, heatmap)
        return heatmap


# ══════════════════════════════════════════════════════════════════════════════
# ORDERBOOK DEPTH ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class OrderbookAnalyzer:
    """
    Real-time orderbook analysis:
    - Bid/ask walls (large stacked limit orders = S/R)
    - Book imbalance (bids vs asks within 1% of mid)
    - Sweep detection (wall absorbed = momentum signal)
    - Iceberg detection (wall that keeps refilling)

    Uses OKX L2 orderbook (public, no auth).
    """

    def __init__(self):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.cache_ttl = 10  # 10s for orderbook (fast-moving)
        self.prev_books: Dict[str, Dict] = {}  # for sweep detection
        self.okx = ccxt.okx({'enableRateLimit': True})

    def _cache_get(self, key: str):
        if key in self.cache:
            data, ts = self.cache[key]
            if (datetime.now() - ts).seconds < self.cache_ttl:
                return data
        return None

    def _cache_set(self, key: str, data):
        self.cache[key] = (data, datetime.now())

    async def fetch_orderbook(self, symbol: str, depth: int = 50) -> Optional[Dict]:
        """Fetch L2 orderbook from MEXC."""
        cache_key = f"ob_{symbol}_{depth}"
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            full_symbol = _to_ccxt_symbol(symbol)
            loop = asyncio.get_running_loop()
            def _fetch_book():
                with OKX_SEM:
                    return self.okx.fetch_order_book(full_symbol, limit=depth)
            book = await loop.run_in_executor(None, _fetch_book)
            self._cache_set(cache_key, book)
            return book
        except Exception as e:
            logger.debug(f"Orderbook fetch error for {symbol}: {e}")
            return None

    def analyze_walls(
        self, bids: List[List], asks: List[List], mid_price: float
    ) -> Dict:
        """
        Detect bid/ask walls.
        A wall = single price level with volume >= 5x average order size at nearby levels.
        """
        def find_walls(levels: List[List], side: str, threshold_multiplier: float = 4.0):
            if not levels:
                return []
            # Filter to levels within 3% of mid
            nearby = [l for l in levels if abs(l[0] - mid_price) / mid_price < 0.03]
            if not nearby:
                return []

            sizes = [l[1] for l in nearby]
            avg_size = sum(sizes) / len(sizes)
            threshold = avg_size * threshold_multiplier

            walls = []
            for price, size in nearby:
                if size >= threshold:
                    dist_pct = (price - mid_price) / mid_price * 100
                    walls.append({
                        "price": price,
                        "size": round(size, 4),
                        "size_usd": round(size * price, 2),
                        "dist_pct": round(dist_pct, 2),
                        "side": side,
                        "strength": round(size / avg_size, 1),  # X times avg
                    })
            walls.sort(key=lambda x: abs(x["dist_pct"]))
            return walls[:5]

        bid_walls = find_walls(bids, "BID")
        ask_walls = find_walls(asks, "ASK")

        # Nearest walls (most relevant for S/R)
        nearest_bid_wall = bid_walls[0] if bid_walls else None
        nearest_ask_wall = ask_walls[0] if ask_walls else None

        return {
            "bid_walls": bid_walls,
            "ask_walls": ask_walls,
            "nearest_bid_wall": nearest_bid_wall,
            "nearest_ask_wall": nearest_ask_wall,
        }

    def calculate_imbalance(
        self, bids: List[List], asks: List[List], mid_price: float, depth_pct: float = 0.01
    ) -> Dict:
        """
        Bid/Ask imbalance within `depth_pct` (1%) of mid price.

        Imbalance > 1.5 = strong bid pressure (bullish)
        Imbalance < 0.67 = strong ask pressure (bearish)
        """
        bid_vol = sum(size for price, size in bids if price >= mid_price * (1 - depth_pct))
        ask_vol = sum(size for price, size in asks if price <= mid_price * (1 + depth_pct))

        total = bid_vol + ask_vol
        if total == 0:
            return {"imbalance_ratio": 1.0, "bias": "NEUTRAL", "bid_vol": 0, "ask_vol": 0}

        ratio = bid_vol / ask_vol if ask_vol > 0 else 99.0

        if ratio > 2.0:
            bias = "STRONG_BULLISH"
            desc = "Bids dominating — strong buyer support"
        elif ratio > 1.4:
            bias = "BULLISH"
            desc = "More bids than asks within 1% — buyer pressure"
        elif ratio < 0.5:
            bias = "STRONG_BEARISH"
            desc = "Asks dominating — strong seller pressure"
        elif ratio < 0.7:
            bias = "BEARISH"
            desc = "More asks than bids within 1% — seller pressure"
        else:
            bias = "NEUTRAL"
            desc = "Balanced order book"

        return {
            "imbalance_ratio": round(ratio, 3),
            "bid_vol": round(bid_vol, 4),
            "ask_vol": round(ask_vol, 4),
            "bid_pct": round(bid_vol / total * 100, 1),
            "ask_pct": round(ask_vol / total * 100, 1),
            "bias": bias,
            "desc": desc,
        }

    def detect_sweeps(self, symbol: str, bids: List[List], asks: List[List]) -> List[Dict]:
        """
        Detect sweep events: a previously large wall that has now disappeared.
        This means aggressive market orders ate through the wall = momentum signal.
        """
        sweeps = []
        prev = self.prev_books.get(symbol)

        if prev:
            prev_bid_walls = {b["price"]: b["size_usd"] for b in prev.get("walls", {}).get("bid_walls", [])}
            prev_ask_walls = {a["price"]: a["size_usd"] for a in prev.get("walls", {}).get("ask_walls", [])}

            current_bid_prices = [p for p, _ in bids]
            current_ask_prices = [p for p, _ in asks]

            def _price_still_present(price: float, levels: list, tol: float = 0.0005) -> bool:
                """Check if price level still exists within 0.05% tolerance."""
                return any(abs(p - price) / price < tol for p in levels)

            # Check if a previous bid wall price disappeared
            for price, size_usd in prev_bid_walls.items():
                if not _price_still_present(price, current_bid_prices) and size_usd > 5000:
                    sweeps.append({
                        "type": "BID_WALL_SWEPT",
                        "direction": "BEARISH",
                        "price": price,
                        "size_usd": size_usd,
                        "desc": f"Bid wall ${size_usd:,.0f} at {price} was swept — bearish momentum",
                    })

            # Check if a previous ask wall price disappeared
            for price, size_usd in prev_ask_walls.items():
                if not _price_still_present(price, current_ask_prices) and size_usd > 5000:
                    sweeps.append({
                        "type": "ASK_WALL_SWEPT",
                        "direction": "BULLISH",
                        "price": price,
                        "size_usd": size_usd,
                        "desc": f"Ask wall ${size_usd:,.0f} at {price} was swept — bullish momentum",
                    })

        return sweeps

    async def analyze(self, symbol: str) -> Dict:
        """Full orderbook analysis."""
        book = await self.fetch_orderbook(symbol, depth=100)
        if not book:
            return {"symbol": symbol, "error": "Could not fetch orderbook"}

        bids = book.get("bids", [])
        asks = book.get("asks", [])

        if not bids or not asks:
            return {"symbol": symbol, "error": "Empty orderbook"}

        mid_price = (bids[0][0] + asks[0][0]) / 2

        walls = self.analyze_walls(bids, asks, mid_price)
        imbalance = self.calculate_imbalance(bids, asks, mid_price)
        sweeps = self.detect_sweeps(symbol, bids, asks)

        result = {
            "symbol": symbol,
            "mid_price": round(mid_price, 6),
            "spread": round(asks[0][0] - bids[0][0], 8),
            "spread_pct": round((asks[0][0] - bids[0][0]) / mid_price * 100, 4),
            "walls": walls,
            "imbalance": imbalance,
            "sweeps": sweeps,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store for sweep detection next call; prune stale entries (> 10 min old)
        now = datetime.now()
        self.prev_books = {
            s: b for s, b in self.prev_books.items()
            if (now - b["ts"]).seconds < 600
        }
        self.prev_books[symbol] = {"walls": walls, "ts": now}

        return result



# ══════════════════════════════════════════════════════════════════════════════
# HYPER ACCURACY TRADING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class HyperAccuracyEngine:
    """
    Seven-layer institutional-grade signal engine.

    ANALYSIS LAYERS:
    1. BTC Macro Gate        — 4H SMA trend blocks LONGs in bear / SHORTs in bull
    2. Asset Trend Structure — Own 4H + Daily HH/HL vs LH/LL market structure
    3. Funding Rate          — Extreme funding = crowded trade = hard gate
    4. Order Blocks (SMC)    — Last bearish/bullish candle before impulse = key S/R zone
    5. Fair Value Gaps (FVG) — Price imbalances price returns to fill = magnets
    6. Volume Profile        — POC, VAH/VAL, HVN/LVN, Naked POC
    7. Flow Confirmation     — CVD, RSI + divergence, orderbook, liq clusters, Fibonacci

    HARD GATES (absolute block regardless of score):
    - BTC macro opposes direction
    - Funding extreme (>0.15% / <-0.15%) against direction

    STRUCTURAL ZONE REQUIREMENT:
    - At least 1 of: Order Block / FVG / HVN / key institutional level must confirm

    SIGNAL THRESHOLD:
    - winning_score >= 22, gap >= 12, confidence >= 65%
    """

    def __init__(self, db=None):
        self.db = db
        self.active = True
        self.vsp = VolumeSessionProfile()
        self.liq = LiquidationHeatmap()
        self.ob = OrderbookAnalyzer()
        self.okx = ccxt.okx({'enableRateLimit': True})

        # Dependencies (set via set_dependencies)
        self.order_flow = None
        self.market_intel = None
        self.send_telegram = None
        self.get_user_settings = None
        self.chat_ids = set()

        # BTC macro bias gate
        self.btc_bias = "NEUTRAL"  # BULLISH / BEARISH / NEUTRAL

        # Stats
        self.signals_generated = 0
        self.scans_run = 0

    def set_dependencies(self, **kwargs):
        self.order_flow = kwargs.get("order_flow")
        self.market_intel = kwargs.get("market_intel")
        self.send_telegram = kwargs.get("send_telegram")
        self.get_user_settings = kwargs.get("get_user_settings")
        self.chat_ids = kwargs.get("chat_ids", set())

    # ── BTC MACRO BIAS ────────────────────────────────────────────────────────

    async def _update_btc_bias(self):
        """BTC 4H SMA bias. BEARISH → block all LONGs. BULLISH → block all SHORTs."""
        try:
            ohlcv = await self._fetch_ohlcv("BTC/USDT", "4h", 20)
            if ohlcv and len(ohlcv) >= 10:
                closes = [c[4] for c in ohlcv]
                sma5 = sum(closes[-5:]) / 5
                sma10 = sum(closes[-10:]) / 10
                if sma5 > sma10 * 1.002:
                    self.btc_bias = "BULLISH"
                elif sma5 < sma10 * 0.998:
                    self.btc_bias = "BEARISH"
                else:
                    self.btc_bias = "NEUTRAL"
                logger.debug(f"HyperAccuracy BTC bias: {self.btc_bias} (SMA5={sma5:.2f} SMA10={sma10:.2f})")
        except Exception as e:
            logger.debug(f"BTC bias update error: {e}")

    # ── DATA FETCHING ─────────────────────────────────────────────────────────

    async def _fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List[List]:
        """Fetch OHLCV from MEXC."""
        try:
            full_symbol = _to_ccxt_symbol(symbol)
            loop = asyncio.get_running_loop()
            def _fetch_ohlcv():
                with OKX_SEM:
                    return self.okx.fetch_ohlcv(full_symbol, timeframe, limit=limit)
            return await loop.run_in_executor(None, _fetch_ohlcv)
        except Exception as e:
            logger.error(f"OHLCV fetch error {symbol} {timeframe}: {e}")
            return []

    async def _fetch_funding_rate(self, symbol: str) -> Dict:
        """
        Fetch current funding rate from OKX public API.
        Extreme rates = crowded trade = hard gate against that direction.
        """
        try:
            inst_id = _to_okx_futures_symbol(symbol)  # already returns OKX SWAP format
            url = f"https://www.okx.com/api/v5/public/funding-rate"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"instId": inst_id}, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
            items = data.get("data") or []
            if items:
                rate = float(items[0].get("fundingRate", 0))
                if rate > 0.0015:
                    bias = "EXTREME_LONG"
                elif rate > 0.0005:
                    bias = "HIGH_LONG"
                elif rate < -0.0015:
                    bias = "EXTREME_SHORT"
                elif rate < -0.0005:
                    bias = "HIGH_SHORT"
                else:
                    bias = "NEUTRAL"
                return {"rate": rate, "rate_pct": round(rate * 100, 4), "bias": bias}
        except Exception as e:
            logger.debug(f"OKX funding rate fetch error {symbol}: {e}")
        return {"rate": 0.0, "rate_pct": 0.0, "bias": "NEUTRAL"}

    # ── MARKET STRUCTURE ──────────────────────────────────────────────────────

    def _get_trend_structure(self, ohlcv: List[List], lookback: int = 30) -> Dict:
        """
        Identify market structure via swing high/low pivot analysis.
        HH + HL = UPTREND (bullish structure)
        LH + LL = DOWNTREND (bearish structure)
        Uses 3-bar pivot detection for robustness.
        """
        if not ohlcv or len(ohlcv) < lookback:
            return {"structure": "UNKNOWN", "bias": "NEUTRAL"}

        data = ohlcv[-lookback:]
        highs = [c[2] for c in data]
        lows = [c[3] for c in data]

        swing_highs = []
        swing_lows = []

        for i in range(3, len(data) - 3):
            if highs[i] == max(highs[i-3:i+4]):
                swing_highs.append(highs[i])
            if lows[i] == min(lows[i-3:i+4]):
                swing_lows.append(lows[i])

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {"structure": "UNCLEAR", "bias": "NEUTRAL"}

        prev_sh, last_sh = swing_highs[-2], swing_highs[-1]
        prev_sl, last_sl = swing_lows[-2], swing_lows[-1]

        hh = last_sh > prev_sh
        hl = last_sl > prev_sl

        if hh and hl:
            structure, bias = "UPTREND", "BULLISH"
        elif not hh and not hl:
            structure, bias = "DOWNTREND", "BEARISH"
        elif hh and not hl:
            structure, bias = "DISTRIBUTION", "NEUTRAL"
        else:
            structure, bias = "ACCUMULATION", "NEUTRAL"

        return {
            "structure": structure,
            "bias": bias,
            "last_swing_high": round(last_sh, 6),
            "last_swing_low": round(last_sl, 6),
            "prev_swing_high": round(prev_sh, 6),
            "prev_swing_low": round(prev_sl, 6),
        }

    # ── ORDER BLOCKS (SMC) ────────────────────────────────────────────────────

    def _detect_order_blocks(self, ohlcv: List[List], current_price: float) -> Dict:
        """
        Smart Money Concepts Order Block detection.

        Bullish OB: Last bearish (down-close) candle before a bullish impulse (>=0.8% up).
                    OB zone = [low, high] of that candle. Acts as support when price returns.
        Bearish OB: Last bullish (up-close) candle before a bearish impulse (>=0.8% down).
                    OB zone = [low, high] of that candle. Acts as resistance when price returns.

        An OB is valid (unmitigated) until price returns to fill/touch it.
        Nearest unmitigated OBs are the highest-quality zones.
        """
        if not ohlcv or len(ohlcv) < 5 or current_price <= 0:
            return {"bullish_obs": [], "bearish_obs": [],
                    "nearest_bullish_ob": None, "nearest_bearish_ob": None}

        bullish_obs = []
        bearish_obs = []

        for i in range(1, len(ohlcv) - 3):
            candle = ohlcv[i]
            o, h, l, c = candle[1], candle[2], candle[3], candle[4]
            next2_closes = [ohlcv[i+j][4] for j in range(1, 3)]

            # Bullish OB: bearish candle + bullish impulse follows
            if c < o:
                max_next_close = max(next2_closes)
                if max_next_close > c * 1.008:  # >=0.8% up impulse
                    ob_mid = (h + l) / 2
                    if h < current_price:
                        # Check not yet mitigated (price returned to touch ob_high)
                        subsequent_lows = [ohlcv[j][3] for j in range(i + 3, len(ohlcv))]
                        if not any(sl <= h for sl in subsequent_lows):
                            dist_pct = (current_price - ob_mid) / current_price * 100
                            bullish_obs.append({
                                "high": round(h, 6), "low": round(l, 6),
                                "mid": round(ob_mid, 6), "dist_pct": round(dist_pct, 2),
                            })

            # Bearish OB: bullish candle + bearish impulse follows
            if c > o:
                min_next_close = min(next2_closes)
                if min_next_close < c * 0.992:  # >=0.8% down impulse
                    ob_mid = (h + l) / 2
                    if l > current_price:
                        subsequent_highs = [ohlcv[j][2] for j in range(i + 3, len(ohlcv))]
                        if not any(sh >= l for sh in subsequent_highs):
                            dist_pct = (ob_mid - current_price) / current_price * 100
                            bearish_obs.append({
                                "high": round(h, 6), "low": round(l, 6),
                                "mid": round(ob_mid, 6), "dist_pct": round(dist_pct, 2),
                            })

        bullish_obs.sort(key=lambda x: x["dist_pct"])
        bearish_obs.sort(key=lambda x: x["dist_pct"])

        return {
            "bullish_obs": bullish_obs[:5],
            "bearish_obs": bearish_obs[:5],
            "nearest_bullish_ob": bullish_obs[0] if bullish_obs else None,
            "nearest_bearish_ob": bearish_obs[0] if bearish_obs else None,
        }

    # ── FAIR VALUE GAPS ───────────────────────────────────────────────────────

    def _detect_fvg(self, ohlcv: List[List], current_price: float) -> Dict:
        """
        Fair Value Gap (FVG / Imbalance) detection.

        Bullish FVG: candle[i-1].high < candle[i+1].low
                     = gap below current price = unfilled support magnet.
        Bearish FVG: candle[i-1].low > candle[i+1].high
                     = gap above current price = unfilled resistance magnet.

        Price almost always returns to fill unmitigated FVGs.
        Only detects gaps >= 0.15% to filter noise.
        """
        if not ohlcv or len(ohlcv) < 5 or current_price <= 0:
            return {"bullish_fvgs": [], "bearish_fvgs": [],
                    "nearest_bullish_fvg": None, "nearest_bearish_fvg": None}

        bullish_fvgs = []
        bearish_fvgs = []

        for i in range(1, len(ohlcv) - 1):
            prev_h = ohlcv[i-1][2]
            prev_l = ohlcv[i-1][3]
            next_h = ohlcv[i+1][2]
            next_l = ohlcv[i+1][3]

            # Bullish FVG: gap between prev high and next low
            if next_l > prev_h:
                fvg_low, fvg_high = prev_h, next_l
                fvg_mid = (fvg_high + fvg_low) / 2
                size_pct = (fvg_high - fvg_low) / fvg_low * 100
                if size_pct > 0.15 and fvg_mid < current_price:
                    subsequent_lows = [ohlcv[j][3] for j in range(i + 2, len(ohlcv))]
                    if not any(sl <= fvg_low for sl in subsequent_lows):
                        dist_pct = (current_price - fvg_mid) / current_price * 100
                        bullish_fvgs.append({
                            "high": round(fvg_high, 6), "low": round(fvg_low, 6),
                            "mid": round(fvg_mid, 6), "size_pct": round(size_pct, 3),
                            "dist_pct": round(dist_pct, 2),
                        })

            # Bearish FVG: gap between next high and prev low
            if next_h < prev_l:
                fvg_high, fvg_low = prev_l, next_h
                fvg_mid = (fvg_high + fvg_low) / 2
                size_pct = (fvg_high - fvg_low) / fvg_low * 100
                if size_pct > 0.15 and fvg_mid > current_price:
                    subsequent_highs = [ohlcv[j][2] for j in range(i + 2, len(ohlcv))]
                    if not any(sh >= fvg_high for sh in subsequent_highs):
                        dist_pct = (fvg_mid - current_price) / current_price * 100
                        bearish_fvgs.append({
                            "high": round(fvg_high, 6), "low": round(fvg_low, 6),
                            "mid": round(fvg_mid, 6), "size_pct": round(size_pct, 3),
                            "dist_pct": round(dist_pct, 2),
                        })

        bullish_fvgs.sort(key=lambda x: x["dist_pct"])
        bearish_fvgs.sort(key=lambda x: x["dist_pct"])

        return {
            "bullish_fvgs": bullish_fvgs[:5],
            "bearish_fvgs": bearish_fvgs[:5],
            "nearest_bullish_fvg": bullish_fvgs[0] if bullish_fvgs else None,
            "nearest_bearish_fvg": bearish_fvgs[0] if bearish_fvgs else None,
        }

    # ── RSI ───────────────────────────────────────────────────────────────────

    def _calc_rsi(self, ohlcv: List[List], period: int = 14) -> float:
        """Wilder's EMA-RSI — matches TradingView/Binance RSI readings exactly."""
        if not ohlcv or len(ohlcv) < period + 2:
            return 50.0
        closes = [c[4] for c in ohlcv]
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        # Wilder's initial average (SMA for first period)
        gains = [max(d, 0) for d in deltas[:period]]
        losses = [max(-d, 0) for d in deltas[:period]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        # Wilder's exponential smoothing for remaining periods
        for d in deltas[period:]:
            avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
        if avg_loss == 0:
            return 100.0
        return round(100 - 100 / (1 + avg_gain / avg_loss), 2)

    def _detect_rsi_divergence(self, ohlcv: List[List]) -> Dict:
        """
        Regular RSI divergence on the last 40 candles (requires 14 warmup).

        Bullish divergence: price makes lower low, RSI makes higher low → reversal up
        Bearish divergence: price makes higher high, RSI makes lower high → reversal down

        Only counts if RSI is in relevant zone (<45 for bullish, >55 for bearish).
        """
        if not ohlcv or len(ohlcv) < 30:
            return {"type": "NONE", "desc": ""}

        lookback = min(54, len(ohlcv))
        segment = ohlcv[-lookback:]
        rsi_vals = []
        for i in range(14, len(segment)):
            rsi_vals.append(self._calc_rsi(segment[:i+1], 14))

        if len(rsi_vals) < 12:
            return {"type": "NONE", "desc": ""}

        price_highs = [c[2] for c in segment[14:]]
        price_lows = [c[3] for c in segment[14:]]
        n = len(rsi_vals)
        half = n // 2

        # Compare extremes in first half vs second half
        min_rsi_1 = min(rsi_vals[:half])
        min_rsi_2 = min(rsi_vals[half:])
        max_rsi_1 = max(rsi_vals[:half])
        max_rsi_2 = max(rsi_vals[half:])

        low_at_1 = price_lows[rsi_vals[:half].index(min_rsi_1)]
        low_at_2 = price_lows[half + rsi_vals[half:].index(min_rsi_2)]
        high_at_1 = price_highs[rsi_vals[:half].index(max_rsi_1)]
        high_at_2 = price_highs[half + rsi_vals[half:].index(max_rsi_2)]

        # Bullish divergence
        if low_at_2 < low_at_1 and min_rsi_2 > min_rsi_1 + 4 and min_rsi_2 < 45:
            return {
                "type": "BULLISH",
                "desc": f"Bullish RSI divergence: price LL, RSI HL ({min_rsi_2:.0f} vs {min_rsi_1:.0f})",
            }
        # Bearish divergence
        if high_at_2 > high_at_1 and max_rsi_2 < max_rsi_1 - 4 and max_rsi_2 > 55:
            return {
                "type": "BEARISH",
                "desc": f"Bearish RSI divergence: price HH, RSI LH ({max_rsi_2:.0f} vs {max_rsi_1:.0f})",
            }

        return {"type": "NONE", "desc": ""}

    # ── KEY LEVELS ────────────────────────────────────────────────────────────

    def _get_key_levels(self, ohlcv_1d: List[List], current_price: float) -> Dict:
        """
        Institutional reference levels: Previous Day H/L/C, Previous Week H/L,
        and round numbers. These are magnets and major S/R zones.
        """
        levels = []

        if ohlcv_1d and len(ohlcv_1d) >= 2:
            pd = ohlcv_1d[-2]
            levels += [
                {"price": pd[2], "type": "PDH", "desc": "Prev Day High"},
                {"price": pd[3], "type": "PDL", "desc": "Prev Day Low"},
                {"price": pd[4], "type": "PDC", "desc": "Prev Day Close"},
            ]
            if len(ohlcv_1d) >= 8:
                week = ohlcv_1d[-8:-1]
                levels += [
                    {"price": max(c[2] for c in week), "type": "PWH", "desc": "Prev Week High"},
                    {"price": min(c[3] for c in week), "type": "PWL", "desc": "Prev Week Low"},
                ]

        if current_price > 0:
            magnitude = 10 ** max(0, len(str(int(current_price))) - 2)
            base = (int(current_price) // magnitude) * magnitude
            for mult in range(-2, 4):
                rp = base + mult * magnitude
                if rp > 0:
                    levels.append({"price": float(rp), "type": "ROUND", "desc": f"Round ${rp:,.0f}"})

        above = sorted([l for l in levels if l["price"] > current_price * 1.001], key=lambda x: x["price"])
        below = sorted([l for l in levels if l["price"] < current_price * 0.999],
                       key=lambda x: x["price"], reverse=True)

        return {
            "nearest_resistance": above[0] if above else None,
            "nearest_support": below[0] if below else None,
            "nearby_resistance": [l for l in above if (l["price"] - current_price) / current_price < 0.025],
            "nearby_support": [l for l in below if (current_price - l["price"]) / current_price < 0.025],
        }

    # ── FIBONACCI LEVELS ──────────────────────────────────────────────────────

    def _get_fib_levels(self, ohlcv: List[List], current_price: float) -> Dict:
        """
        Fibonacci retracement from the most recent significant swing (60-candle lookback).
        Golden zone (0.618–0.786 retracement) = highest probability reversal area.
        Price in golden zone + trend confirmation = premium entry.
        """
        if not ohlcv or len(ohlcv) < 20 or current_price <= 0:
            return {}

        lookback = min(60, len(ohlcv))
        recent = ohlcv[-lookback:]
        swing_high = max(c[2] for c in recent)
        swing_low = min(c[3] for c in recent)
        rng = swing_high - swing_low
        if rng == 0:
            return {}

        # Retracement from swing high downward
        fibs = {r: round(swing_high - rng * r, 6) for r in [0.236, 0.382, 0.5, 0.618, 0.786]}
        golden_low = fibs[0.786]
        golden_high = fibs[0.618]
        in_golden_zone = golden_low <= current_price <= golden_high

        at_fib = None
        for ratio, price in fibs.items():
            if abs(current_price - price) / current_price < 0.006:
                at_fib = {"ratio": ratio, "price": price}
                break

        return {
            "swing_high": round(swing_high, 6),
            "swing_low": round(swing_low, 6),
            "levels": fibs,
            "golden_zone": {"low": golden_low, "high": golden_high},
            "in_golden_zone": in_golden_zone,
            "at_fib_level": at_fib,
        }

    # ── SESSION TIMING ────────────────────────────────────────────────────────

    def _is_in_session(self) -> Dict:
        """
        Trading session quality based on UTC time.
        London/NY overlap (13–17 UTC) = highest liquidity = most reliable signals.
        Asia session is quieter but valid for Asian-listed pairs.
        """
        hour = datetime.now(timezone.utc).hour
        in_london = 8 <= hour < 16
        in_ny = 13 <= hour < 22

        if in_london and in_ny:
            return {"session": "LONDON_NY_OVERLAP", "quality": "HIGHEST", "bonus": 4}
        elif in_london:
            return {"session": "LONDON", "quality": "HIGH", "bonus": 3}
        elif in_ny:
            return {"session": "NEW_YORK", "quality": "HIGH", "bonus": 3}
        elif 0 <= hour < 8:
            return {"session": "ASIA", "quality": "MEDIUM", "bonus": 1}
        else:
            return {"session": "OFF_HOURS", "quality": "LOW", "bonus": 0}

    # ── FULL ANALYSIS ─────────────────────────────────────────────────────────

    async def full_analysis(self, symbol: str) -> Dict:
        """Run complete seven-layer analysis on a symbol."""
        symbol = _to_ccxt_symbol(symbol)

        # Fetch all OHLCV timeframes + orderbook + funding concurrently
        results = await asyncio.gather(
            self._fetch_ohlcv(symbol, "1h", 120),
            self._fetch_ohlcv(symbol, "4h", 80),
            self._fetch_ohlcv(symbol, "1d", 30),
            self.ob.analyze(symbol),
            self._fetch_funding_rate(symbol),
            return_exceptions=True,
        )

        ohlcv_1h     = results[0] if not isinstance(results[0], Exception) else []
        ohlcv_4h     = results[1] if not isinstance(results[1], Exception) else []
        ohlcv_1d     = results[2] if not isinstance(results[2], Exception) else []
        ob_data      = results[3] if not isinstance(results[3], Exception) else {}
        funding_data = results[4] if not isinstance(results[4], Exception) else {"rate": 0.0, "bias": "NEUTRAL"}

        current_price = ob_data.get("mid_price", 0) if isinstance(ob_data, dict) else 0
        if current_price <= 0 and ohlcv_1h:
            current_price = ohlcv_1h[-1][4]

        # Volume profiles
        vsp_1h = self.vsp.build_profile(ohlcv_1h) if ohlcv_1h else {}
        vsp_4h = self.vsp.build_profile(ohlcv_4h) if ohlcv_4h else {}

        # Liq heatmap
        liq_data = await self.liq.analyze(symbol, ohlcv_4h or ohlcv_1h)

        # Price location in profiles
        loc_1h = self.vsp.classify_price_location(vsp_1h, current_price) if vsp_1h and current_price > 0 else {}
        loc_4h = self.vsp.classify_price_location(vsp_4h, current_price) if vsp_4h and current_price > 0 else {}

        # CVD from order_flow module
        cvd_data = {}
        if self.order_flow:
            try:
                cvd_data = await self.order_flow.calculate_cvd(symbol)
            except Exception as e:
                logger.debug(f"CVD fetch error: {e}")

        # New analysis layers (CPU-bound, computed inline)
        trend_4h     = self._get_trend_structure(ohlcv_4h, lookback=30)
        trend_1d     = self._get_trend_structure(ohlcv_1d, lookback=20)
        order_blocks = self._detect_order_blocks(ohlcv_4h, current_price)
        fvg_data     = self._detect_fvg(ohlcv_1h, current_price)
        rsi_4h       = self._calc_rsi(ohlcv_4h, 14)
        rsi_1h       = self._calc_rsi(ohlcv_1h, 14)
        rsi_div_4h   = self._detect_rsi_divergence(ohlcv_4h)
        key_levels   = self._get_key_levels(ohlcv_1d, current_price)
        fib_data     = self._get_fib_levels(ohlcv_4h, current_price)
        session_info = self._is_in_session()

        signal = self._generate_signal(
            symbol=symbol,
            current_price=current_price,
            vsp_1h=vsp_1h, vsp_4h=vsp_4h,
            loc_1h=loc_1h, loc_4h=loc_4h,
            liq_data=liq_data,
            ob_data=ob_data,
            cvd_data=cvd_data,
            btc_bias=self.btc_bias,
            trend_4h=trend_4h, trend_1d=trend_1d,
            funding_data=funding_data,
            order_blocks=order_blocks,
            fvg_data=fvg_data,
            rsi_4h=rsi_4h, rsi_1h=rsi_1h,
            rsi_div_4h=rsi_div_4h,
            key_levels=key_levels,
            fib_data=fib_data,
            session_info=session_info,
        )

        return {
            "symbol": symbol,
            "current_price": current_price,
            "volume_profile_1h": vsp_1h,
            "volume_profile_4h": vsp_4h,
            "price_location_1h": loc_1h,
            "price_location_4h": loc_4h,
            "liquidation_heatmap": liq_data,
            "orderbook": ob_data,
            "cvd": cvd_data,
            "funding": funding_data,
            "trend_4h": trend_4h,
            "trend_1d": trend_1d,
            "order_blocks": order_blocks,
            "fvg": fvg_data,
            "rsi": {"rsi_4h": rsi_4h, "rsi_1h": rsi_1h, "divergence_4h": rsi_div_4h},
            "key_levels": key_levels,
            "fibonacci": fib_data,
            "session": session_info,
            "signal": signal,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── SIGNAL GENERATION ─────────────────────────────────────────────────────

    def _generate_signal(
        self,
        symbol: str,
        current_price: float,
        vsp_1h: Dict, vsp_4h: Dict,
        loc_1h: Dict, loc_4h: Dict,
        liq_data: Dict,
        ob_data: Dict,
        cvd_data: Dict,
        btc_bias: str = "NEUTRAL",
        trend_4h: Dict = None,
        trend_1d: Dict = None,
        funding_data: Dict = None,
        order_blocks: Dict = None,
        fvg_data: Dict = None,
        rsi_4h: float = 50.0,
        rsi_1h: float = 50.0,
        rsi_div_4h: Dict = None,
        key_levels: Dict = None,
        fib_data: Dict = None,
        session_info: Dict = None,
    ) -> Dict:
        """
        Seven-layer signal with hard gates + tiered scoring.

        LAYER A — Macro Bias (max ~16 pts):  own 4H/1D trend, BTC macro, funding
        LAYER B — Structural Zones (max ~26 pts): OB, FVG, HVN, key levels, Fibonacci
        LAYER C — Flow Confirmation (max ~20 pts): CVD, RSI level/divergence, OB imbalance, sweeps, MTF
        LAYER D — Liquidity (max ~10 pts): liq clusters, orderbook walls
        LAYER E — Timing (max ~6 pts): session quality, naked POC

        Hard gates: BTC macro, extreme funding
        Structural zone required: at least 1 OB/FVG/HVN/key-level confirmation
        Threshold: winning_score >= 22, gap >= 12, confidence >= 65%
        """
        bull_score = 0
        bear_score = 0
        confirmations = []
        warnings = []
        has_structural_zone = False

        trend_4h     = trend_4h or {}
        trend_1d     = trend_1d or {}
        funding_data = funding_data or {}
        order_blocks = order_blocks or {}
        fvg_data     = fvg_data or {}
        rsi_div_4h   = rsi_div_4h or {}
        key_levels   = key_levels or {}
        fib_data     = fib_data or {}
        session_info = session_info or {"session": "UNKNOWN", "quality": "LOW", "bonus": 0}

        if not current_price:
            return {"direction": "NONE", "confidence": 0, "reason": "No price data"}

        # ── LAYER A: MACRO BIAS ────────────────────────────────────────────────

        # Asset's own 4H structure (proven signal from data)
        t4h_bias = trend_4h.get("bias", "NEUTRAL")
        if t4h_bias == "BULLISH":
            bull_score += 5
            confirmations.append(f"4H structure UPTREND (HH+HL) — bullish bias")
        elif t4h_bias == "BEARISH":
            bear_score += 5
            confirmations.append(f"4H structure DOWNTREND (LH+LL) — bearish bias")

        # Daily structure (strongest bias — filters noise from shorter TFs)
        t1d_bias = trend_1d.get("bias", "NEUTRAL")
        if t1d_bias == "BULLISH":
            bull_score += 6
            confirmations.append("Daily structure BULLISH — higher timeframe supports longs")
        elif t1d_bias == "BEARISH":
            bear_score += 6
            confirmations.append("Daily structure BEARISH — higher timeframe supports shorts")

        # BTC macro (hard gate below; soft score contribution here)
        if btc_bias == "BEARISH":
            bear_score += 2
            confirmations.append("BTC macro BEARISH (4H SMA) — LONGs hard-blocked")
        elif btc_bias == "BULLISH":
            bull_score += 2
            confirmations.append("BTC macro BULLISH (4H SMA) — SHORTs hard-blocked")

        # Funding rate: overcrowded positions = mean reversion opportunity
        f_bias = funding_data.get("bias", "NEUTRAL")
        f_rate_pct = funding_data.get("rate_pct", 0.0)
        if f_bias == "HIGH_SHORT":     # shorts overcrowded → likely squeeze up
            bull_score += 3
            confirmations.append(f"Funding negative ({f_rate_pct:.4f}%) — shorts overcrowded, squeeze risk")
        elif f_bias == "HIGH_LONG":    # longs overcrowded → likely dump
            bear_score += 3
            confirmations.append(f"Funding elevated ({f_rate_pct:.4f}%) — longs overcrowded, dump risk")

        # ── LAYER B: STRUCTURAL ZONES ──────────────────────────────────────────

        cvd_bias = cvd_data.get("bias", "NEUTRAL")
        ib_bias = ob_data.get("imbalance", {}).get("bias", "NEUTRAL")

        # Order Blocks (SMC) — highest-quality structural zone
        nearest_bull_ob = order_blocks.get("nearest_bullish_ob")
        nearest_bear_ob = order_blocks.get("nearest_bearish_ob")

        if nearest_bull_ob and nearest_bull_ob["dist_pct"] < 3.0:
            bull_score += 8
            has_structural_zone = True
            confirmations.append(
                f"Bullish OB {nearest_bull_ob['dist_pct']:.1f}% below "
                f"({nearest_bull_ob['low']:.4f}–{nearest_bull_ob['high']:.4f}) — unmitigated SMC support"
            )
        if nearest_bear_ob and nearest_bear_ob["dist_pct"] < 3.0:
            bear_score += 8
            has_structural_zone = True
            confirmations.append(
                f"Bearish OB {nearest_bear_ob['dist_pct']:.1f}% above "
                f"({nearest_bear_ob['low']:.4f}–{nearest_bear_ob['high']:.4f}) — unmitigated SMC resistance"
            )

        # Fair Value Gaps — price imbalances that act as fill magnets
        nearest_bull_fvg = fvg_data.get("nearest_bullish_fvg")
        nearest_bear_fvg = fvg_data.get("nearest_bearish_fvg")

        if nearest_bull_fvg and nearest_bull_fvg["dist_pct"] < 3.0:
            bull_score += 5
            has_structural_zone = True
            confirmations.append(
                f"Bullish FVG {nearest_bull_fvg['dist_pct']:.1f}% below "
                f"({nearest_bull_fvg['size_pct']:.2f}% gap) — unfilled support magnet"
            )
        if nearest_bear_fvg and nearest_bear_fvg["dist_pct"] < 3.0:
            bear_score += 5
            has_structural_zone = True
            confirmations.append(
                f"Bearish FVG {nearest_bear_fvg['dist_pct']:.1f}% above "
                f"({nearest_bear_fvg['size_pct']:.2f}% gap) — unfilled resistance magnet"
            )

        # Volume Profile HVN — high volume congestion = strong S/R
        if loc_1h.get("at_hvn"):
            if cvd_bias in ("BULLISH", "SLIGHT_BULLISH") or ib_bias in ("BULLISH", "STRONG_BULLISH"):
                bull_score += 5
                has_structural_zone = True
                confirmations.append("1H HVN support + bullish flow confirmation")
            elif cvd_bias in ("BEARISH", "SLIGHT_BEARISH") or ib_bias in ("BEARISH", "STRONG_BEARISH"):
                bear_score += 5
                has_structural_zone = True
                confirmations.append("1H HVN resistance + bearish flow confirmation")

        if loc_4h.get("at_hvn"):
            if cvd_bias in ("BULLISH", "SLIGHT_BULLISH"):
                bull_score += 4
                has_structural_zone = True
                confirmations.append("4H HVN support + bullish CVD")
            elif cvd_bias in ("BEARISH", "SLIGHT_BEARISH"):
                bear_score += 4
                has_structural_zone = True
                confirmations.append("4H HVN resistance + bearish CVD")

        # Key institutional levels (PDH/PDL/PWH/PWL) — widely watched magnets
        for sup in key_levels.get("nearby_support", []):
            if sup["type"] in ("PDH", "PDL", "PDC", "PWH", "PWL"):
                dist = (current_price - sup["price"]) / current_price * 100
                bull_score += 3
                has_structural_zone = True
                confirmations.append(f"{sup['type']} support at {sup['price']:.4f} ({dist:.1f}% below)")
                break

        for res in key_levels.get("nearby_resistance", []):
            if res["type"] in ("PDH", "PDL", "PDC", "PWH", "PWL"):
                dist = (res["price"] - current_price) / current_price * 100
                bear_score += 3
                has_structural_zone = True
                confirmations.append(f"{res['type']} resistance at {res['price']:.4f} ({dist:.1f}% above)")
                break

        # Fibonacci golden zone (0.618–0.786 retracement) — high-probability reversal
        if fib_data.get("in_golden_zone"):
            if t4h_bias == "BULLISH" or t1d_bias == "BULLISH":
                bull_score += 4
                has_structural_zone = True
                gz = fib_data.get("golden_zone", {})
                confirmations.append(
                    f"Price in Fib golden zone ({gz.get('low', 0):.4f}–{gz.get('high', 0):.4f}) — premium long zone"
                )
            elif t4h_bias == "BEARISH" or t1d_bias == "BEARISH":
                bear_score += 4
                has_structural_zone = True
                confirmations.append("Price in Fib golden zone in downtrend — premium short zone")

        # VAH/VAL proximity (volume profile boundaries)
        vah_1h = vsp_1h.get("vah", 0)
        val_1h = vsp_1h.get("val", 0)
        if val_1h > 0 and current_price > 0:
            if abs(current_price - val_1h) / current_price < 0.005:
                bull_score += 2
                confirmations.append(f"Price at 1H VAL support ({val_1h:.4f})")
            elif abs(current_price - vah_1h) / current_price < 0.005:
                bear_score += 2
                confirmations.append(f"Price at 1H VAH resistance ({vah_1h:.4f})")

        # LVN — thin zone means fast directional move incoming
        if loc_1h.get("in_lvn"):
            confirmations.append("Price in LVN (thin zone) — expect fast directional move")

        # Value area zone signals
        zone_1h = loc_1h.get("zone", "")
        zone_4h = loc_4h.get("zone", "")
        if zone_1h == "BELOW_VALUE_AREA":
            bull_score += 1
            warnings.append("Price below value area — discount zone")
        elif zone_1h == "ABOVE_VALUE_AREA":
            bear_score += 1
            warnings.append("Price above value area — premium zone")

        # ── LAYER C: FLOW CONFIRMATION ─────────────────────────────────────────

        # CVD — cumulative volume delta (real buy vs sell pressure)
        cvd_trend = cvd_data.get("cvd_trend", "UNKNOWN")
        if cvd_bias in ("BULLISH", "SLIGHT_BULLISH"):
            bull_score += 3
            confirmations.append(f"CVD bullish ({cvd_data.get('buy_pct', 50):.0f}% buy vol)")
        elif cvd_bias in ("BEARISH", "SLIGHT_BEARISH"):
            bear_score += 3
            confirmations.append(f"CVD bearish ({cvd_data.get('sell_pct', 50):.0f}% sell vol)")

        if cvd_trend == "RISING":
            bull_score += 1
        elif cvd_trend == "FALLING":
            bear_score += 1

        # RSI level — overbought/oversold (only extreme readings score)
        if rsi_4h < 32:
            bull_score += 3
            confirmations.append(f"4H RSI oversold ({rsi_4h:.0f}) — mean reversion due")
        elif rsi_4h > 68:
            bear_score += 3
            confirmations.append(f"4H RSI overbought ({rsi_4h:.0f}) — exhaustion likely")
        elif rsi_4h < 45:
            bull_score += 1   # weak bullish lean
        elif rsi_4h > 55:
            bear_score += 1   # weak bearish lean

        # RSI divergence — strongest momentum signal
        rsi_div_type = rsi_div_4h.get("type", "NONE")
        if rsi_div_type == "BULLISH":
            bull_score += 6
            confirmations.append(rsi_div_4h["desc"])
        elif rsi_div_type == "BEARISH":
            bear_score += 6
            confirmations.append(rsi_div_4h["desc"])

        # Orderbook imbalance (bid vs ask pressure within 1% of mid)
        ib_ratio = ob_data.get("imbalance", {}).get("imbalance_ratio", 1.0)
        if ib_bias in ("STRONG_BULLISH", "BULLISH"):
            bull_score += 2 if ib_ratio > 2.0 else 1
            confirmations.append(f"Orderbook bid-heavy ({ib_ratio:.1f}x bids vs asks)")
        elif ib_bias in ("STRONG_BEARISH", "BEARISH"):
            bear_score += 2 if ib_ratio < 0.5 else 1
            confirmations.append(f"Orderbook ask-heavy ({ib_ratio:.1f}x asks vs bids)")

        # Sweeps (wall absorbed = strong directional momentum)
        sweeps = ob_data.get("sweeps", [])
        for sweep in sweeps[:2]:
            if sweep["direction"] == "BULLISH":
                bull_score += 3
                confirmations.append(f"Ask wall swept (${sweep['size_usd']:,.0f}) — buyers absorbed supply")
            elif sweep["direction"] == "BEARISH":
                bear_score += 3
                confirmations.append(f"Bid wall swept (${sweep['size_usd']:,.0f}) — sellers absorbed bids")

        # MTF confluence (1H and 4H zone signals both agree)
        zone_1h_sig = loc_1h.get("zone_signal", "")
        zone_4h_sig = loc_4h.get("zone_signal", "")
        bullish_zones = ("BULLISH_BREAKOUT", "AT_VAL_SUPPORT")
        bearish_zones = ("BEARISH_BREAKDOWN", "AT_VAH_RESISTANCE")

        if zone_1h_sig in bullish_zones and zone_4h_sig in bullish_zones:
            bull_score += 3
            confirmations.append("MTF confluence: 1H + 4H both bullish structure")
        elif zone_1h_sig in bearish_zones and zone_4h_sig in bearish_zones:
            bear_score += 3
            confirmations.append("MTF confluence: 1H + 4H both bearish structure")
        elif (zone_1h_sig in bullish_zones and zone_4h_sig in bearish_zones) or \
             (zone_1h_sig in bearish_zones and zone_4h_sig in bullish_zones):
            warnings.append("MTF conflict: 1H and 4H structures disagree")
            bull_score = max(0, bull_score - 3)
            bear_score = max(0, bear_score - 3)

        # ── LAYER D: LIQUIDITY ─────────────────────────────────────────────────

        nearest_long_cluster = liq_data.get("nearest_long_cluster")
        nearest_short_cluster = liq_data.get("nearest_short_cluster")

        if nearest_short_cluster:
            dist_short = abs(nearest_short_cluster["dist_pct"])
            intensity = nearest_short_cluster.get("intensity", 0)
            if dist_short < 3.0 and intensity > 0.5:
                bull_score += 4
                confirmations.append(
                    f"Short liq cluster {dist_short:.1f}% above ({nearest_short_cluster['price']:.4f}) — pump target"
                )
            elif dist_short < 6.0 and intensity > 0.7:
                bull_score += 2
                confirmations.append(f"Short liq cluster {dist_short:.1f}% above — liq magnet zone")

        if nearest_long_cluster:
            dist_long = abs(nearest_long_cluster["dist_pct"])
            intensity = nearest_long_cluster.get("intensity", 0)
            if dist_long < 3.0 and intensity > 0.5:
                bear_score += 4
                confirmations.append(
                    f"Long liq cluster {dist_long:.1f}% below ({nearest_long_cluster['price']:.4f}) — dump target"
                )
            elif dist_long < 6.0 and intensity > 0.7:
                bear_score += 2
                confirmations.append(f"Long liq cluster {dist_long:.1f}% below — liq magnet zone")

        if liq_data.get("approaching_short_liq"):
            confirmations.insert(0, "IMMINENT: At short liq cluster — sweep pump expected")
        if liq_data.get("approaching_long_liq"):
            confirmations.insert(0, "IMMINENT: At long liq cluster — stop hunt dump expected")

        # Orderbook walls close to price
        walls = ob_data.get("walls", {})
        nb = walls.get("nearest_bid_wall")
        na = walls.get("nearest_ask_wall")
        if nb and abs(nb["dist_pct"]) < 1.5:
            bull_score += 1
            confirmations.append(f"Bid wall ${nb['size_usd']:,.0f} at {nb['price']} ({nb['dist_pct']:.1f}%)")
        if na and abs(na["dist_pct"]) < 1.5:
            bear_score += 1
            confirmations.append(f"Ask wall ${na['size_usd']:,.0f} at {na['price']} ({na['dist_pct']:.1f}%)")

        # Naked POC magnet
        if vsp_1h and vsp_4h and current_price > 0:
            naked_pocs = self.vsp.find_naked_poc(vsp_1h, current_price, [vsp_4h])
            for npoc in naked_pocs[:1]:
                dist = npoc.get("distance_pct", 99)
                if dist < 5.0:
                    if npoc.get("direction") == "ABOVE":
                        bull_score += 2
                        confirmations.append(f"Naked POC magnet {dist:.1f}% above ({npoc['poc_price']:.4f})")
                    elif npoc.get("direction") == "BELOW":
                        bear_score += 2
                        confirmations.append(f"Naked POC magnet {dist:.1f}% below ({npoc['poc_price']:.4f})")

        # ── LAYER E: SESSION TIMING ────────────────────────────────────────────

        session_bonus = session_info.get("bonus", 0)
        session_name = session_info.get("session", "UNKNOWN")
        if session_bonus > 0:
            if bull_score > bear_score:
                bull_score += session_bonus
            elif bear_score > bull_score:
                bear_score += session_bonus
            confirmations.append(f"Session: {session_name} ({session_info.get('quality', '')} quality)")

        # ── FINAL DECISION ────────────────────────────────────────────────────

        total_score = bull_score + bear_score
        if total_score == 0:
            return {
                "direction": "NONE", "confidence": 0, "reason": "No signals detected",
                "bull_score": 0, "bear_score": 0,
                "confirmations": confirmations, "warnings": warnings,
            }

        winning_score = max(bull_score, bear_score)
        score_gap = abs(bull_score - bear_score)
        score_ratio = winning_score / max(total_score, 1)

        direction = "LONG" if bull_score > bear_score else "SHORT"

        # ── HARD GATE 1: BTC Macro ──────────────────────────────────────────
        confidence_override = None
        if btc_bias == "BEARISH" and direction == "LONG":
            direction = "NONE"
            confidence_override = max(winning_score * 1.0, 20)
            warnings.append("LONG blocked — BTC macro trend BEARISH")
        elif btc_bias == "BULLISH" and direction == "SHORT":
            direction = "NONE"
            confidence_override = max(winning_score * 1.0, 20)
            warnings.append("SHORT blocked — BTC macro trend BULLISH")

        # ── HARD GATE 2: Extreme Funding ────────────────────────────────────
        if f_bias == "EXTREME_LONG" and direction == "LONG":
            direction = "NONE"
            warnings.append(f"LONG blocked — funding extreme ({f_rate_pct:.4f}%) — longs severely overcrowded")
        elif f_bias == "EXTREME_SHORT" and direction == "SHORT":
            direction = "NONE"
            warnings.append(f"SHORT blocked — funding extreme negative ({f_rate_pct:.4f}%) — shorts severely overcrowded")

        # ── STRUCTURAL ZONE REQUIREMENT ─────────────────────────────────────
        if direction != "NONE" and not has_structural_zone:
            direction = "NONE"
            warnings.append("No structural zone (OB/FVG/HVN/key level) confirmed — entry not justified")

        # ── SCORE THRESHOLD ─────────────────────────────────────────────────
        if direction != "NONE" and (winning_score < 22 or score_gap < 12):
            direction = "NONE"
            warnings.append(f"Score weak (winning={winning_score}, gap={score_gap}) — need ≥22/≥12")

        # ── CONFIDENCE FORMULA ──────────────────────────────────────────────
        if confidence_override is not None:
            confidence = confidence_override
        else:
            confidence = min(95, 15 + (winning_score * 3.0) + (score_ratio * 18))

        if direction == "NONE" and confidence_override is None:
            confidence = max(confidence * 0.4, 20)

        # ── TP/SL USING ALL STRUCTURAL ZONES ────────────────────────────────
        tp_price = None
        sl_price = None

        if direction == "LONG":
            # TP: short liq cluster → bearish OB → bearish FVG → VAH → key resistance
            if nearest_short_cluster and 0.5 < abs(nearest_short_cluster["dist_pct"]) < 10.0:
                tp_price = nearest_short_cluster["price"]
            elif nearest_bear_ob and nearest_bear_ob.get("mid", 0) > current_price:
                tp_price = nearest_bear_ob["low"]
            elif nearest_bear_fvg and nearest_bear_fvg.get("mid", 0) > current_price:
                tp_price = nearest_bear_fvg["low"]
            elif vah_1h and vah_1h > current_price:
                tp_price = vah_1h
            elif vsp_1h.get("poc_price", 0) > current_price:
                tp_price = vsp_1h["poc_price"]
            if tp_price is None and key_levels.get("nearest_resistance"):
                res = key_levels["nearest_resistance"]
                if res["price"] > current_price:
                    tp_price = res["price"]

            # SL: bullish OB low → bullish FVG low → HVN below → 2% default
            if nearest_bull_ob and nearest_bull_ob["low"] < current_price:
                sl_price = nearest_bull_ob["low"] * 0.998
            elif nearest_bull_fvg and nearest_bull_fvg["low"] < current_price:
                sl_price = nearest_bull_fvg["low"] * 0.998
            else:
                sl_candidate = loc_1h.get("nearest_hvn_below", {})
                sl_price = sl_candidate.get("price") if sl_candidate else current_price * 0.980

        elif direction == "SHORT":
            # TP: long liq cluster → bullish OB → bullish FVG → VAL → key support
            if nearest_long_cluster and 0.5 < abs(nearest_long_cluster["dist_pct"]) < 10.0:
                tp_price = nearest_long_cluster["price"]
            elif nearest_bull_ob and nearest_bull_ob.get("mid", 0) < current_price:
                tp_price = nearest_bull_ob["high"]
            elif nearest_bull_fvg and nearest_bull_fvg.get("mid", 0) < current_price:
                tp_price = nearest_bull_fvg["high"]
            elif val_1h and val_1h < current_price:
                tp_price = val_1h
            elif vsp_1h.get("poc_price", 0) < current_price:
                tp_price = vsp_1h["poc_price"]
            if tp_price is None and key_levels.get("nearest_support"):
                sup = key_levels["nearest_support"]
                if sup["price"] < current_price:
                    tp_price = sup["price"]

            # SL: bearish OB high → bearish FVG high → HVN above → 2% default
            if nearest_bear_ob and nearest_bear_ob["high"] > current_price:
                sl_price = nearest_bear_ob["high"] * 1.002
            elif nearest_bear_fvg and nearest_bear_fvg["high"] > current_price:
                sl_price = nearest_bear_fvg["high"] * 1.002
            else:
                sl_candidate = loc_1h.get("nearest_hvn_above", {})
                sl_price = sl_candidate.get("price") if sl_candidate else current_price * 1.020

        # ── SL distance validation ────────────────────────────────────────────
        # If SL is within 0.2% of entry, fall back to 2% structural default.
        # This prevents entries where the HVN lookup returns a level at/near
        # current price, which would create a near-immediate stop-out.
        if sl_price and current_price > 0:
            _sl_dist_pct = abs(sl_price - current_price) / current_price
            if _sl_dist_pct < 0.002:
                # Fall back to 2% default instead of a potentially useless level
                if direction == "LONG":
                    sl_price = round(current_price * 0.980, 6)
                elif direction == "SHORT":
                    sl_price = round(current_price * 1.020, 6)
                warnings.append(
                    f"SL fallback: structural level {_sl_dist_pct*100:.3f}% from entry "
                    f"(< 0.2% minimum) — using 2% default"
                )

        # R:R calculation
        rr = None
        if tp_price and sl_price and current_price > 0:
            reward = abs(tp_price - current_price)
            risk = abs(sl_price - current_price)
            rr = round(reward / risk, 2) if risk > 0 else None

        # R:R filter: minimum 1.5
        if direction in ("LONG", "SHORT") and (rr is None or rr < 1.5):
            direction = "NONE"
            warnings.append(f"Signal filtered: R:R {rr} below 1.5 minimum")

        # Confidence threshold
        if direction in ("LONG", "SHORT") and confidence < 65:
            direction = "NONE"
            warnings.append(f"Confidence {confidence:.1f}% below 65% threshold")

        self.signals_generated += 1

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "bull_score": bull_score,
            "bear_score": bear_score,
            "winning_score": winning_score,
            "score_gap": score_gap,
            "btc_bias": btc_bias,
            "funding_rate": f_rate_pct,
            "rsi_4h": rsi_4h,
            "trend_4h": trend_4h.get("structure", "UNKNOWN"),
            "trend_1d": trend_1d.get("structure", "UNKNOWN"),
            "session": session_info.get("session", "UNKNOWN"),
            "has_structural_zone": has_structural_zone,
            "confirmations": confirmations[:10],
            "warnings": warnings,
            "entry": current_price,
            "tp": round(tp_price, 6) if tp_price else None,
            "sl": round(sl_price, 6) if sl_price else None,
            "rr": rr,
        }

    # ── SCAN ──────────────────────────────────────────────────────────────────

    async def scan_symbol(self, symbol: str) -> Optional[Dict]:
        """Analyze a symbol. Returns result only if confidence >= 70%."""
        self.scans_run += 1
        try:
            result = await self.full_analysis(symbol)
            signal = result.get("signal", {})
            if signal.get("direction") != "NONE" and signal.get("confidence", 0) >= 70:
                return result
            return None
        except Exception as e:
            logger.error(f"HP scan error for {symbol}: {e}")
            return None

    async def scan_all(self, symbols: List[str]) -> List[Dict]:
        """Scan all symbols concurrently, return signals sorted by confidence."""
        tasks = [self.scan_symbol(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        signals = [r for r in results if r is not None and not isinstance(r, Exception)]
        signals.sort(key=lambda x: x.get("signal", {}).get("confidence", 0), reverse=True)
        return signals

    async def run_scan_loop(self, interval_seconds: int = 300):
        """Background scan loop. Runs every 5 min. Sends Telegram + routes paper trades."""
        logger.info("HyperAccuracyEngine scan loop started")
        from free_will_v2 import TOP_PAIRS
        symbols = TOP_PAIRS

        while self.active:
            try:
                await self._update_btc_bias()
                logger.debug(f"HyperAccuracy scan cycle — BTC bias: {self.btc_bias}")

                signals = await self.scan_all(symbols)

                for result in signals:
                    signal = result.get("signal", {})
                    direction = signal.get("direction")
                    confidence = signal.get("confidence", 0)
                    symbol = result.get("symbol", "")

                    # Macro direction gate
                    _macro_threshold = 70
                    try:
                        from regime_engine import get_regime_engine
                        _macro_threshold, _macro_reason = get_regime_engine().apply_macro_confidence_gate(direction, 70)
                        if _macro_reason:
                            logger.debug(f"[MACRO GATE] {symbol}: {_macro_reason}")
                    except Exception:
                        pass
                    if direction == "NONE" or confidence < _macro_threshold:
                        continue

                    try:
                        from paper_trading import route_engine_signal
                        from aeon_engine_system import get_engine_manager, EngineType
                        if direction in ("LONG", "SHORT"):
                            _entry = signal.get("entry") or 0
                            _sl = signal.get("sl") or 0
                            _sl_dist = abs(_entry - _sl) / _entry if _entry and _sl else 0.02
                            _dynamic_lev = min(20, max(5, int(0.04 / max(_sl_dist, 0.005))))
                            paper_signal = {
                                "symbol": symbol,
                                "direction": direction,
                                "entry_price": _entry,
                                "stop_loss": _sl,
                                "take_profit": signal.get("tp"),
                                "confidence": confidence,
                                "leverage": _dynamic_lev,
                                "position_size": 500,
                                "confluences": len(signal.get("confirmations", [])),
                                "confirmations": signal.get("confirmations", []),
                                "timeframe": "4h",
                            }
                            # Always send Telegram alert for valid signals — gate only controls execution
                            if self.send_telegram and self.chat_ids:
                                try:
                                    msg = self._format_alert(result)
                                    for chat_id in self.chat_ids:
                                        await self.send_telegram(chat_id, msg)
                                except Exception as _te:
                                    logger.warning(f"HP Telegram send failed: {_te}")

                            # Gate through unified risk system before routing to paper trading
                            engine_manager = get_engine_manager()
                            gate_result = await engine_manager.submit_signal_gated(
                                paper_signal, EngineType.VOLUME_PROFILE
                            )
                            if gate_result.get("action") == "EXECUTE":
                                # Scale position size by quant gate multiplier
                                _mult = gate_result.get("position_multiplier", 1.0)
                                paper_signal["position_size"] = round(500 * _mult, 2)
                                if gate_result.get("marginal"):
                                    logger.info(f"[VP] Marginal gate pass — size scaled to {_mult:.2f}× ({paper_signal['position_size']})")
                                await route_engine_signal(paper_signal, "HYPER_ACCURACY")
                            else:
                                logger.info(
                                    f"[VP] Signal blocked by engine_manager: "
                                    f"{gate_result.get('reason', 'unknown')}"
                                )
                    except Exception as e:
                        logger.debug(f"HP paper trade routing error: {e}")

            except Exception as e:
                logger.error(f"HP scan loop error: {e}\n{traceback.format_exc()}")

            await asyncio.sleep(interval_seconds)

    # ── TELEGRAM ALERT ────────────────────────────────────────────────────────

    def _format_alert(self, result: Dict) -> str:
        """Format a clean, scannable Hyper Accuracy alert for Telegram."""
        signal     = result.get("signal", {})
        symbol     = result.get("symbol", "").replace("/USDT", "")
        direction  = signal.get("direction", "")
        confidence = signal.get("confidence", 0)
        entry      = signal.get("entry", 0)
        tp         = signal.get("tp")
        sl         = signal.get("sl")
        rr         = signal.get("rr") or 0
        rsi_4h     = signal.get("rsi_4h", 50)
        funding    = signal.get("funding_rate", 0.0)
        trend_4h   = signal.get("trend_4h", "—")
        trend_1d   = signal.get("trend_1d", "—")
        session    = signal.get("session", "—")
        bull_score = signal.get("bull_score", 0)
        bear_score = signal.get("bear_score", 0)
        btc_bias   = signal.get("btc_bias", "NEUTRAL")
        confirmations = [c for c in signal.get("confirmations", []) if not c.startswith("BTC macro")]
        warnings      = signal.get("warnings", [])

        def _fmt(p) -> str:
            if p is None: return "—"
            if p >= 1000:   return f"{p:,.2f}"
            elif p >= 1:    return f"{p:,.4f}"
            elif p >= 0.01: return f"{p:,.6f}"
            else:           return f"{p:,.8f}"

        def _pct(a, b) -> str:
            if not a or not b or b == 0: return ""
            return f"{(a - b) / b * 100:+.2f}%"

        # RSI label
        if rsi_4h < 35:
            rsi_label = "oversold"
        elif rsi_4h > 65:
            rsi_label = "overbought"
        else:
            rsi_label = "neutral"

        # Funding label
        if abs(funding) < 0.0005:
            fund_label = "neutral"
        elif funding > 0:
            fund_label = "longs paying"
        else:
            fund_label = "shorts paying"

        # Session display
        session_map = {
            "LONDON_NY_OVERLAP": "London/NY Overlap",
            "LONDON": "London",
            "NEW_YORK": "New York",
            "ASIA": "Asia",
            "OFF_HOURS": "Off Hours",
        }
        session_display = session_map.get(session, session)

        is_long = direction == "LONG"
        header_emoji = "🟢" if is_long else "🔴"
        dir_label    = "LONG" if is_long else "SHORT"

        liq = result.get("liquidation_heatmap", {})
        nsc = liq.get("nearest_short_cluster")
        nlc = liq.get("nearest_long_cluster")
        vsp = result.get("volume_profile_1h", {})
        poc = vsp.get("poc_price", 0)
        vah = vsp.get("vah", 0)
        val = vsp.get("val", 0)
        obs = result.get("order_blocks", {})
        fvg = result.get("fvg", {})

        tp_pct = _pct(tp, entry)
        sl_pct = _pct(sl, entry)

        # ── HEADER ───────────────────────────────────────────────────────────
        msg  = f"{header_emoji} {dir_label} · {symbol}/USDT\n"
        msg += f"Confidence: {confidence:.0f}%\n"

        # ── TRADE SETUP ──────────────────────────────────────────────────────
        msg += f"\nEntry   ${_fmt(entry)}\n"
        msg += f"Target  ${_fmt(tp)}   {tp_pct}\n"
        msg += f"Stop    ${_fmt(sl)}   {sl_pct}\n"
        msg += f"R:R     {rr:.1f}x\n"

        # ── MARKET CONTEXT ────────────────────────────────────────────────────
        msg += f"\nContext\n"
        msg += f"Trend     {trend_4h} (4H) · {trend_1d} (1D)\n"
        msg += f"RSI 4H    {rsi_4h:.0f} · {rsi_label}\n"
        msg += f"Funding   {funding:+.4f}% · {fund_label}\n"
        msg += f"BTC       {btc_bias} · {session_display}\n"

        # ── KEY ZONES ─────────────────────────────────────────────────────────
        msg += "\nKey Zones\n"
        if poc:
            msg += f"POC          ${_fmt(poc)}\n"
            msg += f"VA           ${_fmt(val)} – ${_fmt(vah)}\n"

        if is_long and obs.get("nearest_bullish_ob"):
            ob = obs["nearest_bullish_ob"]
            msg += f"Bull OB      ${_fmt(ob['low'])} – ${_fmt(ob['high'])}   ({ob['dist_pct']:.1f}% below)\n"
        elif not is_long and obs.get("nearest_bearish_ob"):
            ob = obs["nearest_bearish_ob"]
            msg += f"Bear OB      ${_fmt(ob['low'])} – ${_fmt(ob['high'])}   ({ob['dist_pct']:.1f}% above)\n"

        if is_long and fvg.get("nearest_bullish_fvg"):
            fv = fvg["nearest_bullish_fvg"]
            msg += f"Bull FVG     ${_fmt(fv['low'])} – ${_fmt(fv['high'])}   ({fv['size_pct']:.2f}% gap)\n"
        elif not is_long and fvg.get("nearest_bearish_fvg"):
            fv = fvg["nearest_bearish_fvg"]
            msg += f"Bear FVG     ${_fmt(fv['low'])} – ${_fmt(fv['high'])}   ({fv['size_pct']:.2f}% gap)\n"

        liq_target = nsc if is_long else nlc
        if liq_target:
            side = "Short" if is_long else "Long"
            msg += f"Liq Cluster  ${_fmt(liq_target['price'])}   ({liq_target['dist_pct']:+.1f}%)\n"

        # ── CONFIRMATIONS ─────────────────────────────────────────────────────
        nums = ["①","②","③","④","⑤","⑥"]
        clean_confirms = []
        for c in confirmations[:6]:
            c = c.replace(" — unmitigated SMC support", "").replace(" — unmitigated SMC resistance", "")
            c = c.replace(" — bullish bias", "").replace(" — bearish bias", "")
            c = c.replace(" — higher timeframe supports longs", "").replace(" — higher timeframe supports shorts", "")
            c = c.replace(" — LONGs hard-blocked", "").replace(" — SHORTs hard-blocked", "")
            c = c.replace("confirmation", "").strip()
            clean_confirms.append(c)

        if clean_confirms:
            msg += f"\nWhy This Trade\n"
            for i, c in enumerate(clean_confirms):
                msg += f"{nums[i]} {c}\n"

        # ── WARNINGS ─────────────────────────────────────────────────────────
        if warnings:
            msg += "\nNote\n"
            for w in warnings[:2]:
                msg += f"· {w}\n"

        # ── FOOTER ───────────────────────────────────────────────────────────
        msg += f"\n{bull_score} bull  {bear_score} bear · Hyper Accuracy"

        return msg

    def get_stats(self) -> Dict:
        return {
            "engine": "HyperAccuracyEngine",
            "active": self.active,
            "btc_bias": self.btc_bias,
            "scans_run": self.scans_run,
            "signals_generated": self.signals_generated,
        }

    async def get_key_vp_levels(self, symbol: str) -> Dict:
        """
        Lightweight query: return key institutional price levels for a symbol.
        Used as confirmation inputs by other engines.
        Returns: poc, vah, val, nearest_naked_poc, nearest_liq_cluster, lvn_zones
        """
        try:
            sym = _to_ccxt_symbol(symbol)
            ohlcv_4h = await self._fetch_ohlcv(sym, "4h", 80)
            if not ohlcv_4h:
                return {}

            ob_data = await self.ob.analyze(sym)
            current_price = ob_data.get("mid_price", 0) if isinstance(ob_data, dict) else 0
            if current_price <= 0 and ohlcv_4h:
                current_price = ohlcv_4h[-1][4]

            vsp = self.vsp.build_profile(ohlcv_4h)
            loc = self.vsp.classify_price_location(vsp, current_price) if vsp and current_price > 0 else {}
            liq_data = await self.liq.analyze(sym, ohlcv_4h)

            poc = vsp.get("poc_price", 0)
            vah = vsp.get("vah", 0)
            val = vsp.get("val", 0)
            hvn = [h["price"] for h in vsp.get("hvn_levels", [])]
            lvn = [l["price"] for l in vsp.get("lvn_levels", [])]

            # Nearest liq cluster above and below price
            liq_clusters = liq_data.get("clusters", []) if isinstance(liq_data, dict) else []
            above_clusters = sorted([c for c in liq_clusters if c.get("price", 0) > current_price], key=lambda x: x["price"])
            below_clusters = sorted([c for c in liq_clusters if c.get("price", 0) < current_price], key=lambda x: -x["price"])

            # Naked POC = POC from a recent session that price hasn't revisited
            naked_poc = vsp.get("naked_poc") or None

            return {
                "poc": round(poc, 4),
                "vah": round(vah, 4),
                "val": round(val, 4),
                "hvn": [round(p, 4) for p in hvn],
                "lvn": [round(p, 4) for p in lvn],
                "nearest_naked_poc": round(naked_poc, 4) if naked_poc else None,
                "nearest_liq_above": round(above_clusters[0]["price"], 4) if above_clusters else None,
                "nearest_liq_below": round(below_clusters[0]["price"], 4) if below_clusters else None,
                "price_location": loc.get("location", "unknown"),
                "current_price": round(current_price, 4),
            }
        except Exception as e:
            logger.debug(f"get_key_vp_levels failed for {symbol}: {e}")
            return {}

# ══════════════════════════════════════════════════════════════════════════════
# Module-level instances
# ══════════════════════════════════════════════════════════════════════════════

def init_vp_engine(db=None) -> HyperAccuracyEngine:
    return HyperAccuracyEngine(db=db)


# Standalone instances (used by routes)
vsp_analyzer = VolumeSessionProfile()
liq_heatmap = LiquidationHeatmap()
ob_analyzer = OrderbookAnalyzer()
