"""
Learning Engine Command Handlers
Commands: /learn, /insights, /patterns
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_learn_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /learn command - show learning engine status"""
    import app_state
    
    try:
        learner = app_state.continuous_learner
        if not learner:
            return "❌ Learning engine not initialized", "learning"
        
        status = learner.get_status()
        knowledge = status.get("knowledge_stats", {})
        
        response = f"""🧠 24/7 LEARNING ENGINE

Status: {'🟢 ACTIVE' if status.get('active') else '🔴 INACTIVE'}

📊 KNOWLEDGE BASE
• Patterns Learned: {knowledge.get('patterns_learned', 0)}
• Coins Analyzed: {knowledge.get('coins_analyzed', 0)}
• Timeframes: {knowledge.get('timeframes_tracked', 0)}
• Indicators Tracked: {knowledge.get('indicators_tracked', 0)}

📈 LEARNING STATS
• Trade Outcomes: {knowledge.get('trade_outcomes', 0)}
• Accuracy Rate: {status.get('knowledge_stats', {}).get('accuracy_rate', 0)}%

⏰ SCHEDULE
• Last Pattern Analysis: {status.get('last_pattern_learning', 'Never')[:16]}
• Last Market Analysis: {status.get('last_market_analysis', 'Never')[:16]}
• Next Daily Summary: {status.get('next_daily_summary', 'Unknown')}

The learning engine continuously analyzes:
• Closed trades for patterns
• Market conditions at entry/exit
• Indicator combinations that work best
• Time-of-day performance patterns"""
        
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "learning"


async def handle_insights(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /insights command - get AI trading insights"""
    import app_state
    
    try:
        learner = app_state.continuous_learner
        if not learner:
            return "❌ Learning engine not initialized", "learning"
        
        insights = learner.daily_insights if hasattr(learner, 'daily_insights') else []
        
        if not insights:
            response = """🔮 AI TRADING INSIGHTS

No insights generated yet.

The learning engine generates insights based on:
• Closed trade analysis
• Pattern recognition
• Market condition correlation

Keep trading to build up the knowledge base!

Use /learn to check learning status."""
        else:
            response = f"🔮 AI TRADING INSIGHTS ({len(insights)} insights)\n\n"
            
            for i, insight in enumerate(insights[:5], 1):
                response += f"{i}. {insight}\n\n"
        
        return response, "learning"
        
    except Exception as e:
        return f"❌ Error: {str(e)}", "learning"


async def handle_patterns(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /patterns command - show learned patterns"""
    import app_state
    
    try:
        learner = app_state.continuous_learner
        if not learner:
            return "❌ Learning engine not initialized", "learning"
        
        pl = learner.pattern_learner if hasattr(learner, 'pattern_learner') else None
        
        if not pl or not hasattr(pl, 'pattern_stats') or not pl.pattern_stats:
            return """📊 LEARNED PATTERNS

No patterns learned yet.

Patterns are identified from closed trades.
The engine looks for:
• RSI levels at profitable entries
• MACD histogram patterns
• Volume spikes before moves
• Time-of-day tendencies

Keep trading to build pattern knowledge!""", "learning"
        
        response = f"📊 LEARNED PATTERNS ({len(pl.pattern_stats)} patterns)\n\n"
        
        # Show top patterns by win rate
        sorted_patterns = sorted(
            pl.pattern_stats.items(),
            key=lambda x: x[1].get('win_rate', 0),
            reverse=True
        )
        
        for pattern_name, stats in sorted_patterns[:5]:
            trades = stats.get('total_trades', 0)
            win_rate = stats.get('win_rate', 0)
            avg_pnl = stats.get('avg_pnl', 0)
            
            emoji = "🟢" if win_rate >= 60 else "🟡" if win_rate >= 50 else "🔴"
            
            response += f"""{emoji} {pattern_name}
• Trades: {trades} | Win Rate: {win_rate:.1f}%
• Avg PnL: ${avg_pnl:+.2f}

"""
        
        return response, "learning"
        
    except Exception as e:
        return f"❌ Error: {str(e)}", "learning"


# Export handlers
LEARNING_HANDLERS = {
    '/learn': handle_learn_status,
    '/insights': handle_insights,
    '/patterns': handle_patterns,
}


async def route_learning_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route learning commands"""
    text_lower = text.lower().strip()
    
    if text_lower == '/learn':
        return await handle_learn_status(text, chat_id, context)
    elif text_lower == '/insights':
        return await handle_insights(text, chat_id, context)
    elif text_lower == '/patterns':
        return await handle_patterns(text, chat_id, context)
    
    return None
