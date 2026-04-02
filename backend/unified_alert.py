"""
Unified Alert System — single point of control for all Telegram messages.

Levels:
  SIGNAL  — trade signals, routed through SignalDeduplicator
  TRADE   — trade opens/closes, always sent immediately
  RISK    — risk warnings, always sent immediately, prepend ⚠️ RISK ALERT
  SYSTEM  — system events, always sent immediately, prepend 🔴 SYSTEM
  INFO    — informational, batched every 30 min into single summary
  DEBUG   — only sent if DEBUG_ALERTS=true in env, otherwise silently dropped
"""

import asyncio
import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Awaitable, List, Optional, Set

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

LEVEL_EMOJI = {
    "SIGNAL": "📡",
    "TRADE":  "⚡",
    "RISK":   "⚠️",
    "SYSTEM": "🔴",
    "INFO":   "ℹ️",
    "DEBUG":  "🔧",
}

_DEBUG_ALERTS = os.environ.get("DEBUG_ALERTS", "").lower() in ("true", "1", "yes")
_RATE_LIMIT_MSGS = 15   # max messages per window
_RATE_LIMIT_SEC  = 60   # window in seconds
_INFO_BATCH_SEC  = 1800 # flush INFO queue every 30 min


# ── AeonPersona ───────────────────────────────────────────────────────────────

class AeonPersona:
    """
    Static factory methods for AEON's Telegram message templates.
    Tone: cold, precise, clinical — Bloomberg terminal with a personality.
    No emojis in body text. Numbers formatted with commas. R:R when available.
    """

    @staticmethod
    def position_opened(
        symbol: str, direction: str, price: float, sl: float, tp: float,
        leverage: int, engine: str, rr: Optional[float] = None
    ):
        """Returns (title, body) for trade open."""
        title = "POSITION INITIATED"
        sl_dist  = abs(price - sl)
        tp_dist  = abs(tp - price)
        rr_val   = tp_dist / sl_dist if sl_dist > 0 else 0.0
        rr_str   = f"R:R 1:{rr_val:.1f}" if rr is None else f"R:R 1:{rr:.1f}"
        body = (
            f"{symbol} · {direction.upper()} · ${price:,.2f}\n"
            f"SL: ${sl:,.2f} | TP: ${tp:,.2f}\n"
            f"{rr_str} · {leverage}x leverage"
        )
        return title, body

    @staticmethod
    def position_closed(
        symbol: str, direction: str, entry: float, exit_price: float,
        pnl_pct: float, pnl_usd: float, reason: str, engine: str
    ):
        """Returns (title, body) for trade close."""
        pnl_sign  = "+" if pnl_usd >= 0 else ""
        outcome   = "WIN" if pnl_usd >= 0 else "LOSS"
        title     = f"POSITION CLOSED — {outcome}"
        body = (
            f"{symbol} · {direction.upper()}\n"
            f"Entry: ${entry:,.2f} | Exit: ${exit_price:,.2f}\n"
            f"PnL: {pnl_sign}{pnl_usd:,.2f} USD ({pnl_sign}{pnl_pct:.2f}%)\n"
            f"Reason: {reason}"
        )
        return title, body

    @staticmethod
    def signal_confirmed(
        symbol: str, direction: str, confidence: float, score: float, engine: str
    ):
        """Returns (title, body) for confirmed signal."""
        conf_label = "HIGH" if confidence >= 80 else "MEDIUM" if confidence >= 65 else "LOW"
        title = "SIGNAL CONFIRMED"
        body = (
            f"{symbol} · {direction.upper()}\n"
            f"Confidence: {conf_label} · Score: {score:.0f}/100\n"
            f"Awaiting execution gate..."
        )
        return title, body

    @staticmethod
    def quant_block(
        symbol: str, direction: str, score: float, threshold: float,
        reason: str, engine: str
    ):
        """Returns (title, body) for execution block."""
        title = "EXECUTION BLOCKED"
        body = (
            f"{symbol} {direction.upper()} rejected\n"
            f"Quant score: {score:.0f}/100 (threshold: {threshold:.0f})\n"
            f"Reason: {reason}\n"
            f"No position opened."
        )
        return title, body

    @staticmethod
    def risk_drawdown(account_id: str, current_pnl_pct: float, threshold_pct: float):
        """Returns (title, body) for drawdown breach."""
        title = "DRAWDOWN THRESHOLD BREACHED"
        body = (
            f"Account {account_id} · {current_pnl_pct:+.1f}% today\n"
            f"Threshold: {threshold_pct:+.1f}%\n"
            f"Consider reducing exposure."
        )
        return title, body

    @staticmethod
    def liquidation_warning(
        symbol: str, direction: str, unrealized_loss_pct: float, margin_remaining: float
    ):
        """Returns (title, body) for liquidation proximity."""
        title = "LIQUIDATION PROXIMITY WARNING"
        body = (
            f"{symbol} · {direction.upper()}\n"
            f"Unrealized loss: {unrealized_loss_pct:.1f}% of margin\n"
            f"Margin remaining: ${margin_remaining:,.2f}\n"
            f"Position at risk. Review immediately."
        )
        return title, body

    @staticmethod
    def win_rate_alert(
        engine: str, win_rate: float, sample_size: int, consecutive_losses: int
    ):
        """Returns (title, body) for win rate degradation."""
        title = "WIN RATE DEGRADATION"
        body = (
            f"Engine: {engine}\n"
            f"Win rate: {win_rate:.1f}% (last {sample_size} trades)\n"
            f"Consecutive losses: {consecutive_losses}\n"
            f"Performance below threshold. Monitoring."
        )
        return title, body

    @staticmethod
    def engine_offline(engine_name: str, minutes_silent: int):
        """Returns (title, body) for silent engine alert."""
        title = "ENGINE SIGNAL SILENCE"
        body = (
            f"Engine: {engine_name}\n"
            f"Last signal: {minutes_silent} minutes ago\n"
            f"No activity detected. Check engine status."
        )
        return title, body

    @staticmethod
    def daily_summary(
        trades: int, wins: int, losses: int, net_pnl_usd: float,
        best_trade: str, worst_trade: str, quant_blocks: int, engines_active: int
    ):
        """Returns (title, body) for daily summary."""
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        pnl_sign = "+" if net_pnl_usd >= 0 else ""
        title    = "DAILY PERFORMANCE SUMMARY"
        body = (
            f"Trades: {trades} | Wins: {wins} | Losses: {losses}\n"
            f"Win rate: {win_rate:.1f}%\n"
            f"Net PnL: {pnl_sign}${net_pnl_usd:,.2f}\n"
            f"Best: {best_trade}\n"
            f"Worst: {worst_trade}\n"
            f"Quant blocks: {quant_blocks} | Engines active: {engines_active}"
        )
        return title, body

    @staticmethod
    def execution_failure(symbol: str, direction: str, reason: str, engine: str):
        """Returns (title, body) for execution failure."""
        title = "EXECUTION FAILURE"
        body = (
            f"{symbol} · {direction.upper()}\n"
            f"Engine: {engine}\n"
            f"Reason: {reason}\n"
            f"Position not opened."
        )
        return title, body


