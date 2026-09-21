"""
Central Command Router
Routes all Telegram commands to appropriate handlers
"""
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Import all command modules
from .elite_commands import route_elite_command
from .engine_commands import route_engine_command
from .general_commands import route_general_command
from .market_commands import route_market_command
from .model_commands import route_model_command
from .mtf_commands import route_mtf_command
from .paper_commands import route_paper_command
from .scan_commands import route_scan_command
from .trading_commands import route_trading_command
from .stats_commands import route_stats_command
from .alerts_commands import route_alert_command
from .auto_commands import route_auto_command
from .news_commands import route_news_command
from .price_commands import route_price_command
from .vwap_commands import route_vwap_command
from .yolo_commands import route_yolo_command
from .learning_commands import route_learning_command
from .quant_commands import route_quant_command
from .chart_commands import route_chart_command
from .manual_trade_commands import handle as route_manual_trade_command


async def route_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """
    Central router that delegates to appropriate command handler.
    Returns (response, context_type) or None if no handler found.
    """
    text_lower = text.lower().strip()
    
    # Skip non-commands
    if not text_lower.startswith('/'):
        return None
    
    # Try each command router in order of priority
    routers = [
        # Highest priority — manual trade placement (Carlos's direct commands)
        route_manual_trade_command, # /trade SYMBOL DIRECTION [lev] [acc], /close SYMBOL

        # High priority - frequently used
        route_general_command,      # /start, /help
        route_trading_command,      # /positions
        route_elite_command,        # /elite commands
        
        # Market data
        route_price_command,        # /price, /top100, /movers
        route_market_command,       # /market, /fear, /summary
        
        # Trading features
        route_paper_command,        # /accounts, /pro, /starter, /tier5k, /tier1k, /tier500, /reallife, /proof, /benchmark
        route_engine_command,       # /engines, /engine, /governance, /gov
        route_scan_command,         # /scan, /opps
        route_mtf_command,          # /mtf, /confluence
        route_auto_command,         # /auto, /riskcheck
        route_vwap_command,         # /vwap, /vwap scan
        route_yolo_command,         # /yolo, /yolo scan, /yolo on/off
        route_learning_command,     # /learn, /insights, /patterns
        route_quant_command,        # /quant, /quant [coin]
        
        # Analytics
        route_stats_command,        # /stats, /accuracy, /leaderboard
        route_alert_command,        # /alerts
        route_chart_command,        # /chart, /watch
        
        # Intel
        route_news_command,         # /news, /whales, /intel
        
        # AI models
        route_model_command,        # /claude, /gemini
    ]
    
    for router in routers:
        try:
            result = await router(text, chat_id, context)
            # Treat (None, None) the same as None — no match
            if result and isinstance(result, tuple) and result[0] is not None:
                return result
        except Exception as e:
            logger.error(f"Router error in {router.__name__}: {e}")
            continue

    return None


# Export for use in server.py
__all__ = ['route_command']
