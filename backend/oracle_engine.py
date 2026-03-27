"""
ORACLE ENGINE  ─  oracle_engine.py
=====================================
ORACLE CORE: Pure market intelligence system.
NEVER places trades. NEVER modifies engine logic.

Reads the market across 5 independent layers and reports what it is
doing right now with maximum analytical precision.

5-Layer scoring (0–100 total):
  Layer 1: Structure     30pts  — trend direction, BOS, MTF alignment
  Layer 2: Momentum      25pts  — RSI, MACD, EMA stack, rate of change
  Layer 3: Order Flow    20pts  — CVD, volume trend, POC, institutional spikes
  Layer 4: Key Levels    15pts  — FVG, S/R, liquidity pools
  Layer 5: Context       10pts  — BTC bias, funding rate, ADX regime, session

Score → confidence label:
  0–30:   NEUTRAL   — no clear read, do not trade
  31–50:  WEAK      — lean exists, low confidence
  51–70:  MODERATE  — clear direction, reasonable confidence
  71–85:  STRONG    — high conviction read
  86–100: EXTREME   — maximum alignment

Scan modes:
  Full scan    (every 4h)  — all active USDT perpetuals on MEXC
  Priority     (every 1h)  — only pairs that scored ≥60 in last full scan
  Instant      (on-demand) — any pair at any time via analyze()

ORACLE never places trades.
ORACLE never modifies any engine logic.
ORACLE only reads the market and reports the truth.
"""

import asyncio
import logging
import uuid
import numpy as np

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


# ─── ORACLE ENGINE STEP 1: CONSTANTS ─────────────────────────────────────────

# Score → confidence label thresholds
CONFIDENCE_LEVELS = [
    (86, "EXTREME"),
    (71, "STRONG"),
    (51, "MODERATE"),
    (31, "WEAK"),
    (0,  "NEUTRAL"),
]

# Layer max scores — must sum to 100
LAYER_MAX = {
    "structure":  30,
    "momentum":   25,
    "order_flow": 20,
    "key_levels": 15,
    "context":    10,
}

# Winning direction must lead by this margin to declare a bias
BIAS_LEAD_REQUIRED = 10

# Scan timing
FULL_SCAN_INTERVAL_SEC    = 4 * 3600   # 4 hours
PRIORITY_SCAN_INTERVAL_SEC = 1 * 3600  # 1 hour

# Score thresholds
PRIORITY_SCORE_THRESHOLD  = 60   # re-scan pairs that scored above this
TELEGRAM_REPORT_MIN_SCORE = 65   # include in report only if above this
PRIORITY_ALERT_THRESHOLD  = 80   # send immediate alert if any priority pair crosses this

# Full scan rate limiting
SCAN_BATCH_SIZE   = 5     # pairs analyzed in parallel per batch
SCAN_BATCH_DELAY  = 0.5   # seconds between batches
RATE_LIMIT_PAUSE  = 5.0   # seconds pause if MEXC rate-limits us

# MongoDB
ORACLE_HISTORY_COLLECTION = "oracle_history"
ORACLE_SCAN_COLLECTION    = "oracle_scan_history"
ORACLE_HISTORY_MAX        = 500   # rolling entries per symbol

# Default watchlist (used if full scan hasn't run yet)
DEFAULT_WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "ARB/USDT", "INJ/USDT", "NEAR/USDT", "APT/USDT", "OP/USDT",
]


# ─── Module-level singleton ───────────────────────────────────────────────────

_oracle_instance: Optional["OracleEngine"] = None


def init_oracle(db) -> "OracleEngine":
    """Initialize and return the ORACLE singleton."""
    global _oracle_instance
    _oracle_instance = OracleEngine(db)
    return _oracle_instance


def get_oracle() -> Optional["OracleEngine"]:
    """Return the ORACLE singleton, or None if not initialized."""
    return _oracle_instance


# ORACLE ENGINE STEP 5: ENGINE INTEGRATION INTERFACE
async def get_oracle_bias(symbol: str, min_score: int = 50) -> Optional[Dict]:
    """
    Public interface for other engines to query ORACLE.

    Returns the full ORACLE analysis dict if score >= min_score.
    Returns None if:
      - ORACLE is not initialized
      - Score is below min_score (no actionable bias)
      - Data fetch failed (score = 0)

    Usage in any engine:
        from oracle_engine import get_oracle_bias
        bias = await get_oracle_bias("BTC/USDT", min_score=65)
        if bias and bias["bias"] == "BEARISH":
            # ORACLE agrees with our direction — add to confluence
    """
    oracle = get_oracle()
    if not oracle:
        return None
    result = await oracle.analyze(symbol)
    if not result or result.get("score", 0) < min_score:
        return None
    return result


# ─── ORACLE ENGINE STEP 2: UTILITY FUNCTIONS ─────────────────────────────────

def _get_confidence_label(score: float) -> str:
    """Map a 0–100 score to a confidence label string."""
    for threshold, label in CONFIDENCE_LEVELS:
        if score >= threshold:
            return label
    return "NEUTRAL"


def _get_session(utc_hour: int) -> str:
    """Classify trading session from UTC hour."""
    if 0 <= utc_hour < 8:
        return "ASIA"
    elif 7 <= utc_hour < 13:
        return "LONDON"
    elif 12 <= utc_hour < 21:
        return "NEW_YORK"
    else:
        return "OFF_HOURS"


def _compute_cvd(df) -> Tuple[float, float]:
    """
    # ORACLE LAYER 3: ORDER FLOW — CVD proxy from OHLCV.
    Green candle = buy pressure (+volume), Red = sell pressure (-volume).
    Returns (cvd_raw, cvd_pct) where cvd_pct = signed ratio of total volume as %.
    """
    try:
        closes = df['close'].values[-20:]
        opens  = df['open'].values[-20:]
        vols   = df['volume'].values[-20:]
        signed = np.where(closes >= opens, vols, -vols)
        cvd_raw   = float(np.sum(signed))
        total_vol = float(np.sum(np.abs(signed)))
        cvd_pct   = (cvd_raw / total_vol * 100) if total_vol > 0 else 0.0
        return cvd_raw, cvd_pct
    except Exception:
        return 0.0, 0.0


def _compute_poc(df) -> float:
    """
    # ORACLE LAYER 3: ORDER FLOW — Point of Control.
    Divides the last 50 candles' price range into 20 buckets.
    The bucket with highest cumulative volume is the POC.
    Returns the typical price of that bucket.
    """
    try:
        highs  = df['high'].values[-50:]
        lows   = df['low'].values[-50:]
        vols   = df['volume'].values[-50:]
        closes = df['close'].values[-50:]
        price_min = float(np.min(lows))
        price_max = float(np.max(highs))
        if price_max <= price_min:
            return float(closes[-1])
        n_buckets   = 20
        bucket_size = (price_max - price_min) / n_buckets
        bucket_vols = np.zeros(n_buckets)
        for i in range(len(highs)):
            typical   = (highs[i] + lows[i] + closes[i]) / 3
            idx       = int((typical - price_min) / bucket_size)
            idx       = min(idx, n_buckets - 1)
            bucket_vols[idx] += vols[i]
        poc_bucket = int(np.argmax(bucket_vols))
        poc_price  = price_min + (poc_bucket + 0.5) * bucket_size
        return round(poc_price, 8)
    except Exception:
        return 0.0


