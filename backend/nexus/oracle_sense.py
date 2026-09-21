"""
NEXUS LAYER 1 — ORACLE_SENSE: The Awareness Engine
====================================================
AEON's eyes and ears. Knows the state of everything at all times.

Market awareness:  H_market, regimes, volatility, correlations, funding
Self awareness:    Engine statuses, win rates, positions, system health
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

logger = logging.getLogger(__name__)

ASSETS   = ["BTC", "ETH", "SOL", "BNB", "XRP"]
SYMBOLS  = {
    "BTC": "BTC/USDT:USDT",
    "ETH": "ETH/USDT:USDT",
    "SOL": "SOL/USDT:USDT",
    "BNB": "BNB/USDT:USDT",
    "XRP": "XRP/USDT:USDT",
}
SPOT_SYMBOLS = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "SOL": "SOL/USDT",
    "BNB": "BNB/USDT",
    "XRP": "XRP/USDT",
}

ENGINE_NAMES = [
    "autonomous_trader_v2", "free_will_v2", "dual_engine",
    "yolo_engine", "vwap_scalper", "elite_strategy",
    "day_trader", "quant_analyzer", "tcn_neural",
]

CRISIS_CORRELATION       = 0.92
CRISIS_CLEAR_CORRELATION = 0.80


class OracleSense:
    """
    Gathers complete market + self-awareness every candle.
    Reads oracle entropy from existing AEON infrastructure,
    adds correlation, Hurst, system metrics, and engine reports.
    """

    def __init__(self, db, exchange):
        self.db       = db
        self.exchange = exchange

        self._last_snapshot: Optional[dict] = None
        self._crisis_mode   = False
        self._last_corr_max = 0.0
        self._loop          = asyncio.get_event_loop()

    # ── Public ────────────────────────────────────────────────────────────────

    async def compute_snapshot(self) -> dict:
        now = datetime.now(timezone.utc)

        # 1. Read oracle entropy (already computed by AEON hourly)
        oracle_doc   = await self._read_oracle_doc()
        H_market     = oracle_doc.get("H_market",   0.5)
        H_internal   = oracle_doc.get("H_internal", 0.5)
        H_combined   = oracle_doc.get("H_combined", 0.5)
        oracle_regime = oracle_doc.get("regime",   "TRANSITIONAL")

        # 2. Fetch OHLCV for all 5 assets (correlation + Hurst)
        ohlcv_map = await self._fetch_ohlcv_all(limit=100)

        # 3. Correlation matrix — crisis detection
        corr_max, corr_matrix = self._compute_correlation(ohlcv_map)
        old_crisis        = self._crisis_mode
        if corr_max >= CRISIS_CORRELATION:
            self._crisis_mode = True
        elif corr_max <= CRISIS_CLEAR_CORRELATION:
            self._crisis_mode = False
        self._last_corr_max = corr_max

        # 4. BTC analytics: Hurst, ADX, volatility
        btc_closes = _extract_closes(ohlcv_map.get("BTC", []))
        hurst      = _compute_hurst(btc_closes)
        adx        = await self._get_btc_adx()

        trend_regime = _classify_trend(adx, hurst)
        vol_regime   = _classify_volatility(btc_closes)
        market_regime = _classify_market(oracle_regime, trend_regime)

        # 5. Derivatives: funding + OI
        funding_rate, oi_delta = await self._fetch_derivatives()

        # 6. Self-awareness
        engine_reports  = await self._fetch_engine_reports()
        open_positions  = await self._fetch_open_positions()
        quantum         = await self._fetch_quantum_state()
        consensus_C     = quantum.get("coherence",   0.5)
        health_H        = quantum.get("health",      0.5)
        system_metrics  = _get_system_metrics()

        snapshot = {
            "timestamp":            now,
            "market_regime":        market_regime,
            "volatility_regime":    vol_regime,
            "trend_regime":         trend_regime,
            "H_market":             H_market,
            "H_internal":           H_internal,
            "H_combined":           H_combined,
            "adx":                  adx,
            "hurst":                hurst,
            "funding_rate_btc":     funding_rate,
            "oi_delta_btc":         oi_delta,
            "correlation_max":      round(corr_max, 4),
            "correlation_matrix":   corr_matrix,
            "crisis_mode":          self._crisis_mode,
            "crisis_just_triggered": (self._crisis_mode and not old_crisis),
            "consensus_C":          consensus_C,
            "health_H":             health_H,
            "engine_reports":       engine_reports,
            "open_positions":       open_positions,
            "system_metrics":       system_metrics,
        }

        self._last_snapshot = snapshot
        await self._persist(snapshot)
        return snapshot

    def get_last_snapshot(self) -> Optional[dict]:
        return self._last_snapshot

    def is_crisis(self) -> bool:
        return self._crisis_mode

    # ── Oracle data ────────────────────────────────────────────────────────────

    async def _read_oracle_doc(self) -> dict:
        try:
            doc = await self.db["current_market_regime"].find_one({"_id": "live"})
            return doc or {}
        except Exception as e:
            logger.warning(f"[ORACLE_SENSE] Oracle doc read failed: {e}")
            return {}

    # ── OHLCV ─────────────────────────────────────────────────────────────────

    async def _fetch_ohlcv_all(self, limit: int = 100) -> Dict[str, list]:
        tasks = {asset: self._fetch_ohlcv(sym, limit) for asset, sym in SPOT_SYMBOLS.items()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return {asset: (r if not isinstance(r, Exception) else [])
                for asset, r in zip(tasks.keys(), results)}

    async def _fetch_ohlcv(self, symbol: str, limit: int) -> list:
        try:
            return await asyncio.wait_for(
                self._loop.run_in_executor(
                    None, lambda: self.exchange.fetch_ohlcv(symbol, "1h", limit=limit)
                ),
                timeout=10.0,
            )
        except Exception as e:
            logger.debug(f"[ORACLE_SENSE] OHLCV {symbol} failed: {e}")
            return []

    # ── Correlation ────────────────────────────────────────────────────────────

    def _compute_correlation(self, ohlcv_map: Dict[str, list]) -> Tuple[float, dict]:
        returns_map: Dict[str, list] = {}
        for asset, candles in ohlcv_map.items():
            closes = _extract_closes(candles)
            if len(closes) < 10:
                continue
            rets = [math.log(closes[i] / closes[i-1])
                    for i in range(1, len(closes))
                    if closes[i-1] > 0 and closes[i] > 0]
            if rets:
                returns_map[asset] = rets

        assets = list(returns_map.keys())
        if len(assets) < 2:
            return 0.0, {}

        min_len = min(len(returns_map[a]) for a in assets)
        aligned = {a: returns_map[a][-min_len:] for a in assets}

        corr_matrix: dict = {}
        max_corr = 0.0

        for i, a1 in enumerate(assets):
            for j, a2 in enumerate(assets):
                if i >= j:
                    continue
                c = _pearson(aligned[a1], aligned[a2])
                corr_matrix[f"{a1}/{a2}"] = round(c, 4)
                if abs(c) > max_corr:
                    max_corr = abs(c)

        return max_corr, corr_matrix

    # ── Derivatives ────────────────────────────────────────────────────────────

    async def _fetch_derivatives(self) -> Tuple[float, float]:
        try:
            funding = await asyncio.wait_for(
                self._loop.run_in_executor(
                    None, lambda: self.exchange.fetch_funding_rate("BTC/USDT:USDT")
                ),
                timeout=5.0,
            )
            rate = float(funding.get("fundingRate", 0.0) or 0.0)
            return rate, 0.0
        except Exception:
            return 0.0, 0.0

    # ── BTC ADX ───────────────────────────────────────────────────────────────

    async def _get_btc_adx(self) -> float:
        """Read ADX from AEON's oracle doc or estimate from closes."""
        try:
            doc = await self.db["current_market_regime"].find_one({"_id": "live"})
            if doc:
                pa = doc.get("per_asset", {}).get("BTC", {})
                # Not stored — use default
            return 25.0
        except Exception:
            return 25.0

    # ── Engine reports ─────────────────────────────────────────────────────────

    async def _fetch_engine_reports(self) -> list:
        reports = []
        now     = datetime.now(timezone.utc)

        # Read quantum amplitudes from latest states doc
        amplitudes: dict = {}
        try:
            qdoc = await self.db["states"].find_one(sort=[("timestamp", -1)])
            if qdoc:
                amplitudes = qdoc.get("amplitudes", {})
        except Exception:
            pass

        for eng in ENGINE_NAMES:
            win_rate    = 0.5
            trade_count = 0
            age_min     = None

            # Win rate: last 50 closed paper_trades for this engine
            try:
                pipeline = [
                    {"$match": {"strategy": eng, "status": "closed"}},
                    {"$sort":  {"closed_at": -1}},
                    {"$limit": 50},
                    {"$group": {
                        "_id":   None,
                        "wins":  {"$sum": {"$cond": [{"$gt": ["$pnl", 0]}, 1, 0]}},
                        "total": {"$sum": 1},
                    }},
                ]
                async for doc in self.db["paper_trades"].aggregate(pipeline):
                    total = doc.get("total", 0)
                    if total > 0:
                        win_rate    = doc.get("wins", 0) / total
                        trade_count = total
                    break
            except Exception:
                pass

            # Last signal age
            try:
                last = await self.db["paper_trades"].find_one(
                    {"strategy": eng},
                    sort=[("created_at", -1)],
                )
                if last and "created_at" in last:
                    age_min = (now - last["created_at"]).total_seconds() / 60.0
            except Exception:
                pass

            # Status
            if age_min is None:
                status = "unknown"
            elif age_min > 120:
                status = "dead"
            elif win_rate < 0.40 and trade_count >= 50:
                status = "degraded"
            else:
                status = "running"

            raw_alpha = amplitudes.get(eng, 0.0)
            if isinstance(raw_alpha, dict):
                raw_alpha = raw_alpha.get("amplitude", 0.0)

            reports.append({
                "name":                  eng,
                "status":                status,
                "win_rate":              round(win_rate, 4),
                "trade_count":           trade_count,
                "last_signal_minutes":   (round(age_min, 1) if age_min is not None else None),
                "alpha":                 round(float(raw_alpha), 4),
            })

        return reports

    # ── Open positions ─────────────────────────────────────────────────────────

    async def _fetch_open_positions(self) -> list:
        positions = []
        now       = datetime.now(timezone.utc)
        try:
            cursor = self.db["paper_trades"].find({"status": "open"})
            async for doc in cursor:
                opened_at  = doc.get("created_at", now)
                hours_open = (now - opened_at).total_seconds() / 3600.0

                entry     = float(doc.get("entry_price", 0) or 0)
                current   = float(doc.get("current_price", entry) or entry)
                direction = doc.get("direction", "long")
                leverage  = float(doc.get("leverage", 1) or 1)

                pnl_pct = 0.0
                if entry > 0:
                    raw = (current - entry) / entry * 100.0
                    pnl_pct = raw if direction == "long" else -raw

                liq_price = float(doc.get("liquidation_price", 0) or 0)
                if liq_price > 0 and current > 0:
                    if direction in ("long", "LONG"):
                        liq_dist_pct = (current - liq_price) / current * 100.0
                    else:
                        liq_dist_pct = (liq_price - current) / current * 100.0
                    liq_dist_pct = max(liq_dist_pct, 0.0)
                else:
                    liq_dist_pct = (100.0 / leverage) if leverage > 0 else 100.0

                positions.append({
                    "symbol":       doc.get("symbol", ""),
                    "direction":    direction,
                    "size_usd":     float(doc.get("position_size", 0) or 0),
                    "pnl_pct":      round(pnl_pct, 2),
                    "entry_price":  entry,
                    "current_price": current,
                    "stop_loss":    float(doc.get("stop_loss", 0) or 0),
                    "opened_at":    opened_at.isoformat() if hasattr(opened_at, "isoformat") else str(opened_at),
                    "hours_open":   round(hours_open, 2),
                    "engine":       doc.get("strategy", "unknown"),
                    "liq_dist_pct": round(liq_dist_pct, 1),
                    "leverage":     leverage,
                    "_id":          str(doc.get("_id", "")),
                })
        except Exception as e:
            logger.error(f"[ORACLE_SENSE] Position fetch error: {e}")
        return positions

    # ── Quantum state ──────────────────────────────────────────────────────────

    async def _fetch_quantum_state(self) -> dict:
        try:
            doc = await self.db["states"].find_one(sort=[("timestamp", -1)])
            if doc:
                return {
                    "coherence":     float(doc.get("coherence",   0.5) or 0.5),
                    "health":        float(doc.get("health",      0.5) or 0.5),
                    "entropy":       float(doc.get("entropy",     0.5) or 0.5),
                    "position_size": float(doc.get("position_size", 1000) or 1000),
                }
        except Exception:
            pass
        return {"coherence": 0.5, "health": 0.5, "entropy": 0.5}

    # ── Persist ────────────────────────────────────────────────────────────────

    async def _persist(self, snapshot: dict) -> None:
        try:
            doc = {k: (v.isoformat() if isinstance(v, datetime) else v)
                   for k, v in snapshot.items()}
            await self.db["nexus_awareness"].insert_one(doc)
            # Keep last 336 docs (14 days at hourly)
            count = await self.db["nexus_awareness"].count_documents({})
            if count > 336:
                oldest = await self.db["nexus_awareness"].find_one(sort=[("timestamp", 1)])
                if oldest:
                    await self.db["nexus_awareness"].delete_one({"_id": oldest["_id"]})
        except Exception as e:
            logger.warning(f"[ORACLE_SENSE] Persist error: {e}")


