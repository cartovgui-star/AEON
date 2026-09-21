"""
Live Chart Analysis Telegram Commands
/chart [coin] [timeframe] — full TA on any coin/timeframe
/watch                    — show what the chart scanner is watching
"""
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

VALID_TFS = {"5m", "15m", "30m", "1h", "4h", "1d"}
TF_LABEL = {"5m": "5 Min", "15m": "15 Min", "30m": "30 Min",
             "1h": "1 Hour", "4h": "4 Hour", "1d": "Daily"}


def _fmt_price(p: float) -> str:
    if p == 0:
        return "n/a"
    return f"{p:,.4f}" if p < 1 else f"{p:,.2f}"


def _bias_emoji(bias: str) -> str:
    return {"BULLISH": "🟢", "BEARISH": "🔴"}.get(bias.upper(), "⚪")


def _score_label(bull: int, bear: int) -> str:
    total = bull + bear
    if total == 0:
        return "No clear read"
    aligned = max(bull, bear)
    if aligned >= 5:
        return "HIGH CONVICTION"
    if aligned >= 3:
        return "STRONG"
    if aligned >= 2:
        return "MODERATE"
    return "WEAK"


def _format_analysis(ta: dict) -> str:
    sym       = (ta.get("symbol") or "?").replace("/USDT", "")
    tf        = ta.get("interval", "1h")
    tf_label  = TF_LABEL.get(tf, tf.upper())
    price     = ta.get("price", 0)
    bias      = ta.get("overall_bias", "NEUTRAL")
    bull      = ta.get("bullish_signals", 0)
    bear      = ta.get("bearish_signals", 0)
    ind       = ta.get("indicators", {})
    structure = ta.get("market_structure", {})
    signals   = ta.get("signals", [])

    rsi       = ind.get("rsi", 0)
    adx       = ind.get("adx", 0)
    ema_9     = ind.get("ema_9", 0)
    ema_21    = ind.get("ema_21", 0)
    ema_50    = ind.get("ema_50", 0)
    ema_200   = ind.get("ema_200")
    macd      = ind.get("macd", 0)
    macd_sig  = ind.get("macd_signal", 0)
    macd_hist = ind.get("macd_histogram", 0)
    bb_upper  = ind.get("bb_upper", 0)
    bb_lower  = ind.get("bb_lower", 0)
    atr       = ind.get("atr", 0)
    vol_ratio = ind.get("volume_ratio", 1)
    stoch_k   = ind.get("stoch_k", 50)
    struct_bias = structure.get("bias", "neutral")

    # EMA stack
    if ema_9 and ema_21 and ema_50:
        if ema_9 > ema_21 > ema_50:
            ema_stack = "9 > 21 > 50 ✅ Bullish"
        elif ema_9 < ema_21 < ema_50:
            ema_stack = "9 < 21 < 50 🔴 Bearish"
        else:
            ema_stack = "Mixed ⚪"
    else:
        ema_stack = "n/a"

    # MACD read
    if macd_hist > 0 and macd > macd_sig:
        macd_read = "Bullish crossover ✅"
    elif macd_hist < 0 and macd < macd_sig:
        macd_read = "Bearish crossover 🔴"
    elif macd_hist > 0:
        macd_read = "Above signal ↑"
    else:
        macd_read = "Below signal ↓"

    # RSI read
    if rsi < 30:
        rsi_read = f"{rsi:.0f} — Oversold 🟢"
    elif rsi > 70:
        rsi_read = f"{rsi:.0f} — Overbought 🔴"
    elif rsi < 45:
        rsi_read = f"{rsi:.0f} — Low"
    elif rsi > 55:
        rsi_read = f"{rsi:.0f} — High"
    else:
        rsi_read = f"{rsi:.0f} — Neutral"

    # ADX read
    if adx >= 35:
        adx_read = f"{adx:.0f} — Strong trend"
    elif adx >= 20:
        adx_read = f"{adx:.0f} — Trending"
    else:
        adx_read = f"{adx:.0f} — Weak / ranging"

    # Volume
    if vol_ratio >= 2.0:
        vol_read = f"{vol_ratio:.1f}x avg 🔥 High"
    elif vol_ratio >= 1.3:
        vol_read = f"{vol_ratio:.1f}x avg ↑"
    else:
        vol_read = f"{vol_ratio:.1f}x avg"

    # Bollinger
    bb_read = ""
    if price and bb_upper and bb_lower:
        if price > bb_upper:
            bb_read = "Above upper band 🔴"
        elif price < bb_lower:
            bb_read = "Below lower band 🟢"
        else:
            pct = (price - bb_lower) / (bb_upper - bb_lower) * 100
            bb_read = f"{pct:.0f}% of band"

    # Structure
    struct_map = {"bullish": "Higher highs / higher lows 🟢",
                  "bearish": "Lower highs / lower lows 🔴",
                  "neutral": "Ranging / mixed ⚪"}
    struct_read = struct_map.get(struct_bias, "n/a")

    # 200 EMA context
    ema200_line = ""
    if ema_200 and price:
        diff_pct = (price - ema_200) / ema_200 * 100
        ema200_line = f"\nEMA 200: ${_fmt_price(ema_200)} ({diff_pct:+.1f}%)"

    conviction = _score_label(bull, bear)
    b_emoji = _bias_emoji(bias)

    lines = [
        f"📊 {sym}/USDT — {tf_label}",
        "",
        f"Bias: {b_emoji} {bias}  ({conviction})",
        f"Signals: {bull} bullish / {bear} bearish",
        "",
        f"💰 Price: ${_fmt_price(price)}",
        f"ATR: ${_fmt_price(atr)}  |  Stoch K: {stoch_k:.0f}",
        "",
        "📈 INDICATORS",
        f"• RSI: {rsi_read}",
        f"• ADX: {adx_read}",
        f"• MACD: {macd_read}",
        f"• EMA Stack: {ema_stack}",
    ]
    if bb_read:
        lines.append(f"• Bollinger: {bb_read}")
    lines.append(f"• Volume: {vol_read}")
    if ema200_line:
        lines.append(f"• {ema200_line.strip()}")

    lines += [
        "",
        "🏗️ STRUCTURE",
        f"• {struct_read}",
        f"• BB Range: ${_fmt_price(bb_lower)} — ${_fmt_price(bb_upper)}",
    ]

    return "\n".join(lines)


