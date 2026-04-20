"""
QUANT ANALYZER V2 — SYSTEM-WIDE GATEKEEPER
==========================================
100-point scoring system across 4 pillars:
  On-Chain Data      : 30 pts  (MEXC OI + funding + Coinglass liquidations)
  Order Book Intel   : 25 pts  (MEXC futures depth — reference market)
  Market Structure   : 25 pts  (existing 9-factor CoinAnalyzer, rescaled)
  Sentiment/OI/Funding: 20 pts (Fear & Greed + Long/Short ratio + CoinGecko)

Dynamic regime-aware threshold (TRENDING 65 / RANGING 80 / HIGH_VOL 85 / ACCUM 60)
Per-engine floor overrides. Anomaly tightening (+10pt per active flag).

5-vector anomaly detection:
  1. Funding rate Z-score    (>2.5σ from 30d rolling mean)
  2. Order book entropy drop (sudden liquidity withdrawal)
  3. OI netflow acceleration (second derivative spike)
  4. Regime chaos detection  (HMM-inspired: ≥4 regime flips in 6 observations)
  5. BTC correlation break   (coin decorrelating below 0.35)

Baselines stored in MongoDB `quant_baselines` — never reset.
Anomaly flags stored in MongoDB `quant_anomaly_flags` — 24h TTL.
Engines receive full anomaly report on block; may adapt and resubmit once.
"""

import asyncio
import logging
import numpy as np
import aiohttp
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from quant_analyzer_engine import CoinAnalyzer, _sym

logger = logging.getLogger(__name__)

# ── per-regime base thresholds ─────────────────────────────────────────────────
# Calibrated for real production data availability:
# Coinglass liq API unreliable (0-1 pts vs 10 theoretical), OI history builds slowly
# (2 pts vs 8), structure penalties for counter-trend signals. Max achievable
# in practice is ~30-40 pts, not the theoretical 100.

REGIME_THRESHOLDS: Dict[str, int] = {
    "TRENDING":        18,
    "RANGING":         16,
    "HIGH_VOLATILITY": 22,
    "ACCUMULATION":    16,
}

# ── per-engine RANGING overrides ────────────────────────────────────────────
ENGINE_RANGING_THRESHOLDS: Dict[str, int] = {
    "free_will_v2": 14,
}

# ── per-engine minimum floors (never go below these regardless of regime) ──────

ENGINE_QUANT_FLOORS: Dict[str, int] = {
    "elite_strategy":       14,
    "dual_engine":          16,
    "autonomous_trader_v2": 16,
    "free_will_v2":         14,
    "vwap_scalper":         18,
    "yolo_engine":          14,
    "day_trader":           16,
}

# ── constants ─────────────────────────────────────────────────────────────────

ANOMALY_TTL_HOURS     = 24
ANOMALY_TIGHTEN_PTS   = 3       # added to threshold per active contra anomaly flag
FUNDING_WINDOW        = 720     # 30d × 24 hourly samples
OB_ENTROPY_MIN_HIST   = 10
OB_ENTROPY_DROP       = 0.20    # normalized entropy drop threshold
ZSCORE_FUNDING_SIGMA  = 2.5
NETFLOW_SPIKE_MULT    = 6.0     # OI acceleration z-score multiplier
CORR_BREAK_FLOOR      = 0.35    # BTC correlation minimum
CORR_BREAK_DROP       = 0.25    # minimum drop from baseline to flag
REGIME_CHAOS_FLIPS    = 4       # flips in 6 observations = chaos

_CONFIDENCE_TABLE = [
    (90, "ULTRA HIGH"),
    (80, "HIGH"),
    (70, "MEDIUM-HIGH"),
    (65, "MEDIUM"),
    (60, "BORDERLINE"),
    (0,  "LOW"),
]

# Returned when post_mortem blindspot check blocks a trade before scoring
BLOCK_RESPONSE: Dict = {
    "approved":           False,
    "score":              0,
    "threshold_used":     0,
    "regime":             "UNKNOWN",
    "confidence_label":   "BLINDSPOT_BLOCK",
    "anomalies_detected": [],
    "adapted":            False,
    "reason":             "Blindspot block — historical loss rate too high for this condition",
    "breakdown":          {},
    "suggested_entry":    None,
    "suggested_sl":       None,
    "suggested_tp1":      None,
    "suggested_tp2":      None,
    "suggested_tp3":      None,
    "r_r":                0.0,
}

MEXC_BASE    = "https://contract.mexc.com/api/v1/contract"
FNG_URL      = "https://api.alternative.me/fng/?limit=1"
CG_BASE      = "https://api.coingecko.com/api/v3"
OKX_BASE     = "https://www.okx.com/api/v5/rubik/stat/contracts"