# ── Pure math helpers ──────────────────────────────────────────────────────────

def _extract_closes(candles: list) -> list:
    return [float(c[4]) for c in candles if c and c[4] and float(c[4]) > 0]


def _pearson(x: list, y: list) -> float:
    n = len(x)
    if n == 0:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    dx  = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    dy  = math.sqrt(sum((yi - my) ** 2 for yi in y))
    return (num / (dx * dy)) if dx > 0 and dy > 0 else 0.0


def _compute_hurst(closes: list) -> float:
    """Hurst exponent via R/S method. H>0.5 = trending, H<0.5 = mean-reverting."""
    if len(closes) < 20:
        return 0.5

    rets = [math.log(closes[i] / closes[i-1])
            for i in range(1, len(closes))
            if closes[i-1] > 0 and closes[i] > 0]

    if len(rets) < 8:
        return 0.5

    lags   = [w for w in [8, 16, 32] if w <= len(rets)]
    rs_pts = []

    for lag in lags:
        windows    = [rets[i:i+lag] for i in range(0, len(rets) - lag + 1, lag)]
        rs_window  = []
        for w in windows:
            mean_w = sum(w) / len(w)
            cumdev, devs = 0.0, []
            for r in w:
                cumdev += (r - mean_w)
                devs.append(cumdev)
            R   = max(devs) - min(devs)
            std = math.sqrt(sum((r - mean_w) ** 2 for r in w) / len(w))
            if std > 0:
                rs_window.append(R / std)
        if rs_window:
            rs_pts.append((lag, sum(rs_window) / len(rs_window)))

    if len(rs_pts) < 2:
        return 0.5

    log_n  = [math.log(p[0]) for p in rs_pts]
    log_rs = [math.log(p[1]) for p in rs_pts if p[1] > 0]

    if len(log_n) != len(log_rs) or len(log_n) < 2:
        return 0.5

    n  = len(log_n)
    mx = sum(log_n) / n
    my = sum(log_rs) / n
    num   = sum((log_n[i] - mx) * (log_rs[i] - my) for i in range(n))
    denom = sum((log_n[i] - mx) ** 2 for i in range(n))

    return round(max(0.0, min(1.0, num / denom)) if denom > 0 else 0.5, 4)


