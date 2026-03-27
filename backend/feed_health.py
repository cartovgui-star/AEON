"""
AEON Feed Health Monitor
Tracks external data feed availability and provides graceful degradation.
"""
import asyncio
import logging
import time
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

OFFLINE_MESSAGE = (
    "⚠️ AEON data feed is currently offline. "
    "Your broker's live feed is unaffected. "
    "We'll be back shortly."
)

# Lightweight ping endpoints for each critical data source
_PROBE_TARGETS = [
    ("MEXC",      "https://api.mexc.com/api/v3/ping"),
    ("CoinGecko", "https://api.coingecko.com/api/v3/ping"),
]
_PROBE_TIMEOUT   = 5.0   # seconds per probe
_RECOVERY_INTERVAL = 30  # seconds between retries when degraded
_KEEPALIVE_INTERVAL = 300  # seconds between checks when healthy


class FeedHealthMonitor:
    """
    Monitors external data feed reachability.

    Usage:
    - Read `is_healthy` before processing any data-dependent command.
    - Call `start_recovery_loop()` once at startup.
    - Call `stop()` on shutdown.
    """

    def __init__(self):
        self._feed_status: Dict[str, bool] = {name: True for name, _ in _PROBE_TARGETS}
        self._healthy: bool = True
        self._last_probe: float = 0.0
        self._recovery_task: Optional[asyncio.Task] = None
        self._stopped: bool = False

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    @property
    def feed_status(self) -> Dict[str, bool]:
        return dict(self._feed_status)

    def status_line(self) -> str:
        """One-line summary for /ping and /status."""
        if self._healthy:
            return "🟢 Data feeds online"
        parts = [f"{'🟢' if ok else '🔴'} {name}" for name, ok in self._feed_status.items()]
        return "🔴 Feeds degraded: " + " | ".join(parts)

    async def probe(self) -> bool:
        """
        Probe all configured feed endpoints.
        Returns True if at least one feed responds successfully.
        """
        ok_count = 0
        try:
            async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
                for name, url in _PROBE_TARGETS:
                    try:
                        resp = await client.get(url)
                        reachable = resp.status_code < 500
                    except Exception as e:
                        logger.debug("FeedHealthMonitor: probe failed for %s: %s", name, e)
                        reachable = False
                    self._feed_status[name] = reachable
                    if reachable:
                        ok_count += 1
        except Exception as e:
            logger.error("FeedHealthMonitor: probe client error: %s", e)

        was_healthy = self._healthy
        self._healthy = ok_count >= 1
        self._last_probe = time.monotonic()

        if was_healthy and not self._healthy:
            logger.warning("FeedHealthMonitor: feeds went OFFLINE — %s", self._feed_status)
        elif not was_healthy and self._healthy:
            logger.info("FeedHealthMonitor: feeds back ONLINE — %s", self._feed_status)

        return self._healthy

    async def initial_probe(self, retries: int = 3, delay: float = 2.0) -> bool:
        """
        Startup probe — retries a few times before marking feeds as offline.
        Avoids false-negative on startup when engines are hammering external APIs.
        """
        for attempt in range(1, retries + 1):
            result = await self.probe()
            if result:
                return True
            if attempt < retries:
                logger.info("FeedHealthMonitor: startup probe attempt %d/%d failed, retrying in %.0fs…", attempt, retries, delay)
                await asyncio.sleep(delay)
        logger.warning("FeedHealthMonitor: feeds offline after %d startup attempts", retries)
        return False

    def start_recovery_loop(self) -> None:
        """
        Start the background probe loop.
        - When healthy: re-probes every 5 minutes as a keep-alive.
        - When degraded: re-probes every 30 seconds to detect recovery.
        Safe to call multiple times — won't double-start.
        """
        if self._recovery_task and not self._recovery_task.done():
            return
        self._stopped = False
        self._recovery_task = asyncio.create_task(self._recovery_loop())
        logger.info("FeedHealthMonitor: recovery loop started")

    def stop(self) -> None:
        """Cancel the background loop (call on server shutdown)."""
        self._stopped = True
        if self._recovery_task:
            self._recovery_task.cancel()

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _recovery_loop(self) -> None:
        try:
            while not self._stopped:
                interval = _RECOVERY_INTERVAL if not self._healthy else _KEEPALIVE_INTERVAL
                await asyncio.sleep(interval)
                if not self._stopped:
                    await self.probe()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("FeedHealthMonitor: recovery loop crashed: %s", e)


# Module-level singleton — import `feed_health` everywhere it's needed
feed_health = FeedHealthMonitor()