_CG_IDS: Dict[str, str] = {
    "BTC":  "bitcoin",        "ETH":  "ethereum",
    "SOL":  "solana",         "BNB":  "binancecoin",
    "XRP":  "ripple",         "DOGE": "dogecoin",
    "ADA":  "cardano",        "AVAX": "avalanche-2",
    "LINK": "chainlink",      "DOT":  "polkadot",
    "ARB":  "arbitrum",       "INJ":  "injective-protocol",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def _confidence_label(score: int) -> str:
    for floor, label in _CONFIDENCE_TABLE:
        if score >= floor:
            return label
    return "LOW"


def _mexc_sym(symbol: str) -> str:
    """Convert 'BTC/USDT' -> 'BTC_USDT' for MEXC futures endpoints."""
    return symbol.replace("/", "_")


async def _get(
    session: aiohttp.ClientSession,
    url: str,
    params: dict = None,
    timeout: int = 5,
) -> Optional[Dict]:
    try:
        async with session.get(
            url, params=params,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as r:
            if r.status == 200:
                return await r.json(content_type=None)
    except Exception as e:
        logger.debug(f"HTTP {url}: {e}")
    return None


# ── baseline manager ──────────────────────────────────────────────────────────

class BaselineManager:
    """
    Persistent rolling baselines per coin in MongoDB `quant_baselines`.
    Falls back to in-memory if db is None.
    Baselines grow forever — never reset.
    """

    COLLECTION = "quant_baselines"

    def __init__(self, db=None):
        self._db  = db
        self._mem: Dict[str, Dict] = {}

    async def load(self, symbol: str) -> Dict:
        if self._db is not None:
            try:
                doc = await self._db[self.COLLECTION].find_one({"_id": symbol})
                if doc:
                    self._mem[symbol] = doc
                    return doc
            except Exception as e:
                logger.debug(f"BaselineManager.load {symbol}: {e}")
        return self._mem.get(symbol, {})

    async def save(self, symbol: str, baseline: Dict):
        self._mem[symbol] = baseline
        if self._db is not None:
            try:
                doc = {**baseline, "_id": symbol}
                await self._db[self.COLLECTION].replace_one(
                    {"_id": symbol}, doc, upsert=True
                )
            except Exception as e:
                logger.debug(f"BaselineManager.save {symbol}: {e}")

    async def append(self, symbol: str, key: str, value: float, maxlen: int = 720):
        baseline = await self.load(symbol)
        arr = baseline.get(key, [])
        arr.append(float(value))
        if len(arr) > maxlen:
            arr = arr[-maxlen:]
        baseline[key] = arr
        baseline["sample_count"] = baseline.get("sample_count", 0) + 1
        baseline["updated_at"]   = datetime.now(timezone.utc).isoformat()
        await self.save(symbol, baseline)

    async def get_array(self, symbol: str, key: str) -> List[float]:
        baseline = await self.load(symbol)
        return baseline.get(key, [])


# ── anomaly flag ──────────────────────────────────────────────────────────────

@dataclass
class AnomalyFlag:
    symbol:      str
    flag_type:   str
    value:       float
    threshold:   float
    message:     str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at:  datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=ANOMALY_TTL_HOURS)
    )

    def to_dict(self) -> Dict:
        return {
            "symbol":      self.symbol,
            "type":        self.flag_type,
            "value":       round(self.value, 4),
            "threshold":   self.threshold,
            "message":     self.message,
            "detected_at": self.detected_at.isoformat(),
            "expires_at":  self.expires_at.isoformat(),
        }


class AnomalyFlagStore:
    """
    Active anomaly flags with 24h TTL.
    MongoDB `quant_anomaly_flags` if available, else in-memory.
    """

    COLLECTION = "quant_anomaly_flags"

    def __init__(self, db=None):
        self._db  = db
        self._mem: Dict[str, AnomalyFlag] = {}

    async def set(self, flag: AnomalyFlag):
        key = f"{flag.symbol}_{flag.flag_type}"
        self._mem[key] = flag
        if self._db is not None:
            try:
                doc = {**flag.to_dict(), "_id": key}
                await self._db[self.COLLECTION].replace_one({"_id": key}, doc, upsert=True)
            except Exception as e:
                logger.debug(f"AnomalyFlagStore.set: {e}")

    async def get_active(self, symbol: str) -> List[AnomalyFlag]:
        now = datetime.now(timezone.utc)
        # purge expired in-memory entries
        for key in list(self._mem):
            if self._mem[key].expires_at < now:
                del self._mem[key]
        active = [f for f in self._mem.values()
                  if f.symbol == symbol and f.expires_at > now]
        if not active and self._db is not None:
            try:
                cursor = self._db[self.COLLECTION].find({
                    "symbol":     symbol,
                    "expires_at": {"$gt": now.isoformat()},
                })
                async for doc in cursor:
                    active.append(AnomalyFlag(
                        symbol    = doc["symbol"],
                        flag_type = doc["type"],
                        value     = doc["value"],
                        threshold = doc["threshold"],
                        message   = doc["message"],
                    ))
            except Exception as e:
                logger.debug(f"AnomalyFlagStore.get_active: {e}")
        return active

    async def clear_expired(self):
        now = datetime.now(timezone.utc)
        for key in list(self._mem):
            if self._mem[key].expires_at < now:
                del self._mem[key]
        if self._db is not None:
            try:
                await self._db[self.COLLECTION].delete_many(
                    {"expires_at": {"$lt": now.isoformat()}}
                )
            except Exception as e:
                logger.debug(f"AnomalyFlagStore.clear_expired: {e}")


# ── on-chain scorer (30 pts) ──────────────────────────────────────────────────

