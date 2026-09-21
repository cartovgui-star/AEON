"""
ORIA LAYER  —  oria_layer.py
=====================================
Orthogonal Risk Integrated Alpha — four-layer institutional trading framework
built specifically for AEON's 7-engine architecture.

Layers implemented:
  Layer 1 — SignalAggregator : cross-engine signal stacking + composite confidence
  Layer 2 — EdgeFilter       : edge/uncertainty/cost gate + per-symbol decay detection
  Layer 3 — StressMonitor    : unified stress score S(t) + exp(−λ×S) position sizing

Additional improvements:
  - Signal freshness decay          (apply_signal_freshness)
  - Per-symbol 7d vs 30d edge decay (EdgeFilter._detect_decay)
  - Correlation stress multiplier   (StressMonitor: 3+ BTC-eco longs → stress × 1.3)
  - Engine-level Sharpe throttle    (StressMonitor.record_engine_result)

Stress score formula:
  S(t) = 0.30·V(t) + 0.20·T(t) + 0.20·C(t) + 0.20·L(t) + 0.10·H(t)
  Position multiplier = clip(exp(−λ × S), 0.15, 1.00)   λ = 2.5

Usage (from aeon_engine_system.py):
  from oria_layer import init_oria, get_signal_aggregator, get_edge_filter, get_stress_monitor
"""

import asyncio
import logging
import math
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Engine weight model ───────────────────────────────────────────────────────
# Reflects credibility: signal quality, data richness, historical confidence tier
ENGINE_WEIGHT: Dict[str, float] = {
    "elite_strategy":        1.00,   # 90%+ threshold, 5 confluences, BTC aligned
    "free_will_v2":          0.85,   # richest signal set (8 data sources)
    "dual_engine":           0.80,   # long-term sub-engine (82% min confidence)
    "day_trader":            0.70,   # day-trader sub-engine (77% min)
    "autonomous_trader_v2":  0.65,
    "vwap_scalper":          0.60,   # price-action only, narrower edge
    "yolo_engine":           0.50,   # momentum only, highest noise ratio
}

# Per-engine historical confidence priors (bootstrap before 20-trade history exists)
ENGINE_CONF_PRIORS: Dict[str, Dict] = {
    "elite_strategy":        {"mean": 91.0, "std": 3.0},
    "free_will_v2":          {"mean": 79.0, "std": 7.0},
    "dual_engine":           {"mean": 83.0, "std": 5.0},
    "day_trader":            {"mean": 80.0, "std": 5.0},
    "autonomous_trader_v2":  {"mean": 82.0, "std": 5.0},
    "vwap_scalper":          {"mean": 75.0, "std": 8.0},
    "yolo_engine":           {"mean": 77.0, "std": 7.0},
}

# MEXC perpetual fee model
MEXC_TAKER_FEE     = 0.0006   # 0.06% per leg (entry + exit)
MEXC_FUNDING_PERIOD_H = 8     # funding charged every 8 hours

# Typical half bid-ask spread as % of price (used for paper trading cost model)
TYPICAL_SPREAD_PCT: Dict[str, float] = {
    "BTC":  0.01, "ETH":  0.01, "SOL":  0.02, "BNB":  0.02,
    "XRP":  0.03, "ADA":  0.04, "AVAX": 0.04, "DOGE": 0.05,
    "LINK": 0.05, "DOT":  0.05, "ATOM": 0.06, "UNI":  0.06,
    "LTC":  0.04, "OP":   0.07, "INJ":  0.08, "APT":  0.08,
    "FIL":  0.10, "TRX":  0.04, "NEAR": 0.07, "SUI":  0.08,
    "DEFAULT": 0.10,
}

# Stress level thresholds for logging / dashboard display
STRESS_LEVELS = [
    (0.20, "CALM",     "🟢"),
    (0.45, "ELEVATED", "🟡"),
    (0.70, "HIGH",     "🟠"),
    (1.01, "CRITICAL", "🔴"),
]


def get_stress_label(s: float) -> Tuple[str, str]:
    for threshold, label, icon in STRESS_LEVELS:
        if s < threshold:
            return label, icon
    return "CRITICAL", "🔴"


# ──────────────────────────────────────────────────────────────────────────────
# LAYER 1 — SIGNAL AGGREGATOR
# ──────────────────────────────────────────────────────────────────────────────

