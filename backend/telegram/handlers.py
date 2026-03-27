"""
Telegram command handlers - extracted from server.py
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Set

logger = logging.getLogger(__name__)


class TelegramHandlers:
    """Handles all Telegram bot commands and messages"""
    
    def __init__(
        self,
        db,
        market_intel,
        enhanced_intel,
        derivatives_intel,
        news_intel,
        mtf_analysis,
        futures_calc,
        autonomous_trader,
        learning_system,
        free_will,
        send_message_func,
        generate_response_func,
        chat_ids: Set[int]
    ):
        self.db = db
        self.market_intel = market_intel
        self.enhanced_intel = enhanced_intel
        self.derivatives_intel = derivatives_intel
        self.news_intel = news_intel
        self.mtf_analysis = mtf_analysis
        self.futures_calc = futures_calc
        self.autonomous_trader = autonomous_trader
        self.learning_system = learning_system
        self.free_will = free_will
        self.send_message = send_message_func
        self.generate_response = generate_response_func
        self.chat_ids = chat_ids
    
    async def get_user_settings(self, chat_id: int) -> Dict[str, Any]:
        """Get user settings from DB"""
        settings = await self.db.user_settings.find_one({"chat_id": chat_id})
        if not settings:
            default = {
                "chat_id": chat_id,
                "free_will": True,
                "bot_mode": "casual",
                "created_at": datetime.now(timezone.utc)
            }
            await self.db.user_settings.insert_one(default)
            return default
        return settings
    
    async def handle_command(self, chat_id: int, text: str) -> str:
        """Route command to appropriate handler"""
        text_lower = text.lower().strip()
        
        # Price command
        if text_lower == '/price':
            return await self._handle_price()
        
        # Scan command
        elif text_lower.startswith('/scan'):
            return await self._handle_scan(text_lower)
        
        # Technical analysis
        elif text_lower.startswith('/ta'):
            return await self._handle_ta(text_lower)
        
        # Market command
        elif text_lower == '/market':
            return await self._handle_market()
        
        # Fear & Greed
        elif text_lower == '/fear':
            return await self._handle_fear()
        
        # Top 100
        elif text_lower == '/top100':
            return await self._handle_top100()
        
        # Movers
        elif text_lower == '/movers':
            return await self._handle_movers()
        
        # Trending
        elif text_lower == '/trending':
            return await self._handle_trending()
        
        # Funding
        elif text_lower.startswith('/funding'):
            return await self._handle_funding(text_lower)
        
        # Positions/L-S
        elif text_lower.startswith('/positions'):
            return await self._handle_positions(text_lower)
        
        # Derivatives
        elif text_lower.startswith('/deriv') or text_lower.startswith('/oi'):
            return await self._handle_derivatives(text_lower)
        
        # News
        elif text_lower == '/news':
            return await self._handle_news()
        
        # Whales
        elif text_lower == '/whales':
            return await self._handle_whales()
        
        # On-chain
        elif text_lower == '/onchain':
            return await self._handle_onchain()
        
        # MTF analysis
        elif text_lower.startswith('/mtf'):
            return await self._handle_mtf(text_lower)
        
        # Sentiment
        elif text_lower.startswith('/sentiment'):
            return await self._handle_sentiment(text_lower)
        
        # Calculator
        elif text_lower.startswith('/calc'):
            return await self._handle_calc(text_lower)
        
        # Autonomous trading
        elif text_lower.startswith('/auto'):
            return await self._handle_auto(text_lower, chat_id)
        
        # Open positions
        elif text_lower == '/open':
            return await self._handle_open()
        
        # Opportunities
        elif text_lower == '/opps':
            return await self._handle_opportunities()
        
        # Strategy
        elif text_lower == '/strategy':
            return await self._handle_strategy()
        
        # Stats
        elif text_lower == '/stats':
            return await self._handle_stats()
        
        # Free Will
        elif text_lower.startswith('/freewill') or text_lower.startswith('/fw'):
            return await self._handle_freewill(text_lower, chat_id)
        
        # Help
        elif text_lower == '/help':
            return self._get_help_text()
        
        return None  # Not a recognized command
    
    async def _handle_price(self) -> str:
        """Handle /price command"""
        from concurrent.futures import ThreadPoolExecutor
        import ccxt
        
        executor = ThreadPoolExecutor(max_workers=3)
        mexc = ccxt.mexc()
        
        import asyncio
        loop = asyncio.get_running_loop()
        tickers = await loop.run_in_executor(
            executor, 
            mexc.fetch_tickers, 
            ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        )
        
        btc = tickers.get("BTC/USDT", {})
        eth = tickers.get("ETH/USDT", {})
        sol = tickers.get("SOL/USDT", {})
        
        return f"""📊 LIVE PRICES