class OnChainScorer:
    """
    OI change 24h (10pts) + Funding rate alignment (10pts) + Liq imbalance (10pts)
    Sources: MEXC contract public API + Coinglass open API
    Returns breakdown including raw funding_rate_pct and oi_current for anomaly detector.
    """

    def __init__(self, db=None):
        self._db = db

    async def score(
        self,
        symbol:    str,
        direction: str,
        session:   aiohttp.ClientSession,
    ) -> Tuple[int, Dict]:
        sym  = _mexc_sym(symbol)
        d    = direction.lower()
        pts  = 0
        breakdown: Dict[str, Any] = {}

        # ── OI current (0-15 pts) — OKX public (replaces geo-blocked MEXC) ──────
        # Uses quant_baselines oi_history for directional change scoring.
        # History is written by AnomalyDetector._update_baselines after each gate call.
        # OKX returns: [timestamp, oi_contracts, oi_usd] newest-last.
        oi_pts     = 0
        oi_pct     = None
        oi_current = None
        coin = symbol.split("/")[0].upper()
        oi_data = await _get(
            session, f"{OKX_BASE}/open-interest-volume",
            params={"ccy": coin, "period": "1H"},
        )
        if oi_data and oi_data.get("code") == "0" and oi_data.get("data"):
            rows = oi_data["data"]  # list of [ts, oi_contracts, oi_usd]
            oi_current = float(rows[-1][1]) if rows else None  # latest OI in contracts
            if self._db is not None:
                try:
                    doc = await self._db["quant_baselines"].find_one({"_id": symbol})
                    history = doc.get("oi_history", []) if doc else []
                    if len(history) >= 2 and oi_current is not None:
                        prev_oi = history[-1]   # last stored value = previous call's current
                        oi_pct = (oi_current - prev_oi) / prev_oi if prev_oi > 0 else 0
                        if d == "long":
                            oi_pts = (12 if oi_pct > 0.05 else
                                       8 if oi_pct > 0.02 else
                                       5 if oi_pct > 0    else 2)
                        else:
                            oi_pts = (12 if oi_pct < -0.05 else
                                       8 if oi_pct < -0.02 else
                                       5 if oi_pct < 0     else 2)
                    else:
                        oi_pts = 3  # history building
                except Exception:
                    oi_pts = 3
            else:
                oi_pts = 3  # no db
        pts += oi_pts
        breakdown["oi_change_pct"] = round(oi_pct * 100, 2) if oi_pct is not None else None
        breakdown["oi_current"]    = oi_current
        breakdown["oi_pts"]        = oi_pts

        # ── Funding rate (0-15 pts) — MEXC (still works) ─────────────────────
        fund_pts     = 0
        funding_rate = None
        fund_data = await _get(
            session, f"{MEXC_BASE}/funding_rate/{sym}",
        )
        if fund_data and fund_data.get("code") == 0 and fund_data.get("data"):
            funding_rate = float(fund_data["data"].get("fundingRate", 0)) * 100  # in %
            if d == "long":
                fund_pts = (15 if funding_rate < -0.01 else
                            12 if funding_rate < 0     else
                            8  if funding_rate < 0.01  else
                            5  if funding_rate < 0.03  else
                            2  if funding_rate < 0.05  else 0)
            else:
                fund_pts = (15 if funding_rate > 0.05  else
                            12 if funding_rate > 0.03  else
                            8  if funding_rate > 0.01  else
                            5  if funding_rate > 0     else
                            2  if funding_rate > -0.01 else 0)
        pts += fund_pts
        breakdown["funding_rate_pct"] = round(funding_rate, 4) if funding_rate is not None else None
        breakdown["funding_pts"]      = fund_pts

        # Liquidation scorer removed — Coinglass endpoint 404'd (geo-block).
        # 30 pts now split: OI=15, Funding=15. Cap unchanged.
        breakdown["liq_long_ratio"] = None
        breakdown["liq_pts"]        = 0

        return min(pts, 30), breakdown


# ── order book scorer (25 pts) ────────────────────────────────────────────────

class OrderBookScorer:
    """
    Bid/ask imbalance (10pts) + Wall presence (8pts) + Spread quality (7pts)
    Source: MEXC futures public depth
    Also exposes entropy() for anomaly detector.
    """

    async def score(
        self,
        symbol:    str,
        direction: str,
        session:   aiohttp.ClientSession,
    ) -> Tuple[int, Dict]:
        sym = _mexc_sym(symbol)
        d   = direction.lower()
        pts = 0
        breakdown: Dict[str, Any] = {}

        depth = await _get(
            session, f"{MEXC_BASE}/depth/{sym}",
            params={"limit": 100},
        )
        if depth is None or depth.get("code") != 0:
            breakdown["error"] = "MEXC depth unavailable"
            return 0, breakdown

        raw = depth.get("data") or {}
        # MEXC depth entries are [price, qty, count] — take first 2 elements only
        bids = np.array([[float(e[0]), float(e[1])] for e in (raw.get("bids") or [])[:50] if len(e) >= 2])
        asks = np.array([[float(e[0]), float(e[1])] for e in (raw.get("asks") or [])[:50] if len(e) >= 2])
        if bids.size == 0 or asks.size == 0:
            return 0, breakdown

        bid_vol   = np.sum(bids[:, 0] * bids[:, 1])
        ask_vol   = np.sum(asks[:, 0] * asks[:, 1])
        total     = bid_vol + ask_vol
        imbalance = (bid_vol - ask_vol) / (total + 1e-10)

        # imbalance 0-10 pts
        imb_pts = 0
        if d == "long":
            imb_pts = (10 if imbalance > 0.3  else
                        7 if imbalance > 0.1  else
                        4 if imbalance > 0    else
                        2 if imbalance > -0.1 else 0)
        else:
            imb_pts = (10 if imbalance < -0.3  else
                        7 if imbalance < -0.1  else
                        4 if imbalance < 0     else
                        2 if imbalance < 0.1   else 0)
        pts += imb_pts
        breakdown["ob_imbalance"]  = round(float(imbalance), 3)
        breakdown["imbalance_pts"] = imb_pts

        # wall detection 0-8 pts
        mid        = (bids[0, 0] + asks[0, 0]) / 2
        bid_mean_q = float(np.mean(bids[:, 1]))
        ask_mean_q = float(np.mean(asks[:, 1]))
        bid_walls  = [(p, q) for p, q in bids if q > bid_mean_q * 5 and p > mid * 0.99]
        ask_walls  = [(p, q) for p, q in asks if q > ask_mean_q * 5 and p < mid * 1.01]
        wall_pts   = 0
        if d == "long":
            wall_pts = 8 if bid_walls and not ask_walls else 4 if bid_walls else 0
        else:
            wall_pts = 8 if ask_walls and not bid_walls else 4 if ask_walls else 0
        pts += wall_pts
        breakdown["bid_walls"] = len(bid_walls)
        breakdown["ask_walls"] = len(ask_walls)
        breakdown["wall_pts"]  = wall_pts

        # spread 0-7 pts
        spread_pct = (asks[0, 0] - bids[0, 0]) / mid * 100
        spread_pts = (7 if spread_pct < 0.02  else
                      5 if spread_pct < 0.05  else
                      3 if spread_pct < 0.10  else
                      1 if spread_pct < 0.20  else 0)
        pts += spread_pts
        breakdown["spread_pct"] = round(float(spread_pct), 4)
        breakdown["spread_pts"] = spread_pts

        return min(pts, 25), breakdown

    async def entropy(
        self,
        symbol:  str,
        session: aiohttp.ClientSession,
    ) -> float:
        """Normalized Shannon entropy of bid depth. Low = concentrated / potential collapse."""
        sym   = _mexc_sym(symbol)
        depth = await _get(session, f"{MEXC_BASE}/depth/{sym}",
                           params={"limit": 100})
        if depth is None or depth.get("code") != 0:
            return 1.0
        raw  = depth.get("data") or {}
        bids = np.array([float(e[1]) for e in (raw.get("bids") or [])[:50] if len(e) >= 2])
        if bids.sum() == 0:
            return 1.0
        p = bids / bids.sum()
        p = p[p > 0]
        return float(-np.sum(p * np.log2(p)) / np.log2(len(p)))


