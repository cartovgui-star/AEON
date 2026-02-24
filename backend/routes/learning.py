"""
Continuous Learning Engine API Routes
24/7 AI Learning System
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

router = APIRouter(prefix="/learning", tags=["Continuous Learning"])

from continuous_learning import continuous_learner


@router.get("/status")
async def get_learning_status():
    """Get the status of the continuous learning engine"""
    try:
        return await continuous_learner.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_recommendations():
    """Get current learning recommendations"""
    try:
        return await continuous_learner.get_recommendations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights")
async def get_daily_insights():
    """Get today's learning insights"""
    try:
        return {
            "insights": continuous_learner.daily_insights,
            "count": len(continuous_learner.daily_insights),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/force-cycle")
async def force_learning_cycle():
    """Force run all learning cycles immediately"""
    try:
        result = await continuous_learner.force_learning_cycle()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/preview")
async def preview_daily_summary():
    """Preview the daily learning summary"""
    try:
        summary = await continuous_learner.generate_daily_summary()
        return {
            "preview": summary,
            "length": len(summary),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary/send")
async def send_summary_now():
    """Send the daily learning summary immediately"""
    try:
        import asyncio
        asyncio.create_task(continuous_learner.send_daily_summary())
        return {"success": True, "message": "Learning summary sending - check Telegram"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns")
async def get_learned_patterns():
    """Get learned trading patterns"""
    try:
        patterns = dict(continuous_learner.pattern_learner.pattern_stats)
        
        # Calculate win rates
        pattern_list = []
        for pattern, stats in patterns.items():
            total = stats["wins"] + stats["losses"]
            if total > 0:
                pattern_list.append({
                    "pattern": pattern,
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "total": total,
                    "win_rate": round((stats["wins"] / total) * 100, 1),
                    "total_pnl": round(stats["total_pnl"], 2)
                })
        
        # Sort by total trades
        pattern_list.sort(key=lambda x: x["total"], reverse=True)
        
        return {
            "patterns": pattern_list,
            "total_patterns": len(pattern_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coins")
async def get_coin_analysis():
    """Get learned coin performance"""
    try:
        coins = dict(continuous_learner.pattern_learner.coin_stats)
        
        coin_list = []
        for coin, stats in coins.items():
            total = stats["wins"] + stats["losses"]
            if total > 0:
                coin_list.append({
                    "coin": coin,
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "total": total,
                    "win_rate": round((stats["wins"] / total) * 100, 1),
                    "total_pnl": round(stats["total_pnl"], 2),
                    "avg_pnl": round(stats["total_pnl"] / total, 2)
                })
        
        # Sort by win rate
        coin_list.sort(key=lambda x: x["win_rate"], reverse=True)
        
        return {
            "coins": coin_list,
            "total_coins": len(coin_list),
            "best_performers": [c for c in coin_list if c["win_rate"] >= 55][:5],
            "worst_performers": [c for c in coin_list if c["win_rate"] <= 45][:5]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_session_analysis():
    """Get trading session performance analysis"""
    try:
        sessions = continuous_learner.market_analyzer.session_performance
        hours = dict(continuous_learner.market_analyzer.hour_performance)
        days = dict(continuous_learner.market_analyzer.day_performance)
        
        # Process sessions
        session_stats = {}
        for name, stats in sessions.items():
            total = stats["trades"]
            if total > 0:
                session_stats[name] = {
                    "trades": total,
                    "wins": stats["wins"],
                    "win_rate": round((stats["wins"] / total) * 100, 1),
                    "total_pnl": round(stats["pnl"], 2)
                }
        
        # Process hours
        hour_stats = []
        for hour, stats in hours.items():
            total = stats["trades"]
            if total > 0:
                hour_stats.append({
                    "hour": hour,
                    "trades": total,
                    "win_rate": round((stats["wins"] / total) * 100, 1)
                })
        hour_stats.sort(key=lambda x: x["win_rate"], reverse=True)
        
        # Process days
        day_stats = []
        for day, stats in days.items():
            total = stats["trades"]
            if total > 0:
                day_stats.append({
                    "day": day,
                    "trades": total,
                    "win_rate": round((stats["wins"] / total) * 100, 1)
                })
        day_stats.sort(key=lambda x: x["win_rate"], reverse=True)
        
        return {
            "sessions": session_stats,
            "best_hours": hour_stats[:5],
            "worst_hours": hour_stats[-5:][::-1] if len(hour_stats) >= 5 else [],
            "best_days": day_stats[:3],
            "worst_days": day_stats[-3:][::-1] if len(day_stats) >= 3 else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_learning(enabled: bool = True):
    """Enable or disable the learning engine"""
    continuous_learner.is_active = enabled
    return {
        "success": True,
        "enabled": continuous_learner.is_active
    }
