"""
Stats & Analytics Telegram Commands
Handles /stats, /accuracy, /leaderboard, /insights commands
"""
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


async def handle_stats(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /stats command - Show trading statistics"""
    try:
        import app_state
        
        stats = app_state.trading_stats if hasattr(app_state, 'trading_stats') else {}
        
        total_trades = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = stats.get('total_pnl_pct', 0)
        avg_win = stats.get('avg_win_pct', 0)
        avg_loss = stats.get('avg_loss_pct', 0)
        
        response = f"""📊 TRADING STATISTICS

📈 Performance
• Total Trades: {total_trades}
• Wins: {wins} | Losses: {losses}
• Win Rate: {win_rate:.1f}%
• Total PnL: {total_pnl:+.2f}%

💰 Averages
• Avg Win: +{avg_win:.2f}%
• Avg Loss: {avg_loss:.2f}%
• Expectancy: {((win_rate/100)*avg_win - ((100-win_rate)/100)*abs(avg_loss)):.2f}%

Use /accuracy for signal accuracy breakdown
Use /leaderboard for top performing coins"""

    except Exception as e:
        logger.error(f"Stats error: {e}")
        response = f"❌ Error fetching stats: {str(e)}"
    
    return response, "stats"


async def handle_accuracy(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /accuracy command - Signal accuracy breakdown"""
    try:
        import app_state
        from datetime import datetime, timedelta
        
        # Get signal accuracy from database
        db = app_state.db if hasattr(app_state, 'db') else None
        
        if db:
            signals = list(db.signal_history.find({
                "timestamp": {"$gte": datetime.utcnow() - timedelta(days=7)},
                "outcome": {"$in": ["win", "loss"]}
            }).sort("timestamp", -1).limit(100))
            
            if signals:
                total = len(signals)
                wins = len([s for s in signals if s.get('outcome') == 'win'])
                accuracy = (wins / total * 100) if total > 0 else 0
                
                # Breakdown by direction
                longs = [s for s in signals if s.get('direction') == 'LONG']
                shorts = [s for s in signals if s.get('direction') == 'SHORT']
                long_wins = len([s for s in longs if s.get('outcome') == 'win'])
                short_wins = len([s for s in shorts if s.get('outcome') == 'win'])
                
                response = f"""🎯 SIGNAL ACCURACY (7 Days)

Overall: {accuracy:.1f}% ({wins}/{total})

📈 LONG Signals
• Accuracy: {(long_wins/len(longs)*100) if longs else 0:.1f}%
• Count: {len(longs)}

📉 SHORT Signals  
• Accuracy: {(short_wins/len(shorts)*100) if shorts else 0:.1f}%
• Count: {len(shorts)}"""
            else:
                response = "🎯 No signal data available yet. Signals will be tracked as trades complete."
        else:
            response = "❌ Database not available"
            
    except Exception as e:
        logger.error(f"Accuracy error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "stats"


async def handle_leaderboard(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /leaderboard command - Top performing coins"""
    try:
        import app_state
        
        db = app_state.db if hasattr(app_state, 'db') else None
        
        if db:
            # Aggregate performance by symbol
            pipeline = [
                {"$match": {"outcome": {"$in": ["win", "loss"]}}},
                {"$group": {
                    "_id": "$symbol",
                    "total": {"$sum": 1},
                    "wins": {"$sum": {"$cond": [{"$eq": ["$outcome", "win"]}, 1, 0]}},
                    "pnl": {"$sum": "$pnl_pct"}
                }},
                {"$match": {"total": {"$gte": 3}}},  # Min 3 trades
                {"$sort": {"pnl": -1}},
                {"$limit": 10}
            ]
            
            results = list(db.signal_history.aggregate(pipeline))
            
            if results:
                response = "🏆 TOP PERFORMING COINS\n\n"
                for i, r in enumerate(results, 1):
                    symbol = r['_id'].replace('/USDT', '')
                    win_rate = (r['wins'] / r['total'] * 100) if r['total'] > 0 else 0
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    response += f"{emoji} {symbol}: {r['pnl']:+.2f}% ({win_rate:.0f}% WR, {r['total']} trades)\n"
            else:
                response = "🏆 Not enough trade data yet for leaderboard."
        else:
            response = "❌ Database not available"
            
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "stats"


async def handle_insights(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /insights command - AI-generated trading insights"""
    try:
        import app_state
        
        # Get recent performance data
        stats = app_state.trading_stats if hasattr(app_state, 'trading_stats') else {}
        market = app_state.market_data if hasattr(app_state, 'market_data') else {}
        
        win_rate = stats.get('win_rate', 0)
        total_pnl = stats.get('total_pnl_pct', 0)
        btc_bias = market.get('btc_bias', 'NEUTRAL')
        
        # Generate insights based on data
        insights = []
        
        if win_rate >= 60:
            insights.append("✅ Strong win rate - strategy performing well")
        elif win_rate < 40:
            insights.append("⚠️ Low win rate - consider increasing confidence threshold")
        
        if total_pnl > 0:
            insights.append(f"📈 Profitable: +{total_pnl:.2f}% total PnL")
        else:
            insights.append(f"📉 In drawdown: {total_pnl:.2f}% - stay disciplined")
        
        if btc_bias == 'BULLISH':
            insights.append("🟢 BTC bullish - favor LONG positions")
        elif btc_bias == 'BEARISH':
            insights.append("🔴 BTC bearish - favor SHORT positions")
        
        response = "💡 TRADING INSIGHTS\n\n" + "\n".join(insights)
        response += "\n\nUse /strategy for detailed strategy analysis"
        
    except Exception as e:
        logger.error(f"Insights error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "stats"


# Command routing
STATS_HANDLERS = {
    '/stats': handle_stats,
    '/accuracy': handle_accuracy,
    '/acc': handle_accuracy,
    '/leaderboard': handle_leaderboard,
    '/lb': handle_leaderboard,
    '/top coins': handle_leaderboard,
    '/insights': handle_insights,
}


async def route_stats_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route stats commands to appropriate handler"""
    text_lower = text.lower().strip()
    
    for pattern, handler in STATS_HANDLERS.items():
        if text_lower == pattern or text_lower.startswith(pattern + ' '):
            return await handler(text, chat_id, context)
    
    return None