BTC: ${btc.get('last', 0):,.2f} ({btc.get('percentage', 0):+.2f}%)
ETH: ${eth.get('last', 0):,.2f} ({eth.get('percentage', 0):+.2f}%)
SOL: ${sol.get('last', 0):,.2f} ({sol.get('percentage', 0):+.2f}%)

Updated: {datetime.now().strftime('%H:%M:%S')} UTC"""
    
    async def _handle_scan(self, text_lower: str) -> str:
        """Handle /scan command"""
        parts = text_lower.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"
        analysis = await self.market_intel.analyze_market(symbol + "/USDT")
        
        return f"""📈 {symbol} ANALYSIS

Price: ${analysis.get('price', 0):,.2f}
24h Change: {analysis.get('change_24h', 0):+.2f}%

Signal: {analysis.get('signal', 'NEUTRAL')}
Confidence: {analysis.get('confidence', 0)}%

Entry: ${analysis.get('entry', 0):,.2f}
Target: ${analysis.get('target', 0):,.2f}
Stop: ${analysis.get('stop', 0):,.2f}

{analysis.get('reasoning', '')}"""
    
    async def _handle_ta(self, text_lower: str) -> str:
        """Handle /ta command"""
        parts = text_lower.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"
        interval = parts[2] if len(parts) > 2 else "1h"
        
        ta = await self.market_intel.get_technical_analysis(f"{symbol}/USDT", interval)
        indicators = ta.get('indicators', {})
        
        return f"""📊 {symbol} TA ({interval})

RSI: {indicators.get('rsi', 'N/A')} {indicators.get('rsi_signal', '')}
MACD: {indicators.get('macd_histogram', 'N/A'):.4f} {indicators.get('macd_signal', '')}
BB Width: {indicators.get('bb_width', 'N/A'):.2%}
EMA Stack: {indicators.get('ema_stack', 'N/A')}
Stoch: {indicators.get('stoch_k', 'N/A'):.1f}/{indicators.get('stoch_d', 'N/A'):.1f}
ATR: ${indicators.get('atr', 0):,.2f}
Volume Spike: {'Yes' if indicators.get('volume_spike') else 'No'}

Overall: {ta.get('summary', 'NEUTRAL')}"""
    
    async def _handle_market(self) -> str:
        """Handle /market command"""
        summary = await self.enhanced_intel.get_market_summary()
        return f"""🌍 GLOBAL CRYPTO MARKET

Total Cap: {summary.get('market_cap', 'N/A')}
24h Volume: {summary.get('volume_24h', 'N/A')}
BTC Dominance: {summary.get('btc_dominance', 'N/A')}

Fear & Greed: {summary.get('fear_greed', {}).get('value', '?')} ({summary.get('fear_greed', {}).get('classification', '?')})

Top Movers:
{summary.get('top_movers_str', 'Loading...')}

Trending: {', '.join(summary.get('trending', ['Loading...'])[:5])}"""
    
    async def _handle_fear(self) -> str:
        """Handle /fear command"""
        fg = await self.enhanced_intel.get_fear_greed_index(7)
        current = fg.get('current', {})
        history = fg.get('history', [])
        
        response = f"""😱 FEAR & GREED INDEX

Current: {current.get('value', '?')} - {current.get('classification', '?')}

