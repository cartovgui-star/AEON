"""
News & Intel Telegram Commands
Handles /news, /whales, /onchain, /intel commands
"""
from typing import Tuple, Optional
import logging
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)


async def handle_news(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /news command - Get latest crypto news"""
    try:
        import app_state
        
        news_items = []
        
        # Try to get from cached news
        if hasattr(app_state, 'news_cache') and app_state.news_cache:
            news_items = app_state.news_cache[:5]
        else:
            # Fetch from CryptoPanic or similar
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://cryptopanic.com/api/v1/posts/?auth_token=demo&public=true&kind=news",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            news_items = data.get('results', [])[:5]
            except Exception:
                pass
        
        if news_items:
            response = "📰 LATEST CRYPTO NEWS\n\n"
            for i, item in enumerate(news_items, 1):
                title = item.get('title', 'No title')[:60]
                source = item.get('source', {}).get('title', 'Unknown')
                votes = item.get('votes', {})
                sentiment = "🟢" if votes.get('positive', 0) > votes.get('negative', 0) else "🔴" if votes.get('negative', 0) > votes.get('positive', 0) else "⚪"
                
                response += f"{i}. {sentiment} {title}...\n   📍 {source}\n\n"
        else:
            response = "📰 No recent news available. Try again later."
            
    except Exception as e:
        logger.error(f"News error: {e}")
        response = f"❌ Error fetching news: {str(e)}"
    
    return response, "news"


async def handle_whales(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /whales command - Show whale activity"""
    try:
        import app_state
        
        whale_data = []
        
        # Try to get whale data from app state
        if hasattr(app_state, 'whale_alerts') and app_state.whale_alerts:
            whale_data = app_state.whale_alerts[:5]
        
        if whale_data:
            response = "🐋 WHALE ACTIVITY (Last 24h)\n\n"
            for whale in whale_data:
                symbol = whale.get('symbol', 'BTC').replace('/USDT', '')
                amount = whale.get('amount_usd', 0)
                tx_type = whale.get('type', 'transfer')
                exchange = whale.get('exchange', 'Unknown')
                
                emoji = "📥" if tx_type == 'exchange_inflow' else "📤" if tx_type == 'exchange_outflow' else "🔄"
                response += f"{emoji} {symbol}: ${amount/1e6:.1f}M\n"
                response += f"   {tx_type.replace('_', ' ').title()} → {exchange}\n\n"
        else:
            response = """🐋 WHALE TRACKING

No significant whale activity detected recently.

Whale alerts trigger on:
• Exchange inflows > $10M
• Exchange outflows > $10M  
• Large wallet transfers

Use /onchain for on-chain metrics"""

    except Exception as e:
        logger.error(f"Whales error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "whales"


async def handle_onchain(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /onchain command - On-chain metrics"""
    try:
        import app_state
        
        # Get on-chain data if available
        onchain = {}
        if hasattr(app_state, 'onchain_data'):
            onchain = app_state.onchain_data or {}
        
        btc_netflow = onchain.get('btc_netflow', 0)
        eth_netflow = onchain.get('eth_netflow', 0)
        stablecoin_supply = onchain.get('stablecoin_supply', 0)
        
        response = f"""🔗 ON-CHAIN METRICS

📊 Exchange Netflow (24h)
• BTC: {btc_netflow:+,.0f} BTC
  {'🔴 Selling pressure' if btc_netflow > 0 else '🟢 Buying pressure'}
• ETH: {eth_netflow:+,.0f} ETH
  {'🔴 Selling pressure' if eth_netflow > 0 else '🟢 Buying pressure'}

💵 Stablecoin Supply
• Total: ${stablecoin_supply/1e9:.1f}B
  {'🟢 Dry powder available' if stablecoin_supply > 100e9 else '⚪ Normal levels'}

📈 Interpretation
{_get_onchain_interpretation(btc_netflow, eth_netflow)}"""

    except Exception as e:
        logger.error(f"Onchain error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "onchain"


def _get_onchain_interpretation(btc_netflow: float, eth_netflow: float) -> str:
    """Generate interpretation of on-chain data"""
    if btc_netflow < -1000 and eth_netflow < -1000:
        return "• Strong accumulation - bullish signal\n• Coins leaving exchanges for cold storage"
    elif btc_netflow > 1000 and eth_netflow > 1000:
        return "• Distribution phase - bearish signal\n• Coins moving to exchanges for selling"
    else:
        return "• Mixed signals - neutral\n• No strong directional bias"


async def handle_intel(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /intel command - Market intelligence summary"""
    try:
        import app_state
        
        # Gather all intelligence
        market = app_state.market_data if hasattr(app_state, 'market_data') else {}
        fear_greed = market.get('fear_greed', 50)
        btc_dominance = market.get('btc_dominance', 50)
        total_mcap = market.get('total_mcap', 0)
        
        regime = market.get('regime', 'UNKNOWN')
        btc_bias = market.get('btc_bias', 'NEUTRAL')
        
        response = f"""🧠 MARKET INTELLIGENCE

📊 Market Overview
• Total Market Cap: ${total_mcap/1e12:.2f}T
• BTC Dominance: {btc_dominance:.1f}%
• Fear & Greed: {fear_greed} {'😨 Extreme Fear' if fear_greed < 25 else '😰 Fear' if fear_greed < 40 else '😐 Neutral' if fear_greed < 60 else '😊 Greed' if fear_greed < 75 else '🤑 Extreme Greed'}

🎯 Trading Conditions
• Market Regime: {regime}
• BTC Bias: {btc_bias}
• Recommended: {'LONG setups' if btc_bias == 'BULLISH' else 'SHORT setups' if btc_bias == 'BEARISH' else 'Wait for clarity'}

⚡ Quick Actions
• /news - Latest news
• /whales - Whale activity
• /elite scan - Elite signals
• /opps - Current opportunities"""

    except Exception as e:
        logger.error(f"Intel error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "intel"


# Command routing
NEWS_HANDLERS = {
    '/news': handle_news,
    '/whales': handle_whales,
    '/whale': handle_whales,
    '/onchain': handle_onchain,
    '/chain': handle_onchain,
    '/intel': handle_intel,
    '/intelligence': handle_intel,
}


async def route_news_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route news/intel commands to appropriate handler"""
    text_lower = text.lower().strip()
    
    for pattern, handler in NEWS_HANDLERS.items():
        if text_lower == pattern or text_lower.startswith(pattern + ' '):
            return await handler(text, chat_id, context)
    
    return None