class SignalVector:
    """Result of aggregating multiple engine signals on the same (symbol, direction)."""
    __slots__ = (
        "symbol", "direction", "composite_confidence",
        "engine_count", "engines", "best_stop", "best_target",
        "convergence_bonus", "timestamp",
    )

    def __init__(
        self,
        symbol: str,
        direction: str,
        composite_confidence: float,
        engine_count: int,
        engines: List[str],
        best_stop: float,
        best_target: float,
        convergence_bonus: float,
    ):
        self.symbol               = symbol
        self.direction            = direction
        self.composite_confidence = composite_confidence
        self.engine_count         = engine_count
        self.engines              = engines
        self.best_stop            = best_stop
        self.best_target          = best_target
        self.convergence_bonus    = convergence_bonus
        self.timestamp            = time.monotonic()

    def to_dict(self) -> Dict:
        return {
            "symbol":               self.symbol,
            "direction":            self.direction,
            "composite_confidence": round(self.composite_confidence, 1),
            "engine_count":         self.engine_count,
            "engines":              self.engines,
            "convergence_bonus":    round(self.convergence_bonus, 1),
        }


class SignalAggregator:
    """
    Layer 1 — Unified Signal Vector.

    Buffers all pending signals per (symbol, direction) with a 300s TTL.
    When submit_signal() is called, incoming confidence is replaced with the
    weighted composite from all buffered signals on the same coin+direction.

    Engine weights encode credibility (elite > free_will > yolo).
    Confidence is Z-score normalized per engine before combining so a
    90% from ELITE and a 90% from YOLO are treated differently.
    """

    BUFFER_TTL = 300   # seconds — signals older than this are expired

    def __init__(self):
        # (symbol_base, direction) → list of buffered signal dicts
        self._buffer: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
        self._stats = {"total_buffered": 0, "total_aggregated": 0, "convergence_events": 0}

    @staticmethod
    def _base_symbol(symbol: str) -> str:
        return symbol.replace("/USDT", "").replace("USDT", "").upper().strip()

    def _z_normalize(self, engine: str, raw_conf: float, db_stats: Optional[Dict] = None) -> float:
        """Z-score normalize confidence within engine's historical distribution."""
        if db_stats and db_stats.get("trade_count", 0) >= 20:
            mean = float(db_stats.get("conf_mean", 78.0))
            std  = max(float(db_stats.get("conf_std", 5.0)), 1.0)
        else:
            prior = ENGINE_CONF_PRIORS.get(engine, {"mean": 78.0, "std": 7.0})
            mean, std = prior["mean"], prior["std"]
        z = (raw_conf - mean) / std
        return max(-3.0, min(3.0, z))

    def _expire(self, key: Tuple[str, str]):
        now = time.monotonic()
        self._buffer[key] = [
            s for s in self._buffer[key]
            if (now - s["ts"]) < self.BUFFER_TTL
        ]

    def buffer_signal(
        self,
        symbol:      str,
        direction:   str,
        engine:      str,
        confidence:  float,
        stop_loss:   float,
        take_profit: float,
        entry_price: float,
    ):
        """
        Call this once before submit_signal() — ideally in the engine's
        analyze() method just before it calls submit_signal_gated().
        """
        key = (self._base_symbol(symbol), direction.lower())
        self._expire(key)
        self._buffer[key].append({
            "engine":      engine,
            "confidence":  confidence,
            "stop_loss":   stop_loss,
            "take_profit": take_profit,
            "entry_price": entry_price,
            "ts":          time.monotonic(),
        })
        self._stats["total_buffered"] += 1

    def compute_vector(
        self,
        symbol:         str,
        direction:      str,
        db_stats_map:   Optional[Dict[str, Dict]] = None,
    ) -> Optional[SignalVector]:
        """
        Returns a SignalVector for the current (symbol, direction) buffer.
        Returns None if only one signal is buffered (no aggregation needed).
        """
        key = (self._base_symbol(symbol), direction.lower())
        self._expire(key)
        pending = self._buffer[key]

        if len(pending) < 2:
            return None   # single engine — no aggregation benefit

        db_stats_map = db_stats_map or {}
        weighted_sum, total_weight = 0.0, 0.0
        engines, stops, targets = [], [], []

        for s in pending:
            eng = s["engine"]
            w   = ENGINE_WEIGHT.get(eng, 0.50)
            z   = self._z_normalize(eng, s["confidence"], db_stats_map.get(eng))
            weighted_sum += w * z
            total_weight += w
            engines.append(eng)
            if s["stop_loss"]   > 0: stops.append(s["stop_loss"])
            if s["take_profit"] > 0: targets.append(s["take_profit"])

        composite_z    = weighted_sum / max(total_weight, 1e-6)
        composite_conf = 78.0 + composite_z * 12.0   # rescale to confidence space

        # Convergence bonus: extra confidence when multiple engines agree.
        # Bonus is scaled by engine diversity — correlated engines (e.g. all
        # momentum-based) firing together don't add independent confirmation.
        # Diversity = fraction of distinct engine "families" represented.
        n = len(pending)
        ENGINE_FAMILY = {
            "elite_strategy":       "smc",
            "free_will_v2":         "ml",
            "dual_engine":          "trend",
            "day_trader":           "trend",
            "autonomous_trader_v2": "smc",
            "vwap_scalper":         "price_action",
            "yolo_engine":          "momentum",
        }
        families = {ENGINE_FAMILY.get(s["engine"], s["engine"]) for s in pending}
        diversity = len(families) / max(n, 1)   # 1.0 = all different families
        raw_bonus = 10.0 if n >= 4 else (5.0 if n >= 3 else 3.0)
        convergence_bonus = round(raw_bonus * diversity, 1)
        composite_conf   = min(98.0, composite_conf + convergence_bonus)

        # Best stop (tightest protection) and best target (most aggressive)
        dir_lower = direction.lower()
        if stops:
            best_stop = max(stops) if dir_lower == "long" else min(stops)
        else:
            best_stop = pending[0]["stop_loss"]

        if targets:
            best_target = max(targets) if dir_lower == "long" else min(targets)
        else:
            best_target = pending[0]["take_profit"]

        self._stats["total_aggregated"]  += 1
        self._stats["convergence_events"] += 1

        logger.info(
            f"🔗 [ORIA/L1] {symbol} {direction.upper()} — {n} engines converge: "
            f"{engines} → composite={composite_conf:.1f}% (bonus={convergence_bonus:.0f}%)"
        )

        return SignalVector(
            symbol=symbol,
            direction=direction,
            composite_confidence=composite_conf,
            engine_count=n,
            engines=engines,
            best_stop=best_stop,
            best_target=best_target,
            convergence_bonus=convergence_bonus,
        )

    def get_stats(self) -> Dict:
        return dict(self._stats)


