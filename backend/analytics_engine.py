"""
Performance Analytics Engine
Aggregates paper trading results into rich statistics for the dashboard.
"""
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    def __init__(self, db):
        self.db = db

    async def _fetch_closed_trades(self, account_id: str = None, days: int = None) -> List[Dict]:
        query = {"status": {"$in": ["closed", "profit", "stopped", "liquidated"]}}
        if account_id:
            query["account_id"] = account_id
        if days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query["closed_at"] = {"$gte": cutoff}
        trades = await self.db.paper_trades.find(query).sort("closed_at", -1).to_list(10000)
        return trades

    def _ts(self, t) -> str:
        if t is None:
            return ""
        if hasattr(t, "isoformat"):
            return t.isoformat()
        return str(t)

    async def get_full_report(self) -> dict:
        trades = await self._fetch_closed_trades()
        if not trades:
            return {"error": "No closed trades", "total_trades": 0}

        total = len(trades)
        wins = [t for t in trades if (t.get("realized_pnl") or 0) > 0]
        losses = [t for t in trades if (t.get("realized_pnl") or 0) <= 0]
        win_rate = len(wins) / total * 100 if total > 0 else 0
        total_pnl = sum(t.get("realized_pnl") or 0 for t in trades)
        avg_win = sum(t.get("realized_pnl") or 0 for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get("realized_pnl") or 0 for t in losses) / len(losses) if losses else 0
        gross_win = sum(t.get("realized_pnl") or 0 for t in wins)
        gross_loss = abs(sum(t.get("realized_pnl") or 0 for t in losses))
        profit_factor = round(gross_win / gross_loss, 2) if gross_loss > 0 else 999.0

        def breakdown(key_fn):
            d = {}
            for t in trades:
                k = key_fn(t)
                if k not in d:
                    d[k] = {"trades": 0, "wins": 0, "pnl": 0.0}
                d[k]["trades"] += 1
                if (t.get("realized_pnl") or 0) > 0:
                    d[k]["wins"] += 1
                d[k]["pnl"] += t.get("realized_pnl") or 0
            for k in d:
                n = d[k]["trades"]
                d[k]["win_rate"] = round(d[k]["wins"] / n * 100, 1) if n > 0 else 0
                d[k]["pnl"] = round(d[k]["pnl"], 2)
            return d

        by_engine = breakdown(lambda t: t.get("strategy") or "unknown")
        by_direction = breakdown(lambda t: t.get("direction") or "unknown")
        by_account = breakdown(lambda t: t.get("account_id") or "unknown")

        def lev_bucket(t):
            try:
                lev = float(t.get("leverage") or 1)
            except (TypeError, ValueError):
                lev = 1
            if lev <= 5: return "1-5x"
            if lev <= 10: return "5-10x"
            if lev <= 15: return "10-15x"
            if lev <= 20: return "15-20x"
            return "20x+"

        def conf_bucket(t):
            try:
                conf = float(t.get("signal_data", {}).get("confidence") or t.get("confidence") or 0)
            except (TypeError, ValueError):
                conf = 0
            if conf < 70: return "<70%"
            if conf < 75: return "70-75%"
            if conf < 80: return "75-80%"
            if conf < 85: return "80-85%"
            if conf < 90: return "85-90%"
            return "90%+"

        by_leverage = breakdown(lev_bucket)
        by_confidence = breakdown(conf_bucket)
        by_reason = breakdown(lambda t: t.get("close_reason") or "unknown")

        # Symbol breakdown sorted by pnl
        by_symbol = breakdown(lambda t: t.get("symbol") or "unknown")
        by_symbol_sorted = dict(sorted(by_symbol.items(), key=lambda x: x[1]["pnl"], reverse=True))

        # Consecutive loss tracking
        max_consec = 0
        cur = 0
        def _sort_dt(x):
            v = x.get("closed_at")
            if isinstance(v, datetime):
                return v.replace(tzinfo=None)
            return datetime.min
        sorted_trades = sorted(trades, key=_sort_dt)
        for t in sorted_trades:
            if (t.get("realized_pnl") or 0) <= 0:
                cur += 1
                max_consec = max(max_consec, cur)
            else:
                cur = 0

        recent_10 = []
        for t in trades[:10]:
            recent_10.append({
                "symbol": t.get("symbol"),
                "direction": t.get("direction"),
                "pnl": round(t.get("realized_pnl") or 0, 2),
                "close_reason": t.get("close_reason"),
                "strategy": t.get("strategy"),
                "leverage": t.get("leverage"),
                "account_id": t.get("account_id"),
                "closed_at": self._ts(t.get("closed_at")),
            })

        # ── Risk-adjusted ratios ─────────────────────────────────────────────
        pnl_series = [t.get("realized_pnl") or 0 for t in sorted_trades]
        sharpe_ratio = None
        sortino_ratio = None
        calmar_ratio = None

        if len(pnl_series) >= 5:
            n = len(pnl_series)
            mean_r = sum(pnl_series) / n
            variance = sum((r - mean_r) ** 2 for r in pnl_series) / n
            std_r = math.sqrt(variance) if variance > 0 else 0

            if std_r > 0:
                sharpe_ratio = round(mean_r / std_r * math.sqrt(n), 3)

            # Sortino: downside deviation only
            down = [r - mean_r for r in pnl_series if r < mean_r]
            if down:
                down_var = sum(d ** 2 for d in down) / len(down)
                down_std = math.sqrt(down_var)
                if down_std > 0:
                    sortino_ratio = round(mean_r / down_std * math.sqrt(n), 3)

            # Calmar: total return / max drawdown
            peak = 0
            cum = 0
            max_dd = 0
            for r in pnl_series:
                cum += r
                if cum > peak:
                    peak = cum
                dd = peak - cum
                if dd > max_dd:
                    max_dd = dd
            if max_dd > 0:
                calmar_ratio = round(total_pnl / max_dd, 3)

        return {
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": profit_factor,
            "max_consecutive_losses": max_consec,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "by_engine": by_engine,
            "by_symbol": by_symbol_sorted,
            "by_direction": by_direction,
            "by_account": by_account,
            "by_close_reason": by_reason,
            "by_leverage": by_leverage,
            "by_confidence": by_confidence,
            "recent_trades": recent_10,
        }

    async def get_equity_curve(self, account_id: str = None, days: int = 60) -> list:
        trades = await self._fetch_closed_trades(account_id=account_id, days=days)
        trades_sorted = sorted(trades, key=lambda x: x.get("closed_at").replace(tzinfo=None) if isinstance(x.get("closed_at"), datetime) else datetime.min)
        cumulative = 0.0
        curve = []
        for t in trades_sorted:
            pnl = t.get("realized_pnl") or 0
            cumulative += pnl
            curve.append({
                "date": self._ts(t.get("closed_at")),
                "pnl": round(pnl, 2),
                "cumulative_pnl": round(cumulative, 2),
                "symbol": t.get("symbol"),
                "direction": t.get("direction"),
                "close_reason": t.get("close_reason"),
                "account_id": t.get("account_id"),
            })
        return curve

    async def get_win_rate_breakdown(self) -> dict:
        trades = await self._fetch_closed_trades()
        if not trades:
            return {}

        def make_breakdown(key_fn, label):
            d = {}
            for t in trades:
                k = key_fn(t)
                if not k:
                    continue
                if k not in d:
                    d[k] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
                d[k]["trades"] += 1
                if (t.get("realized_pnl") or 0) > 0:
                    d[k]["wins"] += 1
                d[k]["total_pnl"] += t.get("realized_pnl") or 0
            for k in d:
                n = d[k]["trades"]
                d[k]["win_rate"] = round(d[k]["wins"] / n * 100, 1) if n > 0 else 0
                d[k]["avg_pnl"] = round(d[k]["total_pnl"] / n, 2) if n > 0 else 0
                d[k]["total_pnl"] = round(d[k]["total_pnl"], 2)
            return d

        return {
            "by_engine": make_breakdown(lambda t: t.get("strategy"), "engine"),
            "by_pair": make_breakdown(lambda t: t.get("symbol"), "pair"),
            "by_timeframe": make_breakdown(lambda t: (t.get("signal_data") or {}).get("timeframe"), "timeframe"),
            "by_direction": make_breakdown(lambda t: t.get("direction"), "direction"),
            "by_account": make_breakdown(lambda t: t.get("account_id"), "account"),
        }

    async def get_top_performers(self) -> dict:
        trades = await self._fetch_closed_trades()
        if not trades:
            return {}

        # Pair stats
        pair_stats = {}
        for t in trades:
            sym = t.get("symbol", "unknown")
            if sym not in pair_stats:
                pair_stats[sym] = {"trades": 0, "wins": 0, "pnl": 0.0}
            pair_stats[sym]["trades"] += 1
            if (t.get("realized_pnl") or 0) > 0:
                pair_stats[sym]["wins"] += 1
            pair_stats[sym]["pnl"] += t.get("realized_pnl") or 0

        for sym in pair_stats:
            n = pair_stats[sym]["trades"]
            pair_stats[sym]["win_rate"] = round(pair_stats[sym]["wins"] / n * 100, 1) if n > 0 else 0
            pair_stats[sym]["pnl"] = round(pair_stats[sym]["pnl"], 2)

        eligible = {k: v for k, v in pair_stats.items() if v["trades"] >= 3}
        top_by_wr = sorted(eligible.items(), key=lambda x: x[1]["win_rate"], reverse=True)[:5]
        top_by_pnl = sorted(pair_stats.items(), key=lambda x: x[1]["pnl"], reverse=True)[:5]
        worst_by_pnl = sorted(pair_stats.items(), key=lambda x: x[1]["pnl"])[:5]

        return {
            "top_pairs_by_win_rate": [{"symbol": k, **v} for k, v in top_by_wr],
            "top_pairs_by_pnl": [{"symbol": k, **v} for k, v in top_by_pnl],
            "worst_pairs_by_pnl": [{"symbol": k, **v} for k, v in worst_by_pnl],
        }

    async def get_drawdown_analysis(self) -> dict:
        trades = await self._fetch_closed_trades()
        if not trades:
            return {}

        def _sort_dt(x):
            v = x.get("closed_at")
            if isinstance(v, datetime):
                return v.replace(tzinfo=None)
            return datetime.min
        sorted_trades = sorted(trades, key=_sort_dt)

        balance = 0.0
        peak = 0.0
        max_dd = 0.0
        max_dd_pct = 0.0
        dd_start = None
        max_dd_start = None
        dd_series = []

        for t in sorted_trades:
            pnl = t.get("realized_pnl") or 0
            balance += pnl
            if balance > peak:
                peak = balance
                dd_start = self._ts(t.get("closed_at"))

            drawdown = peak - balance
            drawdown_pct = (drawdown / peak * 100) if peak > 0 else 0

            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_pct = drawdown_pct
                max_dd_start = dd_start

            dd_series.append({
                "date": self._ts(t.get("closed_at")),
                "balance": round(balance, 2),
                "peak": round(peak, 2),
                "drawdown": round(drawdown, 2),
                "drawdown_pct": round(drawdown_pct, 1),
            })

        current_dd = peak - balance
        current_dd_pct = (current_dd / peak * 100) if peak > 0 else 0

        return {
            "max_drawdown": round(max_dd, 2),
            "max_drawdown_pct": round(max_dd_pct, 1),
            "max_drawdown_from": max_dd_start,
            "current_drawdown": round(current_dd, 2),
            "current_drawdown_pct": round(current_dd_pct, 1),
            "peak_pnl": round(peak, 2),
            "current_pnl": round(balance, 2),
            "dd_series": dd_series[-60:],  # last 60 data points
        }

    async def get_recent_trades(self, limit: int = 50) -> list:
        trades = await self._fetch_closed_trades()
        result = []
        for t in trades[:limit]:
            result.append({
                "symbol": t.get("symbol"),
                "direction": t.get("direction"),
                "pnl": round(t.get("realized_pnl") or 0, 2),
                "pnl_pct": round((t.get("realized_pnl") or 0) / (t.get("initial_margin") or t.get("margin") or 1) * 100, 1),
                "close_reason": t.get("close_reason"),
                "strategy": t.get("strategy"),
                "leverage": t.get("leverage"),
                "margin": round(t.get("initial_margin") or t.get("margin") or 0, 2),
                "account_id": t.get("account_id"),
                "opened_at": self._ts(t.get("opened_at")),
                "closed_at": self._ts(t.get("closed_at")),
                "confidence": (t.get("signal_data") or {}).get("confidence"),
                "timeframe": (t.get("signal_data") or {}).get("timeframe"),
                "tp1_hit": t.get("tp1_hit", False),
                "tp2_hit": t.get("tp2_hit", False),
            })
        return result