# ── market structure scorer (25 pts) ─────────────────────────────────────────

class MarketStructureScorer:
    """
    Wraps existing CoinAnalyzer result.
    Rescales 1-10 score → 0-25 pts with direction penalty.
    """

    @staticmethod
    def score_from_analysis(
        analysis:  Optional[Dict],
        direction: str,
        btc_macro: str = "NEUTRAL",
    ) -> Tuple[int, Dict]:
        if analysis is None:
            return 0, {"error": "No analysis data"}

        raw_score  = analysis["score"]                  # 1-10
        pts        = int(round((raw_score - 1) / 9 * 25))

        tf_trends  = analysis["trend_structure"]["timeframes"]
        directions = [v["direction"] for v in tf_trends.values()]
        bull       = directions.count("BULLISH")
        bear       = directions.count("BEARISH")
        dominant   = "BULLISH" if bull > bear else ("BEARISH" if bear > bull else "NEUTRAL")

        direction_upper   = direction.upper()
        required_dominant = "BULLISH" if direction_upper == "LONG" else "BEARISH"

        # Check if trade direction aligns with BTC macro (e.g. SHORT in BEARISH macro)
        btc_macro_upper = btc_macro.upper()
        macro_aligned = (
            (direction_upper == "SHORT" and btc_macro_upper in ("BEARISH", "BEAR")) or
            (direction_upper == "LONG"  and btc_macro_upper in ("BULLISH", "BULL"))
        )

        if dominant == "NEUTRAL":
            pts = pts // 2
        elif dominant != required_dominant:
            # Soften penalty when direction aligns with BTC macro:
            # individual coin structure lags macro — use ÷2 instead of ÷4
            pts = pts // 2 if macro_aligned else pts // 4

        breakdown = {
            "quant_score_1_10":  raw_score,
            "quant_signal":      analysis["signal"],
            "dominant":          dominant,
            "trend_alignment":   analysis["trend_structure"]["alignment"],
            "atr":               analysis["volatility"]["atr"],
            "current_price":     analysis["price"],
            "trade_plan":        analysis["trade_plan"],
            "macro_aligned":     macro_aligned,
        }
        return max(0, min(pts, 25)), breakdown


# ── sentiment scorer (20 pts) ─────────────────────────────────────────────────

class SentimentScorer:
    """
    Fear & Greed index (8pts) + OKX L/S ratio (8pts) + CoinGecko 24h change (4pts)
    """

    async def score(
        self,
        symbol:    str,
        direction: str,
        session:   aiohttp.ClientSession,
    ) -> Tuple[int, Dict]:
        d    = direction.lower()
        coin = symbol.split("/")[0].upper()
        pts  = 0
        breakdown: Dict[str, Any] = {}

        # ── Fear & Greed (0-8 pts) ─────────────────────────────────────────────
        fng_pts = 0
        fng_val = None
        fng_data = await _get(session, FNG_URL, timeout=4)
        if fng_data and fng_data.get("data"):
            fng_val = int(fng_data["data"][0]["value"])
            if d == "long":
                fng_pts = (2 if fng_val >= 75 else
                           6 if fng_val >= 55 else
                           4 if fng_val >= 45 else
                           8 if fng_val >= 25 else 7)
            else:
                fng_pts = (8 if fng_val >= 75 else
                           6 if fng_val >= 55 else
                           4 if fng_val >= 45 else
                           2 if fng_val >= 25 else 1)
        pts += fng_pts
        breakdown["fear_greed"] = fng_val
        breakdown["fng_pts"]    = fng_pts

        # ── Long/Short ratio (0-8 pts) — OKX (replaces geo-blocked MEXC) ────────
        # OKX returns: [ts, long_ratio] newest-last, ratio is fraction of longs (0-1).
        ls_pts   = 0
        ls_ratio = None
        ls_coin  = symbol.split("/")[0].upper()
        ls_data = await _get(
            session, f"{OKX_BASE}/long-short-account-ratio",
            params={"ccy": ls_coin, "period": "1H"},
        )
        if ls_data and ls_data.get("code") == "0" and ls_data.get("data"):
            rows = ls_data["data"]  # [[ts, longShortRatio], ...]
            if rows:
                raw_ratio = float(rows[-1][1])  # OKX: longs/shorts ratio (e.g. 1.37)
                ls_ratio = raw_ratio / (1 + raw_ratio)  # convert to fraction 0-1
                if d == "long":
                    ls_pts = (8 if ls_ratio < 0.35 else
                              6 if ls_ratio < 0.45 else
                              4 if ls_ratio < 0.55 else
                              2 if ls_ratio < 0.65 else 0)
                else:
                    ls_pts = (8 if ls_ratio > 0.65 else
                              6 if ls_ratio > 0.55 else
                              4 if ls_ratio > 0.45 else
                              2 if ls_ratio > 0.35 else 0)
        pts += ls_pts
        breakdown["long_ratio"] = round(ls_ratio, 3) if ls_ratio is not None else None
        breakdown["ls_pts"]     = ls_pts

        # ── CoinGecko 24h change (0-4 pts) ────────────────────────────────────
        cg_pts    = 0
        change_24 = None
        cg_id     = _CG_IDS.get(coin)
        if cg_id:
            cg = await _get(
                session, f"{CG_BASE}/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd",
                        "include_24hr_change": "true"},
                timeout=4,
            )
            if cg and cg_id in cg:
                change_24 = cg[cg_id].get("usd_24h_change", 0)
                if d == "long":
                    cg_pts = (2 if change_24 > 5  else
                              4 if change_24 > 1  else
                              3 if change_24 > -1 else
                              2 if change_24 > -5 else 1)
                else:
                    cg_pts = (2 if change_24 < -5  else
                              4 if change_24 < -1  else
                              3 if change_24 < 1   else
                              2 if change_24 < 5   else 1)
        pts += cg_pts
        breakdown["cg_24h_change"] = round(change_24, 2) if change_24 is not None else None
        breakdown["cg_pts"]        = cg_pts

        return min(pts, 20), breakdown