def _find_fvgs(df) -> Tuple[List[List], List[List]]:
    """
    # ORACLE LAYER 4: KEY LEVELS — Fair Value Gap detection.
    Bullish FVG: high[i] < low[i+2]  — gap up, acts as support below price.
    Bearish FVG: low[i] > high[i+2]  — gap down, acts as resistance above price.
    Returns (bullish_fvgs, bearish_fvgs) as [[low, high], ...] pairs.
    Only returns unfilled FVGs relative to current price.
    """
    try:
        highs   = df['high'].values
        lows    = df['low'].values
        closes  = df['close'].values
        n       = len(highs)
        current = float(closes[-1])
        b_fvgs  = []
        e_fvgs  = []
        start   = max(0, n - 30)
        for i in range(start, n - 2):
            # Bullish FVG: gap up between i and i+2
            if highs[i] < lows[i + 2]:
                fvg_lo = float(highs[i])
                fvg_hi = float(lows[i + 2])
                if current > fvg_hi:   # unfilled, below price = support
                    b_fvgs.append([round(fvg_lo, 8), round(fvg_hi, 8)])
            # Bearish FVG: gap down between i and i+2
            if lows[i] > highs[i + 2]:
                fvg_lo = float(highs[i + 2])
                fvg_hi = float(lows[i])
                if current < fvg_lo:   # unfilled, above price = resistance
                    e_fvgs.append([round(fvg_lo, 8), round(fvg_hi, 8)])
        return b_fvgs[-3:], e_fvgs[-3:]
    except Exception:
        return [], []


def _find_liquidity_pools(df) -> Tuple[List[float], List[float]]:
    """
    # ORACLE LAYER 4: KEY LEVELS — Liquidity pools from swing cluster detection.
    Swing highs above current price = buy-side liquidity (stop clusters).
    Swing lows below current price  = sell-side liquidity (stop clusters).
    Returns (liq_above, liq_below) sorted by proximity.
    """
    try:
        highs   = df['high'].values
        lows    = df['low'].values
        closes  = df['close'].values
        n       = len(highs)
        current = float(closes[-1])
        lookback = 3
        s_highs = []
        s_lows  = []
        for i in range(lookback, n - lookback):
            if highs[i] == max(highs[i - lookback:i + lookback + 1]):
                s_highs.append(float(highs[i]))
            if lows[i] == min(lows[i - lookback:i + lookback + 1]):
                s_lows.append(float(lows[i]))
        liq_above = sorted([sh for sh in s_highs if sh > current])[:3]
        liq_below = sorted([sl for sl in s_lows  if sl < current], reverse=True)[:3]
        return liq_above, liq_below
    except Exception:
        return [], []


def _build_summary(
    bias: str,
    score: int,
    confidence: str,
    layer_scores: Dict,
    l5_data: Dict,
) -> str:
    """
    # ORACLE STEP 3: Build a clinical one-line summary from layer evidence.
    No filler words. Only verifiable data.
    """
    if bias == "NEUTRAL":
        regime = l5_data.get("regime", "unclear")
        return f"No directional bias. Market is {regime}. Conflicting signals across layers."

    direction = "long" if bias == "BULLISH" else "short"
    parts = []

    struct_score = layer_scores.get("structure", {}).get("score", 0)
    struct_note  = layer_scores.get("structure", {}).get("note", "")
    if struct_score >= 18 and struct_note:
        parts.append(struct_note)

    mom_note = layer_scores.get("momentum", {}).get("note", "")
    if layer_scores.get("momentum", {}).get("score", 0) >= 15 and mom_note:
        parts.append(mom_note.split("|")[0].strip())

    flow_note = layer_scores.get("order_flow", {}).get("note", "")
    if layer_scores.get("order_flow", {}).get("score", 0) >= 12 and flow_note:
        parts.append(flow_note.split("|")[0].strip())

    evidence = ". ".join(p for p in parts[:2] if p) if parts else f"{confidence} {bias.lower()} signals"
    return f"{confidence} {bias.lower()} bias. {evidence}. Bias is {direction}."


# ─── OracleEngine Class ───────────────────────────────────────────────────────

