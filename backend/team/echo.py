"""
ECHO — AEON's Sentiment Analyst
Fear/greed, social signals, news sentiment, behavioral finance, retail positioning.
Answers: What is the crowd feeling? When is the crowd dangerously wrong?
"""

import logging
from typing import Any, Dict, List, Optional

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Sentiment Analyst. You read the crowd — their fear, their greed, "
    "their narratives. You know that sentiment extremes are the best contrarian signals. "
    "You reference fear/greed, social dominance, and 'the crowd's position'."
)


async def analyze(db, market_intel=None) -> AnalysisResult:
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation: Optional[Recommendation] = None
    bullish_signals = 0
    bearish_signals = 0

    # ── 1. Fear & Greed (primary sentiment indicator) ────────────────────────
    try:
        from sentiment_analyzer import SentimentAnalyzer
        sa = SentimentAnalyzer()
        fg = await sa.get_fear_greed()
        fg_val   = fg.get("value", 50)
        fg_label = fg.get("label", "Neutral")
        fg_prev  = fg.get("previous_value")
        raw["fear_greed"] = {"value": fg_val, "label": fg_label, "prev": fg_prev}

        observations.append(f"Fear & Greed: {fg_val}/100 — {fg_label}")
        if fg_prev:
            delta = fg_val - int(fg_prev)
            observations.append(f"F&G momentum: {delta:+d} from yesterday ({fg_prev})")
            if delta > 15:
                bearish_signals += 1   # rapidly greedy = caution
            elif delta < -15:
                bullish_signals += 1   # rapidly fearful = opportunity

        # Contrarian signals at extremes
        if fg_val > 80:
            bearish_signals += 2
            observations.append("EXTREME GREED — historically precedes corrections. Contrarian SHORT signal.")
        elif fg_val > 65:
            bearish_signals += 1
        elif fg_val < 20:
            bullish_signals += 2
            observations.append("EXTREME FEAR — historically presents buying opportunities. Contrarian LONG signal.")
        elif fg_val < 35:
            bullish_signals += 1

    except Exception as e:
        logger.debug(f"[ECHO] Fear/greed failed: {e}")

    # ── 2. News sentiment ─────────────────────────────────────────────────────
    try:
        from news_intel import NewsIntel
        ni   = NewsIntel()
        news = await ni.get_latest_news(limit=20)
        if news:
            pos = sum(1 for n in news if n.get("sentiment") == "positive")
            neg = sum(1 for n in news if n.get("sentiment") == "negative")
            neu = len(news) - pos - neg
            sentiment_ratio = pos / max(pos + neg, 1)
            raw["news"] = {"positive": pos, "negative": neg, "neutral": neu,
                          "ratio": round(sentiment_ratio, 3)}
            observations.append(
                f"News sentiment: {pos} positive / {neg} negative / {neu} neutral "
                f"({sentiment_ratio*100:.0f}% positive)"
            )
            if sentiment_ratio > 0.75:
                bearish_signals += 1   # overwhelmingly positive news = priced in
                observations.append("News is overwhelmingly positive — 'buy the rumor, sell the news' risk.")
            elif sentiment_ratio < 0.3:
                bullish_signals += 1   # very negative news = oversold sentiment
                observations.append("News is predominantly negative — sentiment may be overcorrecting.")
    except Exception as e:
        logger.debug(f"[ECHO] News sentiment failed: {e}")

    # ── 3. Composite sentiment score ──────────────────────────────────────────
    try:
        from sentiment_analyzer import SentimentAnalyzer
        sa = SentimentAnalyzer()
        composite = await sa.get_composite_sentiment("BTC")
        if composite and not composite.get("error"):
            score     = composite.get("composite_score", 0.5)
            sentiment = composite.get("overall_sentiment", "neutral")
            raw["composite"] = {"score": score, "sentiment": sentiment}
            observations.append(f"Composite sentiment: {sentiment} (score: {score:.2f})")
            if score > 0.7:
                bearish_signals += 1   # very positive composite = contrarian warn
            elif score < 0.3:
                bullish_signals += 1
    except Exception as e:
        logger.debug(f"[ECHO] Composite sentiment failed: {e}")

    # ── 4. Signal ─────────────────────────────────────────────────────────────
    if not observations:
        return AnalysisResult(
            specialist="ECHO", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Sentiment feeds unavailable."]
        )

    net = bullish_signals - bearish_signals
    raw["net_signal"] = net

    fg_val = raw.get("fear_greed", {}).get("value", 50)

    if net >= 2:
        # Contrarian bullish — crowd is too fearful
        signal     = MarketSignal.BULLISH
        confidence = min(75, 50 + net * 8)
    elif net <= -2:
        # Contrarian bearish — crowd is too greedy
        signal     = MarketSignal.BEARISH
        confidence = min(75, 50 + abs(net) * 8)
        if fg_val > 80 and net <= -3:
            recommendation = Recommendation(
                type=RecType.BLOCK_DIRECTION,
                reasoning=(
                    f"Sentiment at extreme greed ({fg_val}/100) with {abs(net)} bearish signals. "
                    "Historically, extreme greed precedes significant corrections. "
                    "Blocking new LONG signals until sentiment normalizes."
                ),
                confidence=0.73,
                params={"symbol": None, "direction": "LONG"},
                duration_hours=6,
            )
    else:
        signal     = MarketSignal.NEUTRAL
        confidence = 50

    return AnalysisResult(
        specialist="ECHO",
        signal=signal,
        confidence=confidence,
        observations=observations,
        recommendation=recommendation,
        raw_data=raw,
    )
