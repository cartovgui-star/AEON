"""
Price & Market Data Telegram Commands
Handles /price, /top100, /movers, /trending commands
"""
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


async def handle_price(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /price [symbol] command - Get current price"""
    try:
        import app_state
        
        parts = text.split()
        
        if len(parts) < 2:
            return "Usage: /price BTC\nExample: /price ETH", "price"
        
        symbol = parts[1].upper()
        if not symbol.endswith('/USDT'):
            symbol_lookup = f"{symbol}/USDT"
        else:
            symbol_lookup = symbol
            symbol = symbol.replace('/USDT', '')
        
        # Find in MEXC data
        coin_data = None
        if hasattr(app_state, 'mexc_data') and app_state.mexc_data:
            for coin in app_state.mexc_data:
                if coin.get('symbol') == symbol_lookup:
                    coin_data = coin
                    break
        
        if coin_data:
            price = coin_data.get('price', 0)
            change_24h = coin_data.get('change_24h', 0)
            volume_24h = coin_data.get('volume_24h', 0)
            high_24h = coin_data.get('high_24h', 0)
            low_24h = coin_data.get('low_24h', 0)
            
            emoji = "🟢" if change_24h >= 0 else "🔴"
            
            response = f"""💰 {symbol}/USDT

{emoji} ${price:,.4f if price < 1 else price:,.2f}
24h Change: {change_24h:+.2f}%

📊 24h Stats
• High: ${high_24h:,.4f if high_24h < 1 else high_24h:,.2f}
• Low: ${low_24h:,.4f if low_24h < 1 else low_24h:,.2f}
• Volume: ${volume_24h/1e6:.2f}M

Use /elite {symbol} for trade setup analysis"""
        else:
            response = f"❌ Price not found for {symbol}. Make sure it's listed on MEXC."
            
    except Exception as e:
        logger.error(f"Price error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "price"


async def handle_top100(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /top100 command - Top 100 by market cap"""
    try:
        import app_state
        
        if hasattr(app_state, 'mexc_data') and app_state.mexc_data:
            # Sort by volume as proxy for market cap
            sorted_coins = sorted(
                app_state.mexc_data, 
                key=lambda x: x.get('volume_24h', 0), 
                reverse=True
            )[:10]
            
            response = "🏆 TOP COINS BY VOLUME\n\n"
            for i, coin in enumerate(sorted_coins, 1):
                symbol = coin.get('symbol', '').replace('/USDT', '')
                price = coin.get('price', 0)
                change = coin.get('change_24h', 0)
                volume = coin.get('volume_24h', 0)
                
                emoji = "🟢" if change >= 0 else "🔴"
                response += f"{i}. {symbol}: ${price:,.2f} {emoji} {change:+.1f}%\n"
                response += f"   Vol: ${volume/1e6:.1f}M\n"
        else:
            response = "❌ Market data not available"
            
    except Exception as e:
        logger.error(f"Top100 error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "market"


async def handle_movers(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /movers command - Biggest gainers and losers"""
    try:
        import app_state
        
        if hasattr(app_state, 'mexc_data') and app_state.mexc_data:
            # Filter out low volume coins
            coins = [c for c in app_state.mexc_data if c.get('volume_24h', 0) > 100000]
            
            # Top gainers
            gainers = sorted(coins, key=lambda x: x.get('change_24h', 0), reverse=True)[:5]
            
            # Top losers
            losers = sorted(coins, key=lambda x: x.get('change_24h', 0))[:5]
            
            response = "📈 TOP GAINERS (24h)\n"
            for coin in gainers:
                symbol = coin.get('symbol', '').replace('/USDT', '')
                change = coin.get('change_24h', 0)
                response += f"🚀 {symbol}: {change:+.1f}%\n"
            
            response += "\n📉 TOP LOSERS (24h)\n"
            for coin in losers:
                symbol = coin.get('symbol', '').replace('/USDT', '')
                change = coin.get('change_24h', 0)
                response += f"💀 {symbol}: {change:.1f}%\n"
        else:
            response = "❌ Market data not available"
            
    except Exception as e:
        logger.error(f"Movers error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "market"


async def handle_trending(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /trending command - Trending coins"""
    try:
        import app_state
        
        if hasattr(app_state, 'mexc_data') and app_state.mexc_data:
            # Calculate "trending" score based on volume increase + price change
            coins = []
            for c in app_state.mexc_data:
                volume = c.get('volume_24h', 0)
                change = c.get('change_24h', 0)
                # Trending = high volume + significant price move
                if volume > 500000 and abs(change) > 2:
                    score = (volume / 1e6) * abs(change)
                    coins.append({**c, 'trending_score': score})
            
            trending = sorted(coins, key=lambda x: x.get('trending_score', 0), reverse=True)[:10]
            
            if trending:
                response = "🔥 TRENDING COINS\n\n"
                for i, coin in enumerate(trending, 1):
                    symbol = coin.get('symbol', '').replace('/USDT', '')
                    change = coin.get('change_24h', 0)
                    volume = coin.get('volume_24h', 0)
                    emoji = "🚀" if change >= 0 else "📉"
                    
                    response += f"{i}. {emoji} {symbol}: {change:+.1f}% (${volume/1e6:.1f}M vol)\n"
            else:
                response = "🔥 No significant trending activity right now."
        else:
            response = "❌ Market data not available"
            
    except Exception as e:
        logger.error(f"Trending error: {e}")
        response = f"❌ Error: {str(e)}"
    
    return response, "market"


# Command routing
PRICE_HANDLERS = {
    '/top100': handle_top100,
    '/top': handle_top100,
    '/movers': handle_movers,
    '/gainers': handle_movers,
    '/trending': handle_trending,
    '/hot': handle_trending,
}


async def route_price_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route price/market commands to appropriate handler"""
    text_lower = text.lower().strip()
    
    # Handle /price with argument
    if text_lower.startswith('/price'):
        return await handle_price(text, chat_id, context)
    
    for pattern, handler in PRICE_HANDLERS.items():
        if text_lower == pattern:
            return await handler(text, chat_id, context)
    
    return None
