"""
VEGA — AEON's On-Chain Analyst
Blockchain data, whale movements, exchange flows, network health.
Answers: Where is smart money moving? Are whales accumulating or distributing?
"""

import logging
from typing import Any, Dict, List

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's On-Chain Analyst. You read the blockchain like a ledger of truth — "
    "every wallet, every flow tells a story. You speak about smart money, "
    "exchange inflows, whale accumulation. Confident. Investigative. Follow the coins."
)


async def analyze(db, market_intel=None) -> AnalysisResult:
    """
    Pull on-chain data: whale activity, exchange flows, network health, fear/greed.
    """
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation = None
    bearish_signals = 0
    bullish_signals = 0

    # ── 1. Fear & Greed Index ────────────────────────────────────────────────
    try:
        from sentiment_analyzer import SentimentAnalyzer
        sa = SentimentAnalyzer()
        fg = await sa.get_fear_greed()
        fg_value = fg.get("value", 50)
        fg_label = fg.get("label", "Neutral")
        raw["fear_greed"] = {"value": fg_value, "label": fg_label}
        observations.append(f"Fear & Greed Index: {fg_value}/100 — {fg_label}")
        if fg_value < 25:
            bearish_signals += 2
            observations.append("Extreme Fear — historically good accumulation zone for smart money.")
        elif fg_value > 75:
            bearish_signals += 1
            observations.append("Extreme Greed — retail FOMO often precedes distribution phases.")
        elif fg_value > 60:
            bullish_signals += 1
    except Exception as e:
        logger.debug(f"[VEGA] Fear/greed fetch failed: {e}")

    # ── 2. Whale & Exchange Flow Estimates ───────────────────────────────────
    try:
        from news_intel import NewsIntel
        ni = NewsIntel()

        whale_summary = await ni.get_whale_summary()
        if whale_summary and not whale_summary.get("error"):
            net_flow = whale_summary.get("net_flow_usd", 0)
            whale_count = whale_summary.get("large_tx_count", 0)
            raw["whale"] = {"net_flow_usd": net_flow, "tx_count": whale_count}
            flow_str = f"${abs(net_flow)/1e6:.1f}M" if abs(net_flow) > 1e6 else f"${abs(net_flow):,.0f}"
            direction = "inflow to exchanges" if net_flow > 0 else "outflow from exchanges"
            observations.append(
                f"Whale activity: {whale_count} large txns | Net {flow_str} {direction}"
            )
            if net_flow > 5e6:      # big inflows = selling pressure
                bearish_signals += 2
                observations.append("Large exchange inflows detected — whales may be positioning to sell.")
            elif net_flow < -5e6:   # outflows = accumulation
                bullish_signals += 2
                observations.append("Exchange outflows dominant — smart money moving to cold storage (accumulation signal).")

        exchange_flow = await ni.get_exchange_flow_estimate()
        if exchange_flow and not exchange_flow.get("error"):
            sentiment = exchange_flow.get("flow_sentiment", "neutral")
            raw["exchange_flow"] = exchange_flow
            if sentiment == "bearish":
                bearish_signals += 1
            elif sentiment == "bullish":
                bullish_signals += 1

    except Exception as e:
        logger.debug(f"[VEGA] Whale data fetch failed: {e}")

    # ── 3. BTC On-Chain Stats ────────────────────────────────────────────────
    try:
        from news_intel import NewsIntel
        ni = NewsIntel()
        btc_chain = await ni.get_btc_onchain_stats()
        if btc_chain and not btc_chain.get("error"):
            hash_rate = btc_chain.get("hash_rate_th", 0)
            mempool   = btc_chain.get("mempool_size", 0)
            raw["btc_chain"] = {"hash_rate": hash_rate, "mempool": mempool}
            if hash_rate:
                observations.append(f"BTC network: hash rate {hash_rate:.0f} TH/s | mempool {mempool:,} txns")
                if hash_rate > 500:
                    bullish_signals += 1   # high hash rate = miner confidence
    except Exception as e:
        logger.debug(f"[VEGA] BTC on-chain stats failed: {e}")

    # ── 4. DeFi TVL via DefiLlama ────────────────────────────────────────────
    try:
        from additional_data import AdditionalDataFetcher
        adf = AdditionalDataFetcher()
        tvl_data = await adf.get_defi_llama_tvl()
        if tvl_data and "total_tvl" in tvl_data:
            tvl = tvl_data["total_tvl"]
            tvl_change = tvl_data.get("change_24h", 0)
            raw["defi_tvl"] = {"total": tvl, "change_24h": tvl_change}
            observations.append(
                f"DeFi TVL: ${tvl/1e9:.1f}B ({tvl_change:+.1f}% 24h)"
            )
            if tvl_change > 3:
                bullish_signals += 1
            elif tvl_change < -5:
                bearish_signals += 1
    except Exception as e:
        logger.debug(f"[VEGA] DeFi TVL failed: {e}")

    # ── 5. News sentiment around on-chain topics ─────────────────────────────
    try:
        from news_intel import NewsIntel
        ni = NewsIntel()
        news = await ni.get_latest_news(limit=10, filter_coin="BTC")
        if news:
            positive = sum(1 for n in news if n.get("sentiment") == "positive")
            negative = sum(1 for n in news if n.get("sentiment") == "negative")
            raw["news_sentiment"] = {"positive": positive, "negative": negative, "total": len(news)}
            observations.append(f"BTC news: {positive} positive / {negative} negative (last {len(news)} items)")
            if positive > negative * 2:
                bullish_signals += 1
            elif negative > positive * 2:
                bearish_signals += 1
    except Exception as e:
        logger.debug(f"[VEGA] News sentiment failed: {e}")

    # ── 6. Determine signal ──────────────────────────────────────────────────
    if not observations:
        observations.append("On-chain data unavailable — all external feeds failed.")
        return AnalysisResult(
            specialist="VEGA", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=observations, raw_data=raw
        )

    net = bullish_signals - bearish_signals
    raw["net_signal"] = net

    if net >= 3:
        signal     = MarketSignal.BULLISH
        confidence = min(85, 55 + net * 8)
    elif net <= -3:
        signal     = MarketSignal.BEARISH
        confidence = min(85, 55 + abs(net) * 8)
        # Strong bearish on-chain → recommend avoiding longs on BTC
        if net <= -4:
            recommendation = Recommendation(
                type=RecType.BLOCK_DIRECTION,
                reasoning=(
                    f"On-chain bearish signals ({abs(net)} indicators) — "
                    "exchange inflows, whale distribution, and sentiment all point to distribution. "
                    "Blocking LONG signals on BTC until chain data improves."
                ),
                confidence=0.72,
                params={"symbol": "BTC/USDT", "direction": "LONG"},
                duration_hours=6,
            )
    elif net <= -1:
        signal     = MarketSignal.CAUTION
        confidence = 55
    else:
        signal     = MarketSignal.NEUTRAL
        confidence = 50

    return AnalysisResult(
        specialist="VEGA",
        signal=signal,
        confidence=confidence,
        observations=observations,
        recommendation=recommendation,
        raw_data=raw,
    )