# ── regime detector ───────────────────────────────────────────────────────────

class RegimeDetector:
    """
    HMM-inspired regime classification from CoinAnalyzer analysis dict.
    States: TRENDING | RANGING | HIGH_VOLATILITY | ACCUMULATION

    Features used:
      bb_width_percentile (from volatility)
      bb_width regime string (coiling / expanding / normal)
      volume confirmation (from volume analysis)
      timeframe trend alignment
    """

    @staticmethod
    def detect_from_analysis(analysis: Optional[Dict]) -> str:
        if analysis is None:
            return "TRENDING"

        vol        = analysis["volatility"]
        bb_pct     = vol.get("bb_width_percentile", 50)
        vol_regime = vol.get("regime", "")

        tf_trends  = analysis["trend_structure"]["timeframes"]
        directions = [v["direction"] for v in tf_trends.values()]
        all_same   = len(set(directions)) == 1 and directions[0] != "NEUTRAL"

        vol_confirm = analysis["volume"]["confirmation"]

        if "expanding" in vol_regime and bb_pct > 70:
            return "HIGH_VOLATILITY"
        if "coiling" in vol_regime and "weak" in vol_confirm and not all_same:
            return "ACCUMULATION"
        if all_same:
            return "TRENDING"
        return "RANGING"