async def handle_chart(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /chart [coin] [timeframe]"""
    import app_state

    parts = text.strip().split()
    symbol_raw = parts[1].upper() if len(parts) > 1 else "BTC"
    tf = parts[2].lower() if len(parts) > 2 else "1h"

    if not symbol_raw.endswith("/USDT"):
        symbol_full = f"{symbol_raw}/USDT"
        symbol_clean = symbol_raw
    else:
        symbol_full = symbol_raw
        symbol_clean = symbol_raw.replace("/USDT", "")

    if tf not in VALID_TFS:
        return (
            f"❌ Invalid timeframe '{tf}'\nValid: {', '.join(sorted(VALID_TFS))}",
            "chart"
        )

    try:
        ta = await app_state.market_intel.get_technical_analysis(symbol_full, tf)
    except Exception as e:
        return f"❌ Error fetching {symbol_clean}: {e}", "chart"

    if "error" in ta:
        return f"❌ {symbol_clean}: {ta['error']}", "chart"

    return _format_analysis(ta), "chart"


async def handle_watch(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /watch — show scanner watchlist and last scan time"""
    try:
        from chart_monitor import get_chart_monitor
        mon = get_chart_monitor()
        if mon is None:
            return "📊 Chart scanner not running yet.", "chart"
        info = mon.status()
        lines = [
            "📊 CHART SCANNER",
            "",
            f"Status: {'🟢 Running' if info['running'] else '🔴 Stopped'}",
            f"Interval: every {info['interval_min']} min",
            f"Last scan: {info['last_scan'] or 'not yet'}",
            f"Alerts sent today: {info['alerts_today']}",
            "",
            "Watching:",
        ]
        for coin in info["watchlist"]:
            lines.append(f"  • {coin}")
        lines.append("\n/chart BTC 4h — on-demand analysis")
        return "\n".join(lines), "chart"
    except Exception as e:
        return f"❌ Error: {e}", "chart"


CHART_HANDLERS = {
    "/watch": handle_watch,
}


async def route_chart_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    text_lower = text.lower().strip()

    if text_lower.startswith("/chart"):
        return await handle_chart(text, chat_id, context)
    if text_lower == "/watch":
        return await handle_watch(text, chat_id, context)

    return None
