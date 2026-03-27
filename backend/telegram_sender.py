"""
Telegram message sender — rate-limit aware, with retry logic.

Includes:
  - send_telegram_message()       core send function
  - can_send_signal_alert()       per-symbol/direction dedup (5-min window)
  - record_signal_alert()         mark alert as sent
  - format_quant_block()          🔬 QUANT GATE section for trade alerts
  - format_leverage_block()       ⚡ LEVERAGE ENGINE section for trade alerts
  - format_atr_block()            📐 ATR STOP section for trade alerts
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

_telegram_token = os.environ.get("TELEGRAM_TOKEN", "")

# ── Signal alert deduplication ──────────────────────────────────────────────
# Keyed by "{symbol}:{direction}", value = last-sent datetime (UTC).
# Window: 15 minutes — prevents same coin+direction from multiple engines.
_ALERT_DEDUP: Dict[str, datetime] = {}
_SIGNAL_ALERT_WINDOW = timedelta(minutes=15)

# Coin-level dedup — keyed by symbol only, blocks any direction for 20 min.
# Prevents BTC LONG → BTC SHORT flip-flopping across engines.
_COIN_DEDUP: Dict[str, datetime] = {}
_COIN_ALERT_WINDOW = timedelta(minutes=20)

# System-status messages (e.g. /status, /health) — max once per hour.
_STATUS_DEDUP: Dict[str, datetime] = {}
_STATUS_WINDOW = timedelta(hours=1)


def can_send_signal_alert(symbol: str, direction: str, window_sec: int = 900) -> bool:
    """
    Return True if the same symbol+direction alert has NOT been sent
    in the last `window_sec` seconds (default 15 minutes).
    """
    key = f"{symbol.upper()}:{direction.upper()}"
    last = _ALERT_DEDUP.get(key)
    if last is None:
        return True
    return (datetime.now(timezone.utc) - last).total_seconds() >= window_sec


def can_send_coin_alert(symbol: str, window_sec: int = 1200) -> bool:
    """
    Return True if NO alert (any direction) has been sent for this coin
    in the last `window_sec` seconds (default 20 minutes).
    Prevents cross-engine same-coin spam and LONG/SHORT flip-flopping.
    """
    last = _COIN_DEDUP.get(symbol.upper())
    if last is None:
        return True
    return (datetime.now(timezone.utc) - last).total_seconds() >= window_sec


def record_signal_alert(symbol: str, direction: str) -> None:
    """Mark a signal alert as sent right now (direction + coin level)."""
    now = datetime.now(timezone.utc)
    key = f"{symbol.upper()}:{direction.upper()}"
    _ALERT_DEDUP[key] = now
    _COIN_DEDUP[symbol.upper()] = now
    # Prune stale entries
    cutoff = now - timedelta(minutes=30)
    expired = [k for k, v in _ALERT_DEDUP.items() if v < cutoff]
    for k in expired:
        del _ALERT_DEDUP[k]
    coin_cutoff = now - timedelta(minutes=40)
    expired_coins = [k for k, v in _COIN_DEDUP.items() if v < coin_cutoff]
    for k in expired_coins:
        del _COIN_DEDUP[k]


def can_send_status_message(key: str) -> bool:
    """Return True if a status message with this key hasn't been sent in the last hour."""
    last = _STATUS_DEDUP.get(key)
    if last is None:
        return True
    return (datetime.now(timezone.utc) - last) >= _STATUS_WINDOW


def record_status_message(key: str) -> None:
    """Mark a status message as sent right now."""
    _STATUS_DEDUP[key] = datetime.now(timezone.utc)


# ── Quant regime threshold table (mirrors quant_analyzer_v2.REGIME_THRESHOLDS) ──
_REGIME_THRESHOLDS: Dict[str, int] = {
    "TRENDING":        65,
    "RANGING":         68,
    "HIGH_VOLATILITY": 85,
    "ACCUMULATION":    60,
    "VOLATILE":        80,
    "WEAK_TREND":      70,
}


