"""
Market Intelligence Command Handlers
Commands: /market, /fear, /greed, /fng, /top100, /movers, /trending, /news, /whales, /onchain
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_market_summary(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /market or /summary command"""
    import app_state
    
    try:
        market = await app_state.market_intel.get_market_overview()
        
        btc = market.get("btc", {})
        eth = market.get("eth", {})
        fng = market.get("fear_greed", {})
        
        btc_change = btc.get("change_24h", 0)
        eth_change = eth.get("change_24h", 0)
        
        response = f"""📊 MARKET SUMMARY

BTC: ${btc.get('price', 0):,.0f} ({'+' if btc_change >= 0 else ''}{btc_change:.1f}%)
ETH: ${eth.get('price', 0):,.0f} ({'+' if eth_change >= 0 else ''}{eth_change:.1f}%)

😱 Fear & Greed: {fng.get('value', 50)} - {fng.get('classification', 'Neutral')}

📈 Dominance: BTC {market.get('btc_dominance', 0):.1f}%
💰 Total MCap: ${market.get('total_market_cap', 0)/1e12:.2f}T
📊 24h Volume: ${market.get('total_volume', 0)/1e9:.1f}B"""
    except Exception as e:
        response = f"❌ Error getting market data: {str(e)}"
    
    return response, "market"


async def handle_fear_greed(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /fear, /greed, /fng command"""
    import app_state
    
    try:
        fng = await app_state.market_intel.get_fear_greed()
        
        value = fng.get("value", 50)
        classification = fng.get("classification", "Neutral")
        
        # Emoji based on value
        if value <= 25:
            emoji = "😱"
            desc = "Extreme fear - possible buying opportunity"
        elif value <= 45:
            emoji = "😰"
            desc = "Fear - market is cautious"
        elif value <= 55:
            emoji = "😐"
            desc = "Neutral - market undecided"
        elif value <= 75:
            emoji = "😊"
            desc = "Greed - market is optimistic"
        else:
            emoji = "🤑"
            desc = "Extreme greed - possible correction coming"
        
        response = f"""{emoji} FEAR & GREED INDEX

Value: {value}/100
Status: {classification}

{desc}

Historical:
• Yesterday: {fng.get('yesterday', value)}
• Last Week: {fng.get('last_week', value)}
• Last Month: {fng.get('last_month', value)}"""
    except Exception as e:
        response = f"❌ Error getting Fear & Greed: {str(e)}"
    
    return response, "market"


async def handle_top_movers(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /movers, /gainers command"""
    import app_state
    
    try:
        movers = await app_state.market_intel.get_top_movers()
        
        gainers = movers.get("gainers", [])[:5]
        losers = movers.get("losers", [])[:5]
        
        response = "📈 TOP MOVERS (24h)\n\n🟢 GAINERS:\n"
        for coin in gainers:
            response += f"• {coin['symbol']}: +{coin['change']:.1f}%\n"
        
        response += "\n🔴 LOSERS:\n"
        for coin in losers:
            response += f"• {coin['symbol']}: {coin['change']:.1f}%\n"
    except Exception as e:
        response = f"❌ Error getting movers: {str(e)}"
    
    return response, "market"


async def handle_trending(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /trending, /hot command"""
    import app_state
    
    try:
        trending = await app_state.market_intel.get_trending_coins()
        
        response = "🔥 TRENDING COINS\n\n"
        for i, coin in enumerate(trending[:10], 1):
            response += f"{i}. {coin.get('name', coin.get('symbol', 'Unknown'))}"
            if coin.get("price_change_24h"):
                response += f" ({'+' if coin['price_change_24h'] >= 0 else ''}{coin['price_change_24h']:.1f}%)"
            response += "\n"
    except Exception as e:
        response = f"❌ Error getting trending: {str(e)}"
    
    return response, "market"


async def handle_whales(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /whales, /whale command"""
    import app_state
    
    try:
        whales = await app_state.enhanced_intel.get_whale_activity()
        
        response = "🐋 WHALE ACTIVITY\n\n"
        
        if whales and whales.get("transactions"):
            for tx in whales["transactions"][:5]:
                response += f"• {tx.get('type', 'Transfer')}: {tx.get('amount', 0):,.0f} {tx.get('symbol', 'BTC')}\n"
                response += f"  Value: ${tx.get('usd_value', 0):,.0f}\n"
        else:
            response += "No significant whale activity detected recently."
            
        response += f"\n📊 24h Summary:\n"
        response += f"• Large Buys: {whales.get('large_buys', 0)}\n"
        response += f"• Large Sells: {whales.get('large_sells', 0)}\n"
        response += f"• Net Flow: {'🟢 Bullish' if whales.get('net_flow', 0) > 0 else '🔴 Bearish'}"
    except Exception as e:
        response = f"❌ Error getting whale data: {str(e)}"
    
    return response, "market"


# Export handlers
MARKET_HANDLERS = {
    '/market': handle_market_summary,
    '/summary': handle_market_summary,
    '/fear': handle_fear_greed,
    '/greed': handle_fear_greed,
    '/fng': handle_fear_greed,
    '/movers': handle_top_movers,
    '/gainers': handle_top_movers,
    '/trending': handle_trending,
    '/hot': handle_trending,
    '/whales': handle_whales,
    '/whale': handle_whales,
}


async def route_market_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route market intelligence commands"""
    text_lower = text.lower().strip()
    
    handler = MARKET_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)
    
    return None
