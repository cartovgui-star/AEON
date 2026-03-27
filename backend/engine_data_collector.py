"""
Engine Data Collector
- Every 15 min: resolve FW/Dual alert outcomes (WIN/LOSS/EXPIRED)
- Every hour: snapshot all engine stats -> engine_snapshots collection
- Every 6 hours: analyze confirmation accuracy -> confirmation_accuracy collection
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def snapshot_all_engines(db, app_state) -> Dict[str, Any]:
    """Collect stats from all engines and return snapshot dict"""
    snapshot: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc),
        "engines": {}
    }

    # Autonomous V2
    try:
        trader = getattr(app_state, "autonomous_trader_v2", None)
        if trader is not None:
            stats = await trader.get_stats()
            snapshot["engines"]["autonomous_v2"] = {
                "active": stats.get("active"),
                "win_rate": stats.get("win_rate"),
                "total_trades": stats.get("total_trades"),
                "wins": stats.get("wins"),
                "losses": stats.get("losses"),
                "total_pnl_pct": stats.get("total_pnl_pct"),
                "avg_win_pct": stats.get("avg_win_pct"),
                "avg_loss_pct": stats.get("avg_loss_pct"),
                "profit_factor": stats.get("profit_factor"),
                "expectancy": stats.get("expectancy"),
                "open_trades": stats.get("open_trades"),
                "total_signals_analyzed": stats.get("total_signals_analyzed"),
            }
    except Exception as e:
        logger.warning(f"autonomous_v2 snapshot error: {e}")
        snapshot["engines"]["autonomous_v2"] = {"error": str(e)}

    # Free Will V2
    try:
        fw = getattr(app_state, "free_will_v2", None)
        if fw is not None:
            stats = await fw.get_stats()
            snapshot["engines"]["free_will_v2"] = {
                "active": stats.get("active"),
                "total_alerts_sent": stats.get("total_alerts_sent"),
                "daily_alerts": stats.get("daily_alerts"),
                "setups_analyzed": stats.get("setups_analyzed"),
                "contradictions_blocked": stats.get("contradictions_blocked"),
                "min_confidence": stats.get("min_confidence"),
                "min_confirmations": stats.get("min_confirmations"),
            }
    except Exception as e:
        logger.warning(f"free_will_v2 snapshot error: {e}")
        snapshot["engines"]["free_will_v2"] = {"error": str(e)}

    # Dual Engine (Day Trader + Long Term)
    try:
        dual = getattr(app_state, "dual_engine", None)
        if dual is not None:
            stats = dual.get_stats()
            dt = stats.get("day_trader", {})
            lt = stats.get("long_term", {})
            snapshot["engines"]["dual_day_trader"] = {
                "active": dt.get("active"),
                "total_alerts": dt.get("total_alerts"),
                "daily_alerts": dt.get("daily_alerts"),
                "setups_analyzed": dt.get("setups_analyzed"),
                "min_confidence": dt.get("min_confidence"),
            }
            snapshot["engines"]["dual_long_term"] = {
                "active": lt.get("active"),
                "total_alerts": lt.get("total_alerts"),
                "daily_alerts": lt.get("daily_alerts"),
                "setups_analyzed": lt.get("setups_analyzed"),
                "min_confidence": lt.get("min_confidence"),
            }
    except Exception as e:
        logger.warning(f"dual_engine snapshot error: {e}")
        snapshot["engines"]["dual_engine"] = {"error": str(e)}

    # Elite Strategy V3
    try:
        adv = getattr(app_state, "advanced_strategies", None)
        intel = getattr(app_state, "enhanced_intel", None)
        if adv is not None:
            from elite_strategy_v3 import get_elite_strategy
            elite = get_elite_strategy(adv, None, intel)
            stats = elite.get_stats()
            snapshot["engines"]["elite_v3"] = {
                "active": stats.get("enabled"),
                "mode": stats.get("mode"),
                "signals_generated": stats.get("signals_generated"),
                "signals_filtered": stats.get("signals_filtered"),
                "daily_trades": stats.get("daily_trades"),
                "max_daily_trades": stats.get("max_daily_trades"),
                "top_filter_reasons": dict(list(stats.get("filter_reasons", {}).items())[:5]),
            }
    except Exception as e:
        logger.warning(f"elite_v3 snapshot error: {e}")
        snapshot["engines"]["elite_v3"] = {"error": str(e)}

    # VWAP Scalper
    try:
        vwap = getattr(app_state, "vwap_scalper", None)
        if vwap is not None:
            stats = vwap.get_stats()
            snapshot["engines"]["vwap_scalper"] = {
                "active": stats.get("active"),
                "total_trades": stats.get("total_trades"),
                "wins": stats.get("wins"),
                "losses": stats.get("losses"),
                "win_rate": stats.get("win_rate"),
                "signals_today": stats.get("signals_today"),
            }
    except Exception as e:
        logger.warning(f"vwap_scalper snapshot error: {e}")
        snapshot["engines"]["vwap_scalper"] = {"error": str(e)}

    # YOLO Engine
    try:
        yolo = getattr(app_state, "yolo_engine", None)
        if yolo is not None:
            stats = yolo.get_stats()
            eng = stats.get("stats", {})
            snapshot["engines"]["yolo"] = {
                "active": stats.get("active"),
                "total_signals": eng.get("total_signals"),
                "daily_signals": eng.get("daily_signals"),
                "wins": eng.get("wins"),
                "losses": eng.get("losses"),
                "win_rate": eng.get("win_rate"),
                "trades_opened": eng.get("trades_opened"),
            }
    except Exception as e:
        logger.warning(f"yolo snapshot error: {e}")
        snapshot["engines"]["yolo"] = {"error": str(e)}

    return snapshot


async def resolve_alert_outcomes(db, market_intel) -> int:
    """
    For pending FW/Dual alerts from the last 48h, check if current price
    has hit TP (WIN) or SL (LOSS). Alerts older than 24h with no outcome -> EXPIRED.
    Returns number of outcomes resolved.
    """
    resolved = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    for collection_name in ["free_will_alerts", "dual_alerts"]:
        try:
            col = db[collection_name]
            pending = await col.find({
                "outcome": {"$exists": False},
                "timestamp": {"$gte": cutoff}
            }).to_list(300)

            for alert in pending:
                setup = alert.get("setup", {})
                symbol = setup.get("symbol")
                direction = setup.get("direction", "").upper()
                entry = float(setup.get("entry", 0) or 0)
                target = float(setup.get("target", 0) or 0)
                stop = float(setup.get("stop", 0) or 0)

                if not symbol or not entry or not target or not stop:
                    continue

                # Compute alert age
                ts = alert.get("timestamp")
                if ts is not None and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - ts).total_seconds() if ts else 999999

                outcome = None
                pnl_pct = 0.0
                current_price = None

                try:
                    ticker = await market_intel.get_ticker(symbol)
                    if ticker and ticker.get("price"):
                        current_price = float(ticker["price"])

                        if direction == "LONG":
                            if current_price >= target:
                                outcome = "WIN"
                                pnl_pct = ((target - entry) / entry) * 100
                            elif current_price <= stop:
                                outcome = "LOSS"
                                pnl_pct = ((stop - entry) / entry) * 100
                        elif direction == "SHORT":
                            if current_price <= target:
                                outcome = "WIN"
                                pnl_pct = ((entry - target) / entry) * 100
                            elif current_price >= stop:
                                outcome = "LOSS"
                                pnl_pct = ((entry - stop) / entry) * 100
                except Exception as e:
                    logger.debug(f"Price fetch failed for {symbol}: {e}")

                # Expire old unresolved alerts
                if outcome is None and age_seconds > 86400:
                    outcome = "EXPIRED"

                if outcome:
                    update = {
                        "outcome": outcome,
                        "pnl_pct": round(pnl_pct, 2),
                        "resolved_at": datetime.now(timezone.utc),
                    }
                    if current_price is not None:
                        update["outcome_price"] = current_price

                    await col.update_one({"_id": alert["_id"]}, {"$set": update})
                    resolved += 1

        except Exception as e:
            logger.warning(f"resolve_alert_outcomes error ({collection_name}): {e}")

    return resolved


async def analyze_confirmation_accuracy(db):
    """
    Tally which confirmations appear most in WIN vs LOSS alerts (last 30 days).
    Upserts results into confirmation_accuracy collection.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        confirmation_stats: Dict[str, Dict] = {}

        for collection_name in ["free_will_alerts", "dual_alerts"]:
            col = db[collection_name]
            resolved = await col.find({
                "outcome": {"$in": ["WIN", "LOSS"]},
                "timestamp": {"$gte": cutoff}
            }).to_list(1000)

            for alert in resolved:
                outcome = alert.get("outcome")
                setup = alert.get("setup", {})
                confirmations = setup.get("confirmations", [])

                for conf in confirmations:
                    key = str(conf).lower().strip()[:60]
                    if not key:
                        continue
                    if key not in confirmation_stats:
                        confirmation_stats[key] = {"wins": 0, "losses": 0, "total": 0}
                    confirmation_stats[key]["total"] += 1
                    if outcome == "WIN":
                        confirmation_stats[key]["wins"] += 1
                    else:
                        confirmation_stats[key]["losses"] += 1

        now = datetime.now(timezone.utc)
        updated = 0
        for conf, stats in confirmation_stats.items():
            if stats["total"] < 3:
                continue
            win_rate = round((stats["wins"] / stats["total"]) * 100, 1)
            await db.confirmation_accuracy.update_one(
                {"confirmation": conf},
                {"$set": {
                    "confirmation": conf,
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "total": stats["total"],
                    "win_rate": win_rate,
                    "updated_at": now,
                }},
                upsert=True
            )
            updated += 1

        if updated:
            logger.info(f"Confirmation accuracy updated: {updated} signals tracked")

    except Exception as e:
        logger.warning(f"analyze_confirmation_accuracy error: {e}")