7-Day History:
"""
        for day in history[:7]:
            response += f"• {day.get('date', 'N/A')}: {day.get('value', '?')} ({day.get('classification', '?')})\n"
        
        return response
    
    async def _handle_top100(self) -> str:
        """Handle /top100 command"""
        coins = await self.enhanced_intel.get_top_100_coins()
        
        response = "🏆 TOP 10 BY MARKET CAP\n\n"
        for i, coin in enumerate(coins[:10], 1):
            response += f"{i}. {coin.get('symbol', '?')}: ${coin.get('price', 0):,.2f} ({coin.get('change_24h', 0):+.2f}%)\n"
        
        return response
    
    async def _handle_movers(self) -> str:
        """Handle /movers command"""
        movers = await self.enhanced_intel.get_top_movers()
        
        response = "📈 TOP GAINERS (24h)\n"
        for coin in movers.get('gainers', [])[:5]:
            response += f"• {coin.get('symbol', '?')}: {coin.get('change_24h', 0):+.2f}%\n"
        
        response += "\n📉 TOP LOSERS (24h)\n"
        for coin in movers.get('losers', [])[:5]:
            response += f"• {coin.get('symbol', '?')}: {coin.get('change_24h', 0):+.2f}%\n"
        
        return response
    
    async def _handle_trending(self) -> str:
        """Handle /trending command"""
        trending = await self.enhanced_intel.get_trending_coins()
        
        response = "🔥 TRENDING COINS\n\n"
        for i, coin in enumerate(trending[:10], 1):
            response += f"{i}. {coin.get('name', '?')} ({coin.get('symbol', '?')})\n"
        
        return response
    
    async def _handle_funding(self, text_lower: str) -> str:
        """Handle /funding command"""
        parts = text_lower.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"
        
        funding = await self.derivatives_intel.get_aggregated_funding(symbol + "USDT")
        
        response = f"""💰 {symbol} FUNDING RATES (REAL DATA)

Average: {funding.get('average_funding_pct', 'N/A')}
{funding.get('interpretation', '')}

By Exchange:
"""
        for ex in funding.get('exchanges', []):
            response += f"• {ex.get('exchange')}: {ex.get('funding_rate_pct', 'N/A')}\n"
        
        return response
    
    async def _handle_positions(self, text_lower: str) -> str:
        """Handle /positions command"""
        parts = text_lower.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"
        
        ls = await self.derivatives_intel.get_aggregated_long_short(symbol + "USDT")
        global_ls = ls.get('global', {})
        top_ls = ls.get('top_traders', {})
        
        return f"""📊 {symbol} LONG/SHORT (REAL - OKX)

Global: {global_ls.get('long_pct', '?')}% Long / {global_ls.get('short_pct', '?')}% Short
Top Traders: {top_ls.get('long_pct', '?')}% Long / {top_ls.get('short_pct', '?')}% Short

{ls.get('interpretation', '')}"""
    
    async def _handle_derivatives(self, text_lower: str) -> str:
        """Handle /deriv command"""
        parts = text_lower.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"
        
        report = await self.derivatives_intel.get_full_derivatives_report(symbol + "USDT")
        
        funding = report.get('funding', {})
        oi = report.get('open_interest', {})
        ls = report.get('long_short', {})
        
        response = f"""📊 {symbol} DERIVATIVES (ALL REAL DATA)

💰 FUNDING (Avg: {funding.get('average_funding_pct', 'N/A')})
{funding.get('interpretation', '')}
"""
        for ex in funding.get('exchanges', [])[:4]:
            response += f"• {ex.get('exchange')}: {ex.get('funding_rate_pct', 'N/A')}\n"
        
        response += f"""
📈 OPEN INTEREST
Total: {oi.get('total_open_interest_str', 'N/A')}
"""
        for ex in oi.get('exchanges', []):
            if ex.get('open_interest_value_str'):
                response += f"• {ex.get('exchange')}: {ex.get('open_interest_value_str')}\n"
        
        global_ls = ls.get('global', {})
        top_ls = ls.get('top_traders', {})
        
        response += f"""
📊 LONG/SHORT RATIO (REAL - OKX)
Global: {global_ls.get('long_pct', '?')}% L / {global_ls.get('short_pct', '?')}% S
Top Traders: {top_ls.get('long_pct', '?')}% L / {top_ls.get('short_pct', '?')}% S
{ls.get('interpretation', '')}