def format_quant_block(lev_bd: Dict, adapted: bool = False) -> str:
    """
    Build the 🔬 QUANT GATE block from the leverage breakdown dict.
    lev_bd comes from EngineManager.get_dynamic_leverage() →
      compute_dynamic_leverage() which always sets score, regime, anomaly_count.
    """
    score         = lev_bd.get("score", 0)
    regime        = lev_bd.get("regime", "UNKNOWN")
    anomaly_count = lev_bd.get("anomaly_count", 0)
    threshold     = _REGIME_THRESHOLDS.get(regime, 70)
    passed        = score >= threshold
    gate_emoji    = "✅ PASS" if passed else "⚠️ ADAPTED" if adapted else "❌ BLOCK"

    return (
        f"🔬 QUANT GATE\n"
        f"Score:     {score}/100  {gate_emoji}\n"
        f"Regime:    {regime}\n"
        f"Threshold: {threshold}/100\n"
        f"Anomalies: {anomaly_count} active\n"
        f"Adapted:   {'Yes' if adapted else 'No'}"
    )


def format_leverage_block(lev_bd: Dict) -> str:
    """
    Build the ⚡ LEVERAGE ENGINE block from the leverage breakdown dict.
    """
    base          = lev_bd.get("base", 0)
    regime_mult   = lev_bd.get("regime_mult", 1.0)
    regime        = lev_bd.get("regime", "")
    penalty       = lev_bd.get("penalty_factor", 1.0)
    anomaly_count = lev_bd.get("anomaly_count", 0)
    bonus         = lev_bd.get("bonus", False)
    final         = lev_bd.get("final", 0)

    penalty_str = (
        "FLOOR (4+ anomalies)"
        if str(penalty) == "FLOOR"
        else f"{penalty:.2f}  ({anomaly_count} anomaly flag{'s' if anomaly_count != 1 else ''})"
    )
    bonus_str = "×1.15" if bonus else "—"

    return (
        f"⚡ LEVERAGE ENGINE\n"
        f"Base:      {base:.1f}x\n"
        f"Regime ×:  {regime_mult:.2f}  ({regime})\n"
        f"Anomaly ×: {penalty_str}\n"
        f"Bonus ×:   {bonus_str}\n"
        f"Final:     {final}x"
    )


def format_atr_block(signal: Dict) -> str:
    """
    Build the 📐 ATR STOP block from signal fields already computed
    during signal analysis (atr, entry, stop, position_size).
    k_approx = stop_distance / ATR14 (the multiplier used).
    lots     = position_size_usd / entry_price (notional contract count).
    """
    atr14      = signal.get("atr", 0)
    entry      = signal.get("entry", signal.get("price", 0))
    stop       = signal.get("stop", signal.get("stop_price", 0))
    pos_size   = signal.get("position_size", signal.get("_position_size", 1000))
    regime     = signal.get("market_regime", signal.get("regime", ""))

    stop_dollar = abs(entry - stop) if (entry and stop) else 0
    k_approx    = round(stop_dollar / atr14, 2) if atr14 > 0 else 0
    lots        = round(pos_size / entry, 4) if entry > 0 else 0

    return (
        f"📐 ATR STOP\n"
        f"ATR(14):    ${atr14:,.4f}\n"
        f"k selected: {k_approx}  (stop/ATR ratio)\n"
        f"λ used:     regime-adaptive ({regime or 'auto'})\n"
        f"Stop$:      ${stop_dollar:,.4f}\n"
        f"SL:         ${stop:,.2f}\n"
        f"Lots:       {lots}"
    )


# ── Core send function ───────────────────────────────────────────────────────

async def send_telegram_message(
    chat_id: int,
    text: str,
    retry: int = 2,
    parse_mode: Optional[str] = None,
):
    """Send a Telegram message with retry and rate-limit handling.

    Args:
        chat_id: Telegram chat ID.
        text: Message text.
        retry: Number of additional attempts after the first.
        parse_mode: 'Markdown' or 'HTML' for rich formatting.
    """
    for attempt in range(retry + 1):
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                payload: dict = {"chat_id": chat_id, "text": text}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                    payload["disable_web_page_preview"] = True

                resp = await c.post(
                    f"https://api.telegram.org/bot{_telegram_token}/sendMessage",
                    json=payload,
                )
                if resp.status_code == 429:
                    retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                    logger.warning(f"Telegram rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                return
        except Exception as e:
            if attempt < retry:
                await asyncio.sleep(1)
            else:
                logger.error(f"Telegram send error: {e}")
