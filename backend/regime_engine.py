"""
Market Regime Detection Engine
Detects one of 4 regimes for any symbol:
  STRONG_TREND, WEAK_TREND, RANGING, VOLATILE_EXPANSION

Each regime adjusts leverage multiplier and blocked strategies.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

REGIME_CONFIG = {
    "STRONG_TREND": {
        "description": "Strong directional trend with momentum",
        "max_leverage_multiplier": 1.0,
        "allowed_strategies": ["trend_follow", "breakout", "momentum"],
        "recommended_action": "Trade WITH trend, scale in on pullbacks",
        "color": "green",
    },
    "WEAK_TREND": {
        "description": "Mild directional bias, choppy price action",
        "max_leverage_multiplier": 0.7,
        "allowed_strategies": ["trend_follow"],
        "recommended_action": "Smaller size, tighter stops, avoid counter-trend",
        "color": "yellow",
    },
    "RANGING": {
        "description": "Sideways consolidation, no clear direction",
        "max_leverage_multiplier": 0.5,
        "allowed_strategies": ["range_fade"],
        "recommended_action": "Fade extremes only, tight stops, no breakout trades",
        "color": "orange",
    },
    "VOLATILE_EXPANSION": {
        "description": "Explosive volatility expansion, unpredictable",
        "max_leverage_multiplier": 0.0,
        "allowed_strategies": [],
        "recommended_action": "STAND ASIDE — wait for regime to stabilize",
        "color": "red",
    },
}


MACRO_CONFIDENCE_PENALTY = 10.0   # extra % confidence required when trading against macro
MACRO_CACHE_TTL          = 1800   # 30 minutes — macro direction changes slowly


class RegimeEngine:
    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._cache_ttl = 300  # 5 minutes

        # BTC macro direction (BULLISH / BEARISH / NEUTRAL) — shared state for all engines
        self._macro_direction: str = "NEUTRAL"
        self._macro_updated_at: Optional[datetime] = None

    def _is_cached(self, symbol: str) -> bool:
        if symbol not in self._cache:
            return False
        age = (datetime.now(timezone.utc) - self._cache[symbol]["detected_at"]).total_seconds()
        return age < self._cache_ttl

    async def detect_regime(self, symbol: str, market_intel) -> dict:
        """
        Detect market regime for symbol using 1H + 4H ADX, BB width, ATR.
        Results cached for 5 minutes.
        """
        if self._is_cached(symbol):
            return self._cache[symbol]

        try:
            ta_1h, ta_4h = None, None
            try:
                ta_1h = await market_intel.get_technical_analysis(symbol, "1h")
            except Exception:
                pass
            try:
                ta_4h = await market_intel.get_technical_analysis(symbol, "4h")
            except Exception:
                pass

            if not ta_1h and not ta_4h:
                return self._default_regime(symbol, "TA fetch failed")

            def get_ind(ta, key, default=0):
                if not ta:
                    return default
                return ta.get("indicators", {}).get(key) or ta.get(key) or default

            adx_1h = get_ind(ta_1h, "adx", 25)
            adx_4h = get_ind(ta_4h, "adx", 25)

            bb_upper_1h = get_ind(ta_1h, "bb_upper", 0)
            bb_lower_1h = get_ind(ta_1h, "bb_lower", 0)
            bb_mid_1h = get_ind(ta_1h, "bb_middle", 0) or get_ind(ta_1h, "bb_mid", 0)
            bb_width_1h = (bb_upper_1h - bb_lower_1h) / bb_mid_1h * 100 if bb_mid_1h > 0 else 0

            bb_upper_4h = get_ind(ta_4h, "bb_upper", 0)
            bb_lower_4h = get_ind(ta_4h, "bb_lower", 0)
            bb_mid_4h = get_ind(ta_4h, "bb_middle", 0) or get_ind(ta_4h, "bb_mid", 0)
            bb_width_4h = (bb_upper_4h - bb_lower_4h) / bb_mid_4h * 100 if bb_mid_4h > 0 else 0

            price_1h = get_ind(ta_1h, "price", 1) or get_ind(ta_1h, "close", 1) or 1
            price_4h = get_ind(ta_4h, "price", 1) or get_ind(ta_4h, "close", 1) or 1
            atr_1h = get_ind(ta_1h, "atr", 0)
            atr_4h = get_ind(ta_4h, "atr", 0)
            atr_pct_1h = atr_1h / price_1h * 100 if price_1h > 0 and atr_1h > 0 else 0
            atr_pct_4h = atr_4h / price_4h * 100 if price_4h > 0 and atr_4h > 0 else 0

            avg_adx = (adx_1h + adx_4h) / 2
            avg_bb_width = ((bb_width_1h or bb_width_4h) + (bb_width_4h or bb_width_1h)) / 2
            avg_atr_pct = ((atr_pct_1h or atr_pct_4h) + (atr_pct_4h or atr_pct_1h)) / 2

            regime_name = self._classify(avg_adx, avg_bb_width, avg_atr_pct)

            # Trend direction from EMA 200
            trend_direction = "NEUTRAL"
            ema_200 = get_ind(ta_4h, "ema_200") or get_ind(ta_4h, "ema200", 0)
            price = price_4h
            if ema_200 > 0 and price > 0:
                if price > ema_200 * 1.005:
                    trend_direction = "BULLISH"
                elif price < ema_200 * 0.995:
                    trend_direction = "BEARISH"

            result = {
                "symbol": symbol,
                "regime": regime_name,
                "trend_direction": trend_direction,
                "config": REGIME_CONFIG[regime_name],
                "indicators": {
                    "adx_1h": round(adx_1h, 1),
                    "adx_4h": round(adx_4h, 1),
                    "avg_adx": round(avg_adx, 1),
                    "bb_width_1h": round(bb_width_1h, 2),
                    "bb_width_4h": round(bb_width_4h, 2),
                    "atr_pct_1h": round(atr_pct_1h, 3),
                    "atr_pct_4h": round(atr_pct_4h, 3),
                },
                "detected_at": datetime.now(timezone.utc),
                "reason": self._reason(regime_name, avg_adx, avg_bb_width, avg_atr_pct),
            }

            self._cache[symbol] = result
            return result

        except Exception as e:
            logger.warning(f"Regime detection failed for {symbol}: {e}")
            return self._default_regime(symbol, str(e))

    def _classify(self, avg_adx: float, avg_bb_width: float, avg_atr_pct: float) -> str:
        if avg_atr_pct > 3.0 or avg_bb_width > 8.0:
            return "VOLATILE_EXPANSION"
        if avg_adx > 30 and avg_bb_width >= 2.0:
            return "STRONG_TREND"
        if avg_adx < 20 and avg_bb_width < 3.0:
            return "RANGING"
        return "WEAK_TREND"

    def _reason(self, regime: str, adx: float, bb_width: float, atr_pct: float) -> str:
        return {
            "STRONG_TREND": f"ADX={adx:.0f} (strong) | BB={bb_width:.1f}% (expanding)",
            "WEAK_TREND": f"ADX={adx:.0f} (moderate) | BB={bb_width:.1f}%",
            "RANGING": f"ADX={adx:.0f} (weak) | BB={bb_width:.1f}% (tight)",
            "VOLATILE_EXPANSION": f"ATR={atr_pct:.2f}% (explosive) | BB={bb_width:.1f}%",
        }.get(regime, "Unknown")

    def _default_regime(self, symbol: str, reason: str) -> dict:
        return {
            "symbol": symbol,
            "regime": "WEAK_TREND",
            "trend_direction": "NEUTRAL",
            "config": REGIME_CONFIG["WEAK_TREND"],
            "indicators": {},
            "detected_at": datetime.now(timezone.utc),
            "reason": f"Default (fallback): {reason}",
        }

    async def get_global_regime(self, market_intel) -> dict:
        return await self.detect_regime("BTC/USDT", market_intel)

    def should_trade(self, regime_result: dict, strategy_type: str = "trend_follow") -> tuple:
        regime = regime_result.get("regime", "WEAK_TREND")
        config = REGIME_CONFIG.get(regime, REGIME_CONFIG["WEAK_TREND"])
        if config["max_leverage_multiplier"] == 0.0:
            return False, "VOLATILE_EXPANSION — standing aside", 0.0
        allowed = config["allowed_strategies"]
        if allowed and strategy_type not in allowed:
            return False, f"{regime} doesn't support {strategy_type}", config["max_leverage_multiplier"]
        return True, config["recommended_action"], config["max_leverage_multiplier"]

    # ── Macro direction gate ──────────────────────────────────────────────────

    async def refresh_macro_direction(self, market_intel) -> str:
        """
        Compute BTC macro direction from EMA20 on 4H and daily timeframes.
        Result is cached for 30 minutes and shared across all engines.

        Rules:
          BEARISH — BTC below EMA20 on BOTH 4H and daily
          BULLISH — BTC above EMA20 on BOTH 4H and daily
          NEUTRAL — mixed signals

        Effect on confidence thresholds (applied in submit_signal):
          BEARISH → LONG entries require min_confidence + 10%
          BULLISH → SHORT entries require min_confidence + 10%
          NEUTRAL → no adjustment
        """
        now = datetime.now(timezone.utc)
        if self._macro_updated_at:
            age = (now - self._macro_updated_at).total_seconds()
            if age < MACRO_CACHE_TTL:
                return self._macro_direction

        try:
            ta_4h  = await market_intel.get_technical_analysis("BTC/USDT", "4h")
            ta_1d  = await market_intel.get_technical_analysis("BTC/USDT", "1d")

            def get_ind(ta, key, default=0.0):
                if not ta:
                    return default
                return ta.get("indicators", {}).get(key) or ta.get(key) or default

            price_4h  = get_ind(ta_4h, "price") or get_ind(ta_4h, "close") or 0.0
            ema20_4h  = get_ind(ta_4h, "ema_20") or get_ind(ta_4h, "ema_21") or 0.0

            price_1d  = get_ind(ta_1d, "price") or get_ind(ta_1d, "close") or 0.0
            ema20_1d  = get_ind(ta_1d, "ema_20") or get_ind(ta_1d, "ema_21") or 0.0

            above_4h = price_4h > ema20_4h if (price_4h > 0 and ema20_4h > 0) else None
            above_1d = price_1d > ema20_1d if (price_1d > 0 and ema20_1d > 0) else None

            if above_4h is False and above_1d is False:
                direction = "BEARISH"
            elif above_4h is True and above_1d is True:
                direction = "BULLISH"
            else:
                direction = "NEUTRAL"

            if direction != self._macro_direction:
                logger.info(
                    f"[MACRO GATE] BTC macro direction changed: "
                    f"{self._macro_direction} → {direction} "
                    f"(4H price={price_4h:.2f} EMA20={ema20_4h:.2f} | "
                    f"1D price={price_1d:.2f} EMA20={ema20_1d:.2f})"
                )

            self._macro_direction = direction
            self._macro_updated_at = now
            return direction

        except Exception as e:
            logger.warning(f"[MACRO GATE] Failed to refresh macro direction: {e}")
            return self._macro_direction

    def get_btc_macro_direction(self) -> str:
        """Return the last cached BTC macro direction synchronously. 'NEUTRAL' until first refresh."""
        return self._macro_direction

    def apply_macro_confidence_gate(self, direction: str, base_confidence: float) -> tuple:
        """
        Apply the macro direction confidence penalty.

        Args:
            direction       — trade direction ("LONG" or "SHORT")
            base_confidence — engine's normal min_confidence threshold

        Returns:
            (effective_threshold, reason_str)
            reason_str is None when no penalty applies.
        """
        macro = self._macro_direction
        d = direction.upper()

        if macro == "BEARISH" and d == "LONG":
            adjusted = base_confidence + MACRO_CONFIDENCE_PENALTY
            return adjusted, f"MACRO BEARISH — LONG requires {adjusted:.0f}% confidence (base {base_confidence:.0f}% + {MACRO_CONFIDENCE_PENALTY:.0f}% penalty)"

        if macro == "BULLISH" and d == "SHORT":
            adjusted = base_confidence + MACRO_CONFIDENCE_PENALTY
            return adjusted, f"MACRO BULLISH — SHORT requires {adjusted:.0f}% confidence (base {base_confidence:.0f}% + {MACRO_CONFIDENCE_PENALTY:.0f}% penalty)"

        return base_confidence, None

    def get_stats(self) -> dict:
        result = {}
        for symbol, data in self._cache.items():
            age = (datetime.now(timezone.utc) - data["detected_at"]).total_seconds()
            result[symbol] = {
                "regime": data["regime"],
                "trend_direction": data.get("trend_direction", "NEUTRAL"),
                "reason": data.get("reason", ""),
                "age_seconds": round(age),
                "indicators": data.get("indicators", {}),
            }
        return result


_regime_engine: Optional[RegimeEngine] = None


def get_regime_engine() -> RegimeEngine:
    global _regime_engine
    if _regime_engine is None:
        _regime_engine = RegimeEngine()
    return _regime_engine