# ── anomaly detector ──────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    5 parallel anomaly detectors.
    Baselines updated as fire-and-forget tasks after each check.
    Anomaly flags written to AnomalyFlagStore with 24h TTL.
    """

    def __init__(self, baseline_mgr: BaselineManager, flag_store: AnomalyFlagStore):
        self._baseline  = baseline_mgr
        self._flags     = flag_store
        self._ob_scorer = OrderBookScorer()

    async def detect_and_flag(
        self,
        symbol:          str,
        session:         aiohttp.ClientSession,
        regime:          str,
        funding_rate:    Optional[float],
        oi_current:      Optional[float],
    ) -> List[AnomalyFlag]:
        results = await asyncio.gather(
            self._check_funding_zscore(symbol, funding_rate),
            self._check_ob_entropy(symbol, session),
            self._check_netflow_momentum(symbol, oi_current),
            self._check_regime_chaos(symbol, regime),
            self._check_btc_correlation(symbol),
            return_exceptions=True,
        )

        flags: List[AnomalyFlag] = []
        for r in results:
            if isinstance(r, AnomalyFlag):
                await self._flags.set(r)
                flags.append(r)

        asyncio.create_task(
            self._update_baselines(symbol, regime, funding_rate, oi_current)
        )
        return flags

    # ── detectors ─────────────────────────────────────────────────────────────

    async def _check_funding_zscore(
        self, symbol: str, current_funding: Optional[float]
    ) -> Optional[AnomalyFlag]:
        if current_funding is None:
            return None
        history = await self._baseline.get_array(symbol, "funding_history")
        if len(history) < 30:
            return None
        arr  = np.array(history[-FUNDING_WINDOW:])
        mean = float(np.mean(arr))
        std  = float(np.std(arr))
        if std < 1e-8:
            return None
        z = (current_funding - mean) / std
        if abs(z) > ZSCORE_FUNDING_SIGMA:
            return AnomalyFlag(
                symbol    = symbol,
                flag_type = "funding_zscore",
                value     = round(z, 3),
                threshold = ZSCORE_FUNDING_SIGMA,
                message   = (
                    f"Funding {current_funding:.4f}% is {abs(z):.1f}σ from "
                    f"30d mean {mean:.4f}% — abnormal leverage positioning"
                ),
            )
        return None

    async def _check_ob_entropy(
        self, symbol: str, session: aiohttp.ClientSession
    ) -> Optional[AnomalyFlag]:
        current_entropy = await self._ob_scorer.entropy(symbol, session)
        history         = await self._baseline.get_array(symbol, "ob_entropy_history")
        if len(history) < OB_ENTROPY_MIN_HIST:
            asyncio.create_task(
                self._baseline.append(symbol, "ob_entropy_history", current_entropy, maxlen=100)
            )
            return None
        baseline_entropy = float(np.mean(history[-20:]))
        drop = baseline_entropy - current_entropy
        if drop > OB_ENTROPY_DROP and current_entropy < 0.5:
            return AnomalyFlag(
                symbol    = symbol,
                flag_type = "ob_entropy_collapse",
                value     = round(current_entropy, 3),
                threshold = OB_ENTROPY_DROP,
                message   = (
                    f"Order book entropy {current_entropy:.2f} dropped {drop:.2f} "
                    f"from baseline {baseline_entropy:.2f} — liquidity withdrawal detected"
                ),
            )
        asyncio.create_task(
            self._baseline.append(symbol, "ob_entropy_history", current_entropy, maxlen=100)
        )
        return None

    async def _check_netflow_momentum(
        self, symbol: str, oi_current: Optional[float]
    ) -> Optional[AnomalyFlag]:
        if oi_current is None:
            return None
        history = await self._baseline.get_array(symbol, "oi_history")
        if len(history) < 5:
            return None
        arr          = np.array(history[-20:] + [oi_current], dtype=float)
        first_deriv  = np.diff(arr)
        second_deriv = np.diff(first_deriv)
        if len(second_deriv) < 3:
            return None
        mean_accel = float(np.mean(np.abs(second_deriv[:-1])))
        if mean_accel < 1e-6:
            return None
        z = abs(float(second_deriv[-1])) / (mean_accel + 1e-10)
        if z > NETFLOW_SPIKE_MULT:
            return AnomalyFlag(
                symbol    = symbol,
                flag_type = "netflow_momentum_spike",
                value     = round(z, 2),
                threshold = NETFLOW_SPIKE_MULT,
                message   = (
                    f"OI acceleration {z:.1f}× baseline — "
                    f"abnormal flow momentum, potential squeeze or stop hunt forming"
                ),
            )
        return None

    async def _check_regime_chaos(
        self, symbol: str, regime: str
    ) -> Optional[AnomalyFlag]:
        history = await self._baseline.get_array(symbol, "regime_history")
        if len(history) < 6:
            return None
        recent      = history[-6:]
        transitions = sum(1 for i in range(1, len(recent)) if recent[i] != recent[i - 1])
        if transitions >= REGIME_CHAOS_FLIPS:
            return AnomalyFlag(
                symbol    = symbol,
                flag_type = "regime_chaos",
                value     = float(transitions),
                threshold = float(REGIME_CHAOS_FLIPS),
                message   = (
                    f"{transitions} regime transitions in last 6 observations — "
                    f"market in chaos state, signal reliability severely degraded"
                ),
            )
        return None

    async def _check_btc_correlation(self, symbol: str) -> Optional[AnomalyFlag]:
        coin = symbol.split("/")[0].upper()
        if coin == "BTC":
            return None
        history = await self._baseline.get_array(symbol, "btc_corr_history")
        if len(history) < 10:
            return None
        arr           = np.array(history)
        baseline_corr = float(np.mean(arr[:-5])) if len(arr) > 5 else float(np.mean(arr))
        recent_corr   = float(np.mean(arr[-5:]))
        drop          = baseline_corr - recent_corr
        if recent_corr < CORR_BREAK_FLOOR and drop > CORR_BREAK_DROP:
            return AnomalyFlag(
                symbol    = symbol,
                flag_type = "btc_correlation_break",
                value     = round(recent_corr, 3),
                threshold = CORR_BREAK_FLOOR,
                message   = (
                    f"{coin} BTC correlation {recent_corr:.2f} "
                    f"(baseline {baseline_corr:.2f}, Δ{drop:.2f}) — "
                    f"coin-specific risk elevated, macro hedge unreliable"
                ),
            )
        return None

    async def _update_baselines(
        self,
        symbol:       str,
        regime:       str,
        funding:      Optional[float],
        oi_current:   Optional[float],
    ):
        try:
            if funding is not None:
                await self._baseline.append(symbol, "funding_history", funding, maxlen=FUNDING_WINDOW)
            if oi_current is not None:
                await self._baseline.append(symbol, "oi_history", oi_current, maxlen=500)
            # Store regime as integer index for numpy ops
            regime_idx = {"TRENDING": 0, "RANGING": 1, "HIGH_VOLATILITY": 2, "ACCUMULATION": 3}
            await self._baseline.append(
                symbol, "regime_history",
                float(regime_idx.get(regime, 0)), maxlen=50
            )
        except Exception as e:
            logger.debug(f"baseline update {symbol}: {e}")


# ── threshold engine ──────────────────────────────────────────────────────────

class ThresholdEngine:
    """
    Effective threshold = max(regime_base + anomaly_tightening, engine_floor)
    """

    @staticmethod
    def compute(regime: str, engine_type: str, anomaly_count: int) -> int:
        base           = REGIME_THRESHOLDS.get(regime, 65)
        floor          = ENGINE_QUANT_FLOORS.get(engine_type, 65)
        # Regime-specific floor override: some engines have a lower floor in RANGING
        # to allow mean-reversion signals through (paired with reduced position sizing)
        if regime == "RANGING" and engine_type in ENGINE_RANGING_THRESHOLDS:
            floor = ENGINE_RANGING_THRESHOLDS[engine_type]
        regime_adj     = min(base + ANOMALY_TIGHTEN_PTS * anomaly_count, 95)
        return max(regime_adj, floor)


# ── suggested level builder ───────────────────────────────────────────────────

def _build_suggested_levels(
    analysis:    Optional[Dict],
    direction:   str,
    signal_data: Dict,
) -> Dict[str, Optional[float]]:
    """
    Builds entry/sl/tp levels from quant analysis (preferred) or falls back
    to signal_data values already supplied by the engine.
    """
    if analysis is not None:
        plan = analysis.get("trade_plan", {})
        if plan.get("side") not in (None, "NEUTRAL"):
            entry = plan.get("entry") or signal_data.get("entry_price")
            sl    = plan.get("stop")  or signal_data.get("stop_loss")
            tp1   = plan.get("tp1")   or signal_data.get("take_profit")
            tp2   = plan.get("tp2")
            tp3   = plan.get("tp3")
            rr    = plan.get("rr1", 0.0)
            return {"suggested_entry": entry, "suggested_sl": sl,
                    "suggested_tp1": tp1, "suggested_tp2": tp2,
                    "suggested_tp3": tp3, "r_r": rr}

    entry = signal_data.get("entry_price")
    sl    = signal_data.get("stop_loss")
    tp1   = signal_data.get("take_profit")
    rr    = 0.0
    if entry and sl and tp1 and entry != sl:
        risk   = abs(entry - sl)
        reward = abs(tp1 - entry)
        rr     = round(reward / risk, 2) if risk > 0 else 0.0
    return {"suggested_entry": entry, "suggested_sl": sl,
            "suggested_tp1": tp1, "suggested_tp2": None,
            "suggested_tp3": None, "r_r": rr}


# ── gatekeeper v2 ─────────────────────────────────────────────────────────────

class QuantGatekeeperV2:
    """
    System-wide gatekeeper.

    Engines call:
        result = await gatekeeper.check(symbol, direction, engine_type, signal_data)

    On block, result["quant_report"] contains the full anomaly report.
    Engine adapts signal_data and resubmits with adapted=True (allowed once via
    submit_signal_gated in EngineManager).

    Injection (in server.py after init):
        engine_manager.quant_gatekeeper = get_quant_gatekeeper_v2(db)
    """

    def __init__(self, db=None, telegram_fn=None):
        self._db           = db
        self._telegram     = telegram_fn          # async fn(msg: str) or None
        self._baseline_mgr = BaselineManager(db)
        self._flag_store   = AnomalyFlagStore(db)
        self._anomaly_det  = AnomalyDetector(self._baseline_mgr, self._flag_store)
        self._ob_scorer    = OrderBookScorer()
        self._ms_scorer    = MarketStructureScorer()
        self._coin_analyzer = CoinAnalyzer()
        self._loop_started = False

    def start_background_tasks(self):
        if not self._loop_started:
            asyncio.create_task(self._cleanup_loop())
            self._loop_started = True

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(3600)
            await self._flag_store.clear_expired()

    # ── main gate ──────────────────────────────────────────────────────────────

    async def check(
        self,
        symbol:      str,
        direction:   str,
        engine_type: str,
        signal_data: Dict,
        adapted:     bool = False,
    ) -> Dict:
        """
        Full gate evaluation.

        Returns approval dict matching spec:
        {
            "approved": bool,
            "score": int,
            "regime": str,
            "threshold_used": int,
            "suggested_entry": float,
            "suggested_sl": float,
            "suggested_tp1": float,
            "suggested_tp2": float,
            "suggested_tp3": float,
            "r_r": float,
            "confidence_label": str,
            "anomalies_detected": list,
            "adapted": bool,
        }
        """
        loop = asyncio.get_running_loop()

        # ── Step 1: MEXC analysis (single blocking call, executor) ────────────
        try:
            analysis = await loop.run_in_executor(
                None, self._coin_analyzer.analyze, symbol
            )
        except Exception as e:
            logger.warning(f"[QuantV2] CoinAnalyzer failed {symbol}: {e} — fail open")
            analysis = None

        # ── Step 2: Derive regime + market structure score ────────────────────
        regime = RegimeDetector.detect_from_analysis(analysis)
        _btc_bias = signal_data.get("btc_bias", signal_data.get("btc_macro", "NEUTRAL"))
        ms_pts, ms_bd = MarketStructureScorer.score_from_analysis(analysis, direction, btc_macro=_btc_bias)

        # ── Blindspot pre-check — before scoring ──────────────────────────────
        from post_mortem_engine import get_post_mortem
        _bs = get_post_mortem().check_blindspot_history(
            engine_type, regime, _btc_bias, signal_data
        )
        if _bs.get("blindspot_block"):
            return BLOCK_RESPONSE
        _bs_threshold_add = _bs.get("quant_threshold_add", 0) if _bs.get("blindspot_warning") else 0

        # ── Step 3: Parallel external API calls ───────────────────────────────
        on_chain_scorer  = OnChainScorer(self._db)
        sentiment_scorer = SentimentScorer()

        async with aiohttp.ClientSession() as session:
            (
                on_chain_result,
                ob_result,
                sentiment_result,
            ) = await asyncio.gather(
                on_chain_scorer.score(symbol, direction, session),
                self._ob_scorer.score(symbol, direction, session),
                sentiment_scorer.score(symbol, direction, session),
                return_exceptions=True,
            )

            # ── Step 4: Anomaly detection (needs on_chain data) ───────────────
            funding_rate = None
            oi_current   = None
            if not isinstance(on_chain_result, Exception):
                on_chain_pts, on_chain_bd = on_chain_result
                funding_rate = on_chain_bd.get("funding_rate_pct")
                oi_current   = on_chain_bd.get("oi_current")
            else:
                on_chain_pts, on_chain_bd = 0, {"error": str(on_chain_result)}

            active_flags = await self._flag_store.get_active(symbol)
            new_flags    = await self._anomaly_det.detect_and_flag(
                symbol, session, regime, funding_rate, oi_current
            )

            # Merge + deduplicate by flag_type
            all_flag_types = {f.flag_type for f in active_flags}
            for f in new_flags:
                if f.flag_type not in all_flag_types:
                    active_flags.append(f)

        # ── Step 5: Unpack remaining scorer results ───────────────────────────
        if isinstance(ob_result, Exception):
            ob_pts, ob_bd = 0, {"error": str(ob_result)}
        else:
            ob_pts, ob_bd = ob_result

        if isinstance(sentiment_result, Exception):
            sent_pts, sent_bd = 0, {"error": str(sentiment_result)}
        else:
            sent_pts, sent_bd = sentiment_result

        # ── Step 6: Total score ────────────────────────────────────────────────
        total_score = on_chain_pts + ob_pts + ms_pts + sent_pts   # 0-100

        # ── Step 7: Dynamic threshold ──────────────────────────────────────────
        # Only count anomaly flags that OPPOSE the trade direction.
        # A funding_zscore with negative value (shorts paying less / longs paying more)
        # is directionally confirming for SHORTs and should not tighten the threshold.
        d_upper = direction.upper()
        contra_flags = 0
        for f in active_flags:
            flag_aligns = False
            if f.flag_type == "funding_zscore":
                # negative funding → bearish sentiment → aligns with SHORT
                # positive funding → bullish sentiment → aligns with LONG
                flag_aligns = (d_upper == "SHORT" and f.value < 0) or \
                              (d_upper == "LONG"  and f.value > 0)
            # All other flag types (ob_entropy_collapse, regime_chaos, etc.) always count
            if not flag_aligns:
                contra_flags += 1
        threshold = ThresholdEngine.compute(regime, engine_type, contra_flags)
        threshold += _bs_threshold_add  # blindspot warning penalty

        # ── Step 8: Proportional decision — position_multiplier scales with score ─
        if total_score >= threshold:
            # Full approval — multiplier scales with score quality above threshold
            position_multiplier = round(min(1.0, total_score / (threshold * 1.2)), 2)
            approved = True
            marginal = False
        elif total_score >= threshold * 0.75:
            # Marginal zone — approved at reduced size (50% × score ratio)
            position_multiplier = round(0.5 * (total_score / threshold), 2)
            approved = True
            marginal = True
        else:
            # Below 75% of threshold — hard block
            position_multiplier = 0.0
            approved = False
            marginal = False

        # ── Step 9: Build anomaly report ───────────────────────────────────────
        anomaly_dicts = [f.to_dict() for f in active_flags]

        # ── Step 10: Suggested levels ──────────────────────────────────────────
        levels = _build_suggested_levels(analysis, direction, signal_data)

        # ── Step 11: Fire Telegram + frontend alert on new anomaly flags ───────
        if new_flags:
            asyncio.create_task(
                self._send_anomaly_alerts(symbol, new_flags, total_score, regime)
            )

        if approved and marginal:
            reason = (
                f"Score {total_score}/100 MARGINAL (≥{int(threshold*0.75)}, <{threshold}) ({regime})"
                f" | size×{position_multiplier}"
                + (f" | {len(active_flags)} anomaly flag(s)" if active_flags else "")
            )
        elif approved:
            reason = (
                f"Score {total_score}/100 >= threshold {threshold} ({regime})"
                f" | size×{position_multiplier}"
                + (f" | {len(active_flags)} anomaly flag(s)" if active_flags else "")
            )
        else:
            reason = (
                f"Score {total_score}/100 < {int(threshold*0.75)} ({regime}) — hard block"
                + (f" | {len(active_flags)} anomaly flag(s)" if active_flags else "")
            )

        # ── Cache last result for pre_check() fast path ────────────────────────
        try:
            bl = await self._baseline_mgr.load(symbol)
            bl["last_score"]  = total_score
            bl["last_regime"] = regime
            await self._baseline_mgr.save(symbol, bl)
        except Exception:
            pass

        return {
            "approved":           approved,
            "position_multiplier": position_multiplier,
            "marginal":           marginal if approved else False,
            "score":              total_score,
            "regime":             regime,
            "threshold_used":     threshold,
            "suggested_entry":    levels["suggested_entry"],
            "suggested_sl":       levels["suggested_sl"],
            "suggested_tp1":      levels["suggested_tp1"],
            "suggested_tp2":      levels["suggested_tp2"],
            "suggested_tp3":      levels["suggested_tp3"],
            "r_r":                levels["r_r"],
            "confidence_label":   _confidence_label(total_score),
            "anomalies_detected": anomaly_dicts,
            "adapted":            adapted,
            "reason":             reason,
            # ── full score breakdown (for engine adaptation + frontend) ─────
            "breakdown": {
                "on_chain":    {"pts": on_chain_pts, "max": 30, **on_chain_bd},
                "order_book":  {"pts": ob_pts,       "max": 25, **ob_bd},
                "market_str":  {"pts": ms_pts,       "max": 25, **ms_bd},
                "sentiment":   {"pts": sent_pts,     "max": 20, **sent_bd},
            },
        }

    # ── lightweight pre-check (MongoDB only, no external API calls) ───────────

    async def pre_check(self, symbol: str, direction: str, engine_type: str) -> Dict:
        """
        Cheap pre-check used by EngineManager.get_dynamic_leverage().
        Reads only:
          - active anomaly flags (quant_anomaly_flags collection)
          - last cached score + regime stored by check() in baselines
        No external API calls (MEXC / CoinGecko).
        Returns: {score, regime, anomaly_count, anomaly_types}
        """
        active_flags  = await self._flag_store.get_active(symbol)
        anomaly_count = len(active_flags)
        anomaly_types = [f.flag_type for f in active_flags]

        score  = 50        # conservative default until first full check
        regime = "RANGING"  # conservative default
        try:
            bl = await self._baseline_mgr.load(symbol)
            score  = bl.get("last_score",  50)
            regime = bl.get("last_regime", "RANGING")
        except Exception:
            pass

        return {
            "score":         score,
            "regime":        regime,
            "anomaly_count": anomaly_count,
            "anomaly_types": anomaly_types,
        }

    # ── telegram alert ─────────────────────────────────────────────────────────

    async def _send_anomaly_alerts(
        self,
        symbol:     str,
        flags:      List[AnomalyFlag],
        score:      int,
        regime:     str,
    ):
        if self._telegram is None:
            return
        for flag in flags:
            msg = (
                f"⚠️ QUANT ANOMALY — {symbol}\n"
                f"Type: {flag.flag_type}\n"
                f"Value: {flag.value} (threshold {flag.threshold})\n"
                f"{flag.message}\n"
                f"Score: {score}/100 | Regime: {regime}\n"
                f"Expires: {flag.expires_at.strftime('%H:%M UTC')}"
            )
            try:
                await self._telegram(msg)
            except Exception as e:
                logger.debug(f"anomaly telegram alert: {e}")

    # ── cache / status ─────────────────────────────────────────────────────────

    async def get_status(self) -> Dict:
        return {
            "regime_thresholds":  REGIME_THRESHOLDS,
            "engine_floors":      ENGINE_QUANT_FLOORS,
            "anomaly_tighten_pt": ANOMALY_TIGHTEN_PTS,
            "anomaly_ttl_hours":  ANOMALY_TTL_HOURS,
        }


# ── singleton ─────────────────────────────────────────────────────────────────

_gatekeeper_v2: Optional[QuantGatekeeperV2] = None


def get_quant_gatekeeper_v2(db=None, telegram_fn=None) -> QuantGatekeeperV2:
    global _gatekeeper_v2
    if _gatekeeper_v2 is None:
        _gatekeeper_v2 = QuantGatekeeperV2(db=db, telegram_fn=telegram_fn)
    return _gatekeeper_v2
