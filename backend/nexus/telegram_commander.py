"""
NEXUS Telegram Command Center
==============================
All outbound Telegram communication for NEXUS.
Formats messages, sends daily briefs, handles command responses.
NEXUS does NOT receive messages (AEON owns the webhook).
All sending is direct via Bot API.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramCommander:
    """Handles all NEXUS outbound Telegram messages."""

    def __init__(self, bot_token: str, db, chat_ids: Set[int]):
        self.bot_token = bot_token
        self.db        = db
        self.chat_ids  = chat_ids
        self._base_url = f"{TELEGRAM_API}/bot{bot_token}"

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(self, text: str, parse_mode: str = "Markdown") -> None:
        """Send to all known chat_ids."""
        for chat_id in list(self.chat_ids):
            await self.send(chat_id, text, parse_mode=parse_mode)

    async def send(self, chat_id: int, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a message to a single chat_id."""
        if not _HTTPX:
            logger.warning("[COMMANDER] httpx not installed — cannot send Telegram")
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload: dict = {"chat_id": chat_id, "text": text}
                if parse_mode:
                    payload["parse_mode"] = parse_mode
                r = await client.post(f"{self._base_url}/sendMessage", json=payload)
                ok = r.status_code == 200
                if not ok:
                    logger.warning(f"[COMMANDER] Telegram send failed: {r.status_code} {r.text[:100]}")
                else:
                    await self._log_alert(chat_id, text)
                return ok
        except Exception as e:
            logger.error(f"[COMMANDER] Telegram send exception: {e}")
            return False

    # ── Command responses ──────────────────────────────────────────────────────

    def format_status(self, snapshot: Optional[dict], heals_24h: int, adaptations_24h: int) -> str:
        if not snapshot:
            return "NEXUS: No awareness snapshot available yet. First cycle pending."

        mr   = snapshot.get("market_regime",   "?")
        vr   = snapshot.get("volatility_regime", "?")
        tr   = snapshot.get("trend_regime",    "?")
        hm   = snapshot.get("H_market",        0.0)
        hi   = snapshot.get("H_internal",      0.0)
        hc   = snapshot.get("H_combined",      0.0)
        cc   = snapshot.get("consensus_C",     0.0)
        hh   = snapshot.get("health_H",        0.0)
        corr = snapshot.get("correlation_max", 0.0)
        crisis = snapshot.get("crisis_mode",   False)
        sm   = snapshot.get("system_metrics",  {})
        cpu  = sm.get("cpu_pct",    0)
        mem  = sm.get("memory_pct", 0)
        disk = sm.get("disk_pct",   0)

        regime_emoji = {"STRUCTURED": "🟢", "TRANSITIONAL": "🟡", "CHAOTIC": "🔴"}.get(mr, "⚪")
        crisis_line  = "\n🚨 CRISIS MODE ACTIVE" if crisis else ""

        return (
            f"*NEXUS STATUS REPORT*{crisis_line}\n"
            f"{'─' * 28}\n\n"
            f"*Market*\n"
            f"{regime_emoji} Regime: `{mr}` | Trend: `{tr}` | Vol: `{vr}`\n"
            f"H_market: `{hm:.4f}` | H_combined: `{hc:.4f}`\n"
            f"Correlation Max: `{corr:.3f}` | ADX: `{snapshot.get('adx', 0):.1f}`\n"
            f"Hurst: `{snapshot.get('hurst', 0.5):.3f}` | Funding: `{snapshot.get('funding_rate_btc', 0)*100:.4f}%`\n\n"
            f"*System Health*\n"
            f"H score: `{hh:.3f}` | Coherence C: `{cc:.3f}`\n"
            f"H_internal: `{hi:.4f}`\n\n"
            f"*Droplet Resources*\n"
            f"CPU: `{cpu:.0f}%` | RAM: `{mem:.0f}%` | Disk: `{disk:.0f}%`\n\n"
            f"*Autonomous Activity (24h)*\n"
            f"Healing actions: `{heals_24h}` | Adaptations: `{adaptations_24h}`"
        )

    def format_regime(self, snapshot: Optional[dict]) -> str:
        if not snapshot:
            return "NEXUS: No regime data available."
        mr   = snapshot.get("market_regime",   "?")
        tr   = snapshot.get("trend_regime",    "?")
        vr   = snapshot.get("volatility_regime","?")
        hm   = snapshot.get("H_market",   0.0)
        hi   = snapshot.get("H_internal", 0.0)
        hc   = snapshot.get("H_combined", 0.0)
        adx  = snapshot.get("adx",        0.0)
        hurst = snapshot.get("hurst",     0.5)
        corr = snapshot.get("correlation_max", 0.0)
        fr   = snapshot.get("funding_rate_btc", 0.0)

        regime_emoji = {"STRUCTURED": "🟢", "TRANSITIONAL": "🟡", "CHAOTIC": "🔴"}.get(mr, "⚪")
        trend_emoji  = {"TRENDING": "📈", "RANGING": "↔️", "REVERSING": "🔄"}.get(tr, "⚪")
        vol_emoji    = {"LOW": "🟢", "NORMAL": "⚪", "SPIKE": "🔴"}.get(vr, "⚪")

        return (
            f"*NEXUS REGIME SNAPSHOT*\n"
            f"{'─' * 28}\n\n"
            f"{regime_emoji} Market: `{mr}`\n"
            f"{trend_emoji} Trend:  `{tr}`\n"
            f"{vol_emoji} Vol:    `{vr}`\n\n"
            f"*Entropy*\n"
            f"H_market:   `{hm:.4f}`\n"
            f"H_internal: `{hi:.4f}`\n"
            f"H_combined: `{hc:.4f}`\n\n"
            f"*Indicators*\n"
            f"ADX: `{adx:.1f}` | Hurst: `{hurst:.3f}`\n"
            f"Corr max: `{corr:.3f}` | Funding: `{fr*100:.4f}%`"
        )

    def format_engines(self, snapshot: Optional[dict]) -> str:
        if not snapshot:
            return "NEXUS: No engine data available."
        engines = snapshot.get("engine_reports", [])
        if not engines:
            return "NEXUS: Engine reports empty."

        lines = []
        for e in engines:
            name    = e.get("name", "?")
            status  = e.get("status", "?")
            wr      = e.get("win_rate", 0.0)
            alpha   = e.get("alpha", 0.0)
            age_min = e.get("last_signal_minutes")

            status_emoji = {"running": "🟢", "degraded": "🟡", "dead": "🔴", "suspended": "⛔"}.get(status, "⚪")
            lines.append(
                f"{status_emoji} `{name[:20]:<20}` WR:`{wr:.0%}` α:`{alpha:.3f}` last:`{(f'{age_min:.0f}m' if age_min is not None else 'n/a')}`"
            )

        return "*NEXUS ENGINE STATUS*\n" + "─" * 28 + "\n" + "\n".join(lines)

    def format_health(self, snapshot: Optional[dict]) -> str:
        if not snapshot:
            return "NEXUS: No health data."
        hh   = snapshot.get("health_H", 0.0)
        cc   = snapshot.get("consensus_C", 0.0)
        hi   = snapshot.get("H_internal", 0.0)
        hm   = snapshot.get("H_market", 0.0)
        sm   = snapshot.get("system_metrics", {})

        if hh >= 0.7:
            trend, te = "RISING", "📈"
        elif hh >= 0.4:
            trend, te = "STABLE", "➡️"
        else:
            trend, te = "FALLING", "📉"

        return (
            f"*NEXUS SYSTEM HEALTH*\n"
            f"{'─' * 28}\n\n"
            f"H score: `{hh:.3f}` {te} {trend}\n"
            f"Coherence C: `{cc:.3f}`\n"
            f"H_internal: `{hi:.4f}`\n"
            f"H_market: `{hm:.4f}`\n\n"
            f"CPU: `{sm.get('cpu_pct', 0):.0f}%` | "
            f"RAM: `{sm.get('memory_pct', 0):.0f}%` | "
            f"Disk: `{sm.get('disk_pct', 0):.0f}%`"
        )

    def format_positions(self, snapshot: Optional[dict]) -> str:
        if not snapshot:
            return "NEXUS: No position data."
        positions = snapshot.get("open_positions", [])
        if not positions:
            return "NEXUS: No open positions."

        lines = [f"*NEXUS OPEN POSITIONS* ({len(positions)})\n" + "─" * 28]
        for p in positions:
            sym   = p.get("symbol", "?")
            dir_  = p.get("direction", "?").upper()
            sz    = p.get("size_usd", 0)
            pnl   = p.get("pnl_pct", 0)
            hrs   = p.get("hours_open", 0)
            eng   = p.get("engine", "?")
            liq   = p.get("liq_dist_pct", 100)
            pnl_e = "🟢" if pnl >= 0 else "🔴"
            liq_e = "🚨" if liq <= 10 else ("⚠️" if liq <= 20 else "✅")

            lines.append(
                f"{pnl_e} `{sym}` {dir_} ${sz:,.0f}\n"
                f"   PnL: `{pnl:+.2f}%` | Open: `{hrs:.1f}h`\n"
                f"   Engine: `{eng}` | Liq: {liq_e}`{liq:.0f}%`"
            )

        return "\n\n".join(lines)

    # ── Daily intelligence report ──────────────────────────────────────────────

    async def send_daily_brief(self, snapshot: Optional[dict]) -> None:
        """Send the 6AM Austin daily intelligence report."""
        now   = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        # Fetch 24h stats from MongoDB
        stats = await self._fetch_daily_stats()

        mr     = snapshot.get("market_regime", "UNKNOWN") if snapshot else "UNKNOWN"
        hm     = snapshot.get("H_market", 0.0) if snapshot else 0.0
        hi     = snapshot.get("H_internal", 0.0) if snapshot else 0.0
        hh     = snapshot.get("health_H", 0.0) if snapshot else 0.0
        crisis = snapshot.get("crisis_mode", False) if snapshot else False

        # Operational status
        if crisis:
            op_status = "CRISIS MODE"
        elif hh >= 0.7:
            op_status = "FULLY OPERATIONAL"
        elif hh >= 0.4:
            op_status = "OPERATIONAL"
        else:
            op_status = "DEGRADED"

        # Top engine by win rate
        engines      = snapshot.get("engine_reports", []) if snapshot else []
        top_engine   = max(engines, key=lambda e: e.get("win_rate", 0), default=None)
        top_eng_name = top_engine.get("name", "N/A") if top_engine else "N/A"

        brief = (
            f"*NEXUS DAILY BRIEF — {today}*\n"
            f"{'═' * 30}\n\n"
            f"*Market Regime:* `{mr}`\n"
            f"H_market: `{hm:.4f}` | H_internal: `{hi:.4f}`\n\n"
            f"*System Health:* `{hh:.3f}`\n\n"
            f"*Yesterday's Trading*\n"
            f"Trades: `{stats['trade_count']}` | "
            f"Win Rate: `{stats['win_rate']:.0%}` | "
            f"PnL: `{stats['total_pnl']:+.2f}%`\n\n"
            f"*Engine Performance*\n"
            f"Top engine: `{top_eng_name}`\n\n"
            f"*Autonomous Actions*\n"
            f"Adaptations: `{stats['adaptations']}` | "
            f"Heals: `{stats['heals']}`\n\n"
            f"*Issues Detected:*\n"
            f"{stats['issues'] or 'None'}\n\n"
            f"*AEON Status:* `{op_status}`\n"
            f"{'─' * 30}\n"
            f"_NEXUS autonomous nervous system_"
        )

        await self.broadcast(brief)
        logger.info("[COMMANDER] Daily brief sent")

    async def _fetch_daily_stats(self) -> dict:
        from datetime import timedelta
        stats = {
            "trade_count": 0,
            "win_rate":    0.0,
            "total_pnl":   0.0,
            "adaptations": 0,
            "heals":       0,
            "issues":      "",
        }
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        try:
            pipeline = [
                {"$match": {"status": "closed", "closed_at": {"$gte": cutoff}}},
                {"$group": {
                    "_id":   None,
                    "wins":  {"$sum": {"$cond": [{"$gt": ["$pnl", 0]}, 1, 0]}},
                    "total": {"$sum": 1},
                    "pnl":   {"$avg": "$pnl"},
                }},
            ]
            async for doc in self.db["paper_trades"].aggregate(pipeline):
                total = doc.get("total", 0)
                if total > 0:
                    stats["trade_count"] = total
                    stats["win_rate"]    = doc.get("wins", 0) / total
                    stats["total_pnl"]   = float(doc.get("pnl", 0) or 0)
                break
        except Exception:
            pass

        try:
            stats["adaptations"] = await self.db["nexus_adaptations"].count_documents(
                {"timestamp": {"$gte": cutoff}}
            )
        except Exception:
            pass

        try:
            stats["heals"] = await self.db["nexus_heals"].count_documents(
                {"timestamp": {"$gte": cutoff}}
            )
        except Exception:
            pass

        # Recent issues from nexus_alerts
        try:
            issues = []
            cursor = self.db["nexus_alerts"].find(
                {"timestamp": {"$gte": cutoff}, "status": {"$ne": "ok"}},
                sort=[("timestamp", -1)],
                limit=3,
            )
            async for doc in cursor:
                issues.append(doc.get("detail", doc.get("component", "?")))
            stats["issues"] = "\n".join(f"• {i}" for i in issues) if issues else ""
        except Exception:
            pass

        return stats

    async def _log_alert(self, chat_id: int, text: str) -> None:
        try:
            await self.db["nexus_alerts"].insert_one({
                "timestamp":  datetime.now(timezone.utc),
                "component":  "telegram_commander",
                "status":     "ok",
                "action":     "alert_sent",
                "detail":     text[:200],
                "chat_id":    chat_id,
            })
        except Exception:
            pass