# ── Rate limiter (token bucket per chat_id) ───────────────────────────────────

class _TokenBucket:
    """Simple token bucket — max N messages per window_sec."""

    def __init__(self, max_msgs: int, window_sec: int):
        self._max     = max_msgs
        self._window  = window_sec
        # {chat_id: deque of send timestamps}
        self._history: dict = {}

    def allowed(self, chat_id: int) -> bool:
        now  = datetime.now(timezone.utc).timestamp()
        hist = self._history.setdefault(chat_id, deque())
        # Evict old entries
        cutoff = now - self._window
        while hist and hist[0] < cutoff:
            hist.popleft()
        if len(hist) >= self._max:
            return False
        hist.append(now)
        return True


# ── UnifiedAlerter ────────────────────────────────────────────────────────────

class UnifiedAlerter:
    """
    Single dispatch point for all Telegram alerts.
    Wire via init_alerter() from server.py.
    """

    def __init__(self):
        self._db              = None
        self._chat_ids: Set[int] = set()
        self._send_fn         = None   # async (chat_id, text) -> None
        self._deduplicator    = None
        self._rate_limiter    = _TokenBucket(_RATE_LIMIT_MSGS, _RATE_LIMIT_SEC)
        self._info_queue: List[str] = []
        self._info_lock       = asyncio.Lock()
        self._batcher_running = False

    # ── Core send ─────────────────────────────────────────────────────────────

    async def send(
        self,
        level: str,
        title: str,
        body: str,
        pair:   Optional[str] = None,
        engine: Optional[str] = None,
        suppress_if_duplicate: bool = True,
    ) -> bool:
        """
        Dispatch an alert.
        Returns True if message was sent (or queued for INFO), False if suppressed.
        """
        level = level.upper()

        # Drop DEBUG unless explicitly enabled
        if level == "DEBUG" and not _DEBUG_ALERTS:
            return False

        # Signal-level dedup
        if level == "SIGNAL" and suppress_if_duplicate and self._deduplicator and pair and engine:
            direction = self._parse_direction(title, body)
            if direction:
                allowed, reason = await self._deduplicator.check(pair, direction, engine)
                if not allowed:
                    await self._deduplicator.log_suppression(pair, direction, engine, reason)
                    logger.debug(f"[UnifiedAlert] Suppressed SIGNAL {pair} {direction}: {reason}")
                    return False
                # Record it
                await self._deduplicator.record(pair, direction, engine)

        text = self._format(level, title, body, pair, engine)

        # INFO goes to batch queue
        if level == "INFO":
            async with self._info_lock:
                self._info_queue.append(text)
            return True

        # All other levels send immediately
        await self._dispatch(text)
        return True

    async def _dispatch(self, text: str) -> None:
        """Send text to all registered chat IDs, respecting rate limiter."""
        if not self._send_fn:
            logger.warning("[UnifiedAlert] send_fn not wired — dropping message")
            return
        for chat_id in list(self._chat_ids):
            if self._rate_limiter.allowed(chat_id):
                try:
                    await self._send_fn(chat_id, text)
                except Exception as exc:
                    logger.error(f"[UnifiedAlert] dispatch to {chat_id} failed: {exc}")
            else:
                logger.warning(f"[UnifiedAlert] Rate limit hit for chat_id={chat_id}, dropping msg")

    # ── Formatting ────────────────────────────────────────────────────────────

    def _format(
        self, level: str, title: str, body: str,
        pair: Optional[str], engine: Optional[str]
    ) -> str:
        emoji     = LEVEL_EMOJI.get(level, "📨")
        now_str   = datetime.now(timezone.utc).strftime("%H:%M UTC")
        meta_parts = []
        if engine:
            meta_parts.append(f"Engine: {engine}")
        if pair:
            meta_parts.append(pair.upper())
        meta_parts.append(now_str)
        meta_line = " | ".join(meta_parts)

        return (
            f"{emoji} {title}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{body}\n\n"
            f"{meta_line}"
        )

    # ── INFO batcher ──────────────────────────────────────────────────────────

    async def start_info_batcher(self) -> None:
        """Background loop — flush INFO queue every 30 min."""
        if self._batcher_running:
            return
        self._batcher_running = True
        while True:
            await asyncio.sleep(_INFO_BATCH_SEC)
            await self._flush_info_queue()

    async def _flush_info_queue(self) -> None:
        async with self._info_lock:
            if not self._info_queue:
                return
            items = list(self._info_queue)
            self._info_queue.clear()

        summary = (
            f"ℹ️ INFO SUMMARY — {len(items)} update(s)\n"
            f"━━━━━━━━━━━━━━━\n"
        ) + "\n\n".join(items)
        await self._dispatch(summary)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_direction(title: str, body: str) -> Optional[str]:
        """Best-effort direction extraction from title+body."""
        combined = (title + " " + body).upper()
        if "LONG" in combined:
            return "LONG"
        if "SHORT" in combined:
            return "SHORT"
        return None


# ── Module-level singleton ────────────────────────────────────────────────────

alerter = UnifiedAlerter()


def init_alerter(db, chat_ids: Set[int], send_fn, signal_deduplicator) -> UnifiedAlerter:
    """
    Wire the singleton with runtime dependencies.
    Called from server.py lifespan after all components are ready.
    """
    alerter._db           = db
    alerter._chat_ids     = chat_ids
    alerter._send_fn      = send_fn
    alerter._deduplicator = signal_deduplicator
    # Start INFO batcher as background task
    asyncio.ensure_future(alerter.start_info_batcher())
    logger.info("[UnifiedAlert] Alerter initialized and INFO batcher scheduled")
    return alerter


async def send_alert(
    level: str,
    title: str,
    body: str,
    pair:   Optional[str] = None,
    engine: Optional[str] = None,
    suppress_if_duplicate: bool = True,
) -> bool:
    """Module-level convenience function — delegates to the singleton alerter."""
    return await alerter.send(
        level=level,
        title=title,
        body=body,
        pair=pair,
        engine=engine,
        suppress_if_duplicate=suppress_if_duplicate,
    )
