"""
AEON STRATEGY HEALTH MONITOR (Moltbot-inspired)
Self-improving strategy management:
- Tracks consecutive wins/losses per strategy
- Auto-benches strategies after 3 consecutive losses
- Cooldown period before re-enabling
- Performance scoring and ranking
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_LOSSES = 3
BENCH_COOLDOWN_MINUTES = 60
MAX_HISTORY = 200


class StrategyHealth:
    def __init__(self):
        self.strategies: Dict[str, Dict] = {
            "day_trader": {
                "name": "Day Trader",
                "style": "AGGRESSIVE",
                "active": True,
                "consecutive_losses": 0,
                "consecutive_wins": 0,
                "total_wins": 0,
                "total_losses": 0,
                "total_trades": 0,
                "benched": False,
                "benched_at": None,
                "bench_count": 0,
                "last_result": None,
                "pnl_history": [],
                "score": 100
            },
            "long_term": {
                "name": "Long Term",
                "style": "SMART",
                "active": True,
                "consecutive_losses": 0,
                "consecutive_wins": 0,
                "total_wins": 0,
                "total_losses": 0,
                "total_trades": 0,
                "benched": False,
                "benched_at": None,
                "bench_count": 0,
                "last_result": None,
                "pnl_history": [],
                "score": 100
            },
            "free_will": {
                "name": "Elite Alerts",
                "style": "SELECTIVE",
                "active": True,
                "consecutive_losses": 0,
                "consecutive_wins": 0,
                "total_wins": 0,
                "total_losses": 0,
                "total_trades": 0,
                "benched": False,
                "benched_at": None,
                "bench_count": 0,
                "last_result": None,
                "pnl_history": [],
                "score": 100
            }
        }

    def record_trade(self, strategy_id: str, pnl_pct: float, symbol: str = "") -> Dict:
        if strategy_id not in self.strategies:
            return {"error": f"Unknown strategy: {strategy_id}"}

        s = self.strategies[strategy_id]
        is_win = pnl_pct > 0

        s["total_trades"] += 1
        s["last_result"] = "WIN" if is_win else "LOSS"

        if is_win:
            s["total_wins"] += 1
            s["consecutive_wins"] += 1
            s["consecutive_losses"] = 0
            s["score"] = min(100, s["score"] + 5)
        else:
            s["total_losses"] += 1
            s["consecutive_losses"] += 1
            s["consecutive_wins"] = 0
            s["score"] = max(0, s["score"] - 10)

        s["pnl_history"].append({
            "pnl": round(pnl_pct, 2),
            "symbol": symbol,
            "ts": datetime.now(timezone.utc).isoformat()
        })
        if len(s["pnl_history"]) > MAX_HISTORY:
            s["pnl_history"] = s["pnl_history"][-MAX_HISTORY:]

        action = None
        if s["consecutive_losses"] >= MAX_CONSECUTIVE_LOSSES and not s["benched"]:
            s["benched"] = True
            s["benched_at"] = datetime.now(timezone.utc)
            s["bench_count"] += 1
            s["active"] = False
            action = f"AUTO-BENCHED after {MAX_CONSECUTIVE_LOSSES} consecutive losses"
            logger.warning(f"Strategy {s['name']} auto-benched! {MAX_CONSECUTIVE_LOSSES} consecutive losses")

        return {
            "strategy": strategy_id,
            "result": s["last_result"],
            "consecutive_wins": s["consecutive_wins"],
            "consecutive_losses": s["consecutive_losses"],
            "score": s["score"],
            "action": action,
            "benched": s["benched"]
        }

    def check_bench_expiry(self):
        now = datetime.now(timezone.utc)
        for sid, s in self.strategies.items():
            if s["benched"] and s["benched_at"]:
                elapsed = (now - s["benched_at"]).total_seconds() / 60
                if elapsed >= BENCH_COOLDOWN_MINUTES:
                    s["benched"] = False
                    s["active"] = True
                    s["consecutive_losses"] = 0
                    s["score"] = max(50, s["score"])
                    logger.info(f"Strategy {s['name']} un-benched after {BENCH_COOLDOWN_MINUTES}m cooldown")

    def force_unbench(self, strategy_id: str) -> Dict:
        if strategy_id not in self.strategies:
            return {"error": "Unknown strategy"}
        s = self.strategies[strategy_id]
        s["benched"] = False
        s["active"] = True
        s["consecutive_losses"] = 0
        s["benched_at"] = None
        return {"success": True, "message": f"{s['name']} manually un-benched"}

    def get_status(self) -> Dict:
        self.check_bench_expiry()
        result = {}
        for sid, s in self.strategies.items():
            win_rate = (s["total_wins"] / s["total_trades"] * 100) if s["total_trades"] > 0 else 0
            total_pnl = sum(h["pnl"] for h in s["pnl_history"])
            remaining_bench = 0
            if s["benched"] and s["benched_at"]:
                elapsed = (datetime.now(timezone.utc) - s["benched_at"]).total_seconds() / 60
                remaining_bench = max(0, round(BENCH_COOLDOWN_MINUTES - elapsed))

            result[sid] = {
                "name": s["name"],
                "style": s["style"],
                "active": s["active"],
                "benched": s["benched"],
                "bench_remaining_min": remaining_bench,
                "bench_count": s["bench_count"],
                "score": s["score"],
                "total_trades": s["total_trades"],
                "wins": s["total_wins"],
                "losses": s["total_losses"],
                "win_rate": round(win_rate, 1),
                "total_pnl": round(total_pnl, 2),
                "consecutive_wins": s["consecutive_wins"],
                "consecutive_losses": s["consecutive_losses"],
                "last_result": s["last_result"],
                "recent_pnl": [h["pnl"] for h in s["pnl_history"][-10:]]
            }
        return result

    def get_ranking(self) -> List[Dict]:
        self.check_bench_expiry()
        ranking = []
        for sid, s in self.strategies.items():
            win_rate = (s["total_wins"] / s["total_trades"] * 100) if s["total_trades"] > 0 else 0
            ranking.append({
                "id": sid,
                "name": s["name"],
                "score": s["score"],
                "win_rate": round(win_rate, 1),
                "benched": s["benched"]
            })
        ranking.sort(key=lambda x: x["score"], reverse=True)
        return ranking


strategy_health = StrategyHealth()