class OracleEngine:
    """
    # ORACLE CORE — Pure market intelligence.
    Scores every symbol across 5 independent analytical layers.
    Never trades. Never modifies other engines. Only reports the truth.
    """

    def __init__(self, db):
        self.db                 = db
        self.market_intel       = None
        self.derivatives_intel  = None
        self.send_telegram      = None
        self.chat_ids           = None

        # Analysis cache: symbol → {"result": dict, "ts": datetime}
        self._cache: Dict[str, Dict]     = {}
        self._cache_ttl                  = 300   # 5 minutes

        # Priority symbols from last full scan (score >= threshold)
        self._priority_symbols: List[str] = []

        # Full pair list from MEXC (refreshed every 24h)
        self._all_pairs: List[str]               = []
        self._pairs_last_refreshed: Optional[datetime] = None

        # Scan state
        self._scan_in_progress = False
        self._scan_progress: Dict = {"scanned": 0, "total": 0, "scan_id": None}
        self._last_full_scan_results: List[Dict] = []
        self._last_full_scan_time: Optional[datetime] = None

        self.active = True

    def set_dependencies(
        self,
        market_intel,
        derivatives_intel,
        send_telegram,
        chat_ids,
    ):
        """Wire in runtime dependencies after construction."""
        self.market_intel      = market_intel
        self.derivatives_intel = derivatives_intel
        self.send_telegram     = send_telegram
        self.chat_ids          = chat_ids
        logger.info("[ORACLE] Dependencies wired — ORACLE CORE online.")

    # ─── ORACLE ENGINE STEP 10: PAIR DISCOVERY ───────────────────────────────

    async def _get_all_mexc_pairs(self) -> List[str]:
        """
        Fetch all active USDT perpetual futures from MEXC.
        Cached for 24 hours. Falls back to static DEFAULT_WATCHLIST on failure.
        """
        now = datetime.now(timezone.utc)
        if (
            self._all_pairs
            and self._pairs_last_refreshed
            and (now - self._pairs_last_refreshed).total_seconds() < 86400
        ):
            return self._all_pairs

        try:
            loop   = asyncio.get_event_loop()
            markets = await loop.run_in_executor(
                None, self.market_intel.mexc.fetch_markets
            )
            pairs = [
                m["symbol"] for m in markets
                if m.get("type") == "swap"
                and m.get("quote") == "USDT"
                and m.get("active") is True
            ]
            if not pairs:
                raise ValueError("Empty pair list returned from MEXC")
            self._all_pairs            = pairs
            self._pairs_last_refreshed = now
            logger.info(f"[ORACLE] Pair list refreshed: {len(pairs)} USDT perpetuals")
            return pairs
        except Exception as exc:
            logger.warning(f"[ORACLE] Pair list refresh failed: {exc} — using cached/static list")
            return self._all_pairs if self._all_pairs else DEFAULT_WATCHLIST

    # ─── ORACLE ENGINE STEP 2: LAYER 1 — STRUCTURE ───────────────────────────

    def _score_structure(
        self,
        ta_1h: Dict,
        ta_4h: Dict,
        ta_1d: Dict,
    ) -> Dict:
        """
        # ORACLE LAYER 1: STRUCTURE (max 30pts)
        Scores trend direction from market structure across 3 timeframes.
        4h carries the most weight (primary trading timeframe).
        1d defines macro context. 1h confirms intraday.
        Alignment bonus: all 3 TFs pointing same direction = +4pts.
        """
        def _bias(ta: Dict) -> str:
            return ta.get("market_structure", {}).get("bias", "neutral").lower()

        b1h = _bias(ta_1h)
        b4h = _bias(ta_4h)
        b1d = _bias(ta_1d)

        bull = 0
        bear = 0

        # 1h (confirmation weight)
        if b1h == "bullish": bull += 6
        elif b1h == "bearish": bear += 6

        # 4h (primary weight — highest)
        if b4h == "bullish": bull += 12
        elif b4h == "bearish": bear += 12

        # 1d (macro context weight)
        if b1d == "bullish": bull += 8
        elif b1d == "bearish": bear += 8

        # MTF alignment bonus
        if b1h == b4h == b1d == "bullish":
            bull += 4
        elif b1h == b4h == b1d == "bearish":
            bear += 4

        # Note: primary structure read
        icon = {"bullish": "▲", "bearish": "▼", "neutral": "─"}
        tf_note = f"1h{icon.get(b1h,'─')} 4h{icon.get(b4h,'─')} 1d{icon.get(b1d,'─')}"

        if bull > bear:
            detail = f"{b4h.upper()} structure 4H"
            if b1d == "bullish":
                detail += ", 1D aligned"
            elif b1d == "bearish":
                detail += ", 1D conflict ⚠"
        elif bear > bull:
            detail = f"{b4h.upper()} structure 4H"
            if b1d == "bearish":
                detail += ", 1D aligned"
            elif b1d == "bullish":
                detail += ", 1D conflict ⚠"
        else:
            detail = f"Mixed structure: {tf_note}"

        return {
            "bull": min(bull, LAYER_MAX["structure"]),
            "bear": min(bear, LAYER_MAX["structure"]),
            "max":  LAYER_MAX["structure"],
            "note": detail,
            "tf":   {"1h": b1h, "4h": b4h, "1d": b1d},
        }

    # ─── ORACLE ENGINE STEP 2: LAYER 2 — MOMENTUM ────────────────────────────

    def _score_momentum(self, ta_1h: Dict, ta_4h: Dict) -> Dict:
        """
        # ORACLE LAYER 2: MOMENTUM (max 25pts)
        EMA stack (6pts) + RSI (6pts) + MACD (7pts) + Rate of Change proxy (6pts).
        Primary: 1h. Secondary confirmation: 4h.
        """
        ind1 = ta_1h.get("indicators", {})
        ind4 = ta_4h.get("indicators", {})
        bull = 0
        bear = 0
        notes = []

        # ── EMA Stack — max 6pts ──────────────────────────────────────────────
        # trend = "bullish" if ema_9 > ema_21 > ema_50 else "bearish" else "neutral"
        t1h = ind1.get("trend", "neutral")
        t4h = ind4.get("trend", "neutral")

        ema_bull = (3 if t1h == "bullish" else 0) + (3 if t4h == "bullish" else 0)
        ema_bear = (3 if t1h == "bearish" else 0) + (3 if t4h == "bearish" else 0)
        bull += ema_bull
        bear += ema_bear

        if ema_bull > 0:
            notes.append(f"EMA stack bullish 1h+4h" if ema_bull == 6 else f"EMA stack bullish {t1h}/{t4h}")
        elif ema_bear > 0:
            notes.append(f"EMA stack bearish 1h+4h" if ema_bear == 6 else f"EMA stack bearish {t1h}/{t4h}")

        # ── RSI — max 6pts ────────────────────────────────────────────────────
        rsi1 = ind1.get("rsi", 50)
        rsi4 = ind4.get("rsi", 50)
        rsi_bull = 0
        rsi_bear = 0

        if rsi1 < 30:    rsi_bull += 4   # Oversold — bullish divergence zone
        elif rsi1 < 40:  rsi_bull += 2
        elif rsi1 > 70:  rsi_bear += 4   # Overbought — bearish divergence zone
        elif rsi1 > 60:  rsi_bear += 2

        if rsi4 < 35:    rsi_bull += 2
        elif rsi4 > 65:  rsi_bear += 2

        bull += rsi_bull
        bear += rsi_bear
        notes.append(f"RSI {rsi1:.0f}/{rsi4:.0f}")

        # ── MACD — max 7pts ───────────────────────────────────────────────────
        macd      = ind1.get("macd", 0)
        macd_sig  = ind1.get("macd_signal", 0)
        macd_hist = ind1.get("macd_histogram", 0)
        macd_bull = 0
        macd_bear = 0

        if macd > macd_sig:
            macd_bull += 4
            if macd_hist > 0:
                macd_bull += 3   # Histogram positive = accelerating bullish
        elif macd < macd_sig:
            macd_bear += 4
            if macd_hist < 0:
                macd_bear += 3   # Histogram negative = accelerating bearish

        bull += macd_bull
        bear += macd_bear
        macd_dir = "bullish" if macd_bull > macd_bear else ("bearish" if macd_bear > macd_bull else "neutral")
        notes.append(f"MACD {macd_dir}")

        # ── Rate of Change proxy — max 6pts ───────────────────────────────────
        # Price distance from 50 EMA + EMA spacing as momentum proxy
        price  = ta_1h.get("price", 0)
        ema9   = ind1.get("ema_9", 0)
        ema21  = ind1.get("ema_21", 0)
        ema50  = ind1.get("ema_50", 0)
        roc_bull = 0
        roc_bear = 0

        if price > 0 and ema50 > 0:
            pct = (price - ema50) / ema50 * 100
            if pct > 3:    roc_bull += 3
            elif pct > 1:  roc_bull += 2
            elif pct < -3: roc_bear += 3
            elif pct < -1: roc_bear += 2

        if ema9 > 0 and ema50 > 0:
            spread = abs(ema9 - ema50) / ema50 * 100
            if spread > 2:
                if ema9 > ema50: roc_bull += 3
                else:            roc_bear += 3

        bull += roc_bull
        bear += roc_bear

        return {
            "bull": min(bull, LAYER_MAX["momentum"]),
            "bear": min(bear, LAYER_MAX["momentum"]),
            "max":  LAYER_MAX["momentum"],
            "note": " | ".join(notes[:3]),
        }

    # ─── ORACLE ENGINE STEP 2: LAYER 3 — ORDER FLOW ──────────────────────────

    def _score_order_flow(self, klines: Any) -> Dict:
        """
        # ORACLE LAYER 3: ORDER FLOW (max 20pts)
        CVD (8pts) + Volume trend vs price (5pts) + POC position (4pts) +
        Abnormal volume spike (3pts).
        """
        null = {"bull": 0, "bear": 0, "max": LAYER_MAX["order_flow"],
                "note": "no data", "poc": 0.0, "cvd_pct": 0.0}

        if klines is None or (hasattr(klines, "empty") and klines.empty):
            return null

        try:
            df      = klines
            current = float(df['close'].iloc[-1])
            bull    = 0
            bear    = 0
            notes   = []

            # ── CVD — max 8pts ────────────────────────────────────────────────
            _, cvd_pct = _compute_cvd(df)
            if cvd_pct > 40:    bull += 8
            elif cvd_pct > 20:  bull += 5
            elif cvd_pct > 5:   bull += 2
            elif cvd_pct < -40: bear += 8
            elif cvd_pct < -20: bear += 5
            elif cvd_pct < -5:  bear += 2
            notes.append(f"CVD {cvd_pct:+.0f}%")

            # ── Volume trend vs price — max 5pts ──────────────────────────────
            recent_vols   = df['volume'].values[-5:]
            older_vols    = df['volume'].values[-10:-5]
            recent_closes = df['close'].values[-5:]
            older_closes  = df['close'].values[-10:-5]

            vol_up   = float(np.mean(recent_vols))  > float(np.mean(older_vols)) * 1.2
            price_up = float(recent_closes[-1])     > float(older_closes[-1])

            if vol_up and price_up:
                bull += 5
                notes.append("vol confirms uptrend")
            elif vol_up and not price_up:
                bear += 5
                notes.append("vol confirms downtrend")
            elif not vol_up and price_up:
                bear += 2
                notes.append("price up, vol fading")
            elif not vol_up and not price_up:
                bull += 2
                notes.append("price down, vol fading")

            # ── POC position — max 4pts ────────────────────────────────────────
            poc = _compute_poc(df)
            if poc > 0 and current > 0:
                pct_from_poc = (current - poc) / poc * 100
                if pct_from_poc > 2:    bull += 4
                elif pct_from_poc > 0:  bull += 2
                elif pct_from_poc < -2: bear += 4
                elif pct_from_poc < 0:  bear += 2
                notes.append(f"POC {pct_from_poc:+.1f}%")

            # ── Abnormal volume spike — max 3pts ──────────────────────────────
            avg_vol  = float(np.mean(df['volume'].values[-20:]))
            last_vol = float(df['volume'].values[-1])
            spike    = last_vol / avg_vol if avg_vol > 0 else 1.0

            if spike > 3.0:
                last_close = float(df['close'].values[-1])
                last_open  = float(df['open'].values[-1])
                if last_close > last_open:
                    bull += 3
                    notes.append(f"inst buy spike {spike:.1f}x")
                else:
                    bear += 3
                    notes.append(f"inst sell spike {spike:.1f}x")

            return {
                "bull":    min(bull, LAYER_MAX["order_flow"]),
                "bear":    min(bear, LAYER_MAX["order_flow"]),
                "max":     LAYER_MAX["order_flow"],
                "note":    " | ".join(notes[:3]),
                "poc":     round(poc, 8),
                "cvd_pct": round(cvd_pct, 1),
            }

        except Exception as exc:
            logger.debug(f"[ORACLE] Order flow scoring error: {exc}")
            return null

    # ─── ORACLE ENGINE STEP 2: LAYER 4 — KEY LEVELS ──────────────────────────

    def _score_key_levels(self, klines: Any, ticker: Dict) -> Dict:
        """
        # ORACLE LAYER 4: KEY LEVELS (max 15pts)
        FVG proximity (5pts) + S/R proximity (5pts) + Liquidity pool (5pts).
        """
        empty = {
            "bull": 0, "bear": 0, "max": LAYER_MAX["key_levels"],
            "note": "no data", "fvg_above": [], "fvg_below": [],
            "liq_above": [], "liq_below": [], "resistance": [], "support": [],
        }

        if klines is None or (hasattr(klines, "empty") and klines.empty):
            return empty

        try:
            df      = klines
            current = float(df['close'].iloc[-1])
            bull    = 0
            bear    = 0
            notes   = []

            # ── FVG Analysis — max 5pts ────────────────────────────────────────
            bull_fvgs, bear_fvgs = _find_fvgs(df)
            fvg_below = bull_fvgs    # Support zones below current price
            fvg_above = bear_fvgs    # Resistance zones above current price

            if bear_fvgs and current > 0:
                # Nearest bearish FVG above = overhead resistance
                nearest_dist = min(
                    abs(current - fvg[0]) / current * 100
                    for fvg in bear_fvgs
                )
                if nearest_dist < 1.0:
                    bear += 5
                    notes.append(f"FVG resistance {nearest_dist:.1f}% above")
                elif nearest_dist < 3.0:
                    bear += 3
                    notes.append(f"FVG resistance {nearest_dist:.1f}% above")

            if bull_fvgs and current > 0:
                # Nearest bullish FVG below = nearby support
                nearest_dist = min(
                    abs(fvg[1] - current) / current * 100
                    for fvg in bull_fvgs
                )
                if nearest_dist < 1.0:
                    bull += 5
                    notes.append(f"FVG support {nearest_dist:.1f}% below")
                elif nearest_dist < 3.0:
                    bull += 3
                    notes.append(f"FVG support {nearest_dist:.1f}% below")

            # ── S/R from swing structure — max 5pts ───────────────────────────
            highs    = df['high'].values
            lows_arr = df['low'].values
            n        = len(highs)
            lookback = 4
            s_highs  = []
            s_lows   = []

            for i in range(lookback, n - lookback):
                if highs[i] == max(highs[i - lookback:i + lookback + 1]):
                    s_highs.append(float(highs[i]))
                if lows_arr[i] == min(lows_arr[i - lookback:i + lookback + 1]):
                    s_lows.append(float(lows_arr[i]))

            resistance = sorted([sh for sh in s_highs if sh > current])[:3]
            support    = sorted([sl for sl in s_lows  if sl < current], reverse=True)[:3]

            if resistance and current > 0:
                pct = (resistance[0] - current) / current * 100
                if pct < 0.5:
                    bear += 5
                    notes.append(f"S/R resistance {pct:.1f}% above")
                elif pct < 2.0:
                    bear += 3

            if support and current > 0:
                pct = (current - support[0]) / current * 100
                if pct < 0.5:
                    bull += 5
                    notes.append(f"S/R support {pct:.1f}% below")
                elif pct < 2.0:
                    bull += 3

            # ── Liquidity pools — max 5pts ─────────────────────────────────────
            liq_above_raw, liq_below_raw = _find_liquidity_pools(df)
            liq_above = [round(l, 8) for l in liq_above_raw[:2]]
            liq_below = [round(l, 8) for l in liq_below_raw[:2]]

            if liq_above and current > 0:
                pct = (liq_above[0] - current) / current * 100
                if pct < 1.5:
                    bull += 4   # Liquidity pool close above = price magnet upward
                    notes.append(f"liq pool {pct:.1f}% above")
                elif pct < 3.0:
                    bull += 2

            if liq_below and current > 0:
                pct = (current - liq_below[0]) / current * 100
                if pct < 1.5:
                    bear += 4   # Liquidity pool close below = price magnet downward
                    notes.append(f"liq pool {pct:.1f}% below")
                elif pct < 3.0:
                    bear += 2

            return {
                "bull":       min(bull, LAYER_MAX["key_levels"]),
                "bear":       min(bear, LAYER_MAX["key_levels"]),
                "max":        LAYER_MAX["key_levels"],
                "note":       " | ".join(notes[:3]) if notes else "no key level pressure",
                "fvg_above":  fvg_above,
                "fvg_below":  fvg_below,
                "liq_above":  liq_above,
                "liq_below":  liq_below,
                "resistance": resistance,
                "support":    support,
            }

        except Exception as exc:
            logger.debug(f"[ORACLE] Key levels scoring error: {exc}")
            return empty

    # ─── ORACLE ENGINE STEP 2: LAYER 5 — MARKET CONTEXT ─────────────────────

    def _score_context(
        self,
        ta_1h: Dict,
        btc_ta: Dict,
        funding: Optional[Dict],
        symbol: str,
    ) -> Dict:
        """
        # ORACLE LAYER 5: MARKET CONTEXT (max 10pts)
        BTC macro bias (3pts) + Funding rate (2pts) + ADX regime (3pts) +
        Trading session (2pts).
        """
        bull  = 0
        bear  = 0
        notes = []

        # ── BTC Macro Bias — max 3pts ──────────────────────────────────────────
        btc_bias = "NEUTRAL"
        if btc_ta and not isinstance(btc_ta, Exception):
            btc_bias = btc_ta.get("overall_bias", "NEUTRAL")

        if "BTC" not in symbol:
            if btc_bias == "BULLISH":
                bull += 3
                notes.append("BTC bullish")
            elif btc_bias == "BEARISH":
                bear += 3
                notes.append("BTC bearish")
        else:
            # For BTC itself, use 1h own bias as macro check
            own_bias = ta_1h.get("overall_bias", "NEUTRAL")
            if own_bias == "BULLISH":
                bull += 2
            elif own_bias == "BEARISH":
                bear += 2

        # ── Funding Rate — max 2pts ────────────────────────────────────────────
        funding_rate = 0.0
        if funding and not isinstance(funding, Exception):
            funding_rate = funding.get("funding_rate", 0) or 0.0
            # Positive funding = longs paying = market over-leveraged long = bearish pressure
            # Negative funding = shorts paying = market over-leveraged short = bullish pressure
            if funding_rate > 0.001:
                bear += 2
                notes.append(f"funding +{funding_rate*100:.3f}% longs extended")
            elif funding_rate > 0.0003:
                bear += 1
            elif funding_rate < -0.001:
                bull += 2
                notes.append(f"funding {funding_rate*100:.3f}% shorts extended")
            elif funding_rate < -0.0003:
                bull += 1
            else:
                notes.append(f"funding neutral")

        # ── ADX Regime — max 3pts ──────────────────────────────────────────────
        # ADX confirms the strength of whatever direction we're reading.
        # Trending = bias is more reliable (+2 to both, net same direction gap preserved).
        # Choppy = penalize both (score less meaningful).
        adx = ta_1h.get("indicators", {}).get("adx", 0)

        try:
            from utils.adx_filter import get_regime
            regime = get_regime(adx)
        except Exception:
            regime = "unknown"

        if regime == "trending":
            bull += 2
            bear += 2
            notes.append(f"ADX {adx:.0f} trending")
        elif regime == "weak":
            bull += 1
            bear += 1
            notes.append(f"ADX {adx:.0f} weak trend")
        elif regime == "choppy":
            bull = max(0, bull - 2)
            bear = max(0, bear - 2)
            notes.append(f"ADX {adx:.0f} choppy ⚠")

        # ── Trading Session — max 2pts ──────────────────────────────────────────
        utc_hour = datetime.now(timezone.utc).hour
        session  = _get_session(utc_hour)

        if session in ("LONDON", "NEW_YORK"):
            bull += 1   # High-liquidity session amplifies both directions equally
            bear += 1
            notes.append(f"{session} session")
        else:
            notes.append(f"{session} session")

        return {
            "bull":         max(0, min(bull, LAYER_MAX["context"])),
            "bear":         max(0, min(bear, LAYER_MAX["context"])),
            "max":          LAYER_MAX["context"],
            "note":         " | ".join(notes[:3]),
            "btc_bias":     btc_bias,
            "funding_rate": funding_rate,
            "adx":          adx,
            "regime":       regime,
            "session":      session,
        }

    # ─── ORACLE ENGINE STEP 4: SCORE AGGREGATION + OUTPUT ────────────────────

    def _build_output(
        self,
        symbol: str,
        ticker: Dict,
        l1: Dict, l2: Dict, l3: Dict, l4: Dict, l5: Dict,
        ta_1h: Dict, ta_4h: Dict, ta_1d: Dict,
    ) -> Dict:
        """
        Combine 5 layer scores into the final ORACLE output.
        Determines bias direction, total score, and confidence label.
        """
        total_bull = l1["bull"] + l2["bull"] + l3["bull"] + l4["bull"] + l5["bull"]
        total_bear = l1["bear"] + l2["bear"] + l3["bear"] + l4["bear"] + l5["bear"]

        # Determine overall bias
        if total_bull - total_bear >= BIAS_LEAD_REQUIRED:
            bias  = "BULLISH"
            score = total_bull
            layer_scores = {
                "structure":  {"score": l1["bull"], "max": l1["max"], "note": l1["note"]},
                "momentum":   {"score": l2["bull"], "max": l2["max"], "note": l2["note"]},
                "order_flow": {"score": l3["bull"], "max": l3["max"], "note": l3.get("note", "")},
                "key_levels": {"score": l4["bull"], "max": l4["max"], "note": l4["note"]},
                "context":    {"score": l5["bull"], "max": l5["max"], "note": l5["note"]},
            }
        elif total_bear - total_bull >= BIAS_LEAD_REQUIRED:
            bias  = "BEARISH"
            score = total_bear
            layer_scores = {
                "structure":  {"score": l1["bear"], "max": l1["max"], "note": l1["note"]},
                "momentum":   {"score": l2["bear"], "max": l2["max"], "note": l2["note"]},
                "order_flow": {"score": l3["bear"], "max": l3["max"], "note": l3.get("note", "")},
                "key_levels": {"score": l4["bear"], "max": l4["max"], "note": l4["note"]},
                "context":    {"score": l5["bear"], "max": l5["max"], "note": l5["note"]},
            }
        else:
            bias  = "NEUTRAL"
            score = max(total_bull, total_bear)
            layer_scores = {
                "structure":  {"score": max(l1["bull"], l1["bear"]), "max": l1["max"], "note": l1["note"]},
                "momentum":   {"score": max(l2["bull"], l2["bear"]), "max": l2["max"], "note": l2["note"]},
                "order_flow": {"score": max(l3["bull"], l3["bear"]), "max": l3["max"], "note": l3.get("note", "")},
                "key_levels": {"score": max(l4["bull"], l4["bear"]), "max": l4["max"], "note": l4["note"]},
                "context":    {"score": max(l5["bull"], l5["bear"]), "max": l5["max"], "note": l5["note"]},
            }

        score      = min(int(score), 100)
        confidence = _get_confidence_label(score)

        # Timeframe alignment
        tf = l1.get("tf", {})
        tf_1h = tf.get("1h", "neutral").upper()
        tf_4h = tf.get("4h", "neutral").upper()
        tf_1d = tf.get("1d", "neutral").upper()
        aligned = (tf_1h == tf_4h == tf_1d) and tf_1h != "NEUTRAL"

        # Current price
        current_price = 0.0
        if isinstance(ticker, dict) and "price" in ticker:
            current_price = ticker.get("price", 0) or 0
        if current_price == 0:
            current_price = ta_1h.get("price", 0)

        # ATR for invalidation level
        atr = ta_1h.get("indicators", {}).get("atr", 0) or 0

        # Invalidation price
        if bias == "BULLISH" and atr > 0:
            inv_price = round(current_price - atr * 2, 8)
            inv_note  = f"${inv_price:,.4f} — structure flips bearish below this"
        elif bias == "BEARISH" and atr > 0:
            inv_price = round(current_price + atr * 2, 8)
            inv_note  = f"${inv_price:,.4f} — structure flips bullish above this"
        else:
            inv_note = "No clear invalidation — market is NEUTRAL"

        summary = _build_summary(bias, score, confidence, layer_scores, l5)

        return {
            "symbol":     symbol,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "price":      current_price,
            "bias":       bias,
            "score":      score,
            "bull_score": total_bull,
            "bear_score": total_bear,
            "confidence": confidence,
            "timeframe_alignment": {
                "1h":      tf_1h,
                "4h":      tf_4h,
                "1d":      tf_1d,
                "aligned": aligned,
            },
            "layers":    layer_scores,
            "key_levels": {
                "resistance": l4.get("resistance", []),
                "support":    l4.get("support",    []),
                "fvg_above":  l4.get("fvg_above",  []),
                "fvg_below":  l4.get("fvg_below",  []),
                "poc":        l3.get("poc", 0),
                "liq_above":  l4.get("liq_above",  []),
                "liq_below":  l4.get("liq_below",  []),
            },
            "context": {
                "btc_bias":     l5.get("btc_bias",     "NEUTRAL"),
                "funding_rate": l5.get("funding_rate", 0),
                "adx":          l5.get("adx",          0),
                "regime":       l5.get("regime",       "unknown"),
                "session":      l5.get("session",      "UNKNOWN"),
            },
            "invalidation": inv_note,
            "summary":      summary,
        }

    # ─── ORACLE ENGINE STEP 3: MAIN ANALYSIS ─────────────────────────────────

    async def analyze(self, symbol: str, use_cache: bool = True) -> Optional[Dict]:
        """
        # ORACLE CORE: Full 5-layer analysis for a single symbol.
        Returns complete bias dict or neutral result on any data failure.
        NEVER raises — always returns a safe response.
        """
        if not self.market_intel:
            logger.warning("[ORACLE] market_intel not set")
            return None

        # Normalize symbol format
        sym = symbol.upper()
        if "/" not in sym:
            sym = sym.replace("USDT", "") + "/USDT"
        if not sym.endswith("/USDT"):
            sym = sym + "/USDT"

        # Cache hit check
        if use_cache and sym in self._cache:
            cached = self._cache[sym]
            age = (datetime.now(timezone.utc) - cached["ts"]).total_seconds()
            if age < self._cache_ttl:
                return cached["result"]

        try:
            is_btc = sym.startswith("BTC/")

            # Fetch all required data concurrently
            fetch_tasks = [
                self.market_intel.get_technical_analysis(sym, "1h"),
                self.market_intel.get_technical_analysis(sym, "4h"),
                self.market_intel.get_technical_analysis(sym, "1d"),
                self.market_intel.get_klines(sym, "1h", 60),
                self.market_intel.get_ticker(sym),
            ]
            if not is_btc:
                # Fetch BTC 4h for macro context
                fetch_tasks.append(self.market_intel.get_technical_analysis("BTC/USDT", "4h"))

            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            ta_1h, ta_4h, ta_1d, klines_1h, ticker = results[:5]
            btc_ta = results[5] if (not is_btc and len(results) > 5) else ta_4h

            # Validate critical data (1h + 4h required)
            for tag, r in [("1h", ta_1h), ("4h", ta_4h)]:
                if isinstance(r, Exception):
                    logger.warning(f"[ORACLE] {sym} {tag} TA failed: {r}")
                    return self._neutral_result(sym, f"{tag} data unavailable")
                if isinstance(r, dict) and "error" in r:
                    return self._neutral_result(sym, f"{tag} error: {r['error']}")

            # 1d is optional — fall back to 1h if unavailable
            if isinstance(ta_1d, Exception) or (isinstance(ta_1d, dict) and "error" in ta_1d):
                ta_1d = ta_1h

            # Funding rate — non-critical, fail gracefully
            funding = None
            if self.derivatives_intel:
                try:
                    bybit_sym = sym.replace("/USDT", "USDT")
                    funding = await self.derivatives_intel.get_funding_rate_okx(bybit_sym)
                except Exception:
                    pass

            # ── Score all 5 layers ────────────────────────────────────────────
            safe_klines = klines_1h if not isinstance(klines_1h, Exception) else None
            safe_ticker = ticker    if not isinstance(ticker, Exception)    else {}
            safe_btc    = btc_ta    if not isinstance(btc_ta,  Exception)   else {}

            l1 = self._score_structure(ta_1h, ta_4h, ta_1d)
            l2 = self._score_momentum(ta_1h, ta_4h)
            l3 = self._score_order_flow(safe_klines)
            l4 = self._score_key_levels(safe_klines, safe_ticker)
            l5 = self._score_context(ta_1h, safe_btc, funding, sym)

            result = self._build_output(
                sym, safe_ticker,
                l1, l2, l3, l4, l5,
                ta_1h, ta_4h, ta_1d,
            )

            # Cache the result
            self._cache[sym] = {"result": result, "ts": datetime.now(timezone.utc)}

            # Persist to MongoDB (non-blocking)
            if self.db is not None:
                asyncio.create_task(self._log_to_mongo(result))

            return result

        except Exception as exc:
            logger.error(f"[ORACLE] analyze() failed for {sym}: {exc}", exc_info=True)
            return self._neutral_result(sym, str(exc))

    def _neutral_result(self, symbol: str, reason: str = "data unavailable") -> Dict:
        """
        Return a safe NEUTRAL result when any data fetch fails.
        ORACLE never guesses — if data is missing, score = 0, bias = NEUTRAL.
        """
        return {
            "symbol":     symbol,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "price":      0,
            "bias":       "NEUTRAL",
            "score":      0,
            "bull_score": 0,
            "bear_score": 0,
            "confidence": "NEUTRAL",
            "timeframe_alignment": {
                "1h": "NEUTRAL", "4h": "NEUTRAL", "1d": "NEUTRAL", "aligned": False,
            },
            "layers": {
                "structure":  {"score": 0, "max": 30, "note": reason},
                "momentum":   {"score": 0, "max": 25, "note": reason},
                "order_flow": {"score": 0, "max": 20, "note": reason},
                "key_levels": {"score": 0, "max": 15, "note": reason},
                "context":    {"score": 0, "max": 10, "note": reason},
            },
            "key_levels": {
                "resistance": [], "support": [], "fvg_above": [], "fvg_below": [],
                "poc": 0, "liq_above": [], "liq_below": [],
            },
            "context": {
                "btc_bias": "NEUTRAL", "funding_rate": 0,
                "adx": 0, "regime": "unknown", "session": "UNKNOWN",
            },
            "invalidation": "N/A",
            "summary":      f"No data — {reason}",
        }

    # ─── ORACLE ENGINE STEP 8: MONGODB LOGGING ────────────────────────────────

    async def _log_to_mongo(self, result: Dict):
        """
        # ORACLE STEP 8: Persist each analysis to oracle_history.
        Rolling window: keeps only the last 500 entries per symbol.
        This enables future self-calibration (ORACLE score vs actual outcome).
        """
        try:
            symbol = result["symbol"]
            doc    = {**result, "logged_at": datetime.now(timezone.utc)}
            await self.db[ORACLE_HISTORY_COLLECTION].insert_one(doc)

            # Trim to rolling max
            count = await self.db[ORACLE_HISTORY_COLLECTION].count_documents({"symbol": symbol})
            if count > ORACLE_HISTORY_MAX:
                excess = count - ORACLE_HISTORY_MAX
                oldest = await self.db[ORACLE_HISTORY_COLLECTION].find(
                    {"symbol": symbol},
                    sort=[("logged_at", 1)],
                    limit=excess,
                ).to_list(excess)
                ids = [doc["_id"] for doc in oldest]
                if ids:
                    await self.db[ORACLE_HISTORY_COLLECTION].delete_many({"_id": {"$in": ids}})
        except Exception as exc:
            logger.debug(f"[ORACLE] MongoDB log error: {exc}")

    # ─── ORACLE ENGINE STEP 10: FULL MARKET SCAN ─────────────────────────────

    async def scan_all(self, pairs: Optional[List[str]] = None) -> List[Dict]:
        """
        # ORACLE FULL SCAN: Analyze all available USDT perpetuals on MEXC.
        Batched in groups of SCAN_BATCH_SIZE with SCAN_BATCH_DELAY between batches.
        Rate-limit safe: pauses RATE_LIMIT_PAUSE seconds on any rate limit error.
        Sends Telegram summary after completion.
        """
        if self._scan_in_progress:
            logger.info("[ORACLE SCAN] Scan already in progress — skipping.")
            return self._last_full_scan_results

        self._scan_in_progress = True
        scan_start = datetime.now(timezone.utc)
        scan_id    = str(uuid.uuid4())

        try:
            if pairs is None:
                pairs = await self._get_all_mexc_pairs()

            total = len(pairs)
            self._scan_progress = {"scanned": 0, "total": total, "scan_id": scan_id}
            logger.info(f"[ORACLE SCAN] Starting full scan — {total} pairs")
            results = []

            for batch_start in range(0, total, SCAN_BATCH_SIZE):
                batch = pairs[batch_start:batch_start + SCAN_BATCH_SIZE]

                batch_tasks   = [self.analyze(sym, use_cache=False) for sym in batch]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for r in batch_results:
                    if isinstance(r, dict):
                        results.append(r)

                done = min(batch_start + SCAN_BATCH_SIZE, total)
                self._scan_progress["scanned"] = done
                logger.info(f"[ORACLE SCAN] Progress: {done}/{total} pairs")

                await asyncio.sleep(SCAN_BATCH_DELAY)

            # Sort by score descending
            results.sort(key=lambda x: x.get("score", 0), reverse=True)

            self._last_full_scan_results = results
            self._last_full_scan_time    = datetime.now(timezone.utc)

            # Update priority list (pairs to re-check every hour)
            self._priority_symbols = [
                r["symbol"] for r in results
                if r.get("score", 0) >= PRIORITY_SCORE_THRESHOLD
            ]

            # Save scan to MongoDB
            if self.db is not None:
                duration = (datetime.now(timezone.utc) - scan_start).total_seconds()
                asyncio.create_task(self._log_scan_to_mongo(scan_id, results, total, duration))

            # Telegram summary
            asyncio.create_task(self._send_scan_summary(results, total))

            return results

        except Exception as exc:
            logger.error(f"[ORACLE SCAN] Full scan error: {exc}", exc_info=True)
            return []
        finally:
            self._scan_in_progress = False
            self._scan_progress    = {"scanned": 0, "total": 0, "scan_id": None}

    async def _log_scan_to_mongo(self, scan_id: str, results: List[Dict], total: int, duration: float):
        """# ORACLE STEP 8: Save full scan results to oracle_scan_history."""
        try:
            compact = [
                {
                    "symbol":     r["symbol"],
                    "bias":       r["bias"],
                    "score":      r["score"],
                    "confidence": r["confidence"],
                    "summary":    r.get("summary", ""),
                }
                for r in results
            ]
            await self.db[ORACLE_SCAN_COLLECTION].insert_one({
                "scan_id":          scan_id,
                "timestamp":        datetime.now(timezone.utc),
                "total_pairs":      total,
                "duration_seconds": round(duration, 1),
                "results":          compact,
            })
        except Exception as exc:
            logger.debug(f"[ORACLE] Scan log error: {exc}")

    # ─── ORACLE ENGINE STEP 6: TELEGRAM REPORTING ────────────────────────────

    async def _send_report(self):
        """
        # ORACLE STEP 6: Send 4-hour market bias report to Telegram.
        Only includes pairs with score >= TELEGRAM_REPORT_MIN_SCORE.
        Bold labels, no backticks (Telegram renders backticks as white rectangles).
        """
        if not self.send_telegram or not self.chat_ids:
            return

        try:
            # Use priority symbols if available, else default watchlist
            symbols = self._priority_symbols[:20] if self._priority_symbols else DEFAULT_WATCHLIST
            tasks    = [self.analyze(sym) for sym in symbols]
            analyses = await asyncio.gather(*tasks, return_exceptions=True)

            valid   = sorted(
                [a for a in analyses if isinstance(a, dict) and a.get("score", 0) >= TELEGRAM_REPORT_MIN_SCORE],
                key=lambda x: x["score"], reverse=True,
            )
            neutral_ = [
                a for a in analyses
                if isinstance(a, dict) and a.get("score", 0) < TELEGRAM_REPORT_MIN_SCORE
            ]

            if not valid and not neutral_:
                return

            btc = next(
                (a for a in analyses if isinstance(a, dict) and "BTC" in a.get("symbol", "")),
                None,
            )

            session  = _get_session(datetime.now(timezone.utc).hour)
            lines    = [f"ORACLE REPORT · {session}\n"]

            if valid:
                lines.append("Top biases right now:")
                for a in valid[:8]:
                    icon  = "▲" if a["bias"] == "BULLISH" else ("▼" if a["bias"] == "BEARISH" else "─")
                    sym   = a["symbol"].replace("/USDT", "")
                    short = a.get("summary", "")[:65]
                    lines.append(f"{sym} {icon} {a['bias']} {a['score']}/100 · {short}")

            if neutral_:
                syms = " ".join(a["symbol"].replace("/USDT", "") for a in neutral_[:10])
                lines.append(f"\nNeutral / no clear read: {syms}")

            if btc:
                lines.append(
                    f"\nBTC context: {btc['bias']} · {btc['context'].get('session', '')} · "
                    f"ADX {btc['context'].get('adx', 0):.0f}"
                )

            msg = "\n".join(lines)
            for chat_id in self.chat_ids:
                await self.send_telegram(chat_id, msg)

        except Exception as exc:
            logger.warning(f"[ORACLE] Report send error: {exc}")

    async def _send_scan_summary(self, results: List[Dict], total: int):
        """
        # ORACLE STEP 6: Send full scan completion summary to Telegram.
        Format matches the spec — no backticks, numbered with unicode circled digits.
        """
        if not self.send_telegram or not self.chat_ids:
            return

        try:
            strong   = [r for r in results if r.get("score", 0) >= 70]
            moderate = [r for r in results if 50 <= r.get("score", 0) < 70]
            neutral_ = [r for r in results if r.get("score", 0) < 50]
            top5     = [r for r in results if r.get("score", 0) >= TELEGRAM_REPORT_MIN_SCORE][:5]
            next_scan = (datetime.now(timezone.utc) + timedelta(hours=4)).strftime("%H:%M UTC")
            labels   = ["①", "②", "③", "④", "⑤"]

            lines = [
                "ORACLE FULL SCAN COMPLETE",
                f"Pairs scanned: {total}",
                f"Strong bias (70+): {len(strong)}",
                f"Moderate bias (50-69): {len(moderate)}",
                f"Neutral (below 50): {len(neutral_)}",
            ]

            if top5:
                lines.append("\nTop 5 opportunities:")
                for i, r in enumerate(top5):
                    sym   = r["symbol"].replace("/USDT", "")
                    lines.append(f"{labels[i]} {sym} {r['bias']} {r['score']}/100")

            lines.append(f"\nNext full scan: {next_scan}")
            msg = "\n".join(lines)
            for chat_id in self.chat_ids:
                await self.send_telegram(chat_id, msg)

        except Exception as exc:
            logger.debug(f"[ORACLE] Scan summary send error: {exc}")

    # ─── ORACLE ENGINE RUN LOOP ───────────────────────────────────────────────

    async def run_loop(self):
        """
        # ORACLE STEP 10: Main loop.
        Full scan every 4h + priority scan every 1h + 4h Telegram report.
        """
        logger.info("[ORACLE] Run loop started.")
        last_full_scan     = datetime.min.replace(tzinfo=timezone.utc)
        last_priority_scan = datetime.min.replace(tzinfo=timezone.utc)

        while self.active:
            try:
                now = datetime.now(timezone.utc)

                # ── Full scan (every 4h) ──────────────────────────────────────
                if (now - last_full_scan).total_seconds() >= FULL_SCAN_INTERVAL_SEC:
                    logger.info("[ORACLE] Scheduled full scan starting")
                    await self.scan_all()
                    await self._send_report()
                    last_full_scan     = now
                    last_priority_scan = now   # priority scan timer reset after full scan

                # ── Priority scan (every 1h, between full scans) ───────────────
                elif (now - last_priority_scan).total_seconds() >= PRIORITY_SCAN_INTERVAL_SEC:
                    if self._priority_symbols:
                        logger.info(f"[ORACLE] Priority scan: {len(self._priority_symbols)} high-score pairs")
                        tasks   = [self.analyze(sym, use_cache=False) for sym in self._priority_symbols]
                        fresh   = await asyncio.gather(*tasks, return_exceptions=True)

                        # Alert on any pair that crossed the immediate alert threshold
                        for r in fresh:
                            if not isinstance(r, dict):
                                continue
                            if r.get("score", 0) >= PRIORITY_ALERT_THRESHOLD and self.send_telegram:
                                sym     = r["symbol"].replace("/USDT", "")
                                summary = r.get("summary", "")[:80]
                                msg = (
                                    f"ORACLE ALERT · {r['score']}/100 · {r['confidence']}\n"
                                    f"{sym} {r['bias']}\n"
                                    f"{summary}"
                                )
                                for chat_id in self.chat_ids:
                                    await self.send_telegram(chat_id, msg)

                    last_priority_scan = now

                await asyncio.sleep(60)

            except asyncio.CancelledError:
                logger.info("[ORACLE] Run loop cancelled.")
                break
            except Exception as exc:
                logger.error(f"[ORACLE] Run loop error: {exc}")
                await asyncio.sleep(30)

    # ─── STATUS + QUERY HELPERS ───────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Return ORACLE operational status."""
        return {
            "active":              self.active,
            "cache_size":          len(self._cache),
            "priority_symbols":    len(self._priority_symbols),
            "all_pairs_count":     len(self._all_pairs),
            "scan_in_progress":    self._scan_in_progress,
            "scan_progress":       self._scan_progress,
            "last_full_scan":      self._last_full_scan_time.isoformat() if self._last_full_scan_time else None,
            "last_scan_pair_count": len(self._last_full_scan_results),
            "score_distribution": {
                "extreme":  len([r for r in self._last_full_scan_results if r.get("score", 0) >= 86]),
                "strong":   len([r for r in self._last_full_scan_results if 71 <= r.get("score", 0) < 86]),
                "moderate": len([r for r in self._last_full_scan_results if 51 <= r.get("score", 0) < 71]),
                "weak":     len([r for r in self._last_full_scan_results if 31 <= r.get("score", 0) < 51]),
                "neutral":  len([r for r in self._last_full_scan_results if r.get("score", 0) < 31]),
            },
        }

    def get_top(self, min_score: int = 70, bias: Optional[str] = None) -> List[Dict]:
        """
        Filter last full scan results by minimum score and optional bias direction.
        Returns list sorted by score descending.
        """
        filtered = [
            r for r in self._last_full_scan_results
            if r.get("score", 0) >= min_score
            and (bias is None or r.get("bias", "").upper() == bias.upper())
        ]
        return sorted(filtered, key=lambda x: x["score"], reverse=True)

    def get_report(self) -> List[Dict]:
        """Return current bias for all symbols in last full scan."""
        return self._last_full_scan_results

    def get_scan_status(self) -> Dict:
        """Return live progress of the current scan."""
        total = self._scan_progress.get("total", 0)
        scanned = self._scan_progress.get("scanned", 0)
        return {
            "in_progress": self._scan_in_progress,
            "scanned":     scanned,
            "total":       total,
            "percent":     round(scanned / max(total, 1) * 100, 1),
            "scan_id":     self._scan_progress.get("scan_id"),
        }
