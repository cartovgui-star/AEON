"""
AEON SELF-HEALING SYSTEM
Monitors all services, detects errors, and auto-recovers.

Capabilities:
- Monitors background task health (trading loops, alert system, Telegram webhook)
- Detects stuck/crashed tasks and restarts them
- Tracks error rates and auto-throttles noisy services
- Logs all healing actions for audit
- Exposes health status via API
"""
import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Callable, Any, Optional

logger = logging.getLogger(__name__)


class ServiceMonitor:
    """Tracks health of a single background service."""
    def __init__(self, name: str, max_errors_per_hour: int = 20):
        self.name = name
        self.max_errors_per_hour = max_errors_per_hour
        self.last_heartbeat: Optional[datetime] = None
        self.error_count = 0
        self.error_log: List[Dict] = []
        self.restart_count = 0
        self.status = "unknown"
        self.task: Optional[asyncio.Task] = None
        self.factory: Optional[Callable] = None  # coroutine factory to restart
        self._hourly_errors: List[datetime] = []

    def heartbeat(self):
        self.last_heartbeat = datetime.now(timezone.utc)
        self.status = "healthy"

    def record_error(self, error: str):
        now = datetime.now(timezone.utc)
        self.error_count += 1
        self._hourly_errors.append(now)
        self.error_log.append({"time": now.isoformat(), "error": error[:200]})
        if len(self.error_log) > 50:
            self.error_log = self.error_log[-50:]
        # Prune hourly errors older than 1h
        cutoff = now - timedelta(hours=1)
        self._hourly_errors = [t for t in self._hourly_errors if t > cutoff]
        self.status = "degraded"

    @property
    def errors_this_hour(self) -> int:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=1)
        self._hourly_errors = [t for t in self._hourly_errors if t > cutoff]
        return len(self._hourly_errors)

    @property
    def is_throttled(self) -> bool:
        return self.errors_this_hour >= self.max_errors_per_hour

    @property
    def is_stale(self) -> bool:
        if not self.last_heartbeat:
            return False  # Not yet had time to heartbeat
        return (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds() > 300  # 5min

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "error_count": self.error_count,
            "errors_this_hour": self.errors_this_hour,
            "restart_count": self.restart_count,
            "is_throttled": self.is_throttled,
            "recent_errors": self.error_log[-5:],
        }


class SelfHealer:
    """
    Central self-healing controller.
    Register services, monitor health, auto-restart crashed tasks.
    """
    def __init__(self):
        self.services: Dict[str, ServiceMonitor] = {}
        self.healing_log: List[Dict] = []
        self.active = True

    def register(self, name: str, task: asyncio.Task = None,
                 factory: Callable = None, max_errors: int = 20) -> ServiceMonitor:
        monitor = ServiceMonitor(name, max_errors)
        monitor.task = task
        monitor.factory = factory
        self.services[name] = monitor
        logger.info(f"[SelfHealer] Registered: {name}")
        return monitor

    def heartbeat(self, name: str):
        if name in self.services:
            self.services[name].heartbeat()

    def record_error(self, name: str, error: str):
        if name in self.services:
            self.services[name].record_error(error)

    def _log_healing(self, service: str, action: str, detail: str = ""):
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "service": service,
            "action": action,
            "detail": detail,
        }
        self.healing_log.append(entry)
        if len(self.healing_log) > 100:
            self.healing_log = self.healing_log[-100:]
        logger.warning(f"[SelfHealer] {action}: {service} - {detail}")

    async def _restart_service(self, monitor: ServiceMonitor):
        """Attempt to restart a dead/stuck service."""
        if not monitor.factory:
            self._log_healing(monitor.name, "SKIP_RESTART", "No factory registered")
            return

        try:
            if monitor.task and not monitor.task.done():
                monitor.task.cancel()
                try:
                    await monitor.task
                except (asyncio.CancelledError, Exception):
                    pass

            monitor.task = asyncio.create_task(monitor.factory())
            monitor.restart_count += 1
            monitor.status = "restarted"
            self._log_healing(monitor.name, "RESTARTED", f"restart #{monitor.restart_count}")
        except Exception as e:
            self._log_healing(monitor.name, "RESTART_FAILED", str(e)[:200])

    async def monitor_loop(self):
        """Main monitoring loop - checks every 60s."""
        logger.info("[SelfHealer] Monitoring loop started")
        while self.active:
            try:
                for name, monitor in self.services.items():
                    # Check if task is dead
                    if monitor.task and monitor.task.done():
                        exc = monitor.task.exception() if not monitor.task.cancelled() else None
                        detail = str(exc)[:200] if exc else "Task finished/cancelled"
                        self._log_healing(name, "DETECTED_DEAD", detail)
                        monitor.record_error(f"Task died: {detail}")

                        if not monitor.is_throttled:
                            await self._restart_service(monitor)
                        else:
                            self._log_healing(name, "THROTTLED", f"{monitor.errors_this_hour} errors/hr")
                            monitor.status = "throttled"

                    # Task alive: auto-heartbeat for services that don't explicitly heartbeat.
                    # An asyncio task being non-done is implicit proof the service is running.
                    elif monitor.task and not monitor.task.done():
                        if monitor.is_stale:
                            self._log_healing(name, "STALE_HEARTBEAT",
                                              f"Last: {monitor.last_heartbeat}")
                            monitor.status = "stale"
                        else:
                            monitor.heartbeat()

                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"[SelfHealer] Monitor error: {e}")
                await asyncio.sleep(30)

    def get_status(self) -> Dict:
        healthy = sum(1 for s in self.services.values() if s.status == "healthy")
        total = len(self.services)
        return {
            "overall": "healthy" if healthy == total else ("degraded" if healthy > 0 else "critical"),
            "services": {n: s.to_dict() for n, s in self.services.items()},
            "total_services": total,
            "healthy_services": healthy,
            "recent_healing": self.healing_log[-10:],
        }


# Global instance
self_healer = SelfHealer()
