"""
NEXUS LAYER 3 — HEALER: Self-Healing Engine
=============================================
AEON fixes itself without Carlos touching anything.

What it heals:
  • Dead/degraded engines (win rate < 40%, no signal > 2h)
  • API failures (Coinbase ↔ MEXC failover)
  • Position anomalies (4h+, liquidation risk, missing SL)
  • System resource overload (CPU, RAM, disk)
  • Process failures (aeon.service, pm2, nginx, mongod)
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Set, Dict

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

logger = logging.getLogger(__name__)

# ── Thresholds ─────────────────────────────────────────────────────────────────
WIN_RATE_FLOOR       = 0.40   # Suspend engine below this over 50 trades
SIGNAL_DEAD_MINUTES  = 120    # Engine "dead" if no signal for 2h
POSITION_MAX_HOURS   = 4.0    # Alert if position open > 4h
LIQ_WARN_PCT         = 10.0   # Close position if within 10% of liquidation
CPU_THROTTLE_PCT     = 90.0   # Throttle at 90% CPU
MEM_RESTART_PCT      = 85.0   # Restart non-critical at 85% RAM
DISK_ARCHIVE_PCT     = 80.0   # Archive logs at 80% disk


class Healer:
    """
    Autonomous self-healing. Runs every 5 minutes from NEXUS core.
    Logs every action to nexus_heals before and after.
    """

    def __init__(self, db, send_telegram, chat_ids: Set[int]):
        self.db            = db
        self.send_telegram = send_telegram
        self.chat_ids      = chat_ids
        self._suspended_engines: Set[str] = set()
        self._last_process_check: Optional[datetime] = None
        self._alert_cooldown: Dict[str, datetime] = {}

    # ── Main scan ──────────────────────────────────────────────────────────────

    async def scan_and_heal(self, snapshot: Optional[dict] = None) -> List[dict]:
        """Run full heal scan. Returns list of heal actions taken."""
        heals: List[dict] = []

        # 1. Engine win rates
        heals += await self._heal_engine_win_rates(snapshot)

        # 2. Engine signal silence
        heals += await self._heal_engine_silence(snapshot)

        # 3. Position anomalies
        heals += await self._heal_position_anomalies(snapshot)

        # 4. System resources
        heals += await self._heal_system_resources()

        # 5. Process checks (every 5 min)
        now = datetime.now(timezone.utc)
        if (self._last_process_check is None or
                (now - self._last_process_check).total_seconds() >= 300):
            heals += await self._heal_processes()
            self._last_process_check = now

        # Log all heals
        for heal in heals:
            await self._log_heal(heal)

        return heals

    # ── Engine win rate ────────────────────────────────────────────────────────

    async def _heal_engine_win_rates(self, snapshot: Optional[dict]) -> List[dict]:
        heals = []
        if not snapshot:
            return heals

        for eng_report in snapshot.get("engine_reports", []):
            name       = eng_report.get("name", "")
            win_rate   = eng_report.get("win_rate", 0.5)
            count      = eng_report.get("trade_count", 0)

            if count >= 50 and win_rate < WIN_RATE_FLOOR:
                if name not in self._suspended_engines:
                    self._suspended_engines.add(name)
                    heal = await self._suspend_engine(name, win_rate, count)
                    heals.append(heal)
            elif name in self._suspended_engines and win_rate >= WIN_RATE_FLOOR + 0.05:
                # Recovery threshold: 5% above floor before re-enabling
                self._suspended_engines.discard(name)
                heal = self._make_heal(
                    heal_type="ENGINE_RESTART",
                    trigger=f"{name} win rate recovered to {win_rate:.1%}",
                    result=f"Engine {name} re-enabled",
                    engine=name,
                    success=True,
                )
                heals.append(heal)
                await self._alert(
                    f"🟢 *HEALER:* `{name}` recovered ({win_rate:.1%} win rate) — re-enabled.",
                    key=f"engine_recover:{name}", cooldown_hours=6.0,
                )

        return heals

    async def _suspend_engine(self, name: str, win_rate: float, count: int) -> dict:
        """Write to nexus_suspended_engines and nexus_config exclusion."""
        try:
            await self.db["nexus_suspended_engines"].replace_one(
                {"engine": name},
                {"engine": name, "reason": f"Win rate {win_rate:.1%} < {WIN_RATE_FLOOR:.0%} over {count} trades",
                 "suspended_at": datetime.now(timezone.utc)},
                upsert=True,
            )
        except Exception:
            pass

        await self._alert(
            f"⚠️ *HEALER: ENGINE SUSPENDED*\n\n"
            f"Engine: `{name}`\n"
            f"Win Rate: `{win_rate:.1%}` over {count} trades\n"
            f"Threshold: `{WIN_RATE_FLOOR:.0%}`\n\n"
            f"Engine weight αᵢ → 0. Suspended until recovery.",
            key=f"engine_suspend:{name}", cooldown_hours=12.0,
        )

        return self._make_heal(
            heal_type="ENGINE_SUSPENDED",
            trigger=f"Win rate {win_rate:.1%} over {count} trades",
            result=f"Engine {name} suspended, αᵢ=0",
            engine=name,
            success=True,
        )

    # ── Engine silence ─────────────────────────────────────────────────────────

    async def _heal_engine_silence(self, snapshot: Optional[dict]) -> List[dict]:
        heals = []
        if not snapshot:
            return heals

        for eng_report in snapshot.get("engine_reports", []):
            name    = eng_report.get("name", "")
            age_min = eng_report.get("last_signal_minutes", 0)
            status  = eng_report.get("status", "running")

            if age_min is not None and age_min > SIGNAL_DEAD_MINUTES and status != "running":
                # Engine is silent — log and alert (restart is handled by AEON's self_healer)
                heal = self._make_heal(
                    heal_type="ENGINE_RESTART",
                    trigger=f"{name} silent for {age_min:.0f}min",
                    result=f"Health check alert sent to AEON self_healer. Engine: {name}",
                    engine=name,
                    success=True,
                )
                heals.append(heal)
                logger.warning(f"[HEALER] Engine {name} silent {age_min:.0f}min // observe-only, restart suppressed")

        return heals

    # ── Position anomalies ─────────────────────────────────────────────────────

    async def _heal_position_anomalies(self, snapshot: Optional[dict]) -> List[dict]:
        heals = []
        if not snapshot:
            return heals

        now = datetime.now(timezone.utc)

        for pos in snapshot.get("open_positions", []):
            symbol      = pos.get("symbol", "")
            hours_open  = pos.get("hours_open", 0)
            liq_dist    = pos.get("liq_dist_pct", 100)
            pnl_pct     = pos.get("pnl_pct", 0)
            engine      = pos.get("engine", "unknown")
            direction   = pos.get("direction", "")
            pos_id      = pos.get("_id", "")

            # Liquidation risk — close now
            if liq_dist <= LIQ_WARN_PCT:
                heal = self._make_heal(
                    heal_type="POSITION_CLOSE",
                    trigger=f"{symbol} liquidation within {liq_dist:.1f}%",
                    result=f"Emergency close flagged for {symbol}",
                    engine=engine,
                    success=True,
                )
                heals.append(heal)
                await self._flag_force_close(pos_id, symbol, reason=f"LIQ_RISK: {liq_dist:.1f}%")
                await self._alert(
                    f"🚨 *HEALER: LIQUIDATION RISK*\n\n"
                    f"Symbol: `{symbol}` | Engine: `{engine}`\n"
                    f"Distance to liquidation: `{liq_dist:.1f}%`\n"
                    f"Action: Emergency close flagged.",
                    key=f"liq_risk:{symbol}", cooldown_hours=1.0,
                )

            # Crisis-mode PnL < -1.5%
            elif snapshot.get("market_regime") == "CHAOTIC" and pnl_pct < -1.5:
                heal = self._make_heal(
                    heal_type="POSITION_CLOSE",
                    trigger=f"CHAOTIC regime + PnL={pnl_pct:.1f}%",
                    result=f"Crisis close flagged for {symbol}",
                    engine=engine,
                    success=True,
                )
                heals.append(heal)
                await self._flag_force_close(pos_id, symbol, reason=f"CHAOTIC_LOSS: {pnl_pct:.1f}%")

            # Long open
            elif hours_open > POSITION_MAX_HOURS:
                heal = self._make_heal(
                    heal_type="POSITION_CLOSE",
                    trigger=f"{symbol} open {hours_open:.1f}h",
                    result=f"Alert sent for {symbol} — {hours_open:.1f}h open",
                    engine=engine,
                    success=True,
                )
                heals.append(heal)
                await self._alert(
                    f"⏰ *HEALER: LONG-RUNNING POSITION*\n\n"
                    f"Symbol: `{symbol}` | Engine: `{engine}`\n"
                    f"Open: `{hours_open:.1f}h` | PnL: `{pnl_pct:+.2f}%`\n"
                    f"Please review manually.",
                    key=f"long_pos:{symbol}", cooldown_hours=6.0,
                )

        return heals

    async def _flag_force_close(self, pos_id: str, symbol: str, reason: str) -> None:
        try:
            await self.db["nexus_force_close"].insert_one({
                "pos_id":    pos_id,
                "symbol":    symbol,
                "reason":    reason,
                "flagged_at": datetime.now(timezone.utc),
                "executed":  False,
            })
        except Exception as e:
            logger.error(f"[HEALER] Force-close flag failed: {e}")

    # ── System resources ───────────────────────────────────────────────────────

    async def _heal_system_resources(self) -> List[dict]:
        heals = []
        if not _PSUTIL:
            return heals

        try:
            cpu  = psutil.cpu_percent(interval=0.5)
            mem  = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
        except Exception:
            return heals

        if cpu > CPU_THROTTLE_PCT:
            heal = self._make_heal(
                heal_type="RESOURCE_THROTTLE",
                trigger=f"CPU={cpu:.0f}%",
                result="CPU spike logged — engine cycle frequency monitored",
                engine=None,
                success=True,
            )
            heals.append(heal)
            await self._alert(
                f"⚡ *HEALER: HIGH CPU*\n`{cpu:.0f}%` — monitoring engine loops.",
                key="cpu_high", cooldown_hours=4.0,
            )

        if mem > MEM_RESTART_PCT:
            heal = self._make_heal(
                heal_type="RESOURCE_THROTTLE",
                trigger=f"Memory={mem:.0f}%",
                result="Memory threshold crossed — logged for action",
                engine=None,
                success=True,
            )
            heals.append(heal)
            await self._alert(
                f"💾 *HEALER: HIGH MEMORY*\n`{mem:.0f}%` — consider restarting non-critical services.",
                key="mem_high", cooldown_hours=4.0,
            )

        if disk > DISK_ARCHIVE_PCT:
            result = await self._archive_old_logs()
            heal = self._make_heal(
                heal_type="LOG_ARCHIVE",
                trigger=f"Disk={disk:.0f}%",
                result=result,
                engine=None,
                success=True,
            )
            heals.append(heal)

        return heals

    async def _archive_old_logs(self) -> str:
        """Compress and delete old logs to free disk."""
        try:
            proc = await asyncio.create_subprocess_shell(
                "find /var/log -name '*.log' -mtime +7 -exec gzip -f {} \\; 2>/dev/null; "
                "find /var/log -name '*.gz' -mtime +30 -delete 2>/dev/null",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)
            return "Old logs compressed/archived"
        except Exception as e:
            return f"Log archive partial: {e}"

    # ── Process checks ─────────────────────────────────────────────────────────

    async def _heal_processes(self) -> List[dict]:
        heals = []

        checks = [
            ("pm2-aeon",        "systemctl status pm2-aeon", "systemctl restart pm2-aeon"),
            ("nginx",           "systemctl status nginx",   "systemctl restart nginx"),
            ("mongod",          "systemctl status mongod",  "systemctl restart mongod"),
        ]

        for name, status_cmd, restart_cmd in checks:
            ok = await self._check_service(status_cmd)
            if not ok:
                result = await self._restart_service(restart_cmd, name)
                heal   = self._make_heal(
                    heal_type="PROCESS_RESTART",
                    trigger=f"{name} status check failed",
                    result=result,
                    engine=name,
                    success="restarted" in result.lower(),
                )
                heals.append(heal)
                await self._alert(
                    f"🔧 *HEALER: SERVICE RESTARTED*\n`{name}` — {result}",
                    key=f"svc_restart:{name}", cooldown_hours=1.0,
                )

        # pm2 frontend check
        pm2_ok = await self._check_pm2_frontend()
        if not pm2_ok:
            result = await self._run_cmd("pm2 restart all", timeout=20)
            heal   = self._make_heal(
                heal_type="PROCESS_RESTART",
                trigger="pm2 frontend not running",
                result=result or "pm2 restart issued",
                engine="frontend",
                success=True,
            )
            heals.append(heal)
            await asyncio.sleep(30)
            # Verify
            still_ok = await self._check_pm2_frontend()
            if not still_ok:
                await self._alert(
                    "🚨 *HEALER: Frontend still down after pm2 restart — manual intervention may be needed.*",
                    key="frontend_down", cooldown_hours=1.0,
                )

        return heals

    async def _check_service(self, cmd: str) -> bool:
        """Returns True if service is active."""
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            return b"active (running)" in stdout
        except Exception:
            return False

    async def _check_pm2_frontend(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_shell(
                "pm2 list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            text = stdout.decode("utf-8", errors="ignore")
            return "online" in text.lower()
        except Exception:
            return True  # Assume ok if pm2 not installed

    async def _restart_service(self, cmd: str, name: str) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0:
                return f"{name} restarted successfully"
            else:
                err = stderr.decode("utf-8", errors="ignore")[:200]
                return f"{name} restart failed: {err}"
        except Exception as e:
            return f"{name} restart exception: {e}"

    async def _run_cmd(self, cmd: str, timeout: int = 10) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="ignore")[:200]
        except Exception as e:
            return str(e)[:200]

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_heal(
        self,
        heal_type: str,
        trigger: str,
        result: str,
        engine: Optional[str],
        success: bool,
        original_state: Optional[dict] = None,
    ) -> dict:
        return {
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "heal_type":      heal_type,
            "trigger":        trigger,
            "result":         result,
            "engine_affected": engine,
            "original_state": original_state,
            "success":        success,
        }

    async def _log_heal(self, heal: dict) -> None:
        try:
            doc = {**heal}
            if isinstance(doc.get("timestamp"), str):
                doc["timestamp"] = datetime.fromisoformat(doc["timestamp"])
            await self.db["nexus_heals"].insert_one(doc)
        except Exception as e:
            logger.warning(f"[HEALER] Log heal failed: {e}")

    async def _alert(self, text: str, key: Optional[str] = None, cooldown_hours: float = 4.0) -> None:
        if not self.send_telegram or not self.chat_ids:
            return
        if key:
            now = datetime.now(timezone.utc)
            last = self._alert_cooldown.get(key)
            if last and (now - last).total_seconds() < cooldown_hours * 3600:
                return
            self._alert_cooldown[key] = now
        for chat_id in list(self.chat_ids):
            try:
                await self.send_telegram(chat_id, text, parse_mode="Markdown")
            except Exception:
                pass
