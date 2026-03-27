"""
AlertThrottler - Shared alert throttling logic for trading engines.

Handles:
- Per-symbol cooldowns
- Daily alert limits
- Anti-contradiction direction locking
- Stale entry cleanup
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AlertThrottler:
    """
    Reusable alert throttling/deduplication for trading signal engines.

    Used by FreeWillEngineV2 and TradingStyleEngine (DualTradingEngine).
    """

    def __init__(
        self,
        cooldown_seconds: int,
        direction_lock_seconds: int,
        max_daily_alerts: int,
        name: str = "Engine",
    ):
        self.cooldown_seconds = cooldown_seconds
        self.direction_lock_seconds = direction_lock_seconds
        self.max_daily_alerts = max_daily_alerts
        self.name = name

        self.recent_alerts: Dict[str, datetime] = {}
        self.last_direction: Dict[str, tuple] = {}  # symbol -> (direction, timestamp)
        self.daily_alerts: int = 0
        self.contradictions_blocked: int = 0
        self.last_reset = datetime.now(timezone.utc).date()

    def _cleanup_old_tracking(self):
        """Remove entries older than 24h to prevent unbounded memory growth."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        self.recent_alerts = {k: v for k, v in self.recent_alerts.items() if v > cutoff}
        self.last_direction = {
            k: v for k, v in self.last_direction.items() if v[1] > cutoff
        }

    def _reset_daily(self):
        """Reset daily counter at midnight UTC; clean stale tracking on reset."""
        today = datetime.now(timezone.utc).date()
        if today > self.last_reset:
            self.daily_alerts = 0
            self.last_reset = today
            self._cleanup_old_tracking()

    def can_alert(self, symbol: str, direction: Optional[str] = None) -> bool:
        """
        Return True if an alert may be sent for this symbol/direction.

        Checks (in order):
        1. Daily limit not exceeded
        2. Per-symbol cooldown elapsed
        3. Direction not contradicting a recent opposite signal
        """
        self._reset_daily()

        if self.daily_alerts >= self.max_daily_alerts:
            return False

        now = datetime.now(timezone.utc)

        if symbol in self.recent_alerts:
            elapsed = (now - self.recent_alerts[symbol]).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False

        if direction and symbol in self.last_direction:
            last_dir, last_time = self.last_direction[symbol]
            elapsed = (now - last_time).total_seconds()
            if elapsed < self.direction_lock_seconds and last_dir != direction:
                logger.info(
                    f"[{self.name}] Blocked contradiction: {symbol} was {last_dir}, now {direction}"
                )
                self.contradictions_blocked += 1
                return False

        return True

    def mark_alerted(self, symbol: str, direction: Optional[str] = None):
        """Record that an alert was sent for this symbol."""
        now = datetime.now(timezone.utc)
        self.recent_alerts[symbol] = now
        self.daily_alerts += 1
        if direction:
            self.last_direction[symbol] = (direction, now)
