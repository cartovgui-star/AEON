"""
DANTE — AEON's Technical Analyst
Price action, moving averages, RSI, MACD, key levels, structure breaks.
Answers: What does the chart say? Where are the key levels? Which side does structure favor?
"""

import logging
from typing import Any, Dict, List, Optional

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Technical Analyst. You read price action like a language — structure, "
    "confluences, key levels, moving averages. You speak in 'market structure', "
    "'higher highs', 'rejection', 'confluence zones'. Disciplined. Chart-first."
)

SYMBOLS = ["BTC/USDT", "ETH/USDT"]


async def analyze(db, market_intel=None) -> AnalysisResult:
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation: Optional[Recommendation] = None
    bullish_count = 0
    bearish_count = 0

    if not market_intel:
        return AnalysisResult(
            specialist="DANTE", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Market intelligence unavailable — cannot run TA."]
        )

    for sym in SYMBOLS:
        base = sym.split("/")[0]
        try:
            df = await market_intel.get_klines(sym, timeframe="4h", limit=50)
            if df is None or len(df) < 20:
                continue

            closes  = df["close"].values
            highs   = df["high"].values
            lows    = df["low"].values
            current = float(closes[-1])

            # ── EMA 20 / 50 ──────────────────────────────────────────────────
            def ema(data, period):
                k   = 2 / (period + 1)
                result = [data[0]]
                for v in data[1:]:
                    result.append(v * k + result[-1] * (1 - k))
                return result

            ema20 = ema(closes, 20)[-1]
            ema50 = ema(closes, 50)[-1]

            raw[f"{base}_ema"] = {"ema20": round(ema20, 2), "ema50": round(ema50, 2),
                                   "price": round(current, 2)}

            price_vs_ema = "ABOVE" if current > ema20 else "BELOW"
            ema_align    = "BULLISH" if ema20 > ema50 else "BEARISH"
            observations.append(
                f"{base} 4h: ${current:,.0f} | EMA20 ${ema20:,.0f} | EMA50 ${ema50:,.0f} | "
                f"{price_vs_ema} EMA20 | EMAs {ema_align}"
            )
            if ema_align == "BULLISH" and current > ema20:
                bullish_count += 1
            elif ema_align == "BEARISH" and current < ema20:
                bearish_count += 1

            # ── RSI (14) ──────────────────────────────────────────────────────
            gains  = [max(0, closes[i] - closes[i-1]) for i in range(1, len(closes))]
            losses = [max(0, closes[i-1] - closes[i]) for i in range(1, len(closes))]
            avg_g  = sum(gains[-14:])  / 14
            avg_l  = sum(losses[-14:]) / 14
            rs     = avg_g / avg_l if avg_l > 0 else 100
            rsi    = 100 - (100 / (1 + rs))
            raw[f"{base}_rsi"] = round(rsi, 1)

            rsi_label = "OVERBOUGHT" if rsi > 70 else "OVERSOLD" if rsi < 30 else "NEUTRAL"
            observations.append(f"{base} RSI(14): {rsi:.1f} — {rsi_label}")

            if rsi > 72:
                bearish_count += 1
            elif rsi < 28:
                bullish_count += 1

            # ── Recent structure (HH/HL vs LH/LL) ────────────────────────────
            last_10_highs = highs[-10:]
            last_10_lows  = lows[-10:]
            recent_hh = last_10_highs[-1] > max(last_10_highs[:-1])
            recent_ll = last_10_lows[-1]  < min(last_10_lows[:-1])
            recent_hl = last_10_lows[-1]  > min(last_10_lows[:-3])

            if recent_hh and recent_hl:
                structure = "BULLISH (HH+HL)"
                bullish_count += 1
            elif recent_ll and not recent_hl:
                structure = "BEARISH (LL+LH)"
                bearish_count += 1
            else:
                structure = "RANGING"

            raw[f"{base}_structure"] = structure
            observations.append(f"{base} market structure: {structure}")

            # ── Key level: distance from recent swing high/low ────────────────
            swing_high = max(highs[-20:])
            swing_low  = min(lows[-20:])
            dist_high  = (swing_high - current) / current * 100
            dist_low   = (current - swing_low)  / current * 100
            raw[f"{base}_levels"] = {
                "swing_high": round(swing_high, 2),
                "swing_low":  round(swing_low,  2),
                "pct_from_high": round(dist_high, 2),
                "pct_from_low":  round(dist_low,  2),
            }
            observations.append(
                f"{base} swing levels: high ${swing_high:,.0f} ({dist_high:.1f}% away) | "
                f"low ${swing_low:,.0f} ({dist_low:.1f}% away)"
            )

        except Exception as e:
            logger.debug(f"[DANTE] TA for {sym}: {e}")

    # ── Signal ────────────────────────────────────────────────────────────────
    if not observations:
        return AnalysisResult(
            specialist="DANTE", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Technical analysis failed — no chart data available."]
        )

    net = bullish_count - bearish_count
    raw["ta_net"] = net

    if net >= 3:
        signal     = MarketSignal.BULLISH
        confidence = min(80, 55 + net * 6)
        observations.append(f"TA consensus: BULLISH ({bullish_count} signals vs {bearish_count} bearish)")
        if net >= 4:
            recommendation = Recommendation(
                type=RecType.BLOCK_DIRECTION,
                reasoning=(
                    f"Technical analysis shows strong bearish confluence ({bearish_count} signals). "
                    "Price below EMA20, bearish structure, and RSI divergence suggest avoiding SHORT entries "
                    "that go against the bullish TA read — countertrend shorts have poor edge here."
                ),
                confidence=0.65,
                params={"symbol": "BTC/USDT", "direction": "SHORT"},
                duration_hours=4,
            )
    elif net <= -3:
        signal     = MarketSignal.BEARISH
        confidence = min(80, 55 + abs(net) * 6)
        observations.append(f"TA consensus: BEARISH ({bearish_count} signals vs {bullish_count} bullish)")
        if net <= -4:
            recommendation = Recommendation(
                type=RecType.BLOCK_DIRECTION,
                reasoning=(
                    f"Technical analysis shows strong bearish confluence ({bearish_count} signals). "
                    "Price below EMAs, bearish structure, and high RSI indicate distribution phase. "
                    "Blocking new LONG entries until structure improves."
                ),
                confidence=0.68,
                params={"symbol": "BTC/USDT", "direction": "LONG"},
                duration_hours=4,
            )
    else:
        signal     = MarketSignal.NEUTRAL
        confidence = 52

    return AnalysisResult(
        specialist="DANTE",
        signal=signal,
        confidence=confidence,
        observations=observations,
        recommendation=recommendation,
        raw_data=raw,
    )
