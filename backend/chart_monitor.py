"""
ChartWatchMonitor — proactive chart analysis, pushes Telegram alerts
when 3+ indicators align on 1h or 4h for top coins.

Cooldown: 2h per symbol+timeframe pair so same coin doesn't spam.
Scan interval: 20 minutes.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT",
    "LTC/USDT", "UNI/USDT", "ATOM/USDT", "NEAR/USDT", "ARB/USDT",
    "OP/USDT",  "SUI/USDT", "APT/USDT",  "INJ/USDT", "TIA/USDT",
]

TIMEFRAMES   = ["1h", "4h"]
SCAN_INTERVAL = 20 * 60        # 20 minutes
COOLDOWN_SEC  = 2 * 60 * 60   # 2 hours per symbol+tf
MIN_SIGNALS   = 3              # minimum aligned signals to alert
MIN_ADX       = 18             # below this = choppy, skip

_instance: Optional["ChartWatchMonitor"] = None


def get_chart_monitor() -> Optional["ChartWatchMonitor"]:
    return _instance


class ChartWatchMonitor:

    def __init__(self, send_fn):
        global _instance
        self._send         = send_fn          # async (chat_id, text) -> None
        self._cooldowns: dict = {}            # {symbol_tf: datetime}
        self._last_scan: Optional[str] = None
        self._alerts_today = 0
        self._today_str    = ""
        self._running      = False
        _instance = self

    def status(self) -> dict:
        return {
            "running":       self._running,
            "interval_min":  SCAN_INTERVAL // 60,
            "last_scan":     self._last_scan,
            "alerts_today":  self._alerts_today,
            "watchlist":     [s.replace("/USDT", "") for s in WATCHLIST],
        }

    async def run_loop(self) -> None:
        self._running = True
        logger.info("[ChartMonitor] Started — scanning %d coins on %s",
                    len(WATCHLIST), TIMEFRAMES)
        # Stagger startup by 60s so server is fully ready
        await asyncio.sleep(60)
        while True:
            try:
                await self._scan_all()
            except Exception as e:
                logger.error("[ChartMonitor] scan error: %s", e)
            await asyncio.sleep(SCAN_INTERVAL)

    async def _scan_all(self) -> None:
        import app_state

        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        if today != self._today_str:
            self._today_str    = today
            self._alerts_today = 0

        self._last_scan = now.strftime("%H:%M UTC")

        chat_ids = getattr(app_state, "chat_ids", set())
        if not chat_ids:
            return

        market_intel = getattr(app_state, "market_intel", None)
        if market_intel is None:
            return

        for symbol in WATCHLIST:
            for tf in TIMEFRAMES:
                try:
                    await self._check_one(market_intel, symbol, tf, now, chat_ids)
                    # Small delay between API calls to avoid hammering OKX
                    await asyncio.sleep(1.5)
                except Exception as e:
                    logger.debug("[ChartMonitor] %s/%s error: %s", symbol, tf, e)

    async def _check_one(self, market_intel, symbol: str, tf: str,
                         now: datetime, chat_ids: set) -> None:
        key = f"{symbol}:{tf}"

        # Cooldown check
        last = self._cooldowns.get(key)
        if last and (now - last).total_seconds() < COOLDOWN_SEC:
            return

        ta = await market_intel.get_technical_analysis(symbol, tf)
        if not ta or "error" in ta:
            return

        bull   = ta.get("bullish_signals", 0)
        bear   = ta.get("bearish_signals", 0)
        bias   = ta.get("overall_bias", "NEUTRAL")
        ind    = ta.get("indicators", {})
        adx    = ind.get("adx", 0) or 0
        vol    = ind.get("volume_ratio", 1) or 1

        aligned = max(bull, bear)

        # Gate: need minimum signals, real trend (ADX), and some volume activity
        if aligned < MIN_SIGNALS:
            return
        if adx < MIN_ADX:
            return
        if bias == "NEUTRAL":
            return

        # Extra conviction check for 4h — require 4+ signals
        if tf == "4h" and aligned < 4:
            return

        self._cooldowns[key] = now
        self._alerts_today  += 1

        msg = self._format_alert(ta, bull, bear, bias, aligned)
        for chat_id in list(chat_ids):
            try:
                await self._send(chat_id, msg)
            except Exception as e:
                logger.warning("[ChartMonitor] send failed chat_id=%s: %s", chat_id, e)

    def _format_alert(self, ta: dict, bull: int, bear: int,
                      bias: str, aligned: int) -> str:
        symbol    = (ta.get("symbol") or "?").replace("/USDT", "")
        tf        = ta.get("interval", "?")
        price     = ta.get("price", 0)
        ind       = ta.get("indicators", {})
        structure = ta.get("market_structure", {})

        rsi      = ind.get("rsi", 0)
        adx      = ind.get("adx", 0)
        ema_9    = ind.get("ema_9", 0)
        ema_21   = ind.get("ema_21", 0)
        ema_50   = ind.get("ema_50", 0)
        macd_h   = ind.get("macd_histogram", 0)
        macd     = ind.get("macd", 0)
        macd_sig = ind.get("macd_signal", 0)
        vol      = ind.get("volume_ratio", 1)
        atr      = ind.get("atr", 0)
        bb_upper = ind.get("bb_upper", 0)
        bb_lower = ind.get("bb_lower", 0)
        struct_b = structure.get("bias", "neutral")

        tf_labels = {"1h": "1H", "4h": "4H", "15m": "15M", "1d": "Daily"}
        tf_label  = tf_labels.get(tf, tf.upper())

        b_emoji = {"BULLISH": "🟢", "BEARISH": "🔴"}.get(bias.upper(), "⚪")
        conviction = "HIGH CONVICTION" if aligned >= 5 else "STRONG" if aligned >= 4 else "SETUP"

        def fp(p):
            if not p:
                return "n/a"
            return f"{p:,.4f}" if p < 1 else f"{p:,.2f}"

        # Build signal bullets
        bullets = []
        if ema_9 and ema_21 and ema_50:
            if ema_9 > ema_21 > ema_50:
                bullets.append("EMA stack bullish (9>21>50) ✅")
            elif ema_9 < ema_21 < ema_50:
                bullets.append("EMA stack bearish (9<21<50) 🔴")
        if macd_h > 0 and macd > macd_sig:
            bullets.append("MACD bullish crossover ✅")
        elif macd_h < 0 and macd < macd_sig:
            bullets.append("MACD bearish crossover 🔴")
        if rsi < 35:
            bullets.append(f"RSI oversold ({rsi:.0f}) 🟢")
        elif rsi > 65:
            bullets.append(f"RSI overbought ({rsi:.0f}) 🔴")
        if struct_b == "bullish":
            bullets.append("Structure: HH/HL ✅")
        elif struct_b == "bearish":
            bullets.append("Structure: LH/LL 🔴")
        if vol >= 1.5:
            bullets.append(f"Volume spike {vol:.1f}x 🔥")
        if price and bb_lower and price < bb_lower:
            bullets.append("Price below BB lower 🟢")
        elif price and bb_upper and price > bb_upper:
            bullets.append("Price above BB upper 🔴")

        lines = [
            f"📊 *{symbol}/USDT — {tf_label} {conviction}*",
            "",
            f"Bias: {b_emoji} {bias}",
            f"Signals: {bull} bullish / {bear} bearish",
            f"ADX: {adx:.0f} (trend strength)",
            "",
            f"Price: ${fp(price)}",
            f"RSI: {rsi:.0f}  |  ATR: ${fp(atr)}",
            "",
            "Signals firing:",
        ]
        for b in bullets[:5]:
            lines.append(f"• {b}")

        lines.append(f"\n/chart {symbol} {tf} — full detail")
        return "\n".join(lines)
