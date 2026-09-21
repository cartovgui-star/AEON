"""
Price & Top Coins Telegram Commands
/price [coin] — live OKX price
/top100       — top coins by market cap (LCW → CoinGecko)

NOTE: /movers, /gainers, /trending, /hot → market_commands.py (enhanced_intel)
"""
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


async def handle_price(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /price [symbol] command"""
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

        ticker = await app_state.market_intel.get_ticker(symbol_lookup)

        if ticker and "error" not in ticker:
            price = ticker.get('price', 0)
            change_24h = ticker.get('change_24h', 0) or 0
            volume_24h = ticker.get('volume_24h', 0) or 0
            high_24h = ticker.get('high_24h', 0) or 0
            low_24h = ticker.get('low_24h', 0) or 0

            emoji = "🟢" if change_24h >= 0 else "🔴"
            price_fmt = f"{price:,.4f}" if price < 1 else f"{price:,.2f}"

            response = f"""💰 {symbol}/USDT

{emoji} ${price_fmt}
24h Change: {change_24h:+.2f}%

📊 24h Stats
• High: ${high_24h:,.4f if high_24h < 1 else high_24h:,.2f}
• Low: ${low_24h:,.4f if low_24h < 1 else low_24h:,.2f}
• Volume: ${volume_24h/1e6:.2f}M

Use /scan {symbol} for trade setup analysis"""
        else:
            err = ticker.get('error', 'not found') if ticker else 'not found'
            response = f"❌ Price not found for {symbol}: {err}"

    except Exception as e:
        logger.error(f"Price error: {e}")
        response = f"❌ Error: {str(e)}"

    return response, "price"


async def handle_top100(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /top100 command — top coins by market cap"""
    try:
        import app_state

        coins = await app_state.enhanced_intel.get_top_100_coins()
        if not coins:
            return "❌ Market data not available right now.", "market"

        top10 = coins[:10]
        response = "🏆 TOP COINS BY MARKET CAP\n\n"
        for i, coin in enumerate(top10, 1):
            symbol = (coin.get('symbol') or '').upper()
            price = coin.get('current_price', 0) or 0
            change = coin.get('price_change_percentage_24h', 0) or 0
            emoji = "🟢" if change >= 0 else "🔴"
            price_fmt = f"{price:,.4f}" if price < 1 else f"{price:,.2f}"
            response += f"{i}. {symbol}: ${price_fmt} {emoji} {change:+.1f}%\n"

        response += "\n/movers for biggest gainers/losers"

    except Exception as e:
        logger.error(f"Top100 error: {e}")
        response = f"❌ Error: {str(e)}"

    return response, "market"


PRICE_HANDLERS = {
    '/top100': handle_top100,
    '/top':    handle_top100,
}


async def route_price_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route /price and /top100 commands"""
    text_lower = text.lower().strip()

    if text_lower.startswith('/price'):
        return await handle_price(text, chat_id, context)

    handler = PRICE_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)

    return None
