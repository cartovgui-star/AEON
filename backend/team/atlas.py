"""
ATLAS — AEON's Macro Economist
Institutional flows, regulatory news, macro regime, DXY correlation, ETF data.
Answers: What is the macro backdrop? Are institutions buying or exiting?
"""

import logging
from typing import Any, Dict, List, Optional

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Macro Economist. You see the big picture — institutional flows, "
    "regulatory winds, macro correlations. You reference 'the macro regime', "
    "'institutional positioning', 'risk-on/risk-off'. Measured. Always zoomed out."
)


async def analyze(db, market_intel=None) -> AnalysisResult:
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation: Optional[Recommendation] = None
    risk_on  = 0
    risk_off = 0

    # ── 1. Macro/institutional news ───────────────────────────────────────────
    try:
        from news_intel import NewsIntel
        ni = NewsIntel()

        # Full news feed for macro keywords
        news = await ni.get_latest_news(limit=30)
        if news:
            macro_kw   = ["etf", "sec", "fed", "rate", "regulate", "institution", "blackrock",
                         "fidelity", "bitcoin reserve", "government", "treasury", "ban", "approve"]
            macro_news = [n for n in news if any(k in (n.get("title","") + n.get("body","")).lower()
                                                  for k in macro_kw)]
            pos_macro  = sum(1 for n in macro_news if n.get("sentiment") == "positive")
            neg_macro  = sum(1 for n in macro_news if n.get("sentiment") == "negative")
            raw["macro_news"] = {"total": len(macro_news), "positive": pos_macro, "negative": neg_macro}

            if macro_news:
                observations.append(
                    f"Macro/institutional news: {len(macro_news)} items | "
                    f"{pos_macro} positive / {neg_macro} negative"
                )
                if pos_macro > neg_macro * 2:
                    risk_on += 1
                    observations.append("Institutional news predominantly positive — risk-on sentiment.")
                elif neg_macro > pos_macro * 2:
                    risk_off += 1
                    observations.append("Regulatory/macro headwinds detected — risk-off pressure.")

    except Exception as e:
        logger.debug(f"[ATLAS] News analysis failed: {e}")

    # ── 2. BTC dominance check (macro risk proxy) ─────────────────────────────
    try:
        from additional_data import AdditionalDataFetcher
        adf    = AdditionalDataFetcher()
        btc_chain = await adf.get_blockchain_btc_stats()
        if btc_chain and not btc_chain.get("error"):
            dominance = btc_chain.get("dominance_pct") or btc_chain.get("market_cap_dominance")
            if dominance:
                raw["btc_dominance"] = dominance
                observations.append(f"BTC dominance: {dominance:.1f}%")
                if dominance > 55:
                    risk_off += 1   # high dominance = risk-off (alt selling)
                    observations.append("High BTC dominance — alts being sold, risk-off rotation into BTC.")
                elif dominance < 45:
                    risk_on += 1    # low dominance = risk-on (alt season)
                    observations.append("Low BTC dominance — risk-on, alt season conditions.")
    except Exception as e:
        logger.debug(f"[ATLAS] BTC dominance failed: {e}")

    # ── 3. DeFi TVL macro signal ──────────────────────────────────────────────
    try:
        from additional_data import AdditionalDataFetcher
        adf = AdditionalDataFetcher()
        tvl_data = await adf.get_defi_llama_tvl()
        if tvl_data and "total_tvl" in tvl_data:
            tvl        = tvl_data["total_tvl"]
            tvl_change = tvl_data.get("change_7d", tvl_data.get("change_24h", 0))
            raw["defi_tvl"] = {"total_b": round(tvl / 1e9, 2), "change_7d": tvl_change}
            observations.append(f"DeFi TVL: ${tvl/1e9:.1f}B ({tvl_change:+.1f}% 7d)")
            if tvl_change > 8:
                risk_on  += 1
            elif tvl_change < -10:
                risk_off += 1
    except Exception as e:
        logger.debug(f"[ATLAS] TVL failed: {e}")

    # ── 4. Current market regime from AEON ────────────────────────────────────
    try:
        regime_doc = await db.current_market_regime.find_one({})
        if regime_doc:
            regime    = regime_doc.get("regime", "unknown")
            macro_dir = regime_doc.get("macro_direction", "neutral")
            raw["aeon_regime"] = {"regime": regime, "macro": macro_dir}
            observations.append(f"AEON regime: {regime} | Macro direction: {macro_dir}")
            if macro_dir in ("bullish", "BULLISH"):
                risk_on  += 1
            elif macro_dir in ("bearish", "BEARISH"):
                risk_off += 1
    except Exception as e:
        logger.debug(f"[ATLAS] Regime read failed: {e}")

    # ── 5. Web intelligence macro scan ────────────────────────────────────────
    try:
        web_doc = await db.trading_insights.find_one({}, sort=[("created_at", -1)])
        if web_doc:
            web_sentiment = web_doc.get("overall_sentiment", "neutral")
            raw["web_intel"] = web_sentiment
            observations.append(f"Web intelligence: {web_sentiment}")
            if "bull" in str(web_sentiment).lower():
                risk_on += 1
            elif "bear" in str(web_sentiment).lower():
                risk_off += 1
    except Exception as e:
        logger.debug(f"[ATLAS] Web intel failed: {e}")

    # ── 6. Signal ─────────────────────────────────────────────────────────────
    if not observations:
        return AnalysisResult(
            specialist="ATLAS", signal=MarketSignal.NEUTRAL, confidence=25,
            observations=["Macro data feeds unavailable."]
        )

    net = risk_on - risk_off
    raw["macro_net"] = net

    if net >= 2:
        signal     = MarketSignal.BULLISH
        confidence = min(78, 55 + net * 7)
    elif net <= -2:
        signal     = MarketSignal.BEARISH
        confidence = min(78, 55 + abs(net) * 7)
        if net <= -3:
            recommendation = Recommendation(
                type=RecType.BLOCK_DIRECTION,
                reasoning=(
                    f"Macro backdrop is risk-off ({abs(net)} bearish signals). "
                    "Regulatory pressure, institutional outflows, and macro headwinds "
                    "create unfavorable conditions for long exposure."
                ),
                confidence=0.70,
                params={"symbol": None, "direction": "LONG"},
                duration_hours=8,
            )
    else:
        signal     = MarketSignal.NEUTRAL
        confidence = 52

    return AnalysisResult(
        specialist="ATLAS",
        signal=signal,
        confidence=confidence,
        observations=observations,
        recommendation=recommendation,
        raw_data=raw,
    )