Data: OKX, Bitget, KuCoin, Gate"""
        
        return response
    
    async def _handle_news(self) -> str:
        """Handle /news command"""
        news = await self.news_intel.get_latest_news(8)
        sentiment = await self.news_intel.get_news_sentiment_summary()
        
        response = f"""📰 CRYPTO NEWS

Sentiment: {sentiment.get('overall_sentiment', 'NEUTRAL')}
Bullish: {sentiment.get('bullish_count', 0)} | Bearish: {sentiment.get('bearish_count', 0)}

Headlines:
"""
        for item in news[:6]:
            emoji = "🟢" if item.get('sentiment') == 'BULLISH' else "🔴" if item.get('sentiment') == 'BEARISH' else "⚪"
            response += f"{emoji} {item.get('title', 'No title')[:60]}...\n"
        
        return response
    
    async def _handle_whales(self) -> str:
        """Handle /whales command"""
        whales = await self.news_intel.get_whale_summary()
        
        response = f"""🐋 WHALE ACTIVITY

Activity Level: {whales.get('activity_level', 'N/A')}
Large Transactions (24h): {whales.get('large_tx_count', 0)}

Recent Moves:
"""
        for tx in whales.get('recent_transactions', [])[:5]:
            response += f"• {tx.get('amount_btc', 0):.2f} BTC ({tx.get('from_type', '?')} → {tx.get('to_type', '?')})\n"
        
        return response
    
    async def _handle_onchain(self) -> str:
        """Handle /onchain command"""
        onchain = await self.news_intel.get_btc_onchain_stats()
        
        return f"""⛓️ BTC ON-CHAIN DATA

Network Fee: {onchain.get('recommended_fee', 'N/A')} sat/vB
Mempool Size: {onchain.get('mempool_size', 'N/A')} MB
Pending TXs: {onchain.get('pending_txs', 'N/A')}

Fee Level: {onchain.get('fee_level', 'N/A')}
Network Demand: {onchain.get('demand_indicator', 'N/A')}

Source: mempool.space"""
    
    async def _handle_mtf(self, text_lower: str) -> str:
        """Handle /mtf command"""
        parts = text_lower.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"
        
        mtf = await self.mtf_analysis.get_multi_timeframe_analysis(symbol + "USDT")
        
        response = f"""📊 {symbol} MULTI-TIMEFRAME ANALYSIS

Overall: {mtf.get('overall_bias', 'NEUTRAL')}
Alignment: {mtf.get('alignment', 'MIXED')}
{mtf.get('confluence', '')}
Confidence: {mtf.get('confidence', 0)}%

"""
        for tf in ['1h', '4h', '1d']:
            tf_data = mtf.get('timeframes', {}).get(tf, {})
            response += f"{tf}: {tf_data.get('bias', 'N/A')} (RSI: {tf_data.get('rsi', 'N/A')})\n"
        
        return response
    
    async def _handle_sentiment(self, text_lower: str) -> str:
        """Handle /sentiment command"""
        parts = text_lower.split()
        symbol = parts[1].upper() if len(parts) > 1 else "BTC"
        
        sent = await self.enhanced_intel.get_coin_sentiment(symbol + "USDT")
        
        return f"""📊 {symbol} SENTIMENT

Overall: {sent.get('overall', 'NEUTRAL')}
Score: {sent.get('score', 0)}/100

Signals:
{chr(10).join(sent.get('signals', ['No signals']))}

Fear & Greed: {sent.get('fear_greed', {}).get('value', '?')} ({sent.get('fear_greed', {}).get('classification', '?')})
Funding: {sent.get('funding', {}).get('funding_rate_pct', 'N/A')}"""
    
    async def _handle_calc(self, text_lower: str) -> str:
        """Handle /calc commands"""
        parts = text_lower.split()
        
        if text_lower.startswith('/calcsize'):
            if len(parts) >= 6:
                balance = float(parts[1])
                risk_pct = float(parts[2])
                entry = float(parts[3])
                stop = float(parts[4])
                leverage = int(parts[5]) if len(parts) > 5 else 1
                
                result = self.futures_calc.calculate_position_size(balance, risk_pct, entry, stop, leverage)
                
                return f"""📐 POSITION SIZE CALCULATOR

