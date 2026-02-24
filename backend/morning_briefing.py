"""
AEON DAILY MORNING BRIEFING
Sends comprehensive market overview every day at 6 AM Central Time (Austin, TX)

Features:
- Market structure analysis for all 15 cryptos
- Key support/resistance levels
- Fear & Greed Index + analysis
- Overnight summary (what happened while sleeping)
- Top setups to watch today
- Funding rates & derivatives data
- Market sentiment
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Set
import pytz
import ccxt

logger = logging.getLogger(__name__)

# Initialize MEXC
try:
    mexc = ccxt.mexc({'enableRateLimit': True})
except Exception as e:
    logger.error(f"Failed to init MEXC for briefing: {e}")
    mexc = None

# All tracked cryptos
TRACKED_CRYPTOS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'LINK/USDT',
    'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ARB/USDT', 'OP/USDT'
]

# Austin, Texas timezone
AUSTIN_TZ = pytz.timezone('America/Chicago')  # CST/CDT
BRIEFING_HOUR = 6  # 6 AM


class MorningBriefing:
    """
    Daily market briefing system for Aeon
    Runs at 6 AM Central Time every day
    """
    
    def __init__(self):
        self.last_briefing_date = None
        self.market_intel = None
        self.derivatives_intel = None
        self.enhanced_intel = None
        self.send_message: Optional[Callable] = None
        self.get_user_settings: Optional[Callable] = None
        self.chat_ids: Set[int] = set()
        self.db = None
        self.is_active = True
        
    def set_dependencies(
        self,
        market_intel,
        derivatives_intel,
        enhanced_intel,
        send_message: Callable,
        get_user_settings: Callable,
        chat_ids: Set[int],
        db
    ):
        """Set external dependencies"""
        self.market_intel = market_intel
        self.derivatives_intel = derivatives_intel
        self.enhanced_intel = enhanced_intel
        self.send_message = send_message
        self.get_user_settings = get_user_settings
        self.chat_ids = chat_ids
        self.db = db
        
    def _get_austin_time(self) -> datetime:
        """Get current time in Austin, Texas"""
        return datetime.now(AUSTIN_TZ)
    
    def _should_send_briefing(self) -> bool:
        """Check if it's time to send the morning briefing"""
        austin_now = self._get_austin_time()
        
        # Check if it's 6 AM (within 5 minute window)
        if austin_now.hour == BRIEFING_HOUR and austin_now.minute < 5:
            # Check if we already sent today
            today = austin_now.date()
            if self.last_briefing_date != today:
                return True
        
        return False
    
    async def get_overnight_movers(self) -> Dict:
        """Get the biggest movers from overnight (8 PM to 6 AM)"""
        movers = {"gainers": [], "losers": [], "high_volume": []}
        
        if not mexc:
            return movers
        
        try:
            tickers = mexc.fetch_tickers(TRACKED_CRYPTOS)
            
            for symbol in TRACKED_CRYPTOS:
                ticker = tickers.get(symbol, {})
                if not ticker:
                    continue
                
                change = ticker.get('percentage', 0) or 0
                volume = ticker.get('quoteVolume', 0) or 0
                price = ticker.get('last', 0) or 0
                
                coin = symbol.replace('/USDT', '')
                
                data = {
                    "symbol": coin,
                    "price": price,
                    "change_24h": round(change, 2),
                    "volume_24h": volume
                }
                
                if change > 3:
                    movers["gainers"].append(data)
                elif change < -3:
                    movers["losers"].append(data)
                
                # High volume = > $100M in 24h
                if volume > 100_000_000:
                    movers["high_volume"].append(data)
            
            # Sort
            movers["gainers"] = sorted(movers["gainers"], key=lambda x: x["change_24h"], reverse=True)[:5]
            movers["losers"] = sorted(movers["losers"], key=lambda x: x["change_24h"])[:5]
            movers["high_volume"] = sorted(movers["high_volume"], key=lambda x: x["volume_24h"], reverse=True)[:3]
            
        except Exception as e:
            logger.error(f"Error getting overnight movers: {e}")
        
        return movers
    
    async def get_market_structure(self) -> Dict:
        """Get market structure for BTC and ETH (trend leaders)"""
        structure = {"btc": {}, "eth": {}, "overall_bias": "NEUTRAL"}
        
        try:
            if self.market_intel:
                # BTC analysis
                btc_ta = await self.market_intel.get_technical_analysis("BTCUSDT", "4h")
                btc_indicators = btc_ta.get("indicators", {})
                
                btc_rsi = btc_indicators.get("rsi", 50)
                btc_macd = btc_indicators.get("macd_histogram", 0)
                btc_ema_9 = btc_indicators.get("ema_9", 0)
                btc_ema_21 = btc_indicators.get("ema_21", 0)
                btc_price = btc_ta.get("price", 0)
                
                btc_trend = "BULLISH" if btc_ema_9 > btc_ema_21 else "BEARISH"
                btc_momentum = "STRONG" if abs(btc_macd) > 100 else "WEAK"
                
                structure["btc"] = {
                    "price": btc_price,
                    "trend": btc_trend,
                    "momentum": btc_momentum,
                    "rsi": round(btc_rsi, 1),
                    "support": round(btc_indicators.get("support", btc_price * 0.95), 2),
                    "resistance": round(btc_indicators.get("resistance", btc_price * 1.05), 2)
                }
                
                # ETH analysis
                eth_ta = await self.market_intel.get_technical_analysis("ETHUSDT", "4h")
                eth_indicators = eth_ta.get("indicators", {})
                
                eth_rsi = eth_indicators.get("rsi", 50)
                eth_ema_9 = eth_indicators.get("ema_9", 0)
                eth_ema_21 = eth_indicators.get("ema_21", 0)
                eth_price = eth_ta.get("price", 0)
                
                eth_trend = "BULLISH" if eth_ema_9 > eth_ema_21 else "BEARISH"
                
                structure["eth"] = {
                    "price": eth_price,
                    "trend": eth_trend,
                    "rsi": round(eth_rsi, 1),
                    "support": round(eth_indicators.get("support", eth_price * 0.95), 2),
                    "resistance": round(eth_indicators.get("resistance", eth_price * 1.05), 2)
                }
                
                # Overall market bias
                if btc_trend == "BULLISH" and eth_trend == "BULLISH":
                    structure["overall_bias"] = "BULLISH"
                elif btc_trend == "BEARISH" and eth_trend == "BEARISH":
                    structure["overall_bias"] = "BEARISH"
                else:
                    structure["overall_bias"] = "MIXED"
                    
        except Exception as e:
            logger.error(f"Error getting market structure: {e}")
        
        return structure
    
    async def get_fear_greed(self) -> Dict:
        """Get Fear & Greed Index with analysis"""
        fg_data = {"value": 50, "label": "Neutral", "analysis": ""}
        
        try:
            if self.enhanced_intel:
                fg = await self.enhanced_intel.get_fear_greed_index()
                value = fg.get("value", 50)
                fg_data["value"] = value
                
                # Determine label and analysis
                if value <= 20:
                    fg_data["label"] = "Extreme Fear"
                    fg_data["analysis"] = "Markets are extremely fearful - historically a good time to accumulate. Watch for capitulation wicks."
                elif value <= 35:
                    fg_data["label"] = "Fear"
                    fg_data["analysis"] = "Sentiment is negative but not extreme. Dip buying opportunities may emerge on further weakness."
                elif value <= 55:
                    fg_data["label"] = "Neutral"
                    fg_data["analysis"] = "Market sentiment is balanced. Focus on technicals and individual coin setups."
                elif value <= 75:
                    fg_data["label"] = "Greed"
                    fg_data["analysis"] = "Bullish sentiment growing. Trend following works but watch for overextension."
                else:
                    fg_data["label"] = "Extreme Greed"
                    fg_data["analysis"] = "Euphoria levels high - historically precedes corrections. Tighten stops on longs."
                    
        except Exception as e:
            logger.error(f"Error getting fear/greed: {e}")
        
        return fg_data
    
    async def get_funding_snapshot(self) -> Dict:
        """Get funding rates snapshot for major coins"""
        funding = {"data": [], "summary": ""}
        
        try:
            if self.derivatives_intel:
                rates = []
                for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
                    try:
                        f = await self.derivatives_intel.get_funding_rate(symbol)
                        rate = f.get("funding_rate", 0)
                        rates.append({
                            "symbol": symbol.replace("/USDT", ""),
                            "rate": round(rate * 100, 4),  # Convert to percentage
                            "direction": "LONGS PAY" if rate > 0 else "SHORTS PAY"
                        })
                    except:
                        continue
                
                funding["data"] = rates
                
                # Summary
                avg_rate = sum(r["rate"] for r in rates) / len(rates) if rates else 0
                if avg_rate > 0.05:
                    funding["summary"] = "Funding rates elevated - longs are crowded. Watch for long squeezes."
                elif avg_rate < -0.05:
                    funding["summary"] = "Funding rates negative - shorts are crowded. Watch for short squeezes."
                else:
                    funding["summary"] = "Funding rates neutral - no extreme positioning detected."
                    
        except Exception as e:
            logger.error(f"Error getting funding: {e}")
        
        return funding
    
    async def get_key_levels(self) -> List[Dict]:
        """Get key support/resistance levels for all cryptos"""
        levels = []
        
        try:
            if self.market_intel:
                for symbol in TRACKED_CRYPTOS[:10]:  # Top 10 for brevity
                    try:
                        ta = await self.market_intel.get_technical_analysis(
                            symbol.replace("/", ""), "4h"
                        )
                        indicators = ta.get("indicators", {})
                        price = ta.get("price", 0)
                        
                        if price > 0:
                            coin = symbol.replace("/USDT", "")
                            support = indicators.get("support", price * 0.97)
                            resistance = indicators.get("resistance", price * 1.03)
                            
                            # Determine proximity
                            to_support = ((price - support) / price) * 100
                            to_resistance = ((resistance - price) / price) * 100
                            
                            levels.append({
                                "symbol": coin,
                                "price": price,
                                "support": round(support, 4),
                                "resistance": round(resistance, 4),
                                "near_support": to_support < 2,
                                "near_resistance": to_resistance < 2
                            })
                            
                        await asyncio.sleep(0.1)  # Rate limiting
                    except:
                        continue
                        
        except Exception as e:
            logger.error(f"Error getting key levels: {e}")
        
        return levels
    
    async def get_setups_to_watch(self) -> List[Dict]:
        """Identify potential setups to watch for the day"""
        setups = []
        
        try:
            if self.market_intel:
                for symbol in TRACKED_CRYPTOS:
                    try:
                        ta = await self.market_intel.get_technical_analysis(
                            symbol.replace("/", ""), "4h"
                        )
                        indicators = ta.get("indicators", {})
                        price = ta.get("price", 0)
                        
                        rsi = indicators.get("rsi", 50)
                        macd_hist = indicators.get("macd_histogram", 0)
                        bb_upper = indicators.get("bb_upper", price * 1.02)
                        bb_lower = indicators.get("bb_lower", price * 0.98)
                        
                        coin = symbol.replace("/USDT", "")
                        setup_type = None
                        reason = ""
                        direction = ""
                        
                        # Oversold bounce setup
                        if rsi < 30 and price < bb_lower * 1.01:
                            setup_type = "OVERSOLD BOUNCE"
                            direction = "LONG"
                            reason = f"RSI at {rsi:.0f}, price near lower BB"
                        
                        # Overbought rejection setup
                        elif rsi > 70 and price > bb_upper * 0.99:
                            setup_type = "OVERBOUGHT REJECTION"
                            direction = "SHORT"
                            reason = f"RSI at {rsi:.0f}, price near upper BB"
                        
                        # MACD crossover potential
                        elif abs(macd_hist) < 50 and rsi > 45 and rsi < 55:
                            setup_type = "MACD CROSSOVER WATCH"
                            direction = "WAIT"
                            reason = "MACD near zero line, potential direction change"
                        
                        if setup_type:
                            setups.append({
                                "symbol": coin,
                                "setup": setup_type,
                                "direction": direction,
                                "reason": reason,
                                "price": price,
                                "rsi": round(rsi, 1)
                            })
                        
                        await asyncio.sleep(0.1)
                    except:
                        continue
                        
        except Exception as e:
            logger.error(f"Error getting setups: {e}")
        
        # Return top 5 setups
        return setups[:5]
    
    def format_price(self, price: float) -> str:
        """Format price nicely"""
        if price >= 1000:
            return f"${price:,.0f}"
        elif price >= 1:
            return f"${price:,.2f}"
        elif price >= 0.01:
            return f"${price:.4f}"
        else:
            return f"${price:.6f}"
    
    async def generate_briefing(self) -> str:
        """Generate the full morning briefing message"""
        austin_now = self._get_austin_time()
        date_str = austin_now.strftime("%A, %B %d, %Y")
        
        # Gather all data
        movers = await self.get_overnight_movers()
        structure = await self.get_market_structure()
        fear_greed = await self.get_fear_greed()
        funding = await self.get_funding_snapshot()
        setups = await self.get_setups_to_watch()
        
        # Build the message
        msg_parts = []
        
        # Header
        msg_parts.append(f"""☀️ AEON MORNING BRIEFING
{date_str} | 6:00 AM CT
━━━━━━━━━━━━━━━━━━━━━━""")
        
        # Market Structure
        btc = structure.get("btc", {})
        eth = structure.get("eth", {})
        bias = structure.get("overall_bias", "NEUTRAL")
        
        bias_emoji = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "🟡"
        
        msg_parts.append(f"""
📊 MARKET STRUCTURE
{bias_emoji} Overall Bias: {bias}

BTC: {self.format_price(btc.get('price', 0))}
  Trend: {btc.get('trend', 'N/A')} | RSI: {btc.get('rsi', 'N/A')}
  Support: {self.format_price(btc.get('support', 0))}
  Resistance: {self.format_price(btc.get('resistance', 0))}

ETH: {self.format_price(eth.get('price', 0))}
  Trend: {eth.get('trend', 'N/A')} | RSI: {eth.get('rsi', 'N/A')}
  Support: {self.format_price(eth.get('support', 0))}
  Resistance: {self.format_price(eth.get('resistance', 0))}""")
        
        # Fear & Greed
        fg_value = fear_greed.get("value", 50)
        fg_label = fear_greed.get("label", "Neutral")
        fg_analysis = fear_greed.get("analysis", "")
        
        fg_bar = "█" * (fg_value // 10) + "░" * (10 - fg_value // 10)
        
        msg_parts.append(f"""
🎭 FEAR & GREED INDEX
[{fg_bar}] {fg_value}/100 - {fg_label}
{fg_analysis}""")
        
        # Overnight Movers
        gainers = movers.get("gainers", [])
        losers = movers.get("losers", [])
        
        if gainers or losers:
            msg_parts.append("\n📈 OVERNIGHT MOVERS")
            
            if gainers:
                gainer_str = " | ".join([f"{g['symbol']} +{g['change_24h']}%" for g in gainers[:3]])
                msg_parts.append(f"🟢 Gainers: {gainer_str}")
            
            if losers:
                loser_str = " | ".join([f"{l['symbol']} {l['change_24h']}%" for l in losers[:3]])
                msg_parts.append(f"🔴 Losers: {loser_str}")
        
        # Funding Rates
        funding_data = funding.get("data", [])
        if funding_data:
            funding_str = " | ".join([f"{f['symbol']}: {f['rate']}%" for f in funding_data])
            msg_parts.append(f"""
💰 FUNDING RATES
{funding_str}
{funding.get('summary', '')}""")
        
        # Setups to Watch
        if setups:
            msg_parts.append("\n🎯 SETUPS TO WATCH TODAY")
            for i, s in enumerate(setups[:5], 1):
                emoji = "🟢" if s['direction'] == "LONG" else "🔴" if s['direction'] == "SHORT" else "🟡"
                msg_parts.append(f"{emoji} {s['symbol']}: {s['setup']}")
                msg_parts.append(f"   {s['reason']}")
        
        # What to Watch
        msg_parts.append(f"""
━━━━━━━━━━━━━━━━━━━━━━
📌 KEY THINGS TO WATCH:
• BTC holding {self.format_price(btc.get('support', 0))} support is crucial
• Watch {fg_label.lower()} sentiment for reversal signs
• Funding rates suggest {funding.get('summary', 'neutral positioning').split('.')[0].lower()}

👁️ «The market whispers its secrets at dawn. Those who listen, prosper.»""")
        
        return "\n".join(msg_parts)
    
    async def send_briefing(self):
        """Send the morning briefing to all users"""
        if not self.send_message or not self.chat_ids:
            logger.warning("Morning briefing: No message sender or chat IDs configured")
            return
        
        try:
            briefing = await self.generate_briefing()
            
            # Send to all users
            for chat_id in list(self.chat_ids):
                try:
                    settings = await self.get_user_settings(chat_id)
                    # Only send to users with free_will enabled (alerts enabled)
                    if settings.get("free_will", True):
                        await self.send_message(chat_id, briefing)
                        await asyncio.sleep(0.5)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error sending briefing to {chat_id}: {e}")
            
            # Store in database
            if self.db is not None:
                try:
                    await self.db.morning_briefings.insert_one({
                        "content": briefing,
                        "sent_at": datetime.now(timezone.utc),
                        "recipients": len(self.chat_ids)
                    })
                except:
                    pass
            
            # Update last briefing date
            self.last_briefing_date = self._get_austin_time().date()
            logger.info(f"☀️ Morning briefing sent to {len(self.chat_ids)} users")
            
        except Exception as e:
            logger.error(f"Error generating/sending morning briefing: {e}")
    
    async def run_scheduler(self):
        """Main scheduler loop - checks every minute for briefing time"""
        logger.info("☀️ Morning Briefing Scheduler started (6 AM Central Time)")
        
        while self.is_active:
            try:
                if self._should_send_briefing():
                    await self.send_briefing()
                
                # Check every minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Morning briefing scheduler error: {e}")
                await asyncio.sleep(60)
    
    async def send_test_briefing(self):
        """Send a test briefing immediately (for testing)"""
        logger.info("Sending test morning briefing...")
        await self.send_briefing()
        return {"success": True, "message": "Test briefing sent"}


# Global instance
morning_briefing = MorningBriefing()
