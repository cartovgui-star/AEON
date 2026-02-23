"""
Accuracy Tracking API Routes
Track alert outcomes and measure trading accuracy
"""

from fastapi import APIRouter, Request
import sys
sys.path.append('..')
from trade_outcome_tracker import trade_outcome_tracker

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


@router.get("")
async def api_accuracy_stats():
    """Get alert accuracy statistics"""
    return trade_outcome_tracker.get_accuracy_report()


@router.get("/pending")
async def api_accuracy_pending():
    """Get pending alerts awaiting outcome"""
    return {"pending": trade_outcome_tracker.get_pending_alerts()}


@router.get("/leaderboard")
async def api_leaderboard():
    """Get coin leaderboard by win rate"""
    report = trade_outcome_tracker.get_accuracy_report()
    symbol_stats = report.get("by_symbol", {})
    
    # Convert to list and sort by win rate
    leaderboard = []
    for symbol, stats in symbol_stats.items():
        total = stats.get("wins", 0) + stats.get("losses", 0)
        if total > 0:
            win_rate = (stats.get("wins", 0) / total) * 100
            leaderboard.append({
                "symbol": symbol,
                "win_rate": round(win_rate, 1),
                "wins": stats.get("wins", 0),
                "losses": stats.get("losses", 0),
                "total": total,
                "avg_pnl": stats.get("avg_pnl", 0)
            })
    
    # Sort by win rate descending
    leaderboard.sort(key=lambda x: (x["win_rate"], x["total"]), reverse=True)
    
    return {
        "leaderboard": leaderboard,
        "top_performers": leaderboard[:5],
        "worst_performers": leaderboard[-5:] if len(leaderboard) >= 5 else [],
        "total_symbols": len(leaderboard)
    }


@router.get("/dashboard")
async def api_accuracy_dashboard():
    """Simple dashboard stats - last 10 trades, best/worst pairs"""
    from server import autonomous_trader_v2
    
    # Get last 10 trades
    last_10 = autonomous_trader_v2.closed_trades[-10:] if autonomous_trader_v2.closed_trades else []
    wins = sum(1 for t in last_10 if t.get("pnl_pct", 0) > 0)
    losses = len(last_10) - wins
    
    # Get best/worst pairs from trader
    pair_data = autonomous_trader_v2.get_best_worst_pairs()
    
    return {
        "last_10_trades": {
            "wins": wins,
            "losses": losses,
            "display": f"{wins}W {losses}L",
            "trades": [{"symbol": t.get("symbol", "").replace("/USDT", ""), 
                       "pnl": t.get("pnl_pct", 0),
                       "direction": t.get("direction", "")} for t in last_10[-5:]]
        },
        "best_pairs": pair_data.get("best", []),
        "worst_pairs": pair_data.get("worst", []),
        "blacklisted": pair_data.get("blacklisted", []),
        "daily_trades": f"{autonomous_trader_v2.daily_trades}/{autonomous_trader_v2.max_daily_trades}",
        "cooldowns": list(autonomous_trader_v2.pair_cooldowns.keys())
    }


@router.post("/record")
async def api_accuracy_record(request: Request):
    """Record outcome for an alert"""
    data = await request.json()
    alert_id = data.get("alert_id", "")
    outcome = data.get("outcome", "")  # WIN, LOSS, BREAKEVEN, EXPIRED
    exit_price = data.get("exit_price", 0)
    
    if not alert_id or not outcome:
        return {"error": "alert_id and outcome required"}
    
    result = trade_outcome_tracker.update_outcome(alert_id, outcome, exit_price)
    return result
