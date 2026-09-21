"""
ZETA — AEON's Derivatives Desk
Funding rates, open interest, long/short ratios, liquidation heatmaps.
Answers: Who is overcrowded? Where are the liq clusters? What side will get squeezed?
"""

import logging
from typing import Any, Dict, List, Optional

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Derivatives Specialist. You live in the perp markets — funding, OI, "
    "basis, gamma. You see where the crowded trades are before they unwind. "
    "Calculated. You talk about 'the funding regime', 'OI divergence', 'liq clusters'."
)

SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]


async def analyze(db, market_intel=None, coinglass_intel=None) -> AnalysisResult:
    """
    Analyze derivatives market: funding rates, L/S ratios, OI, liquidation heatmap.
    """
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation: Optional[Recommendation] = None
    crowded_longs  = 0
    crowded_shorts = 0

    # ── 1. Funding rates across top symbols ─────────────────────────────────
    if market_intel:
        funding_data = {}
        for sym in SYMBOLS[:3]:  # BTC, ETH, SOL
            try:
                fd = await market_intel.get_current_funding_rate(sym)
                rate = fd.get("funding_rate", 0.0)
                next_time = fd.get("next_funding_time", "")
                funding_data[sym] = rate
                pct = rate * 100
                obs = f"{sym.replace('/USDT','')}: {pct:+.4f}% funding"
                if abs(rate) > 0.001:       # > 0.1% is elevated
                    obs += " ⚠️ ELEVATED"
                observations.append(obs)
                if rate > 0.001:            # high positive → longs pay, crowded long
                    crowded_longs += 1
                elif rate < -0.001:         # negative → shorts pay, crowded short
                    crowded_shorts += 1
            except Exception as e:
                logger.debug(f"[ZETA] Funding rate {sym}: {e}")
        raw["funding"] = {k: round(v * 100, 5) for k, v in funding_data.items()}

    # ── 2. Long/Short Ratio — OKX ────────────────────────────────────────────
    if market_intel:
        try:
            ls = await market_intel.get_long_short_ratio("BTC/USDT", period="1h", limit=3)
            if ls:
                latest = ls[0]
                ls_ratio = latest.get("long_short_ratio", 1.0)
                long_pct = latest.get("long_pct", 50)
                raw["ls_ratio"] = {"ratio": ls_ratio, "long_pct": long_pct}
                observations.append(
                    f"BTC L/S ratio: {ls_ratio:.2f} ({long_pct:.1f}% long)"
                )
                if long_pct > 65:
                    crowded_longs += 1
                    observations.append("Retail heavily long — vulnerable to long squeeze.")
                elif long_pct < 35:
                    crowded_shorts += 1
                    observations.append("Retail heavily short — short squeeze risk elevated.")
        except Exception as e:
            logger.debug(f"[ZETA] L/S ratio error: {e}")

    # ── 3. Open Interest Changes ─────────────────────────────────────────────
    if coinglass_intel and coinglass_intel.has_api_key:
        try:
            oi = await coinglass_intel.get_open_interest("BTC")
            if oi and not oi.get("error"):
                oi_value    = oi.get("open_interest_usd", 0)
                oi_change   = oi.get("change_24h_pct", 0)
                raw["open_interest"] = {"value": oi_value, "change_24h_pct": oi_change}
                observations.append(
                    f"BTC OI: ${oi_value/1e9:.2f}B ({oi_change:+.1f}% 24h)"
                )
                if oi_change > 15:
                    observations.append("OI surging — highly leveraged market, volatility risk elevated.")
                elif oi_change < -15:
                    observations.append("OI flushing — deleveraging event, potential bottom formation.")
        except Exception as e:
            logger.debug(f"[ZETA] OI error: {e}")

    # ── 4. Liquidation Heatmap ───────────────────────────────────────────────
    if coinglass_intel and coinglass_intel.has_api_key:
        try:
            liq = await coinglass_intel.get_liquidation_history("BTC", hours=4)
            if liq and not liq.get("error"):
                liq_longs  = liq.get("total_long_liq_usd", 0)
                liq_shorts = liq.get("total_short_liq_usd", 0)
                raw["liquidations_4h"] = {"longs": liq_longs, "shorts": liq_shorts}
                if liq_longs > 50e6:
                    observations.append(
                        f"Heavy long liquidations last 4h: ${liq_longs/1e6:.0f}M — long leverage flushed."
                    )
                if liq_shorts > 50e6:
                    observations.append(
                        f"Heavy short liquidations last 4h: ${liq_shorts/1e6:.0f}M — shorts squeezed."
                    )
        except Exception as e:
            logger.debug(f"[ZETA] Liq history error: {e}")

    # ── 5. Fallback: OKX taker L/S ratio ────────────────────────────────────
    if market_intel and not raw.get("ls_ratio"):
        try:
            taker_ls = await market_intel.get_taker_long_short_ratio("BTC/USDT", period="1h", limit=1)
            if taker_ls:
                tls = taker_ls[0].get("taker_buy_sell_ratio", 1.0)
                raw["taker_ls"] = tls
                observations.append(f"BTC taker buy/sell ratio: {tls:.3f}")
                if tls > 1.3:
                    bullish_pressure = True
                    bullish_signals  = getattr(analyze, "_bullish", 0) + 1
        except Exception as e:
            logger.debug(f"[ZETA] Taker L/S error: {e}")

    # ── 6. Signal determination ───────────────────────────────────────────────
    if not observations:
        return AnalysisResult(
            specialist="ZETA", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Derivatives data unavailable — all feeds failed."],
            raw_data=raw
        )

    raw.update({"crowded_longs": crowded_longs, "crowded_shorts": crowded_shorts})

    if crowded_longs >= 2:
        signal     = MarketSignal.BEARISH     # longs will get squeezed
        confidence = min(80, 55 + crowded_longs * 8)
        observations.append(
            f"Derivatives consensus: {crowded_longs} crowded-long signals — "
            "long squeeze conditions building."
        )
        if crowded_longs >= 3:
            recommendation = Recommendation(
                type=RecType.BLOCK_DIRECTION,
                reasoning=(
                    f"Funding rates and L/S ratio show extreme long crowding ({crowded_longs} signals). "
                    "History shows crowded longs unwind violently. Blocking new LONG signals until conditions normalize."
                ),
                confidence=0.75,
                params={"symbol": None, "direction": "LONG"},   # all symbols
                duration_hours=4,
            )

    elif crowded_shorts >= 2:
        signal     = MarketSignal.BULLISH     # shorts will get squeezed
        confidence = min(80, 55 + crowded_shorts * 8)
        observations.append(
            f"Derivatives consensus: {crowded_shorts} crowded-short signals — short squeeze risk."
        )
        if crowded_shorts >= 3:
            recommendation = Recommendation(
                type=RecType.BLOCK_DIRECTION,
                reasoning=(
                    f"Extreme short crowding detected ({crowded_shorts} signals). "
                    "Short positions face squeeze risk. Blocking new SHORT signals."
                ),
                confidence=0.72,
                params={"symbol": None, "direction": "SHORT"},
                duration_hours=4,
            )
    else:
        signal     = MarketSignal.NEUTRAL
        confidence = 55

    return AnalysisResult(
        specialist="ZETA",
        signal=signal,
        confidence=confidence,
        observations=observations,
        recommendation=recommendation,
        raw_data=raw,
    )
