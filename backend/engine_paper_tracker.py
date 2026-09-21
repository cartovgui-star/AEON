"""
ENGINE PAPER TRACKER
====================
Logs every real engine signal (open + close) to MongoDB `engine_trades` collection.
Computes per-engine live stats and compares against simulation targets.

This is the ground truth layer — real win rates vs our 10,000-trade sim predictions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Sim targets from post-fix 10,000-trade mixed-market run ─────────────────
# Source: sim/sim_results.json — all 8 fixes applied
SIM_TARGETS: Dict[str, Dict] = {
    "elite_strategy":       {"win_rate": 69.2, "pf": 5.11, "expectancy": 1.141},
    "dual_engine":          {"win_rate": 66.0, "pf": 4.41, "expectancy": 1.047},
    "autonomous_trader_v2": {"win_rate": 65.0, "pf": 4.24, "expectancy": 1.020},
    "free_will_v2":         {"win_rate": 63.3, "pf": 2.95, "expectancy": 0.644},
    "day_trader":           {"win_rate": 63.0, "pf": 2.91, "expectancy": 0.635},
    "yolo_engine":          {"win_rate": 63.2, "pf": 2.93, "expectancy": 0.638},
    "vwap_scalper":         {"win_rate": 59.2, "pf": 2.47, "expectancy": 0.541},
}

# Minimum trades before stats are considered reliable
MIN_RELIABLE_TRADES = 30


def _confidence_label(n: int) -> str:
    if n == 0:
        return "no data"
    if n < 10:
        return "very low (< 10 trades)"
    if n < 30:
        return "low (< 30 trades)"
    if n < 100:
        return "moderate"
    return "high"


def _compute_max_drawdown(pnl_r_series: List[float]) -> float:
    """Maximum peak-to-trough drawdown in R units"""
    peak = 0.0
    running = 0.0
    max_dd = 0.0
    for r in pnl_r_series:
        running += r
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


class EnginePaperTracker:
    """
    Tracks real engine signal performance.
    Writes to `engine_trades` collection — separate from paper_trades.
    Each engine calls log_open() when a signal fires and log_close() when it resolves.
    """

    def __init__(self, db):
        self.db = db
        logger.info("EnginePaperTracker initialized — tracking real engine signals to engine_trades")

    async def log_open(
        self,
        trade_id: str,
        engine: str,
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp: float,
        confidence: float,
        leverage: float,
        rr: float,
    ) -> None:
        """Record a signal open. Called when EngineManager approves EXECUTE."""
        try:
            doc = {
                "trade_id": trade_id,
                "engine": engine,
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "rr": rr,
                "confidence": confidence,
                "leverage": leverage,
                "status": "open",
                "opened_at": datetime.now(timezone.utc),
                "closed_at": None,
                "exit_price": None,
                "pnl_r": None,
                "outcome": None,
                "close_reason": None,
            }
            await self.db.engine_trades.insert_one(doc)
        except Exception as e:
            logger.error(f"EnginePaperTracker.log_open failed for {trade_id}: {e}")

    async def log_close(
        self,
        trade_id: str,
        exit_price: float,
        pnl_r: float,
        reason: str,
    ) -> None:
        """Record a signal close. Called when EngineManager closes a trade."""
        try:
            outcome = "win" if pnl_r > 0 else "loss"
            await self.db.engine_trades.update_one(
                {"trade_id": trade_id},
                {
                    "$set": {
                        "status": "closed",
                        "exit_price": exit_price,
                        "pnl_r": round(pnl_r, 3),
                        "outcome": outcome,
                        "close_reason": reason,
                        "closed_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as e:
            logger.error(f"EnginePaperTracker.log_close failed for {trade_id}: {e}")

    async def get_engine_stats(self) -> Dict[str, Dict]:
        """
        Aggregate real per-engine performance from closed engine_trades.
        Returns dict keyed by engine name.
        """
        try:
            closed = await self.db.engine_trades.find(
                {"status": "closed", "pnl_r": {"$ne": None}}
            ).to_list(50000)
        except Exception as e:
            logger.error(f"EnginePaperTracker.get_engine_stats DB error: {e}")
            return {}

        # Group by engine
        buckets: Dict[str, List[float]] = {}
        for trade in closed:
            eng = trade.get("engine", "unknown")
            if eng not in buckets:
                buckets[eng] = []
            pnl_r = trade.get("pnl_r", 0.0) or 0.0
            buckets[eng].append(pnl_r)

        result = {}
        for eng, series in buckets.items():
            total = len(series)
            wins = sum(1 for r in series if r > 0)
            losses = total - wins
            win_rate = round((wins / total) * 100, 1) if total > 0 else 0.0

            gross_profit = sum(r for r in series if r > 0)
            gross_loss = abs(sum(r for r in series if r < 0))
            pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0

            total_r = sum(series)
            expectancy = round(total_r / total, 3) if total > 0 else 0.0
            max_dd = _compute_max_drawdown(series)

            result[eng] = {
                "engine": eng,
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_pnl_r": round(total_r, 2),
                "profit_factor": pf,
                "expectancy_r": expectancy,
                "max_drawdown_r": max_dd,
                "data_confidence": _confidence_label(total),
                "is_reliable": total >= MIN_RELIABLE_TRADES,
            }

        return result

    async def get_sim_comparison(self) -> List[Dict]:
        """
        Side-by-side: real live stats vs 10,000-trade simulation targets.
        Shows the 'optimism gap' for each engine.
        """
        real = await self.get_engine_stats()

        comparison = []
        for eng, sim in SIM_TARGETS.items():
            r = real.get(eng, {})
            n = r.get("total_trades", 0)

            # Gaps only meaningful when we have data
            wr_gap = round(r["win_rate"] - sim["win_rate"], 1) if n > 0 else None
            pf_gap = round(r["profit_factor"] - sim["pf"], 2) if n > 0 else None
            exp_gap = round(r["expectancy_r"] - sim["expectancy"], 3) if n > 0 else None

            def _status(gap, threshold=0):
                if gap is None:
                    return "no data"
                if gap >= threshold:
                    return "beating sim"
                if gap >= threshold - 5:
                    return "near sim"
                return "below sim"

            comparison.append({
                "engine": eng,
                "trades_sampled": n,
                "data_confidence": _confidence_label(n),
                "is_reliable": n >= MIN_RELIABLE_TRADES,
                # Win Rate
                "real_win_rate": r.get("win_rate") if n > 0 else None,
                "sim_win_rate": sim["win_rate"],
                "win_rate_gap": wr_gap,
                # Profit Factor
                "real_pf": r.get("profit_factor") if n > 0 else None,
                "sim_pf": sim["pf"],
                "pf_gap": pf_gap,
                # Expectancy
                "real_expectancy": r.get("expectancy_r") if n > 0 else None,
                "sim_expectancy": sim["expectancy"],
                "expectancy_gap": exp_gap,
                # Other live stats
                "total_pnl_r": r.get("total_pnl_r") if n > 0 else None,
                "max_drawdown_r": r.get("max_drawdown_r") if n > 0 else None,
                "status": _status(wr_gap),
            })

        # Engines live but not in sim targets (shouldn't happen)
        for eng in real:
            if eng not in SIM_TARGETS:
                r = real[eng]
                comparison.append({
                    "engine": eng,
                    "trades_sampled": r["total_trades"],
                    "data_confidence": r["data_confidence"],
                    "is_reliable": r["is_reliable"],
                    "real_win_rate": r["win_rate"],
                    "sim_win_rate": None,
                    "win_rate_gap": None,
                    "real_pf": r["profit_factor"],
                    "sim_pf": None,
                    "pf_gap": None,
                    "real_expectancy": r["expectancy_r"],
                    "sim_expectancy": None,
                    "expectancy_gap": None,
                    "total_pnl_r": r["total_pnl_r"],
                    "max_drawdown_r": r["max_drawdown_r"],
                    "status": "no sim target",
                })

        return sorted(comparison, key=lambda x: (x.get("sim_win_rate") or 0), reverse=True)

    async def get_open_signals(self) -> List[Dict]:
        """All currently open (unresolved) engine signals"""
        try:
            open_trades = await self.db.engine_trades.find(
                {"status": "open"}
            ).sort("opened_at", -1).to_list(200)
            for t in open_trades:
                t.pop("_id", None)
                if isinstance(t.get("opened_at"), datetime):
                    t["opened_at"] = t["opened_at"].isoformat()
            return open_trades
        except Exception as e:
            logger.error(f"EnginePaperTracker.get_open_signals error: {e}")
            return []


# Module-level singleton — set by server.py
engine_paper_tracker: Optional[EnginePaperTracker] = None


def init_engine_paper_tracker(db) -> EnginePaperTracker:
    global engine_paper_tracker
    engine_paper_tracker = EnginePaperTracker(db)
    return engine_paper_tracker
