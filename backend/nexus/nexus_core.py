"""
NEXUS CORE — Master Orchestrator
==================================
AEON's autonomous nervous system. Runs as its own systemd service.
Independent from AEON's main process — if AEON crashes, NEXUS heals it.
If NEXUS crashes, AEON keeps trading.

Architecture:
  Port 8001 — FastAPI for /nexus_* command routing (AEON calls this)
  60s loop   — Oracle → Morpheus → Healer → Warden → Heartbeat

Collections:
  nexus_awareness    — hourly awareness snapshots
  nexus_adaptations  — every regime change
  nexus_heals        — every healing action
  nexus_alerts       — every Telegram message sent
  nexus_heartbeat    — 60s heartbeats
  nexus_config       — live config AEON reads to apply overrides

Run:
  python nexus/nexus_core.py
  OR: python -m nexus.nexus_core
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Set

# ── Bootstrap: load .env from backend dir ─────────────────────────────────────
_BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv(_BACKEND_DIR / ".env")
except ImportError:
    # Manual parse if python-dotenv not available
    _env_file = _BACKEND_DIR / ".env"
    if _env_file.exists():
        for line in _env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

# ── Setup logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [NEXUS] %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nexus_core")

# ── Imports (after sys.path set) ──────────────────────────────────────────────
from nexus.oracle_sense       import OracleSense
from nexus.morpheus           import Morpheus
from nexus.healer             import Healer
from nexus.warden             import Warden
from nexus.telegram_commander import TelegramCommander

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    _MOTOR = True
except ImportError:
    _MOTOR = False
    logger.warning("motor not installed — MongoDB unavailable")

try:
    import ccxt
    _CCXT = True
except ImportError:
    _CCXT = False
    logger.warning("ccxt not installed — market data unavailable")

try:
    from fastapi import FastAPI
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    logger.warning("fastapi/uvicorn not installed — API server unavailable")

# ── Config ────────────────────────────────────────────────────────────────────
MONGO_URL      = os.environ.get("MONGO_URL",       "mongodb://127.0.0.1:27017/aeon")
DB_NAME        = os.environ.get("DB_NAME",         "aeon")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN",  "")
MEXC_KEY       = os.environ.get("MEXC_API_KEY",    "")
MEXC_SECRET    = os.environ.get("MEXC_SECRET_KEY", "")
NEXUS_PORT     = int(os.environ.get("NEXUS_PORT",  "8001"))
LOOP_INTERVAL  = 60   # seconds

# Austin timezone offset (UTC-5 or UTC-6 depending on DST) — use UTC comparison
DAILY_BRIEF_HOUR_UTC = 12   # 6AM Austin CST = UTC-6 → 12 UTC; CDT = UTC-5 → 11 UTC


class NexusCore:
    """
    Master orchestrator. Initializes all 4 layers, runs the master loop,
    and exposes a FastAPI app on port 8001 for AEON to call /nexus/* commands.
    """

    def __init__(self):
        self.db          = None
        self.exchange    = None
        self.chat_ids: Set[int] = set()

        self.oracle:    Optional[OracleSense]       = None
        self.morpheus:  Optional[Morpheus]          = None
        self.healer:    Optional[Healer]            = None
        self.warden:    Optional[Warden]            = None
        self.commander: Optional[TelegramCommander] = None

        self._last_snapshot:   Optional[dict] = None
        self._daily_brief_sent_date: Optional[str] = None
        self._running          = False
        self._loop_errors      = 0
        self._start_time       = datetime.now(timezone.utc)

    # ── Initialization ─────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        logger.info("NEXUS initializing...")

        # MongoDB
        if _MOTOR:
            try:
                client   = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
                self.db  = client[DB_NAME]
                await self.db.command("ping")
                logger.info(f"NEXUS connected to MongoDB: {DB_NAME}")
            except Exception as e:
                logger.error(f"NEXUS MongoDB connection failed: {e}")
                self.db = None

        # MEXC exchange (for market data)
        if _CCXT:
            try:
                self.exchange = ccxt.mexc({
                    "apiKey":    MEXC_KEY,
                    "secret":    MEXC_SECRET,
                    "enableRateLimit": True,
                })
                logger.info("NEXUS MEXC exchange connected")
            except Exception as e:
                logger.warning(f"NEXUS MEXC init failed: {e}")
                self.exchange = None

        # Load chat_ids from MongoDB
        if self.db is not None:
            try:
                existing = await self.db.chat_messages.distinct("chat_id")
                self.chat_ids = set(existing)
                logger.info(f"NEXUS loaded {len(self.chat_ids)} chat IDs")
            except Exception as e:
                logger.warning(f"NEXUS chat_ids load failed: {e}")

        # Build send_telegram function
        send_tg = self._make_send_telegram()

        # Initialize all layers
        self.oracle    = OracleSense(self.db, self.exchange)
        self.morpheus  = Morpheus(self.db, send_tg, self.chat_ids)
        self.healer    = Healer(self.db, send_tg, self.chat_ids)
        self.warden    = Warden(self.db, send_tg, self.chat_ids)
        self.commander = TelegramCommander(TELEGRAM_TOKEN, self.db, self.chat_ids)

        logger.info("NEXUS all layers initialized — AEON is alive.")

    def _make_send_telegram(self):
        """Build a send_telegram coroutine for layers to use."""
        token = TELEGRAM_TOKEN

        async def _send(chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    payload = {"chat_id": chat_id, "text": text}
                    if parse_mode:
                        payload["parse_mode"] = parse_mode
                    await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json=payload,
                    )
            except Exception as e:
                logger.debug(f"[NEXUS] Telegram send error: {e}")

        return _send

    # ── Master loop ────────────────────────────────────────────────────────────

    async def run_forever(self) -> None:
        self._running = True
        logger.info(f"NEXUS master loop started (interval={LOOP_INTERVAL}s)")

        # First tick immediately
        await self._tick()

        while self._running:
            await asyncio.sleep(LOOP_INTERVAL)
            await self._tick()

    async def _tick(self) -> None:
        tick_start = time.monotonic()
        now        = datetime.now(timezone.utc)

        try:
            # ── STEP 1: ORACLE_SENSE — full awareness snapshot ─────────────────
            snapshot = None
            if self.oracle is not None and self.db is not None:
                try:
                    snapshot = await asyncio.wait_for(
                        self.oracle.compute_snapshot(), timeout=45.0
                    )
                    self._last_snapshot = snapshot
                    logger.debug(f"[NEXUS] Oracle: regime={snapshot.get('market_regime')} "
                                 f"H_market={snapshot.get('H_market', 0):.4f}")
                except asyncio.TimeoutError:
                    logger.warning("[NEXUS] Oracle snapshot timed out — using last")
                    snapshot = self._last_snapshot
                except Exception as e:
                    logger.error(f"[NEXUS] Oracle error: {e}")
                    snapshot = self._last_snapshot

            # ── STEP 2: MORPHEUS — check and adapt ───────────────────────────
            if self.morpheus and snapshot:
                try:
                    await asyncio.wait_for(
                        self.morpheus.check_and_adapt(snapshot), timeout=15.0
                    )
                except Exception as e:
                    logger.error(f"[NEXUS] Morpheus error: {e}")

            # ── STEP 3: HEALER — scan and heal ───────────────────────────────
            heals = []
            if self.healer:
                try:
                    heals = await asyncio.wait_for(
                        self.healer.scan_and_heal(snapshot), timeout=30.0
                    )
                    if heals:
                        logger.info(f"[NEXUS] Healer: {len(heals)} actions taken")
                except Exception as e:
                    logger.error(f"[NEXUS] Healer error: {e}")

            # ── STEP 4: WARDEN — check and repair interface ──────────────────
            warden_checks = []
            if self.warden:
                try:
                    warden_checks = await asyncio.wait_for(
                        self.warden.check_and_repair(), timeout=30.0
                    )
                except Exception as e:
                    logger.error(f"[NEXUS] Warden error: {e}")

            # ── STEP 5: Daily intelligence report ────────────────────────────
            today_str = now.strftime("%Y-%m-%d")
            if (now.hour == DAILY_BRIEF_HOUR_UTC and
                    self._daily_brief_sent_date != today_str and
                    self.commander):
                try:
                    await self.commander.send_daily_brief(snapshot)
                    self._daily_brief_sent_date = today_str
                except Exception as e:
                    logger.error(f"[NEXUS] Daily brief error: {e}")

            # ── STEP 6: Heartbeat to MongoDB ─────────────────────────────────
            elapsed = time.monotonic() - tick_start
            await self._log_heartbeat(snapshot, len(heals), len(warden_checks), elapsed)

            self._loop_errors = 0  # Reset error counter on success
            logger.debug(f"[NEXUS] Tick complete in {elapsed:.2f}s")

        except Exception as e:
            self._loop_errors += 1
            logger.exception(f"[NEXUS] Master loop tick error #{self._loop_errors}: {e}")
            if self._loop_errors >= 5:
                await self._emergency_alert(str(e))

    async def _log_heartbeat(
        self,
        snapshot: Optional[dict],
        heals: int,
        warden_issues: int,
        elapsed: float,
    ) -> None:
        if self.db is None:
            return
        try:
            doc = {
                "timestamp":      datetime.now(timezone.utc),
                "elapsed_sec":    round(elapsed, 2),
                "heals_this_tick": heals,
                "warden_issues":  warden_issues,
                "market_regime":  snapshot.get("market_regime", "?") if snapshot else "?",
                "H_market":       snapshot.get("H_market", 0.0) if snapshot else 0.0,
                "health_H":       snapshot.get("health_H", 0.0) if snapshot else 0.0,
                "crisis":         snapshot.get("crisis_mode", False) if snapshot else False,
                "loop_errors":    self._loop_errors,
                "uptime_sec":     (datetime.now(timezone.utc) - self._start_time).total_seconds(),
            }
            await self.db["nexus_heartbeat"].insert_one(doc)
            # Keep last 1440 (24h at 60s intervals)
            count = await self.db["nexus_heartbeat"].count_documents({})
            if count > 1440:
                oldest = await self.db["nexus_heartbeat"].find_one(sort=[("timestamp", 1)])
                if oldest:
                    await self.db["nexus_heartbeat"].delete_one({"_id": oldest["_id"]})
        except Exception:
            pass

    async def _emergency_alert(self, error: str) -> None:
        msg = (
            f"🚨 *NEXUS INTERNAL ERROR*\n\n"
            f"Loop errors: `{self._loop_errors}`\n"
            f"Error: `{error[:200]}`\n\n"
            f"NEXUS is degraded but continuing. Check nexus logs."
        )
        if self.commander:
            await self.commander.broadcast(msg)

    # ── Command handlers ───────────────────────────────────────────────────────

    async def handle_command(self, command: str, chat_id: int) -> str:
        """
        Route /nexus_* commands from AEON's Telegram handler.
        AEON calls POST /nexus/cmd with {"command": "nexus_status", "chat_id": ...}
        and returns this response text to the user.
        """
        cmd = command.lower().strip().lstrip("/")

        if cmd == "nexus_status":
            heals_24h = await self._count_24h("nexus_heals")
            adapt_24h = await self._count_24h("nexus_adaptations")
            return self.commander.format_status(self._last_snapshot, heals_24h, adapt_24h)

        elif cmd == "nexus_regime":
            return self.commander.format_regime(self._last_snapshot)

        elif cmd == "nexus_engines":
            return self.commander.format_engines(self._last_snapshot)

        elif cmd == "nexus_health":
            return self.commander.format_health(self._last_snapshot)

        elif cmd == "nexus_positions":
            return self.commander.format_positions(self._last_snapshot)

        elif cmd == "nexus_pause":
            if self.morpheus:
                await self.morpheus.manual_pause()
            return "NEXUS: Trading PAUSED. All engines blocked. Send /nexus_resume to restart."

        elif cmd == "nexus_resume":
            if self.morpheus:
                await self.morpheus.manual_resume(self._last_snapshot)
            return "NEXUS: Trading RESUMED. Regime-appropriate configuration applied."

        elif cmd == "nexus_crisis":
            if self.morpheus and self._last_snapshot:
                snap = dict(self._last_snapshot)
                snap["crisis_mode"] = True
                snap["crisis_just_triggered"] = True
                snap["correlation_max"] = 1.0
                await self.morpheus.check_and_adapt(snap)
            return "NEXUS: CRISIS MODE manually triggered. All positions being closed, engines halted."

        elif cmd == "nexus_heal":
            if self.healer:
                heals = await self.healer.scan_and_heal(self._last_snapshot)
                return f"NEXUS HEALER: Scan complete. {len(heals)} action(s) taken."
            return "NEXUS: Healer not initialized."

        elif cmd == "nexus_adapt":
            if self.morpheus and self._last_snapshot:
                result = await self.morpheus.force_reconfigure(self._last_snapshot)
                return f"NEXUS MORPHEUS: {result}"
            return "NEXUS: Morpheus not initialized or no snapshot available."

        else:
            return (
                f"NEXUS Commands:\n"
                f"/nexus_status — Full system snapshot\n"
                f"/nexus_regime — Market regime + entropy\n"
                f"/nexus_engines — All 9 engine statuses\n"
                f"/nexus_health — System health H score\n"
                f"/nexus_positions — Open positions\n"
                f"/nexus_pause — Pause all trading\n"
                f"/nexus_resume — Resume trading\n"
                f"/nexus_crisis — Trigger crisis mode\n"
                f"/nexus_heal — Force healer scan\n"
                f"/nexus_adapt — Force MORPHEUS reconfigure"
            )

    async def _count_24h(self, collection: str) -> int:
        if self.db is None:
            return 0
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            return await self.db[collection].count_documents({"timestamp": {"$gte": cutoff}})
        except Exception:
            return 0

    def get_snapshot_summary(self) -> dict:
        """For the /nexus/status API endpoint."""
        if not self._last_snapshot:
            return {"status": "initializing", "uptime_sec": 0}
        snap = self._last_snapshot
        return {
            "status":         "running",
            "market_regime":  snap.get("market_regime", "?"),
            "H_market":       snap.get("H_market", 0.0),
            "health_H":       snap.get("health_H", 0.0),
            "crisis":         snap.get("crisis_mode", False),
            "uptime_sec":     (datetime.now(timezone.utc) - self._start_time).total_seconds(),
            "loop_errors":    self._loop_errors,
        }


# ── FastAPI app ────────────────────────────────────────────────────────────────

_nexus_instance: Optional[NexusCore] = None

if _FASTAPI:
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI(title="NEXUS", version="1.0.0")

    class CmdRequest(BaseModel):
        command:  str
        chat_id:  int = 0

    @app.post("/nexus/cmd")
    async def nexus_cmd(req: CmdRequest):
        global _nexus_instance
        if not _nexus_instance:
            return {"response": "NEXUS: not initialized yet. Retry in 30 seconds."}
        response = await _nexus_instance.handle_command(req.command, req.chat_id)
        return {"response": response}

    @app.get("/nexus/status")
    async def nexus_status():
        global _nexus_instance
        if not _nexus_instance:
            return {"status": "starting"}
        return _nexus_instance.get_snapshot_summary()

    @app.get("/nexus/health")
    async def nexus_health():
        return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    global _nexus_instance

    nexus = NexusCore()
    _nexus_instance = nexus
    await nexus.initialize()

    if _FASTAPI:
        # Run FastAPI in background
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=NEXUS_PORT,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        await asyncio.gather(
            server.serve(),
            nexus.run_forever(),
        )
    else:
        await nexus.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("NEXUS shutdown requested")
    except Exception as e:
        logger.critical(f"NEXUS fatal error: {e}", exc_info=True)
        sys.exit(1)