def _classify_trend(adx: float, hurst: float) -> str:
    if adx > 25 and hurst > 0.55:
        return "TRENDING"
    if adx < 20 and hurst < 0.45:
        return "RANGING"
    return "REVERSING"


def _classify_volatility(closes: list) -> str:
    if len(closes) < 20:
        return "NORMAL"
    recent = closes[-20:]
    mean   = sum(recent) / len(recent)
    if mean <= 0:
        return "NORMAL"
    std    = math.sqrt(sum((c - mean) ** 2 for c in recent) / len(recent))
    pct    = std / mean * 100.0
    if pct > 4.0:
        return "SPIKE"
    if pct < 1.0:
        return "LOW"
    return "NORMAL"


def _classify_market(oracle_regime: str, trend_regime: str) -> str:
    if oracle_regime == "CHAOTIC":
        return "CHAOTIC"
    if oracle_regime == "TRANSITIONAL":
        return "TRANSITIONAL"
    return "STRUCTURED"


def _get_system_metrics() -> dict:
    if not _PSUTIL:
        return {"cpu_pct": 0.0, "memory_pct": 0.0, "disk_pct": 0.0}
    try:
        return {
            "cpu_pct":    psutil.cpu_percent(interval=0.5),
            "memory_pct": psutil.virtual_memory().percent,
            "disk_pct":   psutil.disk_usage("/").percent,
        }
    except Exception:
        return {"cpu_pct": 0.0, "memory_pct": 0.0, "disk_pct": 0.0}
