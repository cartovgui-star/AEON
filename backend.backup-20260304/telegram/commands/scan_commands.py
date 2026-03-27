"""
Scan & Analysis Command Handlers
Commands: /scan, /analyze, /quick, /opps, /opportunities
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_scan(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /scan [symbol] command"""
    from autonomous_trader_v2 import autonomous_trader_v2
    import app_state
    
    parts = text.lower().split()
    
    if len(parts) >= 2:
        # Scan specific symbol
        symbol = parts[1].upper()
        try:
            result = await autonomous_trader_v2.analyze_symbol(symbol + "/USDT")
            
            if result and result.get("signal"):
                signal = result["signal"]
                direction = signal.get("direction", "N/A")
                conf = signal.get("confidence", 0)
                
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                response = f"""{dir_emoji} SCAN: {symbol}

Direction: {direction}
Confidence: {conf}%
Entry: ${signal.get('entry_price', 0):,.2f}
Stop: ${signal.get('stop_price', 0):,.2f}
Target: ${signal.get('target_price', 0):,.2f}

Confirmations:
"""
                for conf_item in signal.get("confirmations", [])[:5]:
                    response += f"• {conf_item}\n"
            else:
                response = f"❌ No trading opportunity for {symbol} right now.\n\nTry /elite {symbol} for Elite Strategy analysis."
        except Exception as e:
            response = f"❌ Error scanning {symbol}: {str(e)}"
    else:
        # Scan all
        try:
            result = await autonomous_trader_v2.scan_opportunities()
            opportunities = result.get("opportunities", [])
            
            if opportunities:
                response = f"🔍 SCAN RESULTS: {len(opportunities)} opportunities\n\n"
                for opp in opportunities[:5]:
                    symbol = opp.get("symbol", "").replace("/USDT", "")
                    direction = opp.get("direction", "N/A")
                    conf = opp.get("confidence", 0)
                    dir_emoji = "🟢" if direction == "LONG" else "🔴"
                    response += f"{dir_emoji} {symbol} {direction} ({conf}%)\n"
                
                response += "\n/scan [symbol] for detailed analysis"
            else:
                response = "🔍 No opportunities found right now.\n\nTry:\n• /elite scan - Elite Strategy signals\n• /mtf - MTF confluence scan"
        except Exception as e:
            response = f"❌ Error scanning: {str(e)}"
    
    return response, "analysis"


async def handle_opportunities(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /opps, /opportunities command"""
    from autonomous_trader_v2 import autonomous_trader_v2
    from elite_strategy_v3 import get_elite_strategy
    import app_state
    
    try:
        # Get opportunities from both strategies
        v2_result = await autonomous_trader_v2.scan_opportunities()
        v2_opps = v2_result.get("opportunities", [])
        
        elite = get_elite_strategy(app_state.advanced_strategies, None, app_state.enhanced_intel)
        elite_signals = await elite.scan_all_elite()
        
        response = "💎 TRADING OPPORTUNITIES\n\n"
        
        # Elite signals first (higher quality)
        if elite_signals:
            response += f"🎯 ELITE ({elite.get_stats().get('mode', 'STRICT')}):\n"
            for sig in elite_signals[:3]:
                symbol = sig.get("symbol", "").replace("/USDT", "")
                direction = sig.get("direction", "N/A")
                conf = sig.get("confidence", 0)
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                response += f"  {dir_emoji} {symbol} {direction} ({conf}%)\n"
            response += "\n"
        
        # V2.1 opportunities
        if v2_opps:
            response += "🤖 AUTONOMOUS V2.1:\n"
            for opp in v2_opps[:3]:
                symbol = opp.get("symbol", "").replace("/USDT", "")
                direction = opp.get("direction", "N/A")
                conf = opp.get("confidence", 0)
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                response += f"  {dir_emoji} {symbol} {direction} ({conf}%)\n"
        
        if not elite_signals and not v2_opps:
            response = "📊 No opportunities found right now.\n\nMarket conditions may not be favorable.\nTry /elite relaxed for more signals."
        else:
            response += "\n/scan [symbol] for details"
        
    except Exception as e:
        response = f"❌ Error getting opportunities: {str(e)}"
    
    return response, "analysis"


async def handle_quick_analysis(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /quick [symbol] command - quick market view"""
    import app_state
    
    parts = text.lower().split()
    symbol = parts[1].upper() if len(parts) >= 2 else "BTC"
    
    try:
        ta = await app_state.market_intel.get_technical_analysis(symbol + "USDT", "4h")
        
        if ta:
            indicators = ta.get("indicators", {})
            price = indicators.get("current_price", indicators.get("close", 0))
            rsi = indicators.get("rsi", 50)
            adx = indicators.get("adx", 0)
            
            # Determine bias
            ema_9 = indicators.get("ema_9", price)
            ema_21 = indicators.get("ema_21", price)
            ema_50 = indicators.get("ema_50", price)
            
            if ema_9 > ema_21 > ema_50:
                trend = "🟢 BULLISH"
            elif ema_9 < ema_21 < ema_50:
                trend = "🔴 BEARISH"
            else:
                trend = "⚪ NEUTRAL"
            
            # RSI status
            if rsi > 70:
                rsi_status = "Overbought ⚠️"
            elif rsi < 30:
                rsi_status = "Oversold ⚠️"
            else:
                rsi_status = "Normal"
            
            response = f"""⚡ QUICK: {symbol}

💰 Price: ${price:,.2f}
📈 Trend: {trend}
📊 RSI: {rsi:.1f} ({rsi_status})
📉 ADX: {adx:.1f}

EMA Stack:
• 9: ${ema_9:,.2f}
• 21: ${ema_21:,.2f}
• 50: ${ema_50:,.2f}

/scan {symbol} for full analysis"""
        else:
            response = f"❌ Could not get data for {symbol}"
    except Exception as e:
        response = f"❌ Error: {str(e)}"
    
    return response, "analysis"


# Export handlers
SCAN_HANDLERS = {
    '/scan': handle_scan,
    '/opps': handle_opportunities,
    '/opportunities': handle_opportunities,
    '/quick': handle_quick_analysis,
}


async def route_scan_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route scan/analysis commands"""
    text_lower = text.lower().strip()
    
    # Exact match
    if text_lower in SCAN_HANDLERS:
        return await SCAN_HANDLERS[text_lower](text, chat_id, context)
    
    # Prefix match for commands with arguments
    for cmd in ['/scan', '/quick']:
        if text_lower.startswith(cmd + ' '):
            return await SCAN_HANDLERS[cmd](text, chat_id, context)
    
    return None
