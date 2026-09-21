"""
NEXUS LAYER 2 — MORPHEUS: The Adaptation Engine
================================================
Reconfigures AEON when the market changes regime.
Writes nexus_config to MongoDB — AEON reads and applies.

RESPONSE TABLE:
  STRUCTURED + TRENDING  → All 9 engines, max leverage, modifier 1.0
  STRUCTURED + RANGING   → Scalper/range engines, modifier 0.7
  TRANSITIONAL           → All engines reduced, modifier 0.5, tighten stops
  CHAOTIC                → Block all trades, alert Carlos
  CRISIS (corr > 0.92)   → Close ALL positions, halt ALL engines, alert
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ── Engine groupings for regime switching ──────────────────────────────────────

ALL_ENGINES = [
    "autonomous_trader_v2", "free_will_v2", "dual_engine",
    "yolo_engine", "vwap_scalper", "elite_strategy",
    "day_trader", "quant_analyzer", "tcn_neural",
]

TRENDING_LEAD   = ["autonomous_trader_v2", "tcn_neural", "elite_strategy"]
RANGING_ENGINES = ["vwap_scalper", "dual_engine", "free_will_v2"]
TREND_FOLLOW    = ["autonomous_trader_v2", "yolo_engine", "day_trader", "tcn_neural", "elite_strategy"]


class Morpheus:
    """
    Reads awareness snapshot → detects regime change →
    writes nexus_config to MongoDB so AEON adapts.
    """

    def __init__(self, db, send_telegram, chat_ids: Set[int]):
        self.db            = db
        self.send_telegram = send_telegram
        self.chat_ids      = chat_ids
        self._last_regime  = None
        self._last_trend   = None
        self._crisis_active = False

    async def check_and_adapt(self, snapshot: dict) -> Optional[dict]:
        """
        Main entry point. Returns adaptation event dict if a change was made.
        """
        market_regime = snapshot.get("market_regime", "TRANSITIONAL")
        trend_regime  = snapshot.get("trend_regime",  "REVERSING")
        crisis        = snapshot.get("crisis_mode",   False)
        crisis_just   = snapshot.get("crisis_just_triggered", False)
        corr_max      = snapshot.get("correlation_max", 0.0)
        H_market      = snapshot.get("H_market", 0.5)

        # ── CRISIS MODE (correlation spike) ──────────────────────────────────
        if crisis:
            if not self._crisis_active or crisis_just:
                self._crisis_active = True
                event = await self._enter_crisis(corr_max, snapshot)
                return event
            return None  # Already in crisis, already alerted

        # Crisis cleared
        if self._crisis_active and not crisis:
            self._crisis_active = False
            await self._exit_crisis(corr_max)

        # ── REGIME CHANGE CHECK ────────────────────────────────────────────────
        regime_key    = f"{market_regime}_{trend_regime}"
        prev_key      = f"{self._last_regime}_{self._last_trend}" if self._last_regime else None
        regime_changed = (regime_key != prev_key) and (prev_key is not None)

        # Always write config (even on no change, for AEON restart recovery)
        config = self._build_config(market_regime, trend_regime, H_market)
        await self._write_config(config)

        if not regime_changed:
            self._last_regime = market_regime
            self._last_trend  = trend_regime
            return None

        # ── REGIME CHANGED — execute response table ────────────────────────────
        event = await self._execute_response_table(
            from_regime  = f"{self._last_regime}/{self._last_trend}",
            to_regime    = f"{market_regime}/{trend_regime}",
            market_regime = market_regime,
            trend_regime  = trend_regime,
            config        = config,
        )

        self._last_regime = market_regime
        self._last_trend  = trend_regime
        return event

    # ── Response table ─────────────────────────────────────────────────────────

    def _build_config(self, market_regime: str, trend_regime: str, H_market: float) -> dict:
        """Derive nexus_config settings from current regime."""
        if market_regime == "CHAOTIC":
            return {
                "_id":               "live",
                "pause":             True,
                "crisis":            False,
                "position_modifier": 0.0,
                "regime":            market_regime,
                "trend_regime":      trend_regime,
                "active_engines":    [],
                "reason":            f"CHAOTIC regime — H_market={H_market:.3f}",
            }

        if market_regime == "TRANSITIONAL":
            return {
                "_id":               "live",
                "pause":             False,
                "crisis":            False,
                "position_modifier": 0.5,
                "regime":            market_regime,
                "trend_regime":      trend_regime,
                "active_engines":    ALL_ENGINES,
                "reason":            f"TRANSITIONAL — position size 50%",
            }

        # STRUCTURED
        if trend_regime == "TRENDING":
            return {
                "_id":               "live",
                "pause":             False,
                "crisis":            False,
                "position_modifier": 1.0,
                "regime":            market_regime,
                "trend_regime":      trend_regime,
                "active_engines":    ALL_ENGINES,
                "reason":            "STRUCTURED + TRENDING — full engines",
            }

        if trend_regime == "RANGING":
            return {
                "_id":               "live",
                "pause":             False,
                "crisis":            False,
                "position_modifier": 0.7,
                "regime":            market_regime,
                "trend_regime":      trend_regime,
                "active_engines":    RANGING_ENGINES,
                "reason":            "STRUCTURED + RANGING — range engines, 70% size",
            }

        # REVERSING
        return {
            "_id":               "live",
            "pause":             False,
            "crisis":            False,
            "position_modifier": 0.6,
            "regime":            market_regime,
            "trend_regime":      trend_regime,
            "active_engines":    ALL_ENGINES,
            "reason":            "STRUCTURED + REVERSING — cautious sizing",
        }

    async def _execute_response_table(
        self,
        from_regime: str,
        to_regime: str,
        market_regime: str,
        trend_regime: str,
        config: dict,
    ) -> dict:
        now     = datetime.now(timezone.utc)
        modifier = config.get("position_modifier", 1.0)
        engines  = config.get("active_engines", ALL_ENGINES)
        reason   = config.get("reason", "")
        paused   = config.get("pause", False)

        # Build human-readable action description
        if market_regime == "CHAOTIC":
            action = "ALL ENGINES BLOCKED — awaiting regime normalization"
        elif market_regime == "TRANSITIONAL":
            action = f"All engines active, position size reduced to 50%"
        elif trend_regime == "TRENDING":
            action = f"All 9 engines active, full leverage. Lead: {', '.join(TRENDING_LEAD)}"
        elif trend_regime == "RANGING":
            action = f"Range engines only: {', '.join(RANGING_ENGINES)}. Size 70%"
        else:
            action = f"All engines, cautious 60% sizing"

        event = {
            "timestamp":        now.isoformat(),
            "from_regime":      from_regime,
            "to_regime":        to_regime,
            "action_taken":     action,
            "engines_affected": engines,
            "position_modifier": modifier,
            "detail":           reason,
        }

        # Log to MongoDB
        try:
            await self.db["nexus_adaptations"].insert_one({
                **event,
                "timestamp": now,
            })
        except Exception as e:
            logger.warning(f"[MORPHEUS] Adaptation log failed: {e}")

        # Telegram alert
        emoji = {"STRUCTURED": "🟢", "TRANSITIONAL": "🟡", "CHAOTIC": "🔴"}.get(market_regime, "⚪")
        msg = (
            f"{emoji} *NEXUS REGIME CHANGE*\n\n"
            f"From: `{from_regime}`\n"
            f"To:   `{to_regime}`\n\n"
            f"Action: {action}\n"
            f"Size modifier: `{modifier:.0%}`\n"
        )
        if paused:
            msg += "\nAll new trades BLOCKED until regime normalizes."

        await self._alert(msg)
        logger.info(f"[MORPHEUS] {from_regime} → {to_regime} | {action}")
        return event

    async def _enter_crisis(self, corr_max: float, snapshot: dict) -> dict:
        now    = datetime.now(timezone.utc)
        config = {
            "_id":               "live",
            "pause":             True,
            "crisis":            True,
            "position_modifier": 0.0,
            "regime":            "CHAOTIC",
            "trend_regime":      snapshot.get("trend_regime", "REVERSING"),
            "active_engines":    [],
            "reason":            f"CRISIS — correlation={corr_max:.3f} exceeds {0.92}",
        }
        await self._write_config(config)

        msg = (
            f"🚨 *NEXUS: CRISIS DETECTED*\n\n"
            f"Cross-asset correlation: `{corr_max:.3f}` (threshold: 0.92)\n\n"
            f"ACTION:\n"
            f"• All positions flagged for close\n"
            f"• All engines halted\n"
            f"• No new trades until correlation < 0.80\n\n"
            f"AEON is standing down. Awaiting regime normalization."
        )
        await self._alert(msg)

        event = {
            "timestamp":        now.isoformat(),
            "from_regime":      "operational",
            "to_regime":        "CRISIS",
            "action_taken":     "ALL engines halted, all positions flagged for close",
            "engines_affected": ALL_ENGINES,
            "position_modifier": 0.0,
            "detail":           f"Correlation spike: {corr_max:.4f}",
        }

        try:
            await self.db["nexus_adaptations"].insert_one({
                **event,
                "timestamp": now,
            })
        except Exception:
            pass

        logger.critical(f"[MORPHEUS] CRISIS MODE — corr={corr_max:.4f}")
        return event

    async def _exit_crisis(self, corr_max: float) -> None:
        msg = (
            f"✅ *NEXUS: CRISIS CLEARED*\n\n"
            f"Correlation dropped to `{corr_max:.3f}` (< 0.80)\n"
            f"Normal trading operations resuming.\n"
            f"MORPHEUS will reconfigure engines per current regime."
        )
        await self._alert(msg)
        logger.info(f"[MORPHEUS] Crisis cleared — corr={corr_max:.4f}")

    async def _write_config(self, config: dict) -> None:
        try:
            await self.db["nexus_config"].replace_one(
                {"_id": "live"},
                {**config, "last_updated": datetime.now(timezone.utc)},
                upsert=True,
            )
        except Exception as e:
            logger.error(f"[MORPHEUS] Config write failed: {e}")

    async def _alert(self, text: str) -> None:
        if not self.send_telegram or not self.chat_ids:
            return
        for chat_id in list(self.chat_ids):
            try:
                await self.send_telegram(chat_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"[MORPHEUS] Telegram alert failed for {chat_id}: {e}")

    # ── Command handlers (called by NEXUS core for /nexus_* commands) ──────────

    async def force_reconfigure(self, snapshot: dict) -> str:
        """Force MORPHEUS reconfiguration regardless of regime change."""
        self._last_regime = None  # Force a "change"
        self._last_trend  = None
        event = await self.check_and_adapt(snapshot)
        if event:
            return f"MORPHEUS reconfigured: {event.get('action_taken', 'done')}"
        return "MORPHEUS: No snapshot available, config refreshed from DB"

    async def manual_pause(self) -> None:
        await self._write_config({
            "_id":               "live",
            "pause":             True,
            "crisis":            False,
            "position_modifier": 0.0,
            "regime":            "MANUAL_PAUSE",
            "trend_regime":      "UNKNOWN",
            "active_engines":    [],
            "reason":            "Manual pause by Carlos via /nexus_pause",
        })
        await self._alert("⏸️ *NEXUS: Trading manually PAUSED by Carlos.*\nSend /nexus_resume to restart.")

    async def manual_resume(self, snapshot: Optional[dict] = None) -> None:
        self._last_regime = None
        if snapshot:
            await self.check_and_adapt(snapshot)
        await self._alert("▶️ *NEXUS: Trading RESUMED.*\nRegime-appropriate configuration applied.")
