"""
AEON Critical Alert Monitors
Runs as background tasks, checks conditions, fires via unified_alert.send()
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable, List, Optional

logger = logging.getLogger(__name__)

# ── DrawdownMonitor ───────────────────────────────────────────────────────────

class DrawdownMonitor:
    """
    Checks paper trading account PnL every 5 minutes.
    Fires RISK alerts at -2%, -5%, -10% thresholds once per threshold per day.
    """

    THRESHOLDS = [-2.0, -5.0, -10.0]

    def __init__(self, db, alerter):
        self._db      = db
        self._alerter = alerter
        # {account_id: {threshold: date_str}}
        self._fired: dict = {}

    async def run_loop(self, interval: int = 300) -> None:
        while True:
            try:
                await self._check()
            except Exception as exc:
                logger.error(f"[DrawdownMonitor] Error: {exc}")
            await asyncio.sleep(interval)

    async def _check(self) -> None:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Enumerate accounts from paper_accounts collection
        try:
            cursor = self._db.paper_accounts.find({})
            async for account in cursor:
                account_id = account.get("account_id") or account.get("_id", "unknown")
                balance    = float(account.get("balance", 0))
                initial    = float(account.get("initial_balance") or account.get("starting_balance", balance))
                if initial <= 0:
                    continue

                pnl_pct = ((balance - initial) / initial) * 100.0

                for threshold in self.THRESHOLDS:
                    if pnl_pct <= threshold:
                        key = f"{account_id}:{threshold}"
                        fired_dates = self._fired.setdefault(key, set())
                        if today_str not in fired_dates:
                            fired_dates.add(today_str)
                            from unified_alert import AeonPersona
                            title, body = AeonPersona.risk_drawdown(
                                str(account_id), pnl_pct, threshold
                            )
                            await self._alerter.send(
                                level="RISK", title=title, body=body,
                                engine="DrawdownMonitor"
                            )
        except Exception as exc:
            logger.error(f"[DrawdownMonitor] _check failed: {exc}")


# ── LiquidationProximityMonitor ───────────────────────────────────────────────

class LiquidationProximityMonitor:
    """
    Checks all open paper positions every 60 seconds.
    Fires RISK alert if unrealized loss > 70% of margin on any position.
    Cooldown: once per position per 5 minutes.
    """

    def __init__(self, db, alerter):
        self._db       = db
        self._alerter  = alerter
        # {position_id: last_alert_ts}
        self._cooldowns: dict = {}

    async def run_loop(self, interval: int = 60) -> None:
        while True:
            try:
                await self._check()
            except Exception as exc:
                logger.error(f"[LiqProximityMonitor] Error: {exc}")
            await asyncio.sleep(interval)

    async def _check(self) -> None:
        now_ts  = datetime.now(timezone.utc).timestamp()
        cooldown_sec = 300  # 5 minutes

        try:
            cursor = self._db.paper_positions.find({"status": "open"})
            async for pos in cursor:
                pos_id     = str(pos.get("_id", ""))
                symbol     = pos.get("symbol", "UNKNOWN")
                direction  = pos.get("direction", "LONG")
                entry      = float(pos.get("entry_price") or pos.get("entry", 0))
                current    = float(pos.get("current_price") or pos.get("mark_price", entry))
                leverage   = float(pos.get("leverage", 1))
                pos_size   = float(pos.get("position_size") or pos.get("notional", 1000))

                if entry <= 0:
                    continue

                # Compute loss % relative to margin
                if direction.upper() == "LONG":
                    price_move_pct = (current - entry) / entry * 100
                else:
                    price_move_pct = (entry - current) / entry * 100

                # Leveraged loss % of margin
                loss_pct = -price_move_pct * leverage if price_move_pct < 0 else 0.0

                margin_size    = pos_size / leverage if leverage > 0 else pos_size
                unrealized_usd = pos_size * (-price_move_pct / 100) if price_move_pct < 0 else 0.0
                margin_remain  = max(0.0, margin_size - unrealized_usd)
                loss_vs_margin = (unrealized_usd / margin_size * 100) if margin_size > 0 else 0.0

                if loss_vs_margin > 70.0:
                    last_alert = self._cooldowns.get(pos_id, 0.0)
                    if now_ts - last_alert >= cooldown_sec:
                        self._cooldowns[pos_id] = now_ts
                        from unified_alert import AeonPersona
                        title, body = AeonPersona.liquidation_warning(
                            symbol, direction, loss_vs_margin, margin_remain
                        )
                        await self._alerter.send(
                            level="RISK", title=title, body=body,
                            pair=symbol, engine="LiquidationMonitor"
                        )
        except Exception as exc:
            logger.error(f"[LiqProximityMonitor] _check failed: {exc}")


# ── WinRateMonitor ────────────────────────────────────────────────────────────

class WinRateMonitor:
    """
    Checks last 20 closed trades every 30 minutes.
    Fires RISK if win_rate < 40% or 3+ consecutive losses on any engine.
    Cooldown: once per engine per 4 hours.
    """

    def __init__(self, db, alerter):
        self._db      = db
        self._alerter = alerter
        # {engine: last_alert_ts}
        self._cooldowns: dict = {}

    async def run_loop(self, interval: int = 1800) -> None:
        while True:
            try:
                await self._check()
            except Exception as exc:
                logger.error(f"[WinRateMonitor] Error: {exc}")
            await asyncio.sleep(interval)

    async def _check(self) -> None:
        now_ts       = datetime.now(timezone.utc).timestamp()
        cooldown_sec = 14400  # 4 hours
        sample_size  = 20

        try:
            # Fetch last 20 closed trades, grouped by engine
            cursor = self._db.paper_trades.find(
                {"status": "closed"},
                sort=[("closed_at", -1)],
                limit=sample_size * 5  # fetch extra to have per-engine samples
            )

            engine_trades: dict = {}
            async for trade in cursor:
                engine = trade.get("engine") or trade.get("strategy") or "unknown"
                engine_trades.setdefault(engine, []).append(trade)

            for engine, trades in engine_trades.items():
                recent = trades[:sample_size]
                if len(recent) < 5:
                    continue  # too few data points

                wins   = sum(1 for t in recent if float(t.get("pnl", 0)) > 0)
                losses = sum(1 for t in recent if float(t.get("pnl", 0)) <= 0)
                total  = wins + losses
                win_rate = (wins / total * 100) if total > 0 else 0.0

                # Consecutive losses (most recent first)
                consec = 0
                for t in trades:
                    if float(t.get("pnl", 0)) <= 0:
                        consec += 1
                    else:
                        break

                should_alert = win_rate < 40.0 or consec >= 3
                if not should_alert:
                    continue

                last_alert = self._cooldowns.get(engine, 0.0)
                if now_ts - last_alert < cooldown_sec:
                    continue

                self._cooldowns[engine] = now_ts
                from unified_alert import AeonPersona
                title, body = AeonPersona.win_rate_alert(engine, win_rate, total, consec)
                await self._alerter.send(
                    level="RISK", title=title, body=body, engine=engine
                )

        except Exception as exc:
            logger.error(f"[WinRateMonitor] _check failed: {exc}")


# ── EngineHeartbeatMonitor ────────────────────────────────────────────────────

class EngineHeartbeatMonitor:
    """
    Checks last signal timestamp per engine every 5 minutes.
    Fires SYSTEM alert if any engine hasn't fired in > 60 min.
    Cooldown: once per engine per 2 hours.
    """

    # Known engine names to check — matches engine field in signal_tracker / engine_trades
    ENGINES_TO_MONITOR = [
        "HYPER_ACCURACY", "YOLO_ENGINE", "INSTITUTIONAL_SCALPER",
        "VWAP_SCALPER", "FREE_WILL_V2", "DUAL_ENGINE_DAY",
        "DUAL_ENGINE_LT", "AUTONOMOUS_V2",
    ]

    def __init__(self, db, alerter):
        self._db      = db
        self._alerter = alerter
        # {engine: last_alert_ts}
        self._cooldowns: dict = {}

    async def run_loop(self, interval: int = 300) -> None:
        while True:
            try:
                await self._check()
            except Exception as exc:
                logger.error(f"[EngineHeartbeatMonitor] Error: {exc}")
            await asyncio.sleep(interval)

    async def _check(self) -> None:
        now_utc      = datetime.now(timezone.utc)
        now_ts       = now_utc.timestamp()
        silence_sec  = 3600   # 60 min
        cooldown_sec = 7200   # 2 hours

        try:
            for engine in self.ENGINES_TO_MONITOR:
                # Look in signal_tracker first, then engine_trades
                last_doc = None
                for collection in ("signal_tracker", "engine_trades", "paper_trades"):
                    last_doc = await self._db[collection].find_one(
                        {"engine": {"$regex": engine, "$options": "i"}},
                        sort=[("timestamp", -1)]
                    )
                    if last_doc:
                        break

                if not last_doc:
                    continue  # no record at all — engine may not have run yet, skip

                ts_raw = last_doc.get("timestamp") or last_doc.get("created_at")
                if ts_raw is None:
                    continue

                if isinstance(ts_raw, datetime):
                    last_ts = ts_raw.timestamp()
                else:
                    try:
                        last_ts = float(ts_raw)
                    except Exception:
                        continue

                age_sec = now_ts - last_ts
                if age_sec < silence_sec:
                    continue  # engine is alive

                # Check cooldown
                last_alert = self._cooldowns.get(engine, 0.0)
                if now_ts - last_alert < cooldown_sec:
                    continue

                self._cooldowns[engine] = now_ts
                minutes_silent = int(age_sec / 60)
                from unified_alert import AeonPersona
                title, body = AeonPersona.engine_offline(engine, minutes_silent)
                await self._alerter.send(
                    level="SYSTEM", title=title, body=body, engine=engine
                )

        except Exception as exc:
            logger.error(f"[EngineHeartbeatMonitor] _check failed: {exc}")


# ── DailySummaryScheduler ─────────────────────────────────────────────────────

class DailySummaryScheduler:
    """
    Fires at 23:59 UTC daily with a full daily performance summary.
    Guard: fires exactly once per UTC date.
    """

    def __init__(self, db, alerter):
        self._db       = db
        self._alerter  = alerter
        self._last_fired_date: Optional[str] = None

    async def run_loop(self, interval: int = 60) -> None:
        while True:
            try:
                await self._check()
            except Exception as exc:
                logger.error(f"[DailySummaryScheduler] Error: {exc}")
            await asyncio.sleep(interval)

    async def _check(self) -> None:
        now_utc  = datetime.now(timezone.utc)
        date_str = now_utc.strftime("%Y-%m-%d")

        # Fire only at 23:59 UTC and only once per day
        if now_utc.hour != 23 or now_utc.minute != 59:
            return
        if self._last_fired_date == date_str:
            return

        self._last_fired_date = date_str
        await self._send_summary(now_utc)

    async def _send_summary(self, now_utc: datetime) -> None:
        try:
            # Time range: today UTC
            today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

            # Closed trades today
            cursor = self._db.paper_trades.find({
                "status": "closed",
                "closed_at": {"$gte": today_start}
            })

            trades_list = []
            async for trade in cursor:
                trades_list.append(trade)

            total  = len(trades_list)
            wins   = sum(1 for t in trades_list if float(t.get("pnl", 0)) > 0)
            losses = total - wins

            pnl_values = [float(t.get("pnl_usd") or t.get("pnl", 0)) for t in trades_list]
            net_pnl    = sum(pnl_values)

            best_pnl   = max(pnl_values, default=0.0)
            worst_pnl  = min(pnl_values, default=0.0)

            best_trade = "—"
            worst_trade = "—"
            for t in trades_list:
                pnl = float(t.get("pnl_usd") or t.get("pnl", 0))
                sym = t.get("symbol", "UNKNOWN")
                if pnl == best_pnl:
                    best_trade = f"{sym} +${abs(pnl):,.2f}"
                if pnl == worst_pnl:
                    worst_trade = f"{sym} -${abs(pnl):,.2f}"

            # Quant blocks today
            quant_blocks = await self._db.suppressed_signals.count_documents({
                "timestamp": {"$gte": today_start}
            })

            # Active engines today
            engine_pipeline = [
                {"$match": {"timestamp": {"$gte": today_start}}},
                {"$group": {"_id": "$engine"}},
            ]
            eng_cursor = self._db.paper_trades.aggregate(engine_pipeline)
            engines_today = 0
            async for _ in eng_cursor:
                engines_today += 1

            from unified_alert import AeonPersona
            title, body = AeonPersona.daily_summary(
                trades=total, wins=wins, losses=losses,
                net_pnl_usd=net_pnl,
                best_trade=best_trade, worst_trade=worst_trade,
                quant_blocks=quant_blocks, engines_active=max(engines_today, 1)
            )
            await self._alerter.send(
                level="TRADE", title=title, body=body, engine="DailySummary"
            )
            logger.info(f"[DailySummaryScheduler] Summary sent for {now_utc.strftime('%Y-%m-%d')}")

        except Exception as exc:
            logger.error(f"[DailySummaryScheduler] _send_summary failed: {exc}")


# ── Module-level init ─────────────────────────────────────────────────────────

def init_monitors(db, alerter) -> List:
    """
    Create and return all monitor instances.
    Call from server.py lifespan — pass motor db and the UnifiedAlerter singleton.
    """
    monitors = [
        DrawdownMonitor(db, alerter),
        LiquidationProximityMonitor(db, alerter),
        WinRateMonitor(db, alerter),
        EngineHeartbeatMonitor(db, alerter),
        DailySummaryScheduler(db, alerter),
    ]
    logger.info(f"[AlertMonitors] {len(monitors)} monitors created")
    return monitors