# ──────────────────────────────────────────────────────────────────────────────
# LAYER 2 — EDGE FILTER
# ──────────────────────────────────────────────────────────────────────────────

class EdgeFilter:
    """
    Layer 2 — Edge / Uncertainty / Cost Filter.

    A trade only fires when:
        estimated_edge  >  uncertainty_penalty + trading_cost

    Edge = per-engine per-symbol Kelly edge from rolling win/loss stats.
    Cost = round-trip fee + expected funding accrual (leverage-adjusted).
    Uncertainty = (1 - confidence/100) × 0.05

    Also implements:
      - Adaptive R:R floor by market regime
      - Per-symbol 7d vs 30d edge decay → soft position size reduction
      - Spread-adjusted entry price for realistic paper simulation
    """

    MIN_TRADE_COUNT = 20   # edge gate dormant until this many trades on record

    REGIME_RR_FLOOR: Dict[str, float] = {
        "STRONG_TREND":       1.50,
        "TRENDING":           1.50,
        "WEAK_TREND":         1.75,
        "ACCUMULATION":       1.75,
        "RANGING":            2.25,
        "HIGH_VOLATILITY":    3.00,
        "VOLATILE_EXPANSION": 3.00,
    }

    EDGE_DECAY_REDUCTION = 0.50   # position size × 0.5 when decay detected

    def __init__(self, db=None):
        self.db = db
        self._cache:     Dict[str, Dict] = {}
        self._cache_ts:  float = 0.0
        self._cache_ttl: float = 600.0   # 10-minute cache
        # Symbols with detected 7d vs 30d win-rate decay → size halved for 24h
        self._soft_blacklist: Dict[str, datetime] = {}

    # ── Cost model ────────────────────────────────────────────────────────────

    @staticmethod
    def estimate_round_trip_cost(
        leverage:             float,
        expected_hold_hours:  float = 4.0,
        funding_rate:         float = 0.0001,
    ) -> float:
        """
        Returns expected round-trip cost as a fraction of position value.
        Includes: entry taker fee + exit taker fee + funding accrued during hold.
        """
        fee_cost     = 2.0 * MEXC_TAKER_FEE * leverage
        funding_cost = abs(funding_rate) * (expected_hold_hours / MEXC_FUNDING_PERIOD_H) * leverage
        return fee_cost + funding_cost

    @staticmethod
    def spread_adjusted_entry(symbol: str, direction: str, entry_price: float) -> float:
        """
        Returns spread-adjusted entry price for realistic paper simulation.
        Longs pay the ask (slightly higher); shorts hit the bid (slightly lower).
        """
        coin      = symbol.replace("/USDT", "").replace("USDT", "").upper().strip()
        half_sprd = TYPICAL_SPREAD_PCT.get(coin, TYPICAL_SPREAD_PCT["DEFAULT"]) / 200.0
        if direction.lower() == "long":
            return round(entry_price * (1.0 + half_sprd), 8)
        else:
            return round(entry_price * (1.0 - half_sprd), 8)

    def get_regime_rr_floor(self, regime: str) -> float:
        return self.REGIME_RR_FLOOR.get(regime, 1.50)

    # ── Edge stats DB ─────────────────────────────────────────────────────────

    async def _load_cache(self) -> Dict[str, Dict]:
        if not self.db:
            return {}
        now = time.monotonic()
        if now - self._cache_ts < self._cache_ttl:
            return self._cache
        try:
            self._cache = {}
            async for doc in self.db.edge_stats.find({}):
                key = f"{doc['engine']}::{doc['symbol']}"
                self._cache[key] = doc
            self._cache_ts = now
        except Exception as e:
            logger.warning(f"[ORIA/EdgeFilter] edge_stats load failed: {e}")
        return self._cache

    async def check_edge(
        self,
        engine:               str,
        symbol:               str,
        leverage:             float,
        confidence:           float,
        expected_hold_hours:  float = 4.0,
        funding_rate:         float = 0.0001,
    ) -> Tuple[bool, str, Dict]:
        """
        Returns (passes, reason, detail_dict).
        passes=True → edge clears cost+uncertainty → allow trade.
        passes=False → insufficient edge → reject signal.
        """
        cache    = await self._load_cache()
        stats    = cache.get(f"{engine}::{symbol}")
        cost     = self.estimate_round_trip_cost(leverage, expected_hold_hours, funding_rate)
        uncert   = (1.0 - confidence / 100.0) * 0.05
        required = cost + uncert

        detail: Dict = {
            "cost":               round(cost, 4),
            "uncertainty":        round(uncert, 4),
            "min_required_edge":  round(required, 4),
        }

        if not stats or stats.get("trade_count", 0) < self.MIN_TRADE_COUNT:
            detail["edge"]    = "UNKNOWN"
            detail["verdict"] = "PASS (< 20 trades)"
            return True, f"Edge unknown for {engine}::{symbol} — pass through", detail

        wr  = stats.get("win_rate",     0.50)
        aw  = stats.get("avg_win_pct",  3.00) / 100.0
        al  = abs(stats.get("avg_loss_pct", 2.00)) / 100.0
        kelly = wr - (1.0 - wr) * (al / max(aw, 1e-6))

        detail.update({
            "win_rate":     round(wr,    3),
            "avg_win_pct":  round(aw * 100, 2),
            "avg_loss_pct": round(al * 100, 2),
            "kelly_edge":   round(kelly,  4),
            "edge":         round(kelly,  4),
        })

        # Edge decay detection: 7d win rate dropped >15% below 30d baseline
        wr_7d  = stats.get("win_rate_7d",  wr)
        wr_30d = stats.get("win_rate_30d", wr)
        if wr_30d > 0.30 and (wr_30d - wr_7d) > 0.15:
            self._soft_blacklist[symbol] = datetime.now(timezone.utc)
            detail["edge_decay"] = True
            logger.warning(
                f"[ORIA/EdgeDecay] {symbol} ({engine}): 7d WR={wr_7d:.0%} vs "
                f"30d WR={wr_30d:.0%} — decay detected, position halved for 24h"
            )

        if kelly >= required:
            detail["verdict"] = "PASS"
            return True, f"Edge {kelly:.3f} >= required {required:.3f}", detail

        detail["verdict"] = "FAIL"
        return False, (
            f"Insufficient edge: kelly={kelly:.3f} < "
            f"cost({cost:.3f}) + uncertainty({uncert:.3f}) = {required:.3f}"
        ), detail

    def is_soft_blacklisted(self, symbol: str) -> bool:
        """True if symbol's edge has decayed (lasts 24h)."""
        ts = self._soft_blacklist.get(symbol)
        if ts is None:
            return False
        if (datetime.now(timezone.utc) - ts) > timedelta(hours=24):
            del self._soft_blacklist[symbol]
            return False
        return True

    def soft_blacklist_size_mult(self, symbol: str) -> float:
        """Returns 0.5 if soft-blacklisted, 1.0 otherwise."""
        return self.EDGE_DECAY_REDUCTION if self.is_soft_blacklisted(symbol) else 1.0

    # ── Edge stats update (called by memory_engine per closed trade) ──────────

    async def update_edge_stats(
        self,
        engine:     str,
        symbol:     str,
        outcome:    str,
        pnl_pct:    float,
        confidence: float,
    ):
        """
        Updates rolling win/loss stats in MongoDB 'edge_stats' collection.
        Called from memory_engine._process_new_closures() for every closed trade.
        Uses incremental exponential decay to approximate 7d / 30d rolling windows.
        """
        if not self.db:
            return
        try:
            key = {"engine": engine, "symbol": symbol}
            doc = await self.db.edge_stats.find_one(key)
            if doc is None:
                prior = ENGINE_CONF_PRIORS.get(engine, {"mean": 78.0, "std": 7.0})
                doc = {
                    "engine": engine, "symbol": symbol,
                    "trade_count": 0, "wins": 0, "losses": 0,
                    "total_win_pct": 0.0, "total_loss_pct": 0.0,
                    "win_rate": 0.50, "avg_win_pct": 3.0, "avg_loss_pct": 2.0,
                    "conf_mean": prior["mean"], "conf_std": prior["std"],
                    "win_rate_7d": 0.50, "win_rate_30d": 0.50,
                    "trades_7d": 0.0, "wins_7d": 0.0,
                    "trades_30d": 0.0, "wins_30d": 0.0,
                    "last_updated": datetime.now(timezone.utc),
                }

            is_win = outcome.lower() in ("win", "tp", "tp1", "tp2", "tp3") or pnl_pct > 0
            doc["trade_count"] += 1

            if is_win:
                doc["wins"]          += 1
                doc["total_win_pct"] += abs(pnl_pct)
            else:
                doc["losses"]          += 1
                doc["total_loss_pct"]  += abs(pnl_pct)

            doc["win_rate"]     = doc["wins"]   / max(doc["trade_count"], 1)
            doc["avg_win_pct"]  = doc["total_win_pct"]  / max(doc["wins"],   1)
            doc["avg_loss_pct"] = doc["total_loss_pct"] / max(doc["losses"], 1)

            # Running mean/std of confidence (Welford one-pass algorithm)
            n    = doc["trade_count"]
            mean = doc["conf_mean"]
            std  = doc["conf_std"]
            delta  = confidence - mean
            mean  += delta / n
            delta2 = confidence - mean
            var    = ((n - 1) * std ** 2 + delta * delta2) / n if n > 1 else std ** 2
            doc["conf_mean"] = mean
            doc["conf_std"]  = max(math.sqrt(max(var, 0.0)), 1.0)

            # Approximate rolling 7d / 30d via exponential decay
            # Each update, old counts decay so recent trades dominate
            # decay_7d ≈ 1 trade/day × 7 days → half-life ~7 trades
            doc["trades_7d"]  = doc.get("trades_7d",  0.0) * 0.97  + 1.0
            doc["wins_7d"]    = doc.get("wins_7d",    0.0) * 0.97  + (1.0 if is_win else 0.0)
            doc["trades_30d"] = doc.get("trades_30d", 0.0) * 0.999 + 1.0
            doc["wins_30d"]   = doc.get("wins_30d",   0.0) * 0.999 + (1.0 if is_win else 0.0)
            doc["win_rate_7d"]  = doc["wins_7d"]  / max(doc["trades_7d"],  1.0)
            doc["win_rate_30d"] = doc["wins_30d"] / max(doc["trades_30d"], 1.0)
            doc["last_updated"] = datetime.now(timezone.utc)

            await self.db.edge_stats.replace_one(key, doc, upsert=True)
            self._cache_ts = 0.0   # invalidate cache

        except Exception as e:
            logger.error(f"[ORIA/EdgeFilter] update_edge_stats failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# LAYER 3 — STRESS SCORE + SIZING
# ──────────────────────────────────────────────────────────────────────────────

def compute_stress_score(
    atr_pct:            float,   # ATR(14) as % of price on 1H BTC
    adx:                float,   # ADX value on 1H BTC (higher = trending = safer)
    funding_rate:       float,   # current 8H funding rate (signed)
    bb_width_pct:       float,   # Bollinger Band width % on 1H BTC
    consecutive_losses: int,     # total consecutive losses across ALL engines
    daily_pnl_pct:      float,   # today's P&L as % of starting balance (negative = loss)
    long_pct:           float,   # long/short ratio [0, 1] — 0.5 = neutral
    h_value:            float,   # AEON's H from aeon_quantum_state.py
) -> float:
    """
    S(t) = 0.30·V(t) + 0.20·T(t) + 0.20·C(t) + 0.20·L(t) + 0.10·H(t)

    Returns stress_score ∈ [0.0, 1.0]
      0.0 = calm trending market, full sizing
      1.0 = maximum stress, minimum sizing (floor = 15%)

    Stress thresholds:
      S < 0.20  →  CALM      (🟢) — full size
      S < 0.45  →  ELEVATED  (🟡) — ~57% size
      S < 0.70  →  HIGH      (🟠) — ~17% size
      S ≥ 0.70  →  CRITICAL  (🔴) — 15% floor
    """
    # V(t) — Volatility stress (30% weight)
    vol_stress = min(1.0, atr_pct     / 3.0)   # 3% ATR  = max vol stress
    bb_stress  = min(1.0, bb_width_pct / 8.0)  # 8% BB   = max BB stress
    V = 0.60 * vol_stress + 0.40 * bb_stress

    # T(t) — Trend uncertainty stress (20% weight)
    # Low ADX = ranging = uncertainty
    T = max(0.0, 1.0 - adx / 40.0)   # ADX ≥ 40 = 0 stress

    # C(t) — Crowding / funding stress (20% weight)
    fund_stress  = min(1.0, abs(funding_rate) / 0.003)   # 0.3% funding rate = max
    crowd_stress = min(1.0, abs(long_pct - 0.5) * 2.0)  # deviation from 50/50
    C = 0.50 * fund_stress + 0.50 * crowd_stress

    # L(t) — Realized loss stress (20% weight)
    drawdown_stress = min(1.0, max(0.0, -daily_pnl_pct / 0.10))   # −10% daily = max
    consec_stress   = min(1.0, consecutive_losses / 5.0)           # 5 consec = max
    L = max(drawdown_stress, consec_stress)

    # H(t) — AEON self-awareness stress (10% weight)
    # H > 1.0 = AEON is performing well = 0 stress
    H = max(0.0, 1.0 - h_value / 1.0)

    S = 0.30 * V + 0.20 * T + 0.20 * C + 0.20 * L + 0.10 * H
    return float(min(1.0, max(0.0, S)))


def apply_stress_sizing(base_size: float, stress: float, lambda_: float = 2.5) -> float:
    """
    ORIA sizing formula: size = clip(base_size × exp(−λ × stress), min, max)

    λ = 2.5 response curve:
      stress = 0.00  →  1.00×  (no reduction)
      stress = 0.20  →  0.61×  (CALM)
      stress = 0.40  →  0.37×  (ELEVATED)
      stress = 0.60  →  0.22×  (HIGH)
      stress = 0.80  →  0.14×  →  floored at 0.15×
      stress = 1.00  →  0.08×  →  floored at 0.15×
    """
    raw        = math.exp(-lambda_ * stress)
    multiplier = max(0.15, min(1.00, raw))
    return round(base_size * multiplier, 2)


def apply_stress_leverage(base_leverage: float, stress: float, lambda_: float = 2.5) -> int:
    """
    Same formula but with lighter sensitivity (70% of stress impact).
    Leverage has engine-level hard floors so we don't compress as aggressively.
    """
    raw        = math.exp(-lambda_ * 0.70 * stress)
    multiplier = max(0.30, min(1.00, raw))
    return max(1, round(base_leverage * multiplier))


class StressMonitor:
    """
    Layer 3 — Stress-Adjusted Dynamic Sizing.

    Maintains a live stress_score S(t) ∈ [0, 1] refreshed every 60 seconds.
    All engines size through get_size_multiplier() / get_leverage_multiplier().

    Also implements:
      - Correlation stress multiplier: 3+ BTC-eco correlated LONGs → stress × 1.30
      - Engine-level Sharpe throttle: 7d Sharpe < 0 → max_concurrent_trades halved
    """

    REFRESH_INTERVAL = 60   # seconds
    LAMBDA           = 2.5  # sizing sensitivity

    # BTC-ecosystem coins (from paper_trading.py CORRELATION_GROUPS)
    BTC_ECO = {"BTC", "ETH", "BNB", "SOL", "AVAX", "POL", "OP"}

    def __init__(self):
        self.stress_score:  float = 0.10   # start calm
        self._last_refresh: float = 0.0
        self._refresh_lock        = asyncio.Lock()
        self._last_log:     float = 0.0

        self.market_intel    = None
        self.quantum_state   = None
        self._engine_manager = None

        # Engine Sharpe throttle: engine → list of (monotonic_ts, pnl_pct)
        self._pnl_history:    Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        # engine → throttle_until datetime
        self._throttled:      Dict[str, datetime] = {}

    def set_dependencies(self, market_intel, quantum_state=None, engine_manager=None):
        self.market_intel    = market_intel
        self.quantum_state   = quantum_state
        self._engine_manager = engine_manager

    async def run_loop(self):
        """Background task — refresh stress score every 60s."""
        logger.info("📊 [ORIA/StressMonitor] Background loop started")
        while True:
            try:
                await self.refresh()
            except Exception as e:
                logger.error(f"[ORIA/StressMonitor] Refresh error: {e}")
            await asyncio.sleep(self.REFRESH_INTERVAL)

    async def refresh(self):
        """Compute and store current stress_score."""
        async with self._refresh_lock:
            try:
                mi = self.market_intel
                if not mi:
                    return

                # Pull 1H BTC indicators
                atr_pct, adx, bb_width = 1.0, 25.0, 2.0
                try:
                    ta = await mi.get_full_analysis("BTC/USDT")
                    if ta:
                        tf_1h = ta.get("timeframes", {}).get("1h", {})
                        ind   = tf_1h.get("indicators", {})
                        close = float(ind.get("close") or ind.get("price") or 1.0)
                        atr_v = float(ind.get("atr") or 0.0)
                        if atr_v and close:
                            atr_pct = (atr_v / close) * 100.0
                        adx      = float(ind.get("adx")         or 25.0)
                        bb_width = float(ind.get("bb_width_pct") or 2.0)
                except Exception:
                    pass

                # Funding rate
                funding_rate = 0.0001
                try:
                    fr = await mi.get_current_funding_rate("BTC/USDT")
                    if isinstance(fr, (int, float)):
                        funding_rate = float(fr)
                except Exception:
                    pass

                # Long/short ratio
                long_pct = 0.50
                try:
                    ls = await mi.get_long_short_ratio("BTC/USDT")
                    if isinstance(ls, (int, float)):
                        long_pct = float(ls)
                    elif isinstance(ls, dict):
                        long_pct = float(ls.get("long_pct", 0.50))
                except Exception:
                    pass

                # Consecutive losses + daily P&L from EngineManager
                consecutive_losses = 0
                daily_pnl_pct      = 0.0
                if self._engine_manager:
                    try:
                        cl = self._engine_manager._consecutive_losses
                        consecutive_losses = sum(cl.values()) if cl else 0
                        total_pnl = sum(
                            s.daily_pnl
                            for s in self._engine_manager.engine_stats.values()
                        )
                        # Use PRO account starting balance as denominator
                        daily_pnl_pct = total_pnl / 50_000.0
                    except Exception:
                        pass

                # AEON H value
                h_value = 0.50
                if self.quantum_state:
                    try:
                        h_value = float(self.quantum_state.get_h_value())
                    except Exception:
                        pass

                raw_stress = compute_stress_score(
                    atr_pct, adx, funding_rate, bb_width,
                    consecutive_losses, daily_pnl_pct, long_pct, h_value,
                )

                # Correlation stress multiplier
                if self._engine_manager:
                    try:
                        em   = self._engine_manager
                        longs = sum(
                            1
                            for et in em.engine_trades
                            for t  in em._get_open_trades(et)
                            if (t.direction.lower() == "long"
                                and t.symbol.replace("/USDT", "").replace("USDT", "")
                                       .upper().strip() in self.BTC_ECO)
                        )
                        if longs >= 3:
                            raw_stress = min(1.0, raw_stress * 1.30)
                            logger.info(
                                f"[ORIA/Stress] Correlation ×1.30: "
                                f"{longs} BTC-eco LONGs open → S={raw_stress:.3f}"
                            )
                    except Exception:
                        pass

                self.stress_score  = raw_stress
                self._last_refresh = time.monotonic()

                # Log every 5 min
                now = time.monotonic()
                if now - self._last_log > 300:
                    label, icon = get_stress_label(raw_stress)
                    logger.info(
                        f"{icon} [ORIA/Stress] S={raw_stress:.3f} [{label}] | "
                        f"atr={atr_pct:.2f}% adx={adx:.0f} fund={funding_rate:.5f} "
                        f"bb={bb_width:.1f}% consec={consecutive_losses} "
                        f"dpnl={daily_pnl_pct:.2%} H={h_value:.3f}"
                    )
                    self._last_log = now

            except Exception as e:
                logger.error(f"[ORIA/StressMonitor] refresh() error: {e}")

    def get_size_multiplier(self) -> Tuple[float, str]:
        """Returns (multiplier, label). multiplier ∈ [0.15, 1.0]."""
        mult  = max(0.15, min(1.00, math.exp(-self.LAMBDA * self.stress_score)))
        label, icon = get_stress_label(self.stress_score)
        return mult, f"{icon} [{label}] S={self.stress_score:.3f}"

    def get_leverage_multiplier(self) -> float:
        """Lighter stress impact on leverage (70% of full stress). ∈ [0.30, 1.0]."""
        return max(0.30, min(1.00, math.exp(-self.LAMBDA * 0.70 * self.stress_score)))

    # ── Engine Sharpe throttle ────────────────────────────────────────────────

    def record_engine_result(self, engine: str, pnl_pct: float):
        """
        Call this after every closed engine trade.
        Maintains a 7-day rolling history and evaluates Sharpe.
        7d Sharpe < 0 → throttle engine for 24h (max_concurrent_trades halved).
        """
        now = time.monotonic()
        self._pnl_history[engine].append((now, pnl_pct))
        # Prune entries older than 7 days
        cutoff = now - 7 * 86400
        self._pnl_history[engine] = [
            (ts, p) for ts, p in self._pnl_history[engine] if ts > cutoff
        ]
        self._evaluate_sharpe(engine)

    def _evaluate_sharpe(self, engine: str):
        history = self._pnl_history[engine]
        if len(history) < 5:
            return

        pnls = [p for _, p in history]
        mean = sum(pnls) / len(pnls)
        var  = sum((p - mean) ** 2 for p in pnls) / max(len(pnls) - 1, 1)
        std  = math.sqrt(var) if var > 0 else 1e-6
        sharpe = mean / std

        # Clear expired throttle
        if engine in self._throttled:
            if datetime.now(timezone.utc) >= self._throttled[engine]:
                del self._throttled[engine]
            else:
                return   # already throttled, don't re-evaluate

        if sharpe < 0:
            until = datetime.now(timezone.utc) + timedelta(hours=24)
            self._throttled[engine] = until
            logger.warning(
                f"⚡ [ORIA/SharpeThrottle] {engine}: 7d Sharpe={sharpe:.3f} < 0 "
                f"→ max_concurrent_trades halved until {until.strftime('%H:%M UTC')}"
            )

    def is_throttled(self, engine: str) -> bool:
        ts = self._throttled.get(engine)
        if ts is None:
            return False
        if datetime.now(timezone.utc) >= ts:
            del self._throttled[engine]
            return False
        return True

    def effective_concurrent_limit(self, engine: str, normal_limit: int) -> int:
        """Returns halved limit if Sharpe-throttled, normal_limit otherwise."""
        if self.is_throttled(engine):
            return max(1, normal_limit // 2)
        return normal_limit


# ──────────────────────────────────────────────────────────────────────────────
# SIGNAL FRESHNESS DECAY  (additional improvement)
# ──────────────────────────────────────────────────────────────────────────────

def apply_signal_freshness(
    confidence:          float,
    signal_age_seconds:  float,
    decay_rate:          float = 0.001,
) -> float:
    """
    Confidence decays exponentially with signal age.

    effective_confidence = raw_confidence × exp(−decay_rate × age_seconds)

    Default decay_rate = 0.001:
      age =  0 min  →  1.00×  (no decay)
      age =  5 min  →  0.74×
      age = 10 min  →  0.55×
      age = 20 min  →  0.30×

    Use this in submit_signal() when a signal has been queued after
    being blocked by the per-coin cap and is retried later.
    """
    if signal_age_seconds <= 0:
        return confidence
    return round(confidence * math.exp(-decay_rate * signal_age_seconds), 1)


# ──────────────────────────────────────────────────────────────────────────────
# MODULE SINGLETONS
# ──────────────────────────────────────────────────────────────────────────────

_signal_aggregator: Optional[SignalAggregator] = None
_edge_filter:       Optional[EdgeFilter]       = None
_stress_monitor:    Optional[StressMonitor]    = None


def init_oria(db=None) -> Tuple[SignalAggregator, EdgeFilter, StressMonitor]:
    """
    Call once at server startup (server.py lifespan) with the MongoDB db handle.
    Returns the three singletons which are also accessible via the getters below.
    """
    global _signal_aggregator, _edge_filter, _stress_monitor
    _signal_aggregator = SignalAggregator()
    _edge_filter       = EdgeFilter(db=db)
    _stress_monitor    = StressMonitor()
    logger.info("🧠 [ORIA] Initialized — SignalAggregator + EdgeFilter + StressMonitor")
    return _signal_aggregator, _edge_filter, _stress_monitor


def get_signal_aggregator() -> Optional[SignalAggregator]:
    return _signal_aggregator


def get_edge_filter() -> Optional[EdgeFilter]:
    return _edge_filter


def get_stress_monitor() -> Optional[StressMonitor]:
    return _stress_monitor