Balance: ${balance:,.2f}
Risk: {risk_pct}%
Entry: ${entry:,.2f}
Stop: ${stop:,.2f}
Leverage: {leverage}x

Recommended Size: ${result.get('position_size', 0):,.2f}
Margin Required: ${result.get('margin_required', 0):,.2f}
Risk Amount: ${result.get('risk_amount', 0):,.2f}
Liquidation: ${result.get('liquidation_price', 0):,.2f}"""
            else:
                return "Usage: /calcsize [balance] [risk%] [entry] [stop] [leverage]\nExample: /calcsize 10000 2 65000 63000 10"
        
        elif text_lower.startswith('/calc'):
            if len(parts) >= 5:
                entry = float(parts[1])
                exit_price = float(parts[2])
                size = float(parts[3])
                leverage = int(parts[4])
                direction = parts[5].upper() if len(parts) > 5 else "LONG"
                
                result = self.futures_calc.calculate_pnl(entry, exit_price, size, leverage, direction)
                
                return f"""🧮 PNL CALCULATOR

{direction} Position
Entry: ${entry:,.2f}
Exit: ${exit_price:,.2f}
Size: ${size:,.2f}
Leverage: {leverage}x

PnL: ${result.get('pnl', 0):,.2f}
ROI: {result.get('roi', 0):+.2f}%
Margin: ${result.get('margin', 0):,.2f}
Liquidation: ${result.get('liquidation_price', 0):,.2f}"""
            else:
                return "Usage: /calc [entry] [exit] [size] [leverage] [direction]\nExample: /calc 65000 68000 1000 10 long"
        
        return "Calculator commands:\n/calc - PnL calculator\n/calcsize - Position size calculator"
    
    async def _handle_auto(self, text_lower: str, chat_id: int) -> str:
        """Handle /auto commands"""
        parts = text_lower.split()
        
        if len(parts) > 1:
            if parts[1] == "on":
                self.autonomous_trader.active = True
                return "🤖 Autonomous trading ACTIVATED. Aeon now scans markets and takes paper trades."
            elif parts[1] == "off":
                self.autonomous_trader.active = False
                return "🤖 Autonomous trading PAUSED. No new positions will be opened."
        
        summary = await self.autonomous_trader.get_trading_summary(self.market_intel)
        
        return f"""🤖 AUTONOMOUS TRADING

Status: {'ACTIVE' if self.autonomous_trader.active else 'PAUSED'}
Open Positions: {summary.get('open_positions', 0)}
Open PnL: {summary.get('open_pnl', 0):+.2f}%

📊 PERFORMANCE:
Total Trades: {summary.get('closed_stats', {}).get('total_predictions', 0)}
Win Rate: {summary.get('closed_stats', {}).get('win_rate', 0)}%
Total PnL: {summary.get('closed_stats', {}).get('total_pnl_pct', 0):+.2f}%
Best Trade: {summary.get('closed_stats', {}).get('best_trade', 'N/A')}

Commands: /auto on | /auto off"""
    
    async def _handle_open(self) -> str:
        """Handle /open command"""
        open_preds = await self.learning_system.get_open_predictions()
        
        if not open_preds:
            return "📭 No open positions"
        
        response = "📈 OPEN POSITIONS\n\n"
        for pred in open_preds:
            response += f"• {pred.get('symbol', '?')} {pred.get('prediction', '?')}\n"
            response += f"  Entry: ${pred.get('entry_price', 0):,.2f}\n"
            response += f"  Target: ${pred.get('target_price', 0):,.2f}\n"
            response += f"  Stop: ${pred.get('stop_price', 0):,.2f}\n\n"
        
        return response
    
    async def _handle_opportunities(self) -> str:
        """Handle /opps command"""
        opps = await self.autonomous_trader.scan_all_markets()
        
        if not opps:
            return "🔍 No high-confidence opportunities right now. Markets are choppy."
        
        response = "🎯 CURRENT OPPORTUNITIES\n\n"
        for opp in opps[:5]:
            response += f"• {opp.get('symbol', '?')} - {opp.get('signal', '?')}\n"
            response += f"  Confidence: {opp.get('confidence', 0)}%\n"
            response += f"  Entry: ${opp.get('entry', 0):,.2f}\n\n"
        
        return response
    
    async def _handle_strategy(self) -> str:
        """Handle /strategy command"""
        weights = self.autonomous_trader.strategy_weights
        
        response = "⚙️ STRATEGY WEIGHTS\n\n"
        for key, value in weights.items():
            response += f"• {key}: {value:.2f}\n"
        
        return response
    
    async def _handle_stats(self) -> str:
        """Handle /stats command"""
        stats = await self.learning_system.get_prediction_stats()
        
        return f"""📊 FULL TRADING STATS