async def run_engine_data_collector(db, app_state, market_intel):
    """
    Main background loop:
    - Every 15 min: resolve alert outcomes
    - Every hour: snapshot all engine stats
    - Every 6 hours: analyze confirmation accuracy
    """
    logger.info("Engine Data Collector starting...")

    # Create indexes once
    try:
        await db.engine_snapshots.create_index("timestamp")
        await db.free_will_alerts.create_index([("outcome", 1), ("timestamp", -1)])
        await db.dual_alerts.create_index([("outcome", 1), ("timestamp", -1)])
        await db.confirmation_accuracy.create_index("confirmation", unique=True)
        logger.info("Engine Data Collector indexes ready")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")

    last_snapshot: datetime | None = None
    last_confirmation_analysis: datetime | None = None

    while True:
        try:
            now = datetime.now(timezone.utc)

            # Every 15 min: resolve outcomes
            resolved = await resolve_alert_outcomes(db, market_intel)
            if resolved > 0:
                logger.info(f"Engine Data Collector: resolved {resolved} alert outcomes")

            # Every hour: snapshot
            if last_snapshot is None or (now - last_snapshot).total_seconds() >= 3600:
                snapshot = await snapshot_all_engines(db, app_state)
                await db.engine_snapshots.insert_one(snapshot)
                last_snapshot = now
                engine_count = len([k for k, v in snapshot["engines"].items() if "error" not in v])
                logger.info(f"Engine snapshot saved ({engine_count} engines active)")

            # Every 6 hours: confirmation accuracy
            if last_confirmation_analysis is None or (now - last_confirmation_analysis).total_seconds() >= 21600:
                await analyze_confirmation_accuracy(db)
                last_confirmation_analysis = now

            await asyncio.sleep(900)  # 15 min

        except asyncio.CancelledError:
            logger.info("Engine Data Collector stopped")
            break
        except Exception as e:
            logger.error(f"Engine Data Collector error: {e}")
            await asyncio.sleep(60)
