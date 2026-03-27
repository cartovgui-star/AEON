"""
Quant Analyzer Command Handlers
Commands: /quant, /quant [coin]
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "AVAX/USDT", "DOGE/USDT", "LINK/USDT", "DOT/USDT",
]

SIGNAL_EMOJI = {
    "Strong Buy":  "🚀",
    "Buy":         "🟢",
    "Neutral":     "⚪",
    "Sell":        "🔴",
    "Strong Sell": "💀",
}


async def handle_quant(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """
    /quant          — scan top 10 coins, ranked by score
    /quant [coin]   — deep report for a single coin
    """
    import app_state

    parts = text.strip().split()

    # ── single coin deep report ─────────────────────────────────────────────
    if len(parts) >= 2:
        raw = parts[1].upper()
        symbol = f"{raw}/USDT" if "/" not in raw else raw

        try:
            quant = app_state.quant_analyzer
            result = await quant.analyze_coins([symbol])
            reports = result.get("ranked_reports", [])

            if not reports:
                return f"❌ Could not analyze {symbol}. Try again.", "analysis"

            r = reports[0]
            tp = r.get("trade_plan", {})
            mom = r.get("momentum", {})
            trend = r.get("trend_structure", {})
            ma = r.get("moving_averages", {})
            vol = r.get("volume", {})
            patterns = r.get("chart_patterns", {})
            levels = r.get("key_levels", {})

            sig_emoji = SIGNAL_EMOJI.get(r["signal"], "⚪")
            coin = r["symbol"].replace("/USDT", "")

            # Trend summary
            tf_summary = trend.get("tf_summary", "N/A")
            alignment = trend.get("alignment", "")

            # Momentum
            rsi = mom.get("rsi", 0)
            rsi_status = "Overbought ⚠️" if rsi > 70 else ("Oversold ⚠️" if rsi < 30 else "Normal")
            macd_cross = mom.get("macd_crossover", "None")

            # MA stack
            ma_stack = ma.get("stack", "Unknown")
            ma_bias = ma.get("bias", "neutral")

            # Volume
            obv_trend = vol.get("obv_trend", "N/A")
            vol_anomaly = vol.get("anomaly", False)

            # Key levels
            nearest_res = levels.get("nearest_resistance")
            nearest_sup = levels.get("nearest_support")

            # Chart patterns
            detected = patterns.get("detected", [])
            pattern_str = ", ".join(detected[:3]) if detected else "None"

            # Trade plan
            entry = tp.get("entry")
            stop = tp.get("stop")
            tp1 = tp.get("tp1")
            tp2 = tp.get("tp2")
            rr1 = tp.get("rr1")

            response = f"""{sig_emoji} QUANT REPORT: {coin}

💰 Price: ${r['price']:,.4f}
📊 Score: {r['score']:.1f}/10  |  Signal: {r['signal']}

📈 TREND STRUCTURE
{tf_summary}
{alignment}

🔄 MOMENTUM
RSI: {rsi:.1f} ({rsi_status})
MACD: {macd_cross}

📉 MOVING AVERAGES
Stack: {ma_stack}
Bias: {ma_bias.upper()}

📦 VOLUME
OBV Trend: {obv_trend}
Anomaly: {'⚠️ YES' if vol_anomaly else 'No'}

🎯 KEY LEVELS
Resistance: {'${:,.4f}'.format(nearest_res) if nearest_res else 'N/A'}
Support: {'${:,.4f}'.format(nearest_sup) if nearest_sup else 'N/A'}

📐 CHART PATTERNS
{pattern_str}

📋 TRADE PLAN
Entry:  {'${:,.4f}'.format(entry) if entry else 'N/A'}
Stop:   {'${:,.4f}'.format(stop) if stop else 'N/A'}
TP1:    {'${:,.4f}'.format(tp1) if tp1 else 'N/A'}
TP2:    {'${:,.4f}'.format(tp2) if tp2 else 'N/A'}
R:R:    {'{:.2f}'.format(rr1) if rr1 else 'N/A'}"""

        except Exception as e:
            logger.error(f"quant single coin error: {e}", exc_info=True)
            response = f"❌ Error analyzing {symbol}: {str(e)}"

        return response, "analysis"

    # ── multi-coin scan ─────────────────────────────────────────────────────
    try:
        quant = app_state.quant_analyzer
        result = await quant.analyze_coins(DEFAULT_SYMBOLS)
        reports = result.get("ranked_reports", [])
        watchlist = result.get("watchlist_table", [])

        if not reports:
            return "❌ Could not run quant scan. Try again.", "analysis"

        response = f"🧮 QUANT SCAN — Top {len(reports)} Setups\n\n"

        for r in reports[:8]:
            coin = r["symbol"].replace("/USDT", "")
            sig_emoji = SIGNAL_EMOJI.get(r["signal"], "⚪")
            tp = r.get("trade_plan", {})
            rr = tp.get("rr1")
            trend = r.get("trend_structure", {})
            alignment_ok = "✅" if "aligned" in trend.get("alignment", "").lower() else "⚠️"

            response += (
                f"{sig_emoji} {coin:<6} Score:{r['score']:.1f}  "
                f"{r['signal']:<12} {alignment_ok}\n"
            )
            if tp.get("entry"):
                rr_str = f"  R:R {rr:.1f}" if rr else ""
                response += f"   Entry ${tp['entry']:,.4f} → TP ${tp.get('tp1', 0):,.4f}{rr_str}\n"

        response += "\n/quant [coin] for deep report"

    except Exception as e:
        logger.error(f"quant scan error: {e}", exc_info=True)
        response = f"❌ Error running quant scan: {str(e)}"

    return response, "analysis"


QUANT_HANDLERS = {
    "/quant": handle_quant,
}


async def route_quant_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route quant commands."""
    text_lower = text.lower().strip()

    if text_lower == "/quant":
        return await handle_quant(text, chat_id, context)

    if text_lower.startswith("/quant "):
        return await handle_quant(text, chat_id, context)

    return None
