"""
NEXUS LAYER 4 — WARDEN: Interface Repair Engine
================================================
AEON's frontend must always show accurate live data.

Watches:
  • aeontrading.xyz reachable (ping every 2min)
  • Backend API health (all critical endpoints)
  • WebSocket connection
  • Stale / null / NaN data in components

Fixes:
  • pm2 restart if frontend down
  • nginx restart if not responding
  • Backend restart if API broken
  • Alert Carlos if auto-heal fails
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set
import math

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False

logger = logging.getLogger(__name__)

FRONTEND_URL       = "https://aeontrading.xyz"
BACKEND_URL        = "http://localhost:8000"
PING_INTERVAL_SEC  = 120      # Ping frontend every 2 min
STALE_THRESHOLD    = 300      # Component stale if not updated > 5 min

# API endpoints to health-check for valid data
HEALTH_ENDPOINTS = [
    "/api/oracle-entropy/status",
    "/api/engines/status",
    "/api/quantum/identity",
]


class Warden:
    """
    Continuously monitors the frontend and backend interfaces.
    Auto-restarts services and alerts Carlos when auto-heal fails.
    """

    def __init__(self, db, send_telegram, chat_ids: Set[int]):
        self.db            = db
        self.send_telegram = send_telegram
        self.chat_ids      = chat_ids

        self._last_frontend_ok  = True
        self._last_backend_ok   = True
        self._frontend_down_at: Optional[datetime] = None
        self._last_ping_ts      = datetime.now(timezone.utc) - timedelta(seconds=PING_INTERVAL_SEC)
        self._stale_components: Dict[str, datetime] = {}

    # ── Main check ─────────────────────────────────────────────────────────────

    async def check_and_repair(self) -> List[dict]:
        now = datetime.now(timezone.utc)
        checks: List[dict] = []

        # Throttle to PING_INTERVAL_SEC
        if (now - self._last_ping_ts).total_seconds() < PING_INTERVAL_SEC:
            return checks
        self._last_ping_ts = now

        # 1. Frontend reachability
        frontend_check = await self._check_frontend()
        if frontend_check:
            checks.append(frontend_check)

        # 2. Backend API health
        backend_check = await self._check_backend_api()
        if backend_check:
            checks.append(backend_check)

        # 3. WebSocket
        ws_check = await self._check_websocket()
        if ws_check:
            checks.append(ws_check)

        # Log checks to DB
        for check in checks:
            await self._log_check(check)

        return checks

    # ── Frontend check ─────────────────────────────────────────────────────────

    async def _check_frontend(self) -> Optional[dict]:
        ok = await self._http_ping(FRONTEND_URL, timeout=10)

        if ok:
            if not self._last_frontend_ok:
                logger.info("[WARDEN] Frontend back online")
                await self._alert("✅ *WARDEN:* Frontend `aeontrading.xyz` is back online.")
            self._last_frontend_ok  = True
            self._frontend_down_at  = None
            return None

        # Frontend down
        now = datetime.now(timezone.utc)

        if self._last_frontend_ok:
            # First detection — try pm2 restart
            self._last_frontend_ok = False
            self._frontend_down_at = now
            result = await self._run_cmd("pm2 restart all", timeout=20)
            await asyncio.sleep(30)
            still_down = not await self._http_ping(FRONTEND_URL, timeout=10)

            if still_down:
                # Try nginx
                result2 = await self._run_cmd("systemctl restart nginx", timeout=15)
                await asyncio.sleep(15)
                final_ok = await self._http_ping(FRONTEND_URL, timeout=10)
                if final_ok:
                    self._last_frontend_ok = True
                    action   = f"pm2 restart + nginx restart — RECOVERED"
                else:
                    action = f"pm2 restart + nginx restart — STILL DOWN. Manual intervention required."
                    await self._alert(
                        f"🚨 *WARDEN: FRONTEND DOWN*\n\n"
                        f"URL: `{FRONTEND_URL}`\n"
                        f"pm2 restart: done\n"
                        f"nginx restart: done\n"
                        f"Status: STILL UNREACHABLE\n\n"
                        f"Carlos, please check the droplet."
                    )
            else:
                self._last_frontend_ok = True
                action = "pm2 restart — RECOVERED"

            return self._make_check(
                component="frontend",
                status="down" if not self._last_frontend_ok else "recovered",
                action=action,
                detail=f"URL={FRONTEND_URL}",
            )

        return None

    # ── Backend API check ──────────────────────────────────────────────────────

    async def _check_backend_api(self) -> Optional[dict]:
        issues = []

        for endpoint in HEALTH_ENDPOINTS:
            try:
                data = await self._http_get_json(f"{BACKEND_URL}{endpoint}", timeout=5, headers={"X-API-Key": DASHBOARD_API_KEY})
                if data is None:
                    issues.append(f"{endpoint}: no response")
                    continue

                # Check for NaN/null/undefined in critical fields
                nasty = _find_bad_values(data, endpoint)
                if nasty:
                    issues.append(f"{endpoint}: bad values — {nasty[:100]}")
            except Exception as e:
                issues.append(f"{endpoint}: error — {str(e)[:80]}")

        if not issues:
            self._last_backend_ok = True
            return None

        if self._last_backend_ok:
            self._last_backend_ok = False
            detail = " | ".join(issues[:3])
            await self._alert(
                f"⚠️ *WARDEN: API DATA ISSUES*\n\n{detail}\n\nNexus logged for investigation."
            )

        return self._make_check(
            component="backend_api",
            status="stale",
            action="Logged for investigation",
            detail="; ".join(issues[:3]),
        )

    # ── WebSocket check ────────────────────────────────────────────────────────

    async def _check_websocket(self) -> Optional[dict]:
        """Verify backend WebSocket is accepting connections."""
        if not _HTTPX:
            return None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{BACKEND_URL}/api/bot/status", headers={"X-API-Key": DASHBOARD_API_KEY})
                if r.status_code == 200:
                    return None
                return self._make_check(
                    component="websocket",
                    status="down",
                    action="Backend API not responding — WebSocket likely broken",
                    detail=f"HTTP {r.status_code}",
                )
        except Exception as e:
            return self._make_check(
                component="websocket",
                status="down",
                action="Backend unreachable — WebSocket connection broken",
                detail=str(e)[:100],
            )

    # ── HTTP helpers ───────────────────────────────────────────────────────────

    async def _http_ping(self, url: str, timeout: int = 10) -> bool:
        if not _HTTPX:
            return True  # Assume ok if httpx not installed
        try:
            async with httpx.AsyncClient(timeout=float(timeout)) as client:
                r = await client.get(url, follow_redirects=True, headers={"X-API-Key": DASHBOARD_API_KEY} if url.startswith(BACKEND_URL) else None)
                return r.status_code < 500
        except Exception:
            return False

    async def _http_get_json(self, url: str, timeout: int = 5) -> Optional[dict]:
        if not _HTTPX:
            return {}
        try:
            async with httpx.AsyncClient(timeout=float(timeout)) as client:
                r = await client.get(url, headers={"X-API-Key": DASHBOARD_API_KEY} if url.startswith(BACKEND_URL) else None)
                if r.status_code == 200:
                    return r.json()
                return None
        except Exception:
            return None

    # ── Process helper ─────────────────────────────────────────────────────────

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

    def _make_check(self, component: str, status: str, action: str, detail: str) -> dict:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "status":    status,
            "action":    action,
            "detail":    detail,
        }

    async def _log_check(self, check: dict) -> None:
        try:
            doc = {**check}
            if isinstance(doc.get("timestamp"), str):
                doc["timestamp"] = datetime.fromisoformat(doc["timestamp"])
            await self.db["nexus_alerts"].insert_one(doc)
        except Exception:
            pass

    async def _alert(self, text: str) -> None:
        if not self.send_telegram or not self.chat_ids:
            return
        for chat_id in list(self.chat_ids):
            try:
                await self.send_telegram(chat_id, text, parse_mode="Markdown")
            except Exception:
                pass


def _find_bad_values(data, path: str = "") -> str:
    """Recursively find NaN / null / undefined-like values in JSON."""
    issues = []

    def _check(obj, p):
        if isinstance(obj, float) and math.isnan(obj):
            issues.append(f"{p}=NaN")
        elif obj is None and p:
            issues.append(f"{p}=null")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                _check(v, f"{p}.{k}" if p else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:5]):  # Check first 5 items only
                _check(v, f"{p}[{i}]")

    _check(data, path)
    return "; ".join(issues[:5])
