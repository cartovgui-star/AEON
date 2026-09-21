"""
Market Intelligence Command Handlers
/market, /summary — global overview
/fear, /greed, /fng — Fear & Greed index
/movers, /gainers  — top gainers/losers (enhanced_intel)
/trending, /hot    — trending coins (CoinGecko)
/whales            — large OI / funding snapshot
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


async def handle_market_summary(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /market or /summary command"""
    import app_state

    try:
        global_data = await app_state.enhanced_intel.get_global_market_data()
        fng = await app_state.enhanced_intel.get_fear_greed_index()

        btc_ticker = await app_state.market_intel.get_ticker("BTC/USDT")
        eth_ticker = await app_state.market_intel.get_ticker("ETH/USDT")

        btc_price = btc_ticker.get("price", 0) if "error" not in btc_ticker else 0
        btc_change = btc_ticker.get("change_24h", 0) or 0
        eth_price = eth_ticker.get("price", 0) if "error" not in eth_ticker else 0
        eth_change = eth_ticker.get("change_24h", 0) or 0

        total_mcap = global_data.get("total_market_cap", 0) or 0
        total_vol = global_data.get("total_volume_24h", 0) or 0
        btc_dom = global_data.get("btc_dominance", 0) or 0

        fng_val = fng.get("value", 50)
        fng_cls = fng.get("classification", "Neutral")

        response = f"""📊 MARKET SUMMARY

BTC: ${btc_price:,.0f} ({'+' if btc_change >= 0 else ''}{btc_change:.1f}%)
ETH: ${eth_price:,.0f} ({'+' if eth_change >= 0 else ''}{eth_change:.1f}%)

😱 Fear & Greed: {fng_val} - {fng_cls}

📈 BTC Dominance: {btc_dom:.1f}%
💰 Total MCap: ${total_mcap/1e12:.2f}T
📊 24h Volume: ${total_vol/1e9:.1f}B"""

    except Exception as e:
        response = f"❌ Error getting market data: {str(e)}"

    return response, "market"


async def handle_fear_greed(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /fear, /greed, /fng command"""
    import app_state

    try:
        fng = await app_state.enhanced_intel.get_fear_greed_index(days=7)

        value = fng.get("value", 50)
        classification = fng.get("classification", "Neutral")
        history = fng.get("history") or []

        if value <= 25:
            emoji = "😱"
            desc = "Extreme fear — possible buying opportunity"
        elif value <= 45:
            emoji = "😰"
            desc = "Fear — market is cautious"
        elif value <= 55:
            emoji = "😐"
            desc = "Neutral — market undecided"
        elif value <= 75:
            emoji = "😊"
            desc = "Greed — market is optimistic"
        else:
            emoji = "🤑"
            desc = "Extreme greed — possible correction coming"

        response = f"""{emoji} FEAR & GREED INDEX

Value: {value}/100
Status: {classification}

{desc}"""

        # Pull yesterday / last week from history if available
        if len(history) >= 2:
            yesterday_val = int(history[1].get("value", value))
            response += f"\n\nYesterday: {yesterday_val}"
        if len(history) >= 7:
            week_val = int(history[6].get("value", value))
            response += f"\nLast Week: {week_val}"

    except Exception as e:
        response = f"❌ Error getting Fear & Greed: {str(e)}"

    return response, "market"


async def handle_top_movers(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /movers, /gainers command"""
    import app_state

    try:
        movers = await app_state.enhanced_intel.get_top_movers(5)

        gainers = movers.get("gainers", [])[:5]
        losers = movers.get("losers", [])[:5]

        response = "📈 TOP MOVERS (24h)\n\n🟢 GAINERS:\n"
        for coin in gainers:
            symbol = (coin.get('symbol') or '').upper()
            change = coin.get('change_24h', 0) or 0
            response += f"• {symbol}: +{change:.1f}%\n"

        response += "\n🔴 LOSERS:\n"
        for coin in losers:
            symbol = (coin.get('symbol') or '').upper()
            change = coin.get('change_24h', 0) or 0
            response += f"• {symbol}: {change:.1f}%\n"

    except Exception as e:
        response = f"❌ Error getting movers: {str(e)}"

    return response, "market"


async def handle_trending(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /trending, /hot command"""
    import app_state

    try:
        trending = await app_state.enhanced_intel.get_trending_coins()

        response = "🔥 TRENDING COINS (CoinGecko)\n\n"
        for i, coin in enumerate(trending[:10], 1):
            name = coin.get("name") or coin.get("symbol") or "Unknown"
            change = coin.get("data", {}).get("price_change_percentage_24h", {}).get("usd") or coin.get("price_change_24h")
            line = f"{i}. {name}"
            if change is not None:
                line += f" ({'+' if change >= 0 else ''}{change:.1f}%)"
            response += line + "\n"

        if not trending:
            response = "🔥 No trending data available right now."

    except Exception as e:
        response = f"❌ Error getting trending: {str(e)}"

    return response, "market"


async def handle_whales(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /whales — OI + funding snapshot as large-position proxy"""
    import app_state

    try:
        btc_oi = await app_state.market_intel.get_ticker("BTC/USDT")
        fng = await app_state.enhanced_intel.get_fear_greed_index()

        fng_val = fng.get("value", 50)
        fng_cls = fng.get("classification", "Neutral")

        # Use top movers as a proxy for institutional flow
        movers = await app_state.enhanced_intel.get_top_movers(3)
        gainers = movers.get("gainers", [])

        response = "🐋 LARGE POSITION SNAPSHOT\n\n"
        response += f"😱 Market Sentiment: {fng_val}/100 ({fng_cls})\n"

        if gainers:
            response += "\n📈 Momentum Leaders (likely institutional interest):\n"
            for g in gainers:
                symbol = (g.get('symbol') or '').upper()
                change = g.get('change_24h', 0) or 0
                response += f"• {symbol}: {change:+.1f}%\n"

        response += "\n💡 For real whale data use: nansen.ai or lookonchain.com"

    except Exception as e:
        response = f"❌ Error getting whale snapshot: {str(e)}"

    return response, "market"


MARKET_HANDLERS = {
    '/market':   handle_market_summary,
    '/summary':  handle_market_summary,
    '/fear':     handle_fear_greed,
    '/greed':    handle_fear_greed,
    '/fng':      handle_fear_greed,
    '/movers':   handle_top_movers,
    '/gainers':  handle_top_movers,
    '/trending': handle_trending,
    '/hot':      handle_trending,
    '/whales':   handle_whales,
    '/whale':    handle_whales,
}


async def route_market_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route market intelligence commands"""
    text_lower = text.lower().strip()

    handler = MARKET_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)

    return None
