"""
Auto Trading Telegram Commands
Handles /auto, /auto on, /auto off, /riskcheck commands
"""
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


async def handle_auto_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /auto command - Show auto trading status"""
    try:
        import app_state
        
        trading_active = False
        settings = {}
        
        if hasattr(app_state, 'trading_active'):
            trading_active = app_state.trading_active
        
        if hasattr(app_state, 'trading_settings'):
            settings = app_state.trading_settings or {}
        
        status_emoji = "🟢" if trading_active else "🔴"
        status_text = "ACTIVE" if trading_active else "PAUSED"
        
        response = f"""🤖 AUTO TRADING STATUS

{status_emoji} Status: {status_text}

⚙️ Settings:
• Min Confidence: {settings.get('min_confidence', 75)}%
• Max Positions: {settings.get('max_positions', 5)}
• Position Size: ${settings.get('position_size', 1000):,.0f}
• Default Leverage: {settings.get('leverage', 10)}x
• Risk per Trade: {settings.get('risk_pct', 2)}%

Commands:
• /auto on - Start auto trading
• /auto off - Pause auto trading
• /riskcheck - Run risk assessment"""

    except Exception as e:
        logger.error(f"Auto status error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "auto"


async def handle_auto_on(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /auto on command - Enable auto trading"""
    try:
        import app_state
        
        app_state.trading_active = True
        
        # Also enable via API if available
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(f"http://localhost:8001/api/trading/v2/toggle?enabled=true")
        except:
            pass
        
        response = """🟢 AUTO TRADING ENABLED

Aeon will now automatically:
• Scan for high-confidence setups
• Execute trades based on Elite Strategy
• Manage positions with trailing stops
• Respect risk management rules

⚠️ Monitor via /stats and /positions
Use /auto off to pause at any time"""

    except Exception as e:
        logger.error(f"Auto on error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "auto"


async def handle_auto_off(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /auto off command - Disable auto trading"""
    try:
        import app_state
        
        app_state.trading_active = False
        
        # Also disable via API if available
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(f"http://localhost:8001/api/trading/v2/toggle?enabled=false")
        except:
            pass
        
        response = """🔴 AUTO TRADING PAUSED

Aeon will:
• Continue monitoring markets
• NOT execute new trades
• Manage existing positions normally

Existing positions remain open.
Use /auto on to resume trading"""

    except Exception as e:
        logger.error(f"Auto off error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "auto"


async def handle_riskcheck(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /riskcheck command - Run risk assessment"""
    try:
        import app_state
        
        # Get current positions and calculate risk metrics
        positions = []
        if hasattr(app_state, 'live_positions'):
            positions = app_state.live_positions or []
        
        total_exposure = 0
        total_leverage = 0
        max_drawdown_risk = 0
        
        for pos in positions:
            size = pos.get('position_size', 0)
            leverage = pos.get('leverage', 10)
            total_exposure += size
            total_leverage += leverage
            
            # Calculate potential loss if all hit stop loss
            sl_distance = abs(pos.get('entry_price', 0) - pos.get('stop_price', 0)) / pos.get('entry_price', 1) * 100
            max_drawdown_risk += sl_distance * leverage
        
        avg_leverage = total_leverage / len(positions) if positions else 0
        
        # Risk assessment
        risk_level = "LOW"
        risk_emoji = "🟢"
        if max_drawdown_risk > 20 or avg_leverage > 30:
            risk_level = "HIGH"
            risk_emoji = "🔴"
        elif max_drawdown_risk > 10 or avg_leverage > 15:
            risk_level = "MEDIUM"
            risk_emoji = "🟡"
        
        response = f"""⚠️ RISK ASSESSMENT

{risk_emoji} Risk Level: {risk_level}

📊 Current Exposure
• Open Positions: {len(positions)}
• Total Exposure: ${total_exposure:,.0f}
• Avg Leverage: {avg_leverage:.1f}x

💀 Worst Case Scenario
• Max Drawdown Risk: {max_drawdown_risk:.1f}%
  (If ALL positions hit stop loss)

📋 Recommendations"""

        if risk_level == "HIGH":
            response += """
• ⚠️ Consider closing some positions
• ⚠️ Reduce leverage on new trades
• ⚠️ Avoid adding new positions"""
        elif risk_level == "MEDIUM":
            response += """
• Monitor positions closely
• Consider tightening stop losses
• Be selective with new entries"""
        else:
            response += """
• ✅ Risk within acceptable limits
• Continue normal operations
• Room for additional positions"""

    except Exception as e:
        logger.error(f"Riskcheck error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "risk"


# Command routing
AUTO_HANDLERS = {
    '/auto': handle_auto_status,
    '/autotrade': handle_auto_status,
    '/auto on': handle_auto_on,
    '/auto off': handle_auto_off,
    '/riskcheck': handle_riskcheck,
    '/risk': handle_riskcheck,
}


async def route_auto_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route auto trading commands to appropriate handler"""
    text_lower = text.lower().strip()
    
    for pattern, handler in AUTO_HANDLERS.items():
        if text_lower == pattern:
            return await handler(text, chat_id, context)
    
    return None