Total Predictions: {stats.get('total_predictions', 0)}
Open: {stats.get('open_predictions', 0)}
Closed: {stats.get('closed_predictions', 0)}

Win Rate: {stats.get('win_rate', 0)}%
Wins: {stats.get('wins', 0)}
Losses: {stats.get('losses', 0)}

Total PnL: {stats.get('total_pnl_pct', 0):+.2f}%
Avg Win: {stats.get('avg_win_pct', 0):+.2f}%
Avg Loss: {stats.get('avg_loss_pct', 0):.2f}%

Best Trade: {stats.get('best_trade', 'N/A')}
Worst Trade: {stats.get('worst_trade', 'N/A')}"""
    
    async def _handle_freewill(self, text_lower: str, chat_id: int) -> str:
        """Handle /freewill commands"""
        parts = text_lower.split()
        
        if text_lower.startswith('/fwconf'):
            if len(parts) > 1:
                try:
                    new_conf = int(parts[1])
                    self.free_will.min_confidence = max(50, min(95, new_conf))
                    return f"✅ Free Will confidence set to {self.free_will.min_confidence}%"
                except:
                    return "Usage: /fwconf [50-95]\nExample: /fwconf 70"
        
        stats = await self.free_will.get_stats()
        
        return f"""🔮 FREE WILL ENGINE

Status: {'ACTIVE' if stats.get('active') else 'PAUSED'}
Min Confidence: {stats.get('min_confidence', 65)}%
Alerts Sent: {stats.get('total_alerts_sent', 0)}

Monitoring:
• Pairs: {stats.get('pairs_monitored', 44)}
• Timeframes: {stats.get('timeframes_monitored', 9)}

Feedback: {stats.get('feedback_received', 0)} total
Win Rate: {stats.get('win_rate', 0)}%

Commands:
• /fwconf [num] - Set min confidence (50-95)
• free on/off - Toggle alerts"""
    
    def _get_help_text(self) -> str:
        """Return help text"""
        return """🤖 AEON COMMANDS

📊 MARKET DATA:
/price - Live BTC, ETH, SOL prices
/scan [coin] - Full analysis with entry/exit
/ta [coin] [tf] - Technical indicators
/market - Global market summary
/fear - Fear & Greed Index
/top100 - Top coins by market cap
/movers - Top gainers/losers
/trending - Trending coins

💰 DERIVATIVES (REAL DATA):
/funding [coin] - Aggregated funding rates
/positions [coin] - Long/short ratio
/deriv [coin] - Full derivatives report

📰 INTELLIGENCE:
/news - Latest crypto news
/whales - Whale activity
/onchain - BTC on-chain data
/mtf [coin] - Multi-timeframe analysis
/sentiment [coin] - Sentiment analysis

🧮 CALCULATORS:
/calc [entry] [exit] [size] [lev] [dir]
/calcsize [bal] [risk%] [entry] [stop] [lev]

🤖 AUTONOMOUS TRADING:
/auto - Trading status
/auto on|off - Toggle trading
/open - Open positions
/opps - Current opportunities
/strategy - Strategy weights
/stats - Full performance

🔮 FREE WILL:
/freewill or /fw - Engine status
/fwconf [num] - Set confidence (50-95)
free on|off - Toggle alerts

💬 CHAT:
Just message me normally for conversation!
Say "alchemy mode" for mystical responses"""
