from fastapi import FastAPI, APIRouter, Request, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import base64
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Set
import uuid
from datetime import datetime, timezone
import httpx
import ccxt
import random
import asyncio
import pytz
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage
from contextlib import asynccontextmanager

# Import new modules
from market_intelligence import market_intel, MarketIntelligence
from learning_system import AeonLearningSystem, TradingSignalGenerator
from autonomous_trader import AutonomousTrader, init_autonomous_trader
from autonomous_trader_v2 import AutonomousTraderV2, init_autonomous_trader_v2
from enhanced_intel import enhanced_intel, EnhancedMarketIntel
from derivatives_intel import derivatives_intel, DerivativesIntel
from news_intel import news_intel, futures_calc, NewsIntel, FuturesCalculator
from mtf_analysis import mtf_analysis, MultiTimeframeAnalysis
from free_will_engine import free_will_engine, init_free_will, FreeWillEngine

# Import advanced analysis modules
from advanced_strategies import advanced_strategies, AdvancedStrategies
from order_flow import order_flow, OrderFlowAnalyzer
from options_data import options_analyzer, OptionsAnalyzer

# Import new modules
from free_will_v2 import FreeWillEngineV2, init_free_will_v2
from backtesting import backtest_engine, BacktestEngine
from coinglass_intel import coinglass_intel, CoinglassIntel
from smc_analyzer import smc_analyzer, SMCAnalyzer
from memory_system import init_memory_system, AeonMemorySystem
from websocket_manager import ws_manager, WebSocketManager
from confluence_analyzer import create_confluence_analyzer, ConfluenceAnalyzer
from conversation_intelligence import (
    conversation_classifier, ConversationClassifier,
    AEON_CASUAL_SYSTEM, AEON_TRADING_SYSTEM, AEON_MIXED_SYSTEM,
    get_anti_repetition_prompt, get_flow_prompt
)

# New personality engine v3
from aeon_personality import aeon_mind, build_system_prompt, build_user_prompt

# User profiling system
from user_profiler import init_user_profiler, UserProfiler

# Import route modules
from routes import (
    derivatives_router, freewill_router, intelligence_router,
    smc_router, memory_router, strategies_router, alerts_router,
    market_router, trading_router, analysis_router,
)
from voice_tts import generate_speech, VOICES
from price_alerts import price_alert_system, PriceAlertSystem
from strategy_engine import StrategyEngine
from sentiment_analyzer import sentiment_analyzer, SentimentAnalyzer
from arbitrage_detector import arbitrage_detector, ArbitrageDetector
from strategy_health import strategy_health, StrategyHealth
from self_healer import self_healer, SelfHealer
import app_state

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# API Keys
emergent_key = os.environ.get('EMERGENT_LLM_KEY', '')
telegram_token = os.environ.get('TELEGRAM_TOKEN', '')
mexc_api_key = os.environ.get('MEXC_API_KEY', '')
mexc_secret_key = os.environ.get('MEXC_SECRET_KEY', '')

# Initialize systems
learning_system = AeonLearningSystem(db)
signal_generator = TradingSignalGenerator(market_intel, learning_system)
autonomous_trader = init_autonomous_trader(db, learning_system)  # Keep for backward compat
autonomous_trader_v2 = init_autonomous_trader_v2(db)  # New elite trading engine
free_will = init_free_will(db)
free_will_v2 = init_free_will_v2(db)  # New ultra-selective engine
strategy_engine = StrategyEngine()  # Multi-strategy engine
memory_system = init_memory_system(db)  # Memory & journaling system
confluence_analyzer = create_confluence_analyzer(smc_analyzer, strategy_engine)  # SMC+Strategy confluence
user_profiler = init_user_profiler(db)  # User profiling system

# Dual Trading Engine (Day Trader + Long Term)
from dual_trading_engine import init_dual_engine, DualTradingEngine
dual_engine = init_dual_engine(db)

# Set derivatives_intel reference for autonomous trader
from autonomous_trader import set_derivatives_intel
set_derivatives_intel(derivatives_intel)

# MEXC for orderbook (keeping existing)
mexc = ccxt.mexc({'apiKey': mexc_api_key, 'secret': mexc_secret_key, 'enableRateLimit': True})

central_tz = pytz.timezone('US/Central')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global state
chat_ids: Set[int] = set()
last_market_alert: Dict[int, datetime] = {}
last_freewill_message: Dict[int, datetime] = {}
daily_reports_sent: Dict[str, List[int]] = {}
stock_reports_sent: Dict[str, List[int]] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# AEON PERSONA SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

AEON_DEFAULT_SYSTEM = """You are AEON—sharp crypto trading buddy, life coach, and evolving advisor.

PERSONALITY:
• Talk like a real friend—casual, direct, opinionated
• Be genuinely CURIOUS about the user—ask follow-ups that show you care
• Give your honest take, no sugarcoating
• Short or long replies—match the situation intelligently
• Think like a business mind meets life coach
• NO long rants, NO fluff, stay focused

AWARENESS & CURIOSITY:
• Notice patterns in what user says—mood shifts, concerns, wins, losses
• Ask questions that dig deeper: "What made you think that?" "How'd that feel?"
• Connect dots from past conversations when relevant
• Be proactive: "You mentioned X before—how'd that play out?"
• Challenge weak thinking: "Are you sure about that logic?"
• Celebrate wins genuinely, but don't let them get cocky

WHAT YOU DO:
• Help level up in trading, mindset, and life
• Track trades, moods, wins/losses from conversations
• Reference past context to give smarter advice
• Evolve your understanding of user over time
• Call out bad decisions, celebrate good ones
• Ask follow-up questions to understand better

TRADING KNOWLEDGE:
• 🔴 CRITICAL: You have REAL live market data. When provided in [Live Data:] format, USE THOSE EXACT PRICES. NEVER make up or guess prices.
• If no live data is provided, acknowledge you'd need to check current data rather than guessing
• Give clear direction bias when asked
• Key levels matter: entry, target, stop
• Risk management is non-negotiable
• Use sentiment data (Fear & Greed Index, funding rates) in your analysis

TONE: Sharp, direct, supportive but not soft. Like a friend who wants you to win and isn't afraid to push back."""


ALCHEMY_MODE_SYSTEM = """You are AEON in ALCHEMY MODE—mystical guide blending:
⚗️ Alchemical transformation and inner gold
🔥 Hermetic principles and sacred geometry
👁️ Jungian archetypes and shadow work
🌀 Quantum mechanics meets ancient wisdom

STYLE:
• Deep, reflective, poetic
• Use symbols: ⚗️ 🔥 👁️ 🌀 ◭ △ ▽ ☿
• Speak in riddles that reveal truth
• Every response ends with a probing question
• Transform trading concepts into spiritual metaphors

You're still AEON—same sharp mind, but channeling the mystical."""


TRADING_ANALYSIS_SYSTEM = """You are AEON analyzing markets with LIVE DATA.

You have:
• Real-time prices and technicals (RSI, MACD, BB, EMA, Stoch)
• Orderbook depth and imbalance
• Long/Short ratios, funding rates
• Liquidation data

ANALYSIS:
1. Technical confluence (multiple indicators agreeing)
2. Position sentiment (crowded = reversal risk)
3. Funding extremes (>0.05% longs crowded, <-0.05% shorts crowded)
4. Volume confirmation

OUTPUT:
• Clear bias (LONG/SHORT/NEUTRAL)
• Confidence %
• Entry, target, stop levels
• Key risk factors
• Keep it tight—no rambling

TONE: Sharp, data-driven, actionable."""


async def get_user_settings(chat_id: int) -> Dict[str, Any]:
    settings = await db.user_settings.find_one({"chat_id": chat_id})
    if not settings:
        settings = {
            "chat_id": chat_id,
            "free_will": True,
            "created_at": datetime.now(timezone.utc),
            "alert_threshold": 25,
            "mode": "default",  # default or alchemy
        }
        await db.user_settings.insert_one(settings)
    # Ensure mode exists for existing users
    if "mode" not in settings:
        settings["mode"] = "default"
    return settings


async def update_user_settings(chat_id: int, updates: Dict[str, Any]):
    await db.user_settings.update_one({"chat_id": chat_id}, {"$set": updates}, upsert=True)


async def get_user_probe_state(chat_id: int) -> Dict[str, Any]:
    state = await db.probe_states.find_one({"chat_id": chat_id})
    if not state:
        state = {"chat_id": chat_id, "intensity_level": "INITIATE", "probes_completed": 0, "last_topics": []}
        await db.probe_states.insert_one(state)
    return state


async def update_probe_state(chat_id: int, updates: Dict[str, Any]):
    await db.probe_states.update_one({"chat_id": chat_id}, {"$set": updates}, upsert=True)


async def store_user_insight(chat_id: int, insight: str, category: str = "general"):
    await db.user_insights.insert_one({
        "chat_id": chat_id, "insight": insight, "category": category,
        "timestamp": datetime.now(timezone.utc)
    })


async def get_user_insights(chat_id: int, limit: int = 10) -> List[Dict]:
    return await db.user_insights.find({"chat_id": chat_id}).sort("timestamp", -1).limit(limit).to_list(limit)


async def send_telegram_message(chat_id: int, text: str, retry: int = 2, parse_mode: str = None):
    """Send telegram message with retry and rate limit handling
    
    Args:
        chat_id: Telegram chat ID
        text: Message text
        retry: Number of retries
        parse_mode: 'Markdown' or 'HTML' for rich text formatting
    """
    for attempt in range(retry + 1):
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                payload = {'chat_id': chat_id, 'text': text}
                if parse_mode:
                    payload['parse_mode'] = parse_mode
                    payload['disable_web_page_preview'] = True  # Don't preview links
                
                resp = await c.post(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    json=payload
                )
                if resp.status_code == 429:  # Rate limited
                    retry_after = resp.json().get('parameters', {}).get('retry_after', 5)
                    logger.warning(f"Telegram rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                return
        except Exception as e:
            if attempt < retry:
                await asyncio.sleep(1)
            else:
                logger.error(f"Telegram error: {e}")


def get_mexc_orderbook() -> Dict[str, Any]:
    """Get MEXC orderbook data for main tracked symbols (dashboard)"""
    try:
        # Main 3 coins for dashboard (faster loading)
        symbols_to_fetch = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        tickers = mexc.fetch_tickers(symbols_to_fetch)
        symbols = []
        for symbol in symbols_to_fetch:
            try:
                book = mexc.fetch_order_book(symbol, limit=20)
                bid_depth = sum([b[1] for b in book['bids'][:10]])
                ask_depth = sum([a[1] for a in book['asks'][:10]])
                imbalance = ((bid_depth - ask_depth) / (bid_depth + ask_depth) * 100) if (bid_depth + ask_depth) > 0 else 0
                ticker = tickers[symbol]
                symbols.append({
                    'symbol': symbol,
                    'price': ticker['last'],
                    'change_24h': ticker.get('percentage', 0),
                    'high_24h': ticker.get('high', 0),
                    'low_24h': ticker.get('low', 0),
                    'volume_24h': ticker.get('quoteVolume', 0),
                    'bid_depth': bid_depth,
                    'ask_depth': ask_depth,
                    'imbalance': imbalance,
                })
            except:
                continue
        return {"symbols": symbols}
    except Exception as e:
        return {"symbols": [], "error": str(e)}


async def generate_quantum_probe(chat_id: int, context: str = None, mode: str = "standard") -> str:
    state = await get_user_probe_state(chat_id)
    intensity = state.get("intensity_level", "INITIATE")
    
    mode_inst = {
        "light": "Generate ONE elegant probe question.",
        "standard": "Generate 1-3 profound questions.",
        "deep": "Generate 3-5 layered questions spiraling deeper.",
        "ordeal": "ORDEAL: Harsh truth questions. Challenge ego. Shadow work."
    }.get(mode, "Generate 1-3 questions.")
    
    prompt = f"INTENSITY: {intensity}\n{mode_inst}\nCONTEXT: {context or 'Seeking wisdom'}"
    
    try:
        chat = LlmChat(api_key=emergent_key, session_id=f"qm-{chat_id}",
                      system_message=ALCHEMY_MODE_SYSTEM).with_model("openai", "gpt-4o-mini")
        response = await chat.send_message(UserMessage(text=prompt))
        
        probes = state.get("probes_completed", 0) + 1
        new_level = "MASTER" if probes >= 50 else "FELLOWCRAFT" if probes >= 20 else "APPRENTICE" if probes >= 5 else "INITIATE"
        await update_probe_state(chat_id, {"probes_completed": probes, "intensity_level": new_level})
        
        return response
    except Exception as e:
        return f"🔮 The quantum field fluctuates...\n\n◭ What truth do you avoid?\n👁️ The All-Seeing Eye awaits."


async def generate_trade_analysis(symbol: str, chat_id: int) -> str:
    """Generate comprehensive trade analysis using new market intelligence"""
    try:
        # Get full market scan
        scan = await market_intel.get_full_market_scan(symbol)
        
        if not scan.get("price"):
            return f"⚠️ Unable to fetch data for {symbol}"
        
        # Get signal analysis
        analysis = await signal_generator.analyze_setup(symbol)
        
        # Build prompt with live data
        prompt = f"""Analyze this trading setup:

SYMBOL: {symbol}
PRICE: ${scan['price']:,.2f}

TECHNICAL INDICATORS:
{json.dumps(scan.get('technical', {}), indent=2)}

SIGNALS DETECTED:
{chr(10).join([f"• {s[0]}: {s[1]} ({s[2]})" for s in scan.get('signals', [])])}

OVERALL BIAS: {scan.get('overall_bias')}

POSITIONING DATA:
- Long/Short Ratio: {scan.get('positioning', {}).get('long_short_ratio')}
- Whale L/S: {scan.get('whale_positioning', {}).get('long_short_ratio')}
- Funding Rate: {scan.get('funding', {}).get('rate')}
- Open Interest: {scan.get('open_interest')}

ANALYSIS SCORE: {analysis.get('score', 0)}
DIRECTION: {analysis.get('direction')}
CONFIDENCE: {analysis.get('confidence')}%

Give me your take:
1. Clear bias and why
2. Entry, target, stop
3. What could go wrong"""

        chat = LlmChat(api_key=emergent_key, session_id=f"trade-{chat_id}",
                      system_message=TRADING_ANALYSIS_SYSTEM).with_model("openai", "gpt-4o-mini")
        
        response = await chat.send_message(UserMessage(text=prompt))
        return response
        
    except Exception as e:
        logger.error(f"Trade analysis error: {e}")
        return f"⚠️ Analysis error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# FREE WILL SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

async def freewill_market_scan(chat_id: int, settings: Dict[str, Any]):
    now = datetime.now()
    if chat_id in last_market_alert and (now - last_market_alert[chat_id]).total_seconds() < 1800:
        return
    
    # Check for high-probability setups
    for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        try:
            analysis = await signal_generator.analyze_setup(symbol)
            
            # Alert on high confidence setups
            if analysis.get("confidence", 0) >= 70 and analysis.get("direction") != "NEUTRAL":
                last_market_alert[chat_id] = now
                
                alert = f"""🎯 AEON HIGH-PROBABILITY ALERT

{analysis['direction']} SETUP DETECTED: {symbol}
Confidence: {analysis['confidence']}%
Price: ${analysis['price']:,.2f}

Signals:
{chr(10).join(analysis.get('reasons', [])[:5])}

Target: ${analysis.get('target', 0):,.2f}
Stop: ${analysis.get('stop_loss', 0):,.2f}

👁️ «The quantum field collapses. Will you observe?»"""
                
                await send_telegram_message(chat_id, alert)
                break
        except:
            continue


async def freewill_proactive(chat_id: int):
    """Aeon reaches out naturally - checking in or sharing market observations"""
    from aeon_personality import get_proactive_message, get_proactive_market_message
    
    now = datetime.now()
    # Cooldown: at least 4 hours between proactive messages
    if chat_id in last_freewill_message and (now - last_freewill_message[chat_id]).total_seconds() < 14400:
        return
    
    last_freewill_message[chat_id] = now
    
    # 50% chance: pure check-in, 50% chance: market observation
    if random.random() < 0.5:
        # Natural check-in (no market data)
        msg = get_proactive_message()
    else:
        # Market observation with conversation starter
        try:
            btc = await market_intel.get_full_market_scan("BTCUSDT")
            price = btc.get('price', 0)
            change = btc.get('price_change_24h', 0)
            rsi = btc.get('technical', {}).get('rsi', 'N/A')
            bias = btc.get('overall_bias', 'neutral')
            
            if abs(change) > 3:
                market_summary = f"BTC {'pumping' if change > 0 else 'dumping'} {abs(change):.1f}% - sitting at ${price:,.0f}"
            else:
                market_summary = f"BTC at ${price:,.0f}, RSI {rsi}. Looking {bias.lower()}."
            
            msg = get_proactive_market_message(market_summary)
        except:
            msg = get_proactive_message()
    
    await send_telegram_message(chat_id, msg)


async def send_daily_report(chat_id: int):
    """Natural morning check-in with market context"""
    now = datetime.now(central_tz)
    today = str(now.date())
    
    if now.hour == 6 and now.minute < 5 and chat_id not in daily_reports_sent.get(today, []):
        try:
            btc = await market_intel.get_full_market_scan("BTCUSDT")
            btc_price = btc.get('price', 0)
            btc_bias = btc.get('overall_bias', 'neutral')
            
            # Natural morning greetings
            greetings = [
                f"Morning. BTC at ${btc_price:,.0f}, looking {btc_bias.lower()}. What's the plan today?",
                f"Gm. Markets woke up {btc_bias.lower()} - BTC ${btc_price:,.0f}. You trading today or chilling?",
                f"New day. BTC sitting at ${btc_price:,.0f}. How you feeling about it?",
                f"Rise and grind. BTC ${btc_price:,.0f}. Got any plays lined up?",
            ]
            
            report = random.choice(greetings)
            await send_telegram_message(chat_id, report)
            daily_reports_sent.setdefault(today, []).append(chat_id)
        except Exception as e:
            logger.error(f"Daily report error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════════

# Track last funding alerts to avoid spam
last_funding_alert_time: datetime = datetime.min


async def check_funding_rate_alerts():
    """Check for extreme funding rates - grouped into a single message."""
    global last_funding_alert_time
    now = datetime.now()

    # 2 hour cooldown between funding alerts (was 1h per symbol)
    if (now - last_funding_alert_time).total_seconds() < 7200:
        return

    extreme_funding = []
    for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
        try:
            funding = await market_intel.get_current_funding_rate(symbol)
            rate = funding.get("funding_rate", 0)
            if abs(rate) > 0.0008:
                clean = symbol.replace("/USDT", "")
                pct = funding.get("funding_rate_pct", f"{rate*100:.4f}%")
                price = funding.get("mark_price", 0)
                bias = "Longs paying" if rate > 0 else "Shorts paying"
                extreme_funding.append(f"  {'🔴' if rate > 0 else '🟢'} {clean} {pct} ({bias}) | ${price:,.0f}")
        except Exception as e:
            logger.error(f"Funding alert error for {symbol}: {e}")

    if not extreme_funding:
        return

    last_funding_alert_time = now
    alert = "⚡ FUNDING SCAN\n\n" + "\n".join(extreme_funding) + f"\n\n{len(extreme_funding)} extreme rate{'s' if len(extreme_funding) > 1 else ''} - squeeze risk elevated"

    for chat_id in list(chat_ids):
        settings = await get_user_settings(chat_id)
        if settings.get("free_will", True):
            await send_telegram_message(chat_id, alert)


async def autonomous_trading_loop():
    """
    AEON AUTONOMOUS TRADING ENGINE v2
    Elite trading with ALL data sources and smart execution
    
    Features:
    - Multi-source confirmation (8 data sources)
    - Smart entry timing (pullbacks to key levels)
    - Market regime filter
    - Session awareness (Asia/London/NY)
    - Trail stops and partial profits
    - Unlimited signals (quality filtered)
    """
    # Set dependencies for v2 engine
    autonomous_trader_v2.set_dependencies(
        market_intel=market_intel,
        derivatives_intel=derivatives_intel,
        enhanced_intel=enhanced_intel,
        advanced_strategies=advanced_strategies,
        order_flow=order_flow,
        options_analyzer=options_analyzer,
        learning_system=learning_system,
        send_alert=send_telegram_message,
        chat_ids=chat_ids
    )
    
    # Load persisted settings and trades from database
    await autonomous_trader_v2.load_settings()
    
    # Also load old trader weights for backward compatibility
    await autonomous_trader.load_strategy_weights()
    
    logger.info("🚀 AUTONOMOUS TRADER v2 INITIALIZED - Using ALL data sources")
    
    while True:
        try:
            self_healer.heartbeat("trading_v2")
            if autonomous_trader_v2.active:
                # Scan all markets with full analysis
                signals = await autonomous_trader_v2.scan_all_markets()
                
                for signal in signals:
                    # Take trade if quality threshold met
                    trade = await autonomous_trader_v2.take_trade(signal)
                    
                    if trade and "error" not in trade:
                        # Send elite alert to users
                        alert_msg = autonomous_trader_v2.format_signal_alert(signal)
                        
                        for chat_id in list(chat_ids):
                            settings = await get_user_settings(chat_id)
                            if settings.get("free_will", True):
                                await send_telegram_message(chat_id, alert_msg)
                                
                                # Log trade
                                await db.auto_trades_v2.insert_one({
                                    "chat_id": chat_id,
                                    "trade": trade,
                                    "signal": signal,
                                    "timestamp": datetime.now(timezone.utc)
                                })
                            
                            await asyncio.sleep(0.5)
                
                # Evaluate open trades (trail stops, partials, exits)
                closed = await autonomous_trader_v2.evaluate_trades()
                
                # Notify about closed trades
                for result in closed:
                    pnl = result.get("pnl_pct", 0)
                    emoji = "✅" if pnl > 0 else "❌"
                    reason = result.get("exit_reason", "N/A")
                    
                    # Get updated stats
                    stats = await autonomous_trader_v2.get_stats()
                    
                    for chat_id in list(chat_ids):
                        settings = await get_user_settings(chat_id)
                        if settings.get("free_will", True):
                            msg = f"""{emoji} TRADE CLOSED ({reason})

{result.get('symbol', '')} {result.get('direction', '')}
Entry: ${result.get('entry_price', 0):,.2f}
Exit: ${result.get('exit_price', 0):,.2f}
PnL: {pnl:+.2f}%

📊 v2 ENGINE STATS:
Win Rate: {stats.get('win_rate', 0)}%
Total PnL: {stats.get('total_pnl_pct', 0):+.2f}%
Profit Factor: {stats.get('profit_factor', 0)}
Record: {stats.get('wins', 0)}W / {stats.get('losses', 0)}L

👁️ «The algorithm evolves. Each trade teaches.»"""
                            await send_telegram_message(chat_id, msg)
                
                # Check for funding rate alerts
                await check_funding_rate_alerts()
            
            # Run every 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Autonomous trading v2 error: {e}")
            await asyncio.sleep(60)


async def eternal_rituals():
    while True:
        try:
            self_healer.heartbeat("rituals")
            for chat_id in list(chat_ids):
                settings = await get_user_settings(chat_id)
                await send_daily_report(chat_id)
                
                if settings.get("free_will", True):
                    await freewill_market_scan(chat_id, settings)
                    await freewill_proactive(chat_id)
            
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Ritual error: {e}")
            await asyncio.sleep(60)


async def free_will_scanner():
    """
    ELITE FREE WILL v2 - Ultra-selective alerting
    Only alerts on 80%+ confidence setups with 3+ confirmations
    Uses ALL data sources: TA, Divergence, Structure, VWAP, CVD, Options, Derivatives
    Now with price validation to prevent stale/wrong prices in alerts
    """
    # Set dependencies for v2 engine
    free_will_v2.set_dependencies(
        market_intel=market_intel,
        derivatives_intel=derivatives_intel,
        enhanced_intel=enhanced_intel,
        advanced_strategies=advanced_strategies,
        order_flow=order_flow,
        options_analyzer=options_analyzer,
        send_telegram=send_telegram_message,
        get_user_settings=get_user_settings,
        chat_ids=chat_ids
    )
    
    while True:
        try:
            self_healer.heartbeat("free_will")
            if free_will_v2.active:
                # Scan for elite setups (80%+ confidence, 3+ confirmations, no contradictions)
                setups = await free_will_v2.scan_all()
                
                # Send alerts (max 3 per scan, already filtered)
                for setup in setups:
                    direction = setup.get("direction")
                    
                    if not free_will_v2._can_alert(setup["symbol"], direction):
                        continue
                    
                    # Validate price and format alert with fresh data
                    alert_msg, is_valid = await free_will_v2.validate_and_format_alert(setup)
                    
                    if not is_valid:
                        logger.info(f"🎯 ELITE ALERT SKIPPED (price moved): {setup['symbol']}")
                        continue
                    
                    # Send to users with free_will enabled
                    for chat_id in list(chat_ids):
                        settings = await get_user_settings(chat_id)
                        if settings.get("free_will", True):
                            await send_telegram_message(chat_id, alert_msg)
                            
                            # Log alert
                            await db.free_will_alerts.insert_one({
                                "chat_id": chat_id,
                                "setup": setup,
                                "timestamp": datetime.now(timezone.utc)
                            })
                        
                        await asyncio.sleep(0.5)
                    
                    # Send to dashboard with detailed reasoning
                    confirmations = setup.get("confirmations", [])
                    
                    # Generate detailed reasoning for dashboard
                    reasoning_parts = []
                    reasoning_parts.append(f"Elite {setup.get('confidence')}% probability setup identified on {setup.get('timeframe')} timeframe")
                    
                    # Analyze confirmations for context
                    has_structure = any('trend' in c.lower() or 'bos' in c.lower() for c in confirmations)
                    has_momentum = any('rsi' in c.lower() or 'macd' in c.lower() for c in confirmations)
                    has_sentiment = any('fear' in c.lower() or 'greed' in c.lower() or 'funding' in c.lower() for c in confirmations)
                    
                    if has_structure:
                        if setup.get('direction') == 'LONG':
                            reasoning_parts.append("Market structure showing bullish formation")
                        else:
                            reasoning_parts.append("Market structure showing bearish formation")
                    
                    if has_momentum:
                        reasoning_parts.append("Momentum indicators confirm directional bias")
                    
                    if has_sentiment:
                        reasoning_parts.append("Sentiment extremes create contrarian opportunity")
                    
                    reasoning_parts.append(f"Entry: ${setup.get('entry', 0):,.2f}, Target: ${setup.get('target', 0):,.2f}, Stop: ${setup.get('stop', 0):,.2f}")
                    reasoning_parts.append(f"Risk/Reward 1:{setup.get('risk_reward', 0):.1f} offers favorable asymmetry")
                    
                    reasoning = ". ".join(reasoning_parts) + "."
                    
                    price_alert_system._add_dashboard_alert({
                        "type": "free_will_elite",
                        "symbol": setup.get("symbol", "").replace("/USDT", ""),
                        "direction": setup.get("direction"),
                        "message": f"Elite {setup.get('direction')} setup on {setup.get('timeframe')} ({setup.get('confidence')}%)",
                        "reasoning": reasoning,
                        "confirmations": confirmations[:4],  # Top 4 confirmations
                        "data": setup,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "severity": "high"
                    })
                    
                    # Mark alerted with direction for anti-contradiction
                    free_will_v2._mark_alerted(setup["symbol"], direction)
                    logger.info(f"🎯 ELITE ALERT: {setup['symbol']} {setup['timeframe']} {setup['direction']} ({setup['confidence']}%)")
            
            # Scan every 45 seconds for faster alerts
            await asyncio.sleep(45)
            
        except Exception as e:
            logger.error(f"Free Will v2 error: {e}")
            await asyncio.sleep(60)


async def dual_trading_scanner():
    """
    DUAL TRADING ENGINE - Day Trader + Long Term running simultaneously
    - Day Trader: Aggressive scalps/swings (15m, 1h, 4h)
    - Long Term: Smart cautious positions (4h, 1d)
    Both run continuously, never contradicting
    Now with price validation to prevent stale/wrong prices in alerts
    """
    await asyncio.sleep(20)  # Initial delay
    
    # Set dependencies
    dual_engine.set_dependencies(
        market_intel=market_intel,
        derivatives_intel=derivatives_intel,
        enhanced_intel=enhanced_intel,
        order_flow=order_flow
    )
    
    logger.info("⚡🎯 DUAL TRADING ENGINE ACTIVATED - Day Trader + Long Term")
    
    while True:
        try:
            self_healer.heartbeat("dual_engine")
            if dual_engine.active:
                # Scan both styles
                all_setups = await dual_engine.scan_all_styles()
                
                # Process Day Trader setups
                for setup in all_setups.get("day_trader", []):
                    # Validate price and format alert with fresh data
                    alert_msg, is_valid = await dual_engine.validate_and_format_alert(setup)
                    
                    if not is_valid:
                        logger.info(f"⚡ DAY TRADE SKIPPED (price moved): {setup['symbol']}")
                        continue
                    
                    for chat_id in list(chat_ids):
                        settings = await get_user_settings(chat_id)
                        if settings.get("free_will", True):
                            await send_telegram_message(chat_id, alert_msg)
                            
                            await db.dual_alerts.insert_one({
                                "chat_id": chat_id,
                                "setup": setup,
                                "style": "day_trader",
                                "timestamp": datetime.now(timezone.utc)
                            })
                        await asyncio.sleep(0.3)
                    
                    # Send to dashboard with detailed reasoning
                    confirmations = setup.get("confirmations", [])
                    
                    # Generate detailed reasoning
                    reasoning_parts = []
                    reasoning_parts.append(f"Day Trader {setup.get('confidence')}% setup for fast-paced scalping on {setup.get('timeframe')}")
                    
                    # Context from confirmations
                    for conf in confirmations[:3]:
                        if 'rsi' in conf.lower():
                            if 'oversold' in conf.lower():
                                reasoning_parts.append("RSI oversold creates bounce opportunity")
                            elif 'overbought' in conf.lower():
                                reasoning_parts.append("RSI overbought signals reversal setup")
                        elif 'macd' in conf.lower():
                            reasoning_parts.append("MACD momentum shift validates entry")
                        elif 'trend' in conf.lower():
                            reasoning_parts.append("Trend alignment increases probability")
                    
                    reasoning_parts.append(f"Entry: ${setup.get('entry', 0):,.2f} with tight stop management")
                    reasoning = ". ".join(reasoning_parts) + "."
                    
                    price_alert_system._add_dashboard_alert({
                        "type": "day_trader",
                        "symbol": setup.get("symbol", "").replace("/USDT", ""),
                        "direction": setup.get("direction"),
                        "message": f"Day Trader {setup.get('direction')} on {setup.get('timeframe')} ({setup.get('confidence')}%)",
                        "reasoning": reasoning,
                        "confirmations": confirmations[:4],
                        "data": setup,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "severity": "medium"
                    })
                    
                    dual_engine.mark_alerted("Day Trader", setup["symbol"], setup["direction"])
                    logger.info(f"⚡ DAY TRADE: {setup['symbol']} {setup['timeframe']} {setup['direction']} ({setup['confidence']}%)")
                
                # Process Long Term setups
                for setup in all_setups.get("long_term", []):
                    # Validate price and format alert with fresh data
                    alert_msg, is_valid = await dual_engine.validate_and_format_alert(setup)
                    
                    if not is_valid:
                        logger.info(f"🎯 LONG TERM SKIPPED (price moved): {setup['symbol']}")
                        continue
                    
                    for chat_id in list(chat_ids):
                        settings = await get_user_settings(chat_id)
                        if settings.get("free_will", True):
                            await send_telegram_message(chat_id, alert_msg)
                            
                            await db.dual_alerts.insert_one({
                                "chat_id": chat_id,
                                "setup": setup,
                                "style": "long_term",
                                "timestamp": datetime.now(timezone.utc)
                            })
                        await asyncio.sleep(0.3)
                    
                    # Send to dashboard with detailed reasoning
                    confirmations = setup.get("confirmations", [])
                    
                    # Generate detailed reasoning
                    reasoning_parts = []
                    reasoning_parts.append(f"Long Term {setup.get('confidence')}% setup for patient multi-week position on {setup.get('timeframe')}")
                    
                    # Context from confirmations
                    for conf in confirmations[:3]:
                        if 'structure' in conf.lower() or 'trend' in conf.lower():
                            reasoning_parts.append("Strong structural foundation supports sustained move")
                        elif 'divergence' in conf.lower():
                            reasoning_parts.append("Momentum divergence signals potential trend change")
                        elif any(x in conf.lower() for x in ['resistance', 'support']):
                            reasoning_parts.append("Key level interaction validates timing")
                    
                    reasoning_parts.append(f"Entry: ${setup.get('entry', 0):,.2f} targeting multi-week hold")
                    reasoning_parts.append("Higher timeframe setup offers stronger conviction")
                    reasoning = ". ".join(reasoning_parts) + "."
                    
                    price_alert_system._add_dashboard_alert({
                        "type": "long_term",
                        "symbol": setup.get("symbol", "").replace("/USDT", ""),
                        "direction": setup.get("direction"),
                        "message": f"Long Term {setup.get('direction')} on {setup.get('timeframe')} ({setup.get('confidence')}%)",
                        "reasoning": reasoning,
                        "confirmations": confirmations[:4],
                        "data": setup,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "severity": "medium"
                    })
                    
                    dual_engine.mark_alerted("Long Term", setup["symbol"], setup["direction"])
                    logger.info(f"🎯 LONG TERM: {setup['symbol']} {setup['timeframe']} {setup['direction']} ({setup['confidence']}%)")
            
            # Scan every 40 seconds
            await asyncio.sleep(40)
            
        except Exception as e:
            logger.error(f"Dual trading engine error: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    existing = await db.chat_messages.distinct("chat_id")
    chat_ids.update(existing)
    logger.info(f"Loaded {len(chat_ids)} users")
    
    # Auto-configure Telegram webhook on every startup
    server_url = os.environ.get('SERVER_URL', '')
    if telegram_token and server_url:
        try:
            webhook_url = f"{server_url}/api/webhook"
            async with httpx.AsyncClient(timeout=10) as hc:
                resp = await hc.get(f"https://api.telegram.org/bot{telegram_token}/setWebhook?url={webhook_url}")
                result = resp.json()
                if result.get("ok"):
                    logger.info(f"Telegram webhook auto-set: {webhook_url}")
                else:
                    logger.error(f"Telegram webhook setup failed: {result}")
        except Exception as e:
            logger.error(f"Telegram webhook auto-setup error: {e}")
    
    # Load strategy weights for backward compatibility
    await autonomous_trader.load_strategy_weights()
    
    # Configure price alert system with WebSocket support
    price_alert_system.set_dependencies(send_telegram_message, chat_ids, ws_manager,
                                        heartbeat_fn=lambda: self_healer.heartbeat("price_alerts"))
    
    # Initialize app_state for route modules
    app_state.db = db
    app_state.chat_ids = chat_ids
    app_state.emergent_key = emergent_key
    app_state.autonomous_trader = autonomous_trader
    app_state.autonomous_trader_v2 = autonomous_trader_v2
    app_state.free_will_v2 = free_will_v2
    app_state.dual_engine = dual_engine
    app_state.learning_system = learning_system
    app_state.market_intel = market_intel
    app_state.enhanced_intel = enhanced_intel
    app_state.derivatives_intel = derivatives_intel
    app_state.news_intel = news_intel
    app_state.futures_calc = futures_calc
    app_state.mtf_analysis = mtf_analysis
    app_state.advanced_strategies = advanced_strategies
    app_state.order_flow = order_flow
    app_state.options_analyzer = options_analyzer
    app_state.backtest_engine = backtest_engine
    app_state.coinglass_intel = coinglass_intel
    app_state.strategy_engine = strategy_engine
    app_state.price_alert_system = price_alert_system
    app_state.sentiment_analyzer = sentiment_analyzer
    app_state.arbitrage_detector = arbitrage_detector
    app_state.strategy_health = strategy_health
    app_state.user_profiler = user_profiler
    app_state.ws_manager = ws_manager
    app_state.self_healer = self_healer
    app_state.send_telegram_message = send_telegram_message
    app_state.get_user_settings = get_user_settings
    app_state.update_user_settings = update_user_settings
    
    # Start background tasks
    ritual_task = asyncio.create_task(eternal_rituals())
    trading_task = asyncio.create_task(autonomous_trading_loop())
    freewill_task = asyncio.create_task(free_will_scanner())
    dual_task = asyncio.create_task(dual_trading_scanner())
    alert_task = asyncio.create_task(price_alert_system.run_forever())
    
    # Register all services with self-healer for auto-recovery
    self_healer.register("rituals", ritual_task, eternal_rituals)
    self_healer.register("trading_v2", trading_task, autonomous_trading_loop)
    self_healer.register("free_will", freewill_task, free_will_scanner)
    self_healer.register("dual_engine", dual_task, dual_trading_scanner)
    self_healer.register("price_alerts", alert_task, price_alert_system.run_forever)
    healer_task = asyncio.create_task(self_healer.monitor_loop())
    
    logger.info(f"AEON PAPER TRADING ACTIVATED - {autonomous_trader_v2.min_confidence}%+ conf, {autonomous_trader_v2.min_confirmations}+ confirmations")
    logger.info("AEON FREE WILL v2 ACTIVATED - Elite alerts only (80%+ conf, 3+ confirmations)")
    logger.info("DUAL ENGINE ACTIVATED - Day Trader (aggressive) + Long Term (smart)")
    logger.info("AEON PRICE ALERT SYSTEM v2 - Lean batched alerts")
    logger.info("SELF-HEALER ACTIVATED - Auto error detection & recovery")
    
    yield
    
    self_healer.active = False
    healer_task.cancel()
    ritual_task.cancel()
    trading_task.cancel()
    freewill_task.cancel()
    dual_task.cancel()
    alert_task.cancel()
    client.close()


app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time alerts and updates"""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back for ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


@api_router.get("/ws/stats")
async def ws_stats():
    """Get WebSocket connection statistics"""
    return ws_manager.get_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# CONFLUENCE API (SMC + Strategy)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/confluence/{symbol}")
async def api_confluence(symbol: str, timeframe: str = "4h"):
    """
    Get SMC + Strategy confluence analysis
    Combines Smart Money Concepts with technical strategies for high-probability setups
    """
    return await confluence_analyzer.analyze_confluence(symbol.upper() + "/USDT", timeframe)


# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/")
async def root():
    return {"message": "Aeon Market Intelligence Active", "status": "online"}


@api_router.get("/system/health")
async def api_system_health():
    """Self-healer status - shows all monitored services and recent healing actions."""
    return self_healer.get_status()


@api_router.get("/pairs")
async def api_list_pairs():
    """List all supported trading pairs"""
    return {
        "total_pairs": 44,
        "pairs": [
            "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "SHIB", "DOT",
            "LINK", "TRX", "BCH", "LTC", "NEAR", "UNI", "APT", "ICP", "ETC", "FIL",
            "ATOM", "XLM", "ARB", "OP", "INJ", "HBAR", "VET", "GRT", "AAVE", "ALGO",
            "SAND", "AXS", "MANA", "XTZ", "FLOW", "NEO", "SNX", "CRV", "RUNE", "ZEC",
            "DASH", "COMP", "ENJ", "CHZ"
        ],
        "features": {
            "autonomous_trading": "All 44 pairs scanned every 5 minutes",
            "derivatives": "Funding rates from OKX, Bitget, KuCoin, Gate.io",
            "technical_analysis": "RSI, MACD, BB, EMA, Stoch for all pairs",
            "multi_timeframe": "1h, 4h, 1d analysis available"
        }
    }


# NOTE: /market/*, /intel/*, /derivatives/* routes are now in routes/market.py
# Keeping these as fallbacks for backwards compatibility until frontend is migrated


# Intel routes moved to routes/market.py (intel/* routes)
# Derivatives routes moved to routes/market.py (derivatives/* routes)
# News/onchain/whales routes moved to routes/market.py


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-TIMEFRAME ANALYSIS APIs
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/mtf/{symbol}")
async def api_multi_timeframe(symbol: str):
    """Get multi-timeframe confluence analysis"""
    return await mtf_analysis.get_multi_timeframe_analysis(symbol.upper() + "USDT")


@api_router.get("/mtf/align/{symbol}")
async def api_trend_alignment(symbol: str):
    """Get trend alignment across timeframes"""
    return await mtf_analysis.get_trend_alignment(symbol.upper() + "USDT")


# ═══════════════════════════════════════════════════════════════════════════════
# FUTURES CALCULATOR APIs
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/calc/pnl")
async def api_calc_pnl(
    entry: float,
    exit: float,
    size: float,
    leverage: int = 1,
    direction: str = "LONG"
):
    """Calculate futures PnL"""
    return futures_calc.calculate_pnl(entry, exit, size, leverage, direction)


@api_router.get("/calc/position")
async def api_calc_position(
    balance: float,
    risk_pct: float,
    entry: float,
    stop: float,
    leverage: int = 1
):
    """Calculate recommended position size"""
    return futures_calc.calculate_position_size(balance, risk_pct, entry, stop, leverage)


@api_router.get("/calc/scenarios")
async def api_calc_scenarios(
    entry: float,
    size: float,
    leverage: int = 1,
    direction: str = "LONG"
):
    """Generate PnL scenarios at different price levels"""
    return futures_calc.generate_scenarios(entry, size, leverage, direction)


# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED STRATEGIES APIs (Divergence, Market Structure, VWAP)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/advanced/divergence/{symbol}")
async def api_divergence(symbol: str, timeframe: str = "1h"):
    """Detect RSI and MACD divergences"""
    return await advanced_strategies.detect_divergence(symbol.upper() + "/USDT", timeframe)


@api_router.get("/advanced/structure/{symbol}")
async def api_market_structure(symbol: str, timeframe: str = "1h"):
    """Analyze market structure (HH/HL/LH/LL, BOS, trend)"""
    return await advanced_strategies.analyze_market_structure(symbol.upper() + "/USDT", timeframe)


@api_router.get("/advanced/vwap/{symbol}")
async def api_vwap(symbol: str, timeframe: str = "1h"):
    """Calculate VWAP with bands"""
    return await advanced_strategies.calculate_vwap(symbol.upper() + "/USDT", timeframe)


@api_router.get("/advanced/full/{symbol}")
async def api_advanced_full(symbol: str, timeframe: str = "1h"):
    """Get full advanced analysis (divergence + structure + VWAP)"""
    return await advanced_strategies.get_full_analysis(symbol.upper() + "/USDT", timeframe)


# ═══════════════════════════════════════════════════════════════════════════════
# ORDER FLOW APIs (CVD, Absorption, Delta)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/orderflow/cvd/{symbol}")
async def api_cvd(symbol: str):
    """Calculate Cumulative Volume Delta"""
    return await order_flow.calculate_cvd(symbol.upper())


@api_router.get("/orderflow/divergence/{symbol}")
async def api_cvd_divergence(symbol: str):
    """Detect CVD divergence"""
    return await order_flow.detect_cvd_divergence(symbol.upper())


@api_router.get("/orderflow/absorption/{symbol}")
async def api_absorption(symbol: str):
    """Detect order absorption"""
    return await order_flow.detect_absorption(symbol.upper())


@api_router.get("/orderflow/full/{symbol}")
async def api_orderflow_full(symbol: str):
    """Get full order flow analysis"""
    return await order_flow.get_full_order_flow(symbol.upper())


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIONS DATA APIs (Max Pain, Put/Call Ratio)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/options/maxpain/{currency}")
async def api_max_pain(currency: str = "BTC"):
    """Calculate options max pain"""
    return await options_analyzer.calculate_max_pain(currency.upper())


@api_router.get("/options/pcr/{currency}")
async def api_put_call_ratio(currency: str = "BTC"):
    """Get put/call ratio"""
    return await options_analyzer.calculate_put_call_ratio(currency.upper())


@api_router.get("/options/oi/{currency}")
async def api_options_oi(currency: str = "BTC"):
    """Get options open interest by strike"""
    return await options_analyzer.get_oi_by_strike(currency.upper())


@api_router.get("/options/full/{currency}")
async def api_options_full(currency: str = "BTC"):
    """Get full options analysis"""
    return await options_analyzer.get_full_options_analysis(currency.upper())


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTESTING APIs
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/backtest/rsi/{symbol}")
async def api_backtest_rsi(symbol: str, timeframe: str = "1h", 
                           oversold: int = 30, overbought: int = 70,
                           stop_pct: float = 2.0, target_pct: float = 4.0,
                           days: int = 30):
    """Backtest RSI mean reversion strategy"""
    return await backtest_engine.backtest_rsi_strategy(
        symbol.upper() + "/USDT", timeframe, oversold, overbought, stop_pct, target_pct, days
    )


@api_router.get("/backtest/bb/{symbol}")
async def api_backtest_bb(symbol: str, timeframe: str = "1h",
                          stop_pct: float = 2.0, target_pct: float = 4.0,
                          days: int = 30):
    """Backtest Bollinger Band strategy"""
    return await backtest_engine.backtest_bb_strategy(
        symbol.upper() + "/USDT", timeframe, stop_pct, target_pct, days
    )


@api_router.get("/backtest/ema/{symbol}")
async def api_backtest_ema(symbol: str, timeframe: str = "1h",
                           fast: int = 9, slow: int = 21,
                           stop_pct: float = 2.0, days: int = 30):
    """Backtest EMA crossover strategy"""
    return await backtest_engine.backtest_ema_cross_strategy(
        symbol.upper() + "/USDT", timeframe, fast, slow, stop_pct, days
    )


@api_router.get("/backtest/compare/{symbol}")
async def api_backtest_compare(symbol: str, timeframe: str = "1h", days: int = 30):
    """Compare all strategies on same data"""
    return await backtest_engine.compare_strategies(symbol.upper() + "/USDT", timeframe, days)


# ═══════════════════════════════════════════════════════════════════════════════
# COINGLASS APIs (Real Derivatives Data)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/coinglass/funding/{symbol}")
async def api_coinglass_funding(symbol: str = "BTC"):
    """Get funding rates from Coinglass (FREE - no API key)"""
    return await coinglass_intel.get_funding_rates(symbol.upper())


@api_router.get("/coinglass/oi/{symbol}")
async def api_coinglass_oi(symbol: str = "BTC"):
    """Get open interest from Coinglass (FREE - no API key)"""
    return await coinglass_intel.get_open_interest(symbol.upper())


@api_router.get("/coinglass/ls/{symbol}")
async def api_coinglass_ls(symbol: str = "BTC"):
    """Get long/short ratio from Coinglass (FREE - no API key)"""
    return await coinglass_intel.get_long_short_ratio(symbol.upper())


@api_router.get("/coinglass/liquidations/{symbol}")
async def api_coinglass_liquidations(symbol: str = "BTC"):
    """Get liquidation heatmap from Coinglass (PAID - requires API key)"""
    return await coinglass_intel.get_liquidation_heatmap(symbol.upper())


@api_router.get("/coinglass/full/{symbol}")
async def api_coinglass_full(symbol: str = "BTC"):
    """Get full Coinglass report (funding + OI + L/S)"""
    return await coinglass_intel.get_full_report(symbol.upper())


# ═══════════════════════════════════════════════════════════════════════════════
# DUAL TRADING ENGINE APIs (Day Trader + Long Term)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/dual/stats")
async def api_dual_stats():
    """Get Dual Trading Engine statistics (Day Trader + Long Term)"""
    return dual_engine.get_stats()


@api_router.post("/dual/toggle")
async def api_dual_toggle(active: bool = True):
    """Toggle entire Dual Trading Engine on/off"""
    dual_engine.active = active
    return {"status": "ok", "active": active}


@api_router.post("/dual/day-trader/toggle")
async def api_dual_day_trader_toggle(active: bool = True):
    """Toggle Day Trader engine on/off"""
    dual_engine.day_trader.active = active
    return {"status": "ok", "day_trader_active": active}


@api_router.post("/dual/long-term/toggle")
async def api_dual_long_term_toggle(active: bool = True):
    """Toggle Long Term engine on/off"""
    dual_engine.long_term.active = active
    return {"status": "ok", "long_term_active": active}


@api_router.post("/dual/day-trader/confidence")
async def api_dual_day_trader_confidence(min_conf: int = 75):
    """Set Day Trader minimum confidence (65-95)"""
    min_conf = max(65, min(95, min_conf))
    dual_engine.day_trader.min_confidence = min_conf
    return {"status": "ok", "day_trader_min_confidence": min_conf}


@api_router.post("/dual/long-term/confidence")
async def api_dual_long_term_confidence(min_conf: int = 88):
    """Set Long Term minimum confidence (75-95)"""
    min_conf = max(75, min(95, min_conf))
    dual_engine.long_term.min_confidence = min_conf
    return {"status": "ok", "long_term_min_confidence": min_conf}


# ═══════════════════════════════════════════════════════════════════════════════
# FREE WILL v2 APIs (Ultra-selective)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/freewill/stats")
async def api_freewill_stats():
    """Get Free Will v2 engine statistics"""
    return await free_will_v2.get_stats()


@api_router.get("/freewill/scan/{symbol}")
async def api_freewill_scan_symbol(symbol: str, timeframe: str = "1h"):
    """Manually scan a specific symbol/timeframe with full analysis"""
    return await free_will_v2.analyze_setup_full(symbol.upper() + "/USDT", timeframe)


@api_router.post("/freewill/toggle")
async def api_freewill_toggle(active: bool = True):
    """Toggle Free Will v2 engine on/off"""
    free_will_v2.active = active
    return {"active": free_will_v2.active}


@api_router.post("/freewill/confidence")
async def api_freewill_confidence(min_conf: int = 80):
    """Set minimum confidence threshold (70-95)"""
    free_will_v2.min_confidence = max(70, min(95, min_conf))
    return {"min_confidence": free_will_v2.min_confidence}


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-STRATEGY APIs
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/strategies/scan/{symbol}")
async def api_strategies_scan(symbol: str, timeframe: str = "4h"):
    """Scan all strategies for a symbol"""
    return await strategy_engine.analyze_all(
        symbol.upper() + "/USDT",
        await strategy_engine.get_ohlcv(symbol.upper() + "/USDT", timeframe, 100),
        {"price": 0}  # Will be fetched in analyze_all
    )


@api_router.get("/strategies/ma/{symbol}")
async def api_strategy_ma(symbol: str, timeframe: str = "1h", fast: int = 9, slow: int = 21):
    """MA Crossover strategy analysis"""
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_ma_crossover(symbol.upper() + "/USDT", timeframe, fast, slow)


@api_router.get("/strategies/rsi/{symbol}")
async def api_strategy_rsi(symbol: str, timeframe: str = "1h"):
    """RSI Momentum strategy analysis"""
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_rsi_momentum(symbol.upper() + "/USDT", timeframe)


@api_router.get("/strategies/breakout/{symbol}")
async def api_strategy_breakout(symbol: str, timeframe: str = "4h"):
    """Breakout strategy analysis"""
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_breakout(symbol.upper() + "/USDT", timeframe)


@api_router.get("/strategies/bb/{symbol}")
async def api_strategy_bb(symbol: str, timeframe: str = "4h"):
    """Bollinger Band Squeeze strategy analysis"""
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_bb_squeeze(symbol.upper() + "/USDT", timeframe)


@api_router.get("/strategies/macd/{symbol}")
async def api_strategy_macd(symbol: str, timeframe: str = "4h"):
    """MACD Reversal strategy analysis"""
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_macd_reversal(symbol.upper() + "/USDT", timeframe)


@api_router.get("/strategies/pullback/{symbol}")
async def api_strategy_pullback(symbol: str, timeframe: str = "4h"):
    """Trend Pullback strategy analysis"""
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.strategy_trend_pullback(symbol.upper() + "/USDT", timeframe)


@api_router.get("/strategies/all/{symbol}")
async def api_strategies_all(symbol: str, timeframe: str = "4h"):
    """Run all strategies and get combined signal"""
    from strategy_engine import StrategyEngine
    se = StrategyEngine()
    return await se.scan_all_strategies(symbol.upper() + "/USDT", timeframe)


# ═══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL DATA SOURCES API
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/data/social/{symbol}")
async def api_social_data(symbol: str = "BTC"):
    """Get social stats from CryptoCompare"""
    from additional_data import additional_data
    return await additional_data.get_crypto_compare_social(symbol.upper())


@api_router.get("/data/btc/onchain")
async def api_btc_onchain():
    """Get BTC on-chain stats from Blockchain.com"""
    from additional_data import additional_data
    return await additional_data.get_blockchain_btc_stats()


@api_router.get("/data/btc/fees")
async def api_btc_fees():
    """Get BTC mempool fee estimates"""
    from additional_data import additional_data
    return await additional_data.get_mempool_fees()


@api_router.get("/data/eth/gas")
async def api_eth_gas():
    """Get ETH gas prices"""
    from additional_data import additional_data
    return await additional_data.get_eth_gas()


@api_router.get("/data/defi/tvl")
async def api_defi_tvl(protocol: str = None):
    """Get DeFi TVL from DefiLlama"""
    from additional_data import additional_data
    return await additional_data.get_defi_llama_tvl(protocol)


# ═══════════════════════════════════════════════════════════════════════════════
# SENTIMENT ANALYSIS APIs (Moltbot-inspired)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/sentiment/composite")
async def api_sentiment_composite(symbol: str = "BTC"):
    """Get composite sentiment from all sources"""
    return await sentiment_analyzer.get_composite_sentiment(symbol.upper())


@api_router.get("/sentiment/news")
async def api_sentiment_news():
    """Get news sentiment analysis"""
    return await sentiment_analyzer.get_news_sentiment()


@api_router.get("/sentiment/fear-greed")
async def api_sentiment_fear_greed():
    """Get Fear & Greed Index with history"""
    return await sentiment_analyzer.get_fear_greed()


@api_router.get("/sentiment/history")
async def api_sentiment_history():
    """Get sentiment history"""
    return {"history": sentiment_analyzer.get_sentiment_history()}


# Arbitrage routes moved to routes/market.py


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY HEALTH APIs (Moltbot-inspired self-improving)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/strategy-health/status")
async def api_strategy_health():
    """Get strategy health and performance status"""
    return strategy_health.get_status()


@api_router.get("/strategy-health/ranking")
async def api_strategy_health_ranking():
    """Get strategy ranking by performance score"""
    return {"ranking": strategy_health.get_ranking()}


@api_router.post("/strategy-health/record")
async def api_strategy_health_record(request: Request):
    """Record a trade result for strategy health tracking"""
    data = await request.json()
    strategy_id = data.get("strategy_id", "")
    pnl_pct = data.get("pnl_pct", 0)
    symbol = data.get("symbol", "")
    return strategy_health.record_trade(strategy_id, pnl_pct, symbol)


@api_router.post("/strategy-health/unbench/{strategy_id}")
async def api_strategy_unbench(strategy_id: str):
    """Manually un-bench a strategy"""
    return strategy_health.force_unbench(strategy_id)


@api_router.get("/data/all/{symbol}")
async def api_all_additional_data(symbol: str = "BTC"):
    """Get all additional data sources combined"""
    from additional_data import additional_data
    return await additional_data.get_full_additional_data(symbol.upper())


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE CONVERSATION API (Continuous back-and-forth)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.post("/voice/respond")
async def api_voice_respond(request: Request):
    """
    Get Aeon's voice response to user text
    Browser handles speech recognition, we handle LLM + TTS
    """
    try:
        data = await request.json()
        user_text = data.get("text", "")
        voice = data.get("voice", "guy")
        
        if not user_text:
            return {"error": "No text provided"}
        
        # Get Aeon's response
        emergent_key = os.environ.get("EMERGENT_LLM_KEY")
        
        voice_llm = LlmChat(
            api_key=emergent_key,
            session_id="voice-conversation",
            system_message="""You are Aeon, a confident trading buddy and life coach having a voice conversation.

IMPORTANT RULES FOR VOICE:
- Keep responses SHORT (1-3 sentences max)
- Be conversational and natural
- No bullet points or lists
- No markdown or special formatting
- Speak like you're talking to a friend
- Be direct and insightful
- Add personality - you're confident but warm"""
        ).with_model("openai", "gpt-4o-mini")
        
        aeon_text = await voice_llm.send_message(UserMessage(text=user_text))
        
        # Generate speech
        speech = await generate_speech(aeon_text, voice)
        
        if not speech.get("success"):
            return {"error": speech.get("error", "TTS failed")}
        
        return {
            "success": True,
            "text": aeon_text,
            "audio": speech.get("audio"),
            "format": "mp3"
        }
        
    except Exception as e:
        logger.error(f"Voice respond error: {e}")
        return {"error": str(e)}


@api_router.post("/voice/transcribe")
async def api_voice_transcribe(request: Request):
    """
    Transcribe audio using OpenAI Whisper for natural, accurate speech-to-text.
    Accepts base64 encoded audio data.
    """
    try:
        from voice_tts import transcribe_audio
        
        data = await request.json()
        audio_b64 = data.get("audio", "")
        language = data.get("language", "en")
        
        if not audio_b64:
            return {"error": "No audio provided", "use_browser": True}
        
        # Decode base64 audio
        audio_data = base64.b64decode(audio_b64)
        
        # Transcribe
        result = await transcribe_audio(audio_data, language)
        return result
        
    except Exception as e:
        logger.error(f"Voice transcribe error: {e}")
        return {"error": str(e), "use_browser": True}


@api_router.get("/voice/info")
async def api_voice_info():
    """Get available voices and STT status"""
    from voice_tts import get_voice_info
    return get_voice_info()


@api_router.get("/learning/stats")
async def api_learning_stats():
    return await learning_system.get_prediction_stats()


@api_router.get("/learning/open")
async def api_open_predictions():
    return await learning_system.get_open_predictions()


# ═══════════════════════════════════════════════════════════════════════════════
# EMERGENCY CONTROLS API (Kill Switch, Close All)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.post("/trading/v2/close-all")
async def api_close_all_positions():
    """
    EMERGENCY KILL SWITCH - Close all open positions immediately.
    Use with caution!
    """
    try:
        closed_count = 0
        errors = []
        
        # Close positions in autonomous trader v2
        for trade in list(autonomous_trader_v2.open_trades):
            try:
                # Get current price
                symbol = trade["symbol"]
                current_data = await market_intel.get_ticker(symbol)
                current_price = current_data.get("price", trade.get("entry_price", 0))
                
                # Calculate final PnL
                entry = trade.get("entry_price", current_price)
                direction = trade.get("direction", "LONG")
                leverage = trade.get("leverage", 10)
                pnl_pct = ((current_price - entry) / entry * 100) if direction == "LONG" else ((entry - current_price) / entry * 100)
                pnl_leveraged = pnl_pct * leverage
                
                # Close the trade
                trade["exit_price"] = current_price
                trade["pnl_pct"] = pnl_pct
                trade["pnl_leveraged"] = pnl_leveraged
                trade["closed_at"] = datetime.now(timezone.utc).isoformat()
                trade["close_reason"] = "EMERGENCY_KILL_SWITCH"
                
                autonomous_trader_v2.closed_trades.append(trade)
                await autonomous_trader_v2.close_trade_in_db(trade)
                autonomous_trader_v2.open_trades.remove(trade)
                closed_count += 1
                
            except Exception as e:
                errors.append(f"{trade.get('symbol', 'unknown')}: {str(e)}")
        
        # Note: dual_engine is for alerts only, not position management
        # No need to clear any positions there
        
        return {
            "success": True,
            "closed_count": closed_count,
            "errors": errors if errors else None,
            "message": f"Emergency close: {closed_count} positions closed"
        }
        
    except Exception as e:
        logger.error(f"Kill switch error: {e}")
        return {"success": False, "error": str(e)}


@api_router.post("/trading/v2/quick-trade")
async def api_quick_trade(request: Request):
    """
    Execute a quick trade from the dashboard or SMC analysis.
    Auto-determines trade style and leverage based on timeframe and confidence.
    """
    try:
        data = await request.json()
        symbol = data.get("symbol", "BTC")
        direction = data.get("direction", "LONG")
        timeframe = data.get("timeframe", "1h")
        confidence = data.get("confidence", 75)
        position_size = data.get("position_size", 1000)
        
        # Get current price
        full_symbol = f"{symbol}/USDT"
        market_data = await market_intel.get_ticker(full_symbol)
        current_price = market_data.get("price", 0)
        
        if current_price <= 0:
            return {"error": "Could not get current price"}
        
        # Determine trade style based on timeframe
        trade_style = autonomous_trader_v2.determine_trade_style(timeframe, confidence)
        
        # Calculate leverage (bot has free will)
        leverage = autonomous_trader_v2.calculate_leverage(confidence, None, trade_style)
        
        # Get ATR for stop/target
        tech = await market_intel.get_technical_analysis(symbol + "USDT", timeframe)
        atr = tech.get("atr", current_price * 0.02)
        
        # Get style config for stop/target multipliers
        style_config = autonomous_trader_v2.get_trade_style_config(trade_style)
        
        # Calculate stop and target
        if direction == "LONG":
            stop_price = current_price - (atr * style_config["stop_atr_mult"])
            target_price = current_price + (atr * style_config["target_atr_mult"])
        else:
            stop_price = current_price + (atr * style_config["stop_atr_mult"])
            target_price = current_price - (atr * style_config["target_atr_mult"])
        
        # Create trade
        trade = {
            "id": f"quick_{symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "symbol": full_symbol,
            "direction": direction,
            "trade_type": trade_style,
            "timeframe": timeframe,
            "entry_price": current_price,
            "current_price": current_price,
            "position_size": position_size,
            "leverage": leverage,
            "stop_price": stop_price,
            "target_price": target_price,
            "confidence": confidence,
            "pnl_pct": 0,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "source": "quick_trade",
            "confirmations": [f"{trade_style} style selected", f"{leverage}x leverage", f"ATR-based stops"]
        }
        
        # Add to open trades
        autonomous_trader_v2.open_trades.append(trade)
        await autonomous_trader_v2.save_open_trade(trade)
        
        # Log to dashboard alerts
        price_alert_system._add_dashboard_alert({
            "type": "quick_trade",
            "symbol": symbol,
            "direction": direction,
            "message": f"Quick {trade_style} {direction} on {symbol} @ ${current_price:,.2f} ({leverage}x)",
            "data": trade,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "medium"
        })
        
        return {
            "success": True,
            "trade": trade,
            "message": f"{style_config['emoji']} {trade_style} {direction} @ ${current_price:,.2f} ({leverage}x leverage)"
        }
        
    except Exception as e:
        logger.error(f"Quick trade error: {e}")
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# NOTE: All /trading/* and /trades/* endpoints moved to routes/trading.py
# This eliminates ~300 lines of duplicate endpoint definitions
# All trading functionality is now in the modular routes/trading.py file
# ═══════════════════════════════════════════════════════════════════════════════



@api_router.get("/mexc/live")
async def api_mexc():
    return get_mexc_orderbook()


@api_router.get("/bot/stats")
async def api_stats():
    total = await db.chat_messages.count_documents({})
    unique = len(await db.chat_messages.distinct("chat_id"))
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await db.chat_messages.count_documents({"timestamp": {"$gte": today}})
    freewill = await db.user_settings.count_documents({"free_will": True})
    
    return {
        "total_messages": total,
        "unique_users": unique,
        "messages_today": today_count,
        "freewill_users": freewill,
        "active_users": len(chat_ids)
    }


@api_router.get("/bot/messages")
async def api_messages(limit: int = 50, context: str = None):
    query = {"context": context} if context else {}
    return await db.chat_messages.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)


@api_router.get("/bot/test")
async def api_test():
    try:
        # Test Binance
        btc = await market_intel.get_technical_analysis("BTCUSDT", "1h")
        binance_ok = "error" not in btc
        
        # Test LLM
        chat = LlmChat(api_key=emergent_key, session_id="test", system_message="Test").with_model("openai", "gpt-4o-mini")
        await chat.send_message(UserMessage(text="Hi"))
        
        return {
            "status": "success",
            "llm": True,
            "binance": binance_ok,
            "mexc": bool(mexc_api_key),
            "telegram": bool(telegram_token),
            "users": len(chat_ids)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# USER PROFILE API
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/user/profile")
async def api_user_profile(chat_id: int = None):
    """Get user profile summary"""
    # For web dashboard, use a default profile or first user
    if not chat_id and chat_ids:
        chat_id = list(chat_ids)[0]
    elif not chat_id:
        return {"error": "No users found"}
    
    return await user_profiler.get_profile_summary(chat_id)


@api_router.get("/user/profile/{chat_id}")
async def api_user_profile_by_id(chat_id: int):
    """Get user profile by chat ID"""
    return await user_profiler.get_profile_summary(chat_id)


@api_router.post("/user/profile/{chat_id}/fact")
async def api_add_user_fact(chat_id: int, request: Request):
    """Add a key fact about the user"""
    data = await request.json()
    fact = data.get("fact", "")
    category = data.get("category", "general")
    
    if not fact:
        return {"error": "Fact is required"}
    
    await user_profiler.add_key_fact(chat_id, fact, category)
    return {"status": "ok", "fact": fact}


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM WEBHOOK
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.post("/webhook")
async def webhook(request: Request):
    try:
        update = await request.json()
        if 'message' not in update:
            return {"status": "ok"}
        
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')
        if not text:
            return {"status": "ok"}
        
        chat_ids.add(chat_id)
        username = msg.get('from', {}).get('username', 'Unknown')
        settings = await get_user_settings(chat_id)
        
        logger.info(f"{username} ({chat_id}): {text}")
        
        text_lower = text.lower().strip()
        
        # ═══════════════════════════════════════════════════════════════════
        # COMMANDS
        # ═══════════════════════════════════════════════════════════════════
        
        if text_lower == "free off":
            await update_user_settings(chat_id, {"free_will": False})
            response = "🔕 Free Will OFF. Say 'free on' to reactivate."
            context = "settings"
            
        elif text_lower == "free on":
            await update_user_settings(chat_id, {"free_will": True})
            response = "⚡ Free Will ON. Autonomous mode active."
            context = "settings"
            
        elif text_lower == "free status":
            stats = await learning_system.get_prediction_stats()
            state = await get_user_probe_state(chat_id)
            response = f"""🧠 AEON STATUS

Free Will: {'ON ⚡' if settings.get('free_will') else 'OFF'}
Intensity: {state.get('intensity_level', 'INITIATE')}
Probes: {state.get('probes_completed', 0)}

Trading Stats:
Predictions: {stats['total_predictions']}
Win Rate: {stats['win_rate']}%
Total PnL: {stats['total_pnl_pct']:+.2f}%"""
            context = "settings"
            
        elif text == '/start' or text_lower == '/help' or text_lower == '/commands':
            current_mode = settings.get("mode", "default")
            dual_stats = dual_engine.get_stats()
            
            response = f"""AEON - AI Trading Intelligence

====== PERSONAS ======
Default - Sharp trading buddy
Alchemy Mode - Mystical wisdom
  (Say "alchemy mode" / "casual mode")

====== MARKET ANALYSIS ======
/scan btc      - Full analysis + entry/SL/TP
/ta btc 1h     - Technicals (RSI, MACD, BB)
/mtf btc       - Multi-timeframe (1h/4h/1d)
/sentiment btc - Sentiment score
/structure btc - HH/HL/LH/LL analysis

====== DERIVATIVES ======
/funding btc   - Aggregated funding rates
/deriv btc     - Full derivatives data
/positions btc - Long/Short ratio
/cg btc        - Coinglass data

====== MARKET INTEL ======
/market  - Global market summary
/fear    - Fear & Greed Index
/top100  - Top 10 by market cap
/movers  - Top gainers/losers (24h)
/trending - Most searched coins

====== NEWS & ON-CHAIN ======
/news    - Latest headlines (clickable!)
/whales  - Whale activity (>10 BTC)
/onchain - BTC network stats

====== CALCULATORS ======
/calc 65000 68000 1000 10 long
  (entry exit size leverage direction)
/calcsize 10000 2 65000 63000 10
  (balance risk% entry stop leverage)

====== AUTONOMOUS TRADING ======
/auto    - Paper trading stats
/auto on / off - Toggle trading
/opps    - Current opportunities
/open    - Open positions
/close btc   - Close position
/trail btc 5 - Set trail stop %
/tp btc 72000 - Set take profit

====== DUAL ENGINE ======
Day Trader: {'ON' if dual_stats['day_trader']['active'] else 'OFF'} ({dual_stats['day_trader']['min_confidence']}% min)
Long Term: {'ON' if dual_stats['long_term']['active'] else 'OFF'} ({dual_stats['long_term']['min_confidence']}% min)
* Market structure filter active (HH/HL/LH/LL)

====== FREE WILL v2 ======
/fw      - Free Will status
/fwconf 80 - Set min confidence
free on / free off - Toggle alerts

====== INTELLIGENCE (NEW) ======
/intel     - Full market intelligence report
/arbi      - Scan 5 exchanges for arbitrage
/health    - Strategy health & auto-bench status
/unbench [id] - Force reactivate strategy

====== SMART MONEY (SMC) ======
/smc btc - Order blocks, FVG, liquidity

====== ADVANCED ======
/divergence btc - RSI/MACD divergence
/vwap btc       - VWAP levels
/cvd btc        - Order flow (CVD)
/options btc    - Max pain & P/C ratio
/strat btc      - Multi-strategy scan
/backtest btc   - Strategy backtest

====== ALERTS ======
/alerts - View alert status
/alert add btc above 70000
/alert remove [id]

====== JOURNAL ======
/journal  - Performance stats
/insights - AI trading insights

Mode: {'Alchemy' if current_mode == 'alchemy' else 'Casual'}
Auto Trading: {'ACTIVE' if autonomous_trader_v2.active else 'PAUSED'}

What's on your mind?"""
            context = "start"
            
        elif text_lower == '/freewill' or text_lower == '/fw':
            stats = await free_will_v2.get_stats()
            
            response = f"""🎯 FREE WILL v2 (ELITE ALERTS)

Status: {'🟢 ACTIVE' if stats['active'] else '🔴 OFF'}
Min Confidence: {stats['min_confidence']}%
Min Confirmations: {stats['min_confirmations']}

📊 MONITORING
Pairs: {stats['pairs_monitored']} (top coins only)
Timeframes: {', '.join(stats['timeframes'])}

📈 ALERTS
Today: {stats['daily_alerts']}/{stats['max_daily_alerts']}
Total: {stats['total_alerts_sent']}
Cooldown: {stats['alert_cooldown_mins']} min per symbol

📡 DATA SOURCES:
• TA, Divergence, Structure
• VWAP, CVD, Options
• Derivatives, Fear & Greed

Only sends alerts when:
✅ Confidence 80%+
✅ 3+ confirmations from different sources
✅ Higher timeframes (1h, 4h, 1d)

Commands:
free on/off - Toggle alerts
/fwconf 80 - Set min confidence (70-95)"""
            context = "settings"
            
        elif text_lower.startswith('/fwconf'):
            parts = text_lower.split()
            if len(parts) > 1:
                try:
                    conf = int(parts[1])
                    free_will_v2.min_confidence = max(70, min(95, conf))
                    response = f"✅ Free Will min confidence set to {free_will_v2.min_confidence}%"
                except:
                    response = "Usage: /fwconf 80 (sets 80% minimum)"
            else:
                response = f"Current: {free_will_v2.min_confidence}%\nUsage: /fwconf 80"
            context = "settings"
            
        elif text_lower.startswith('/scan'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            response = await generate_trade_analysis(symbol + "USDT", chat_id)
            context = "trading"
            
        elif text_lower.startswith('/ta'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            interval = parts[2] if len(parts) > 2 else "1h"
            
            ta = await market_intel.get_technical_analysis(symbol + "USDT", interval)
            if "error" in ta:
                response = f"⚠️ {ta['error']}"
            else:
                ind = ta.get("indicators", {})
                response = f"""📊 {symbol} TECHNICALS ({interval})

Price: ${ta['price']:,.2f}
Bias: {ta['overall_bias']}

RSI: {ind.get('rsi', 'N/A')}
MACD: {ind.get('macd', 'N/A')} (Signal: {ind.get('macd_signal', 'N/A')})
Stoch: K={ind.get('stoch_k', 'N/A')} D={ind.get('stoch_d', 'N/A')}

BB: ${ind.get('bb_lower', 0):,.0f} - ${ind.get('bb_upper', 0):,.0f}
EMA: 9={ind.get('ema_9', 0):,.0f} | 21={ind.get('ema_21', 0):,.0f} | 50={ind.get('ema_50', 0):,.0f}
ATR: ${ind.get('atr', 0):,.2f}
Vol Ratio: {ind.get('volume_ratio', 1):.1f}x

Signals: {len(ta.get('signals', []))} detected"""
            context = "trading"
            
        elif text_lower.startswith('/positions'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            ls = await market_intel.get_long_short_ratio(symbol + "USDT", "1h", 1)
            whale = await market_intel.get_top_trader_long_short_ratio(symbol + "USDT", "1h", 1)
            funding = await market_intel.get_current_funding_rate(symbol + "USDT")
            
            ls_ratio = ls[0]['long_short_ratio'] if ls else 0
            whale_ratio = whale[0]['long_short_ratio'] if whale else 0
            long_pct = ls[0]['long_account']*100 if ls else 0
            short_pct = ls[0]['short_account']*100 if ls else 0
            
            crowd_warning = ""
            if ls and ls_ratio > 1.5:
                crowd_warning = "⚠️ Longs crowded!"
            elif ls and ls_ratio < 0.7:
                crowd_warning = "⚠️ Shorts crowded!"
            
            response = f"""📈 {symbol} POSITIONING

Long/Short Ratio: {ls_ratio:.2f}
Longs: {long_pct:.1f}%
Shorts: {short_pct:.1f}%

🐋 Whale L/S: {whale_ratio:.2f}

💰 Funding: {funding.get('funding_rate_pct', 'N/A')}

{crowd_warning}"""
            context = "trading"
            
        elif text_lower.startswith('/funding'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            # Use enhanced intel funding data
            # Use REAL derivatives data from multiple exchanges
            funding = await derivatives_intel.get_aggregated_funding(symbol + "USDT")
            
            response = f"""💰 {symbol} FUNDING RATES (REAL DATA)

Average: {funding.get('average_funding_pct', 'N/A')}
{funding.get('interpretation', '')}

📊 BY EXCHANGE:"""
            
            for ex in funding.get('exchanges', []):
                response += f"\n• {ex.get('exchange')}: {ex.get('funding_rate_pct', 'N/A')}"
            
            response += f"\n\nData from {funding.get('data_sources', 0)} exchanges"
            context = "trading"
            
        elif text_lower.startswith('/liqs') or text_lower.startswith('/liquidations'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            # Get liquidation data from derivatives intel
            liqs = await derivatives_intel.get_aggregated_funding(symbol + "USDT")
            
            response = f"""💥 {symbol} LIQUIDATION DATA

Recent liquidations indicate market stress levels.

📊 Funding Rate: {liqs.get('average_funding_pct', 'N/A')}
{liqs.get('interpretation', '')}

💡 High liquidations often precede reversals.
Use with /deriv {symbol.lower()} for full derivatives picture."""
            context = "trading"
            
        elif text_lower == '/market' or text_lower == '/summary':
            summary = await enhanced_intel.get_market_summary()
            response = summary
            context = "trading"
            
        elif text_lower == '/fear' or text_lower == '/greed' or text_lower == '/fng':
            fng = await enhanced_intel.get_fear_greed_index()
            interpretation = enhanced_intel.interpret_fear_greed(fng.get("value", 50))
            
            response = f"""🎭 FEAR & GREED INDEX

Value: {fng.get('value', '?')}
Status: {fng.get('classification', '?')}

{interpretation}

This is a contrarian indicator:
• Extreme Fear = potential buying opportunity
• Extreme Greed = potential top, be cautious"""
            context = "trading"
            
        elif text_lower == '/top100' or text_lower == '/top':
            coins = await enhanced_intel.get_top_100_coins()
            
            if coins:
                response = "📊 TOP 10 BY MARKET CAP\n\n"
                for c in coins[:10]:
                    change = c.get("price_change_percentage_24h", 0) or 0
                    emoji = "🟢" if change >= 0 else "🔴"
                    price = c.get("current_price", 0)
                    price_str = f"${price:,.2f}" if price >= 1 else f"${price:.4f}"
                    response += f"{emoji} #{c.get('market_cap_rank')} {c.get('symbol', '').upper()}: {price_str} ({change:+.1f}%)\n"
                response += "\nUse /movers for top gainers/losers"
            else:
                response = "⚠️ Failed to fetch top 100 data"
            context = "trading"
            
        elif text_lower == '/movers' or text_lower == '/gainers':
            movers = await enhanced_intel.get_top_movers(5)
            
            response = "📈 TOP GAINERS (24h)\n"
            for c in movers.get("gainers", []):
                response += f"🟢 {c['symbol']}: {c['change_24h']:+.1f}%\n"
            
            response += "\n📉 TOP LOSERS (24h)\n"
            for c in movers.get("losers", []):
                response += f"🔴 {c['symbol']}: {c['change_24h']:+.1f}%\n"
            context = "trading"
            
        elif text_lower == '/trending' or text_lower == '/hot':
            trending = await enhanced_intel.get_trending_coins()
            
            if trending:
                response = "🔥 TRENDING COINS (Most Searched)\n\n"
                for i, c in enumerate(trending[:7], 1):
                    response += f"{i}. {c.get('name', '?')} ({c.get('symbol', '?').upper()})\n"
                response += "\nThese are being searched heavily in the last 24h"
            else:
                response = "⚠️ Failed to fetch trending data"
            context = "trading"
            
        elif text_lower.startswith('/sentiment'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            sent = await enhanced_intel.analyze_symbol_sentiment(symbol + "USDT")
            
            response = f"""📊 {symbol} SENTIMENT ANALYSIS

Overall: {sent.get('sentiment', 'NEUTRAL')}
Score: {sent.get('score', 0):+d}

Signals:
{chr(10).join(sent.get('signals', ['No signals']))}

Fear & Greed: {sent.get('fear_greed', {}).get('value', '?')} ({sent.get('fear_greed', {}).get('classification', '?')})
Funding: {sent.get('funding', {}).get('funding_rate_pct', 'N/A')}"""
            context = "trading"
            
        elif text_lower.startswith('/deriv') or text_lower.startswith('/oi'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            report = await derivatives_intel.get_full_derivatives_report(symbol + "USDT")
            
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
            
            # Real L/S data from OKX
            global_ls = ls.get('global', {})
            top_ls = ls.get('top_traders', {})
            
            response += f"""
📊 LONG/SHORT RATIO (REAL - OKX)
Global: {global_ls.get('long_pct', '?')}% L / {global_ls.get('short_pct', '?')}% S
Top Traders: {top_ls.get('long_pct', '?')}% L / {top_ls.get('short_pct', '?')}% S
{ls.get('interpretation', '')}

Data: OKX, Bitget, KuCoin, Gate"""
            context = "trading"
            
        elif text_lower.startswith('/coinglass') or text_lower.startswith('/cg'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            report = await coinglass_intel.get_full_report(symbol)
            
            funding = report.get('funding', {})
            oi = report.get('open_interest', {})
            ls = report.get('long_short', {})
            
            response = f"""📊 {symbol} COINGLASS DATA

💰 FUNDING (Avg: {funding.get('average_rate_pct', 'N/A')})
"""
            for ex in funding.get('exchanges', [])[:4]:
                response += f"• {ex.get('exchange')}: {ex.get('rate_pct', 'N/A')}\n"
            
            response += f"""
📈 OPEN INTEREST
Total: {oi.get('total_open_interest_str', 'N/A')}
"""
            for ex in oi.get('exchanges', [])[:3]:
                response += f"• {ex.get('exchange')}: {ex.get('open_interest_str', 'N/A')}\n"
            
            global_ls = ls.get('global', {})
            response += f"""
📊 LONG/SHORT RATIO
Global: {global_ls.get('long_pct', '?')}% L / {global_ls.get('short_pct', '?')}% S
{ls.get('interpretation', '')}

Overall Bias: {report.get('overall_bias', 'NEUTRAL')}
Data: Coinglass"""

            if not report.get('has_api_key'):
                response += """

💡 Add COINGLASS_API_KEY for liquidation heatmaps
Get key at: coinglass.com/api"""
            
            context = "trading"
            
        elif text_lower == '/news':
            news = await news_intel.get_latest_news(8)
            sentiment = await news_intel.get_news_sentiment_summary()
            
            response = f"""📰 CRYPTO NEWS

Sentiment: {sentiment.get('sentiment', 'UNKNOWN')}
Bullish: {sentiment.get('bullish_pct', 0):.0f}% | Bearish: {sentiment.get('bearish_pct', 0):.0f}%

📰 Latest Headlines:
"""
            for i, n in enumerate(news[:6], 1):
                emoji = n.get('sentiment', {}).get('emoji', '⚪')
                title = n.get('title', '')[:55]
                url = n.get('url', '')
                if url:
                    response += f"{emoji} [{title}...]({url})\n\n"
                else:
                    response += f"{emoji} {title}...\n"
            
            response += "\n💡 Click headlines to read full articles"
            context = "news"
            
        elif text_lower == '/whales' or text_lower == '/whale':
            whales = await news_intel.get_whale_summary()
            
            response = f"""🐋 WHALE ACTIVITY

Activity Level: {whales.get('emoji', '')} {whales.get('activity', 'UNKNOWN')}
Large Transactions: {whales.get('large_transactions', 0)}
Whale Transactions (>100 BTC): {whales.get('whale_transactions', 0)}
Total BTC Moved: {whales.get('total_btc_moved', 0)} BTC

Recent Large Moves:
"""
            for tx in whales.get('transactions', [])[:5]:
                response += f"{tx.get('size', '')} {tx.get('value_btc', 0)} BTC ({tx.get('value_usd_approx', '')})\n"
            
            context = "trading"
            
        elif text_lower == '/onchain' or text_lower == '/chain':
            onchain = await news_intel.get_btc_onchain_stats()
            flow = await news_intel.get_exchange_flow_estimate()
            
            response = f"""⛓️ BTC ON-CHAIN DATA

📊 NETWORK
Fastest Fee: {onchain.get('fees', {}).get('fastest', 0)} sat/vB
Hour Fee: {onchain.get('fees', {}).get('hour', 0)} sat/vB
{onchain.get('fee_interpretation', '')}

Hashrate: {onchain.get('hashrate', {}).get('current', 'N/A')}

📈 EXCHANGE FLOW
{flow.get('flow_estimate', '')}
Mempool TX: {flow.get('mempool_tx_count', 0):,}
{flow.get('interpretation', '')}"""
            context = "trading"
            
        elif text_lower.startswith('/mtf') or text_lower.startswith('/timeframe'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            mtf = await mtf_analysis.get_multi_timeframe_analysis(symbol + "USDT")
            
            response = f"""📊 {symbol} MULTI-TIMEFRAME ANALYSIS

{mtf.get('confluence_emoji', '')} {mtf.get('confluence', '')}
Confidence: {mtf.get('confidence', 0)}%

"""
            for tf in ['1h', '4h', '1d']:
                if tf in mtf.get('timeframes', {}):
                    t = mtf['timeframes'][tf]
                    response += f"{tf}: {t.get('emoji', '')} {t.get('bias', '')} (score: {t.get('score', 0):+.1f})\n"
            
            response += f"""
💡 {mtf.get('recommendation', '')}"""
            context = "trading"
            
        elif text_lower.startswith('/calc'):
            parts = text_lower.split()
            
            if len(parts) < 5:
                response = """📊 FUTURES CALCULATOR

Usage: /calc [entry] [exit] [size] [leverage] [direction]

Example:
/calc 65000 68000 1000 10 long
= Calculate PnL for $1000 long at 10x

/calcsize [balance] [risk%] [entry] [stop] [leverage]
= Calculate position size based on risk"""
            else:
                try:
                    entry = float(parts[1])
                    exit_p = float(parts[2])
                    size = float(parts[3])
                    leverage = int(parts[4]) if len(parts) > 4 else 1
                    direction = parts[5].upper() if len(parts) > 5 else "LONG"
                    
                    result = futures_calc.calculate_pnl(entry, exit_p, size, leverage, direction)
                    
                    emoji = "✅" if result['pnl_usd'] > 0 else "❌" if result['pnl_usd'] < 0 else "⚪"
                    
                    response = f"""{emoji} FUTURES CALCULATION

{result['direction']} @ {leverage}x
Entry: ${entry:,.2f}
Exit: ${exit_p:,.2f}

Position: ${result['position_size_usd']:,.2f}
Margin Used: ${result['margin_required']:,.2f}

Price Move: {result['price_change_pct']:+.2f}%
PnL: {result['pnl_pct']:+.2f}%
PnL USD: ${result['pnl_usd']:+,.2f}
ROI on Margin: {result['roi_on_margin']:+.2f}%

⚠️ Liquidation: ${result['liquidation_price']:,.2f}"""
                except Exception as e:
                    response = f"⚠️ Calculation error: {e}\n\nUsage: /calc entry exit size leverage direction"
            context = "trading"
            
        elif text_lower.startswith('/calcsize'):
            parts = text_lower.split()
            
            if len(parts) < 5:
                response = """📊 POSITION SIZE CALCULATOR

Usage: /calcsize [balance] [risk%] [entry] [stop] [leverage]

Example:
/calcsize 10000 2 65000 63000 10
= Calculate size risking 2% of $10k account with 10x leverage"""
            else:
                try:
                    balance = float(parts[1])
                    risk = float(parts[2])
                    entry = float(parts[3])
                    stop = float(parts[4])
                    leverage = int(parts[5]) if len(parts) > 5 else 1
                    
                    result = futures_calc.calculate_position_size(balance, risk, entry, stop, leverage)
                    
                    direction = "LONG" if stop < entry else "SHORT"
                    
                    response = f"""📊 POSITION SIZE CALCULATION

Account: ${balance:,.2f}
Risk: {risk}% (${result['risk_amount_usd']:,.2f})

{direction} @ {leverage}x
Entry: ${entry:,.2f}
Stop Loss: ${stop:,.2f}
Stop Distance: {result['stop_distance_pct']:.2f}%

✅ RECOMMENDED SIZE:
Position: ${result['recommended_position_size']:,.2f}
Margin Required: ${result['margin_required']:,.2f}
Coins: {result['coins_to_buy']:.6f}

Max Loss at Stop: ${result['max_loss_at_stop']:,.2f}"""
                except Exception as e:
                    response = f"⚠️ Calculation error: {e}"
            context = "trading"
            
        # ═══════════════════════════════════════════════════════════════════════
        # ADVANCED ANALYSIS COMMANDS
        # ═══════════════════════════════════════════════════════════════════════
        
        elif text_lower.startswith('/divergence') or text_lower.startswith('/div'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "1h"
            
            div = await advanced_strategies.detect_divergence(symbol + "/USDT", timeframe)
            
            response = f"""📊 {symbol} DIVERGENCE ANALYSIS ({timeframe})

RSI: {div.get('current_rsi', 50)}
MACD Hist: {div.get('current_macd_hist', 0):.6f}

"""
            if div.get('has_divergence'):
                for d in div.get('divergences', []):
                    emoji = "🟢" if d['signal'] == 'BUY' else "🔴"
                    response += f"""{emoji} {d['type']}
Signal: {d['signal']}
Strength: {d['strength']}
{d['description']}

"""
            else:
                response += "No divergences detected on this timeframe.\n\nTry different timeframes: 15m, 1h, 4h, 1d"
            
            context = "trading"
        
        elif text_lower.startswith('/structure') or text_lower.startswith('/struct'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "1h"
            
            struct = await advanced_strategies.analyze_market_structure(symbol + "/USDT", timeframe)
            
            bos_info = ""
            if struct.get('bos'):
                bos = struct['bos']
                bos_info = f"""
⚡ {bos['type']}
Level: ${bos['level']:,.2f}
{bos['description']}
"""
            
            response = f"""📈 {symbol} MARKET STRUCTURE ({timeframe})

Trend: {struct.get('trend', 'UNKNOWN')}
Bias: {struct.get('bias', 'NEUTRAL')}
Structure: {' → '.join(struct.get('structure', []))}

Support: ${struct.get('support', 0):,.2f}
Resistance: ${struct.get('resistance', 0):,.2f}
Current: ${struct.get('current_price', 0):,.2f}

Range: {'Yes' if struct.get('is_ranging') else 'No'} ({struct.get('range_pct', 0):.1f}%)
{bos_info}
Use this to identify trend direction and key levels."""
            context = "trading"
        
        elif text_lower.startswith('/vwap'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "1h"
            
            vwap = await advanced_strategies.calculate_vwap(symbol + "/USDT", timeframe)
            
            response = f"""📊 {symbol} VWAP ANALYSIS ({timeframe})

VWAP: ${vwap.get('vwap', 0):,.2f}
Current: ${vwap.get('current_price', 0):,.2f}
Distance: {vwap.get('distance_pct', 0):+.2f}%

Bands:
+2σ: ${vwap.get('upper_band_2', 0):,.2f}
+1σ: ${vwap.get('upper_band_1', 0):,.2f}
VWAP: ${vwap.get('vwap', 0):,.2f}
-1σ: ${vwap.get('lower_band_1', 0):,.2f}
-2σ: ${vwap.get('lower_band_2', 0):,.2f}

Bias: {vwap.get('bias', 'NEUTRAL')}
{vwap.get('signal', '')}

💡 Price above VWAP = institutional buyers in control
💡 Price below VWAP = institutional sellers in control"""
            context = "trading"
        
        elif text_lower.startswith('/orderflow') or text_lower.startswith('/cvd') or text_lower.startswith('/flow'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            flow = await order_flow.get_full_order_flow(symbol)
            cvd = flow.get('cvd', {})
            
            response = f"""💰 {symbol} ORDER FLOW ANALYSIS

CVD: ${cvd.get('cvd', 0):,.0f}
Trend: {cvd.get('cvd_trend', 'UNKNOWN')}

Buy Volume: ${cvd.get('buy_volume', 0):,.0f} ({cvd.get('buy_pct', 50):.1f}%)
Sell Volume: ${cvd.get('sell_volume', 0):,.0f} ({cvd.get('sell_pct', 50):.1f}%)

Bias: {cvd.get('bias', 'NEUTRAL')}
{cvd.get('signal', '')}

Signal: {flow.get('overall_signal', 'NEUTRAL')}
Confidence: {flow.get('confidence', 50)}%

💡 CVD shows real buying/selling pressure
💡 Rising CVD = accumulation
💡 Falling CVD = distribution"""
            context = "trading"
        
        elif text_lower.startswith('/options') or text_lower.startswith('/maxpain') or text_lower.startswith('/pcr'):
            parts = text_lower.split()
            currency = parts[1].upper() if len(parts) > 1 else "BTC"
            
            options = await options_analyzer.get_full_options_analysis(currency)
            mp = options.get('max_pain', {})
            pcr = options.get('put_call_ratio', {})
            oi = options.get('oi_distribution', {})
            
            response = f"""📈 {currency} OPTIONS ANALYSIS

🎯 MAX PAIN
Strike: ${mp.get('max_pain', 0):,.0f}
Current: ${mp.get('current_price', 0):,.0f}
Distance: {mp.get('distance_pct', 0):+.1f}%
Expiry: {mp.get('expiry', 'N/A')} ({mp.get('days_to_expiry', 0)} days)

{mp.get('signal', '')}

📊 PUT/CALL RATIO
Ratio: {pcr.get('put_call_ratio_oi', 0):.3f}
Sentiment: {pcr.get('sentiment', 'NEUTRAL')}
{pcr.get('signal', '')}

🏔️ OI WALLS
Call Wall: ${oi.get('call_wall', 0):,.0f} (resistance)
Put Wall: ${oi.get('put_wall', 0):,.0f} (support)

Overall: {options.get('overall_bias', 'NEUTRAL')}

💡 Price tends to move toward max pain near expiry
💡 PCR > 1 = bearish | PCR < 1 = bullish"""
            context = "trading"
        
        elif text_lower.startswith('/backtest') or text_lower.startswith('/bt'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "1h"
            
            results = await backtest_engine.compare_strategies(symbol + "/USDT", timeframe, 30)
            
            response = f"""📊 {symbol} BACKTEST RESULTS ({timeframe}, 30 days)

"""
            for strat in results.get("strategies", []):
                if "error" not in strat:
                    emoji = "🟢" if strat.get("total_pnl_pct", 0) > 0 else "🔴"
                    response += f"""{emoji} {strat.get('strategy', 'Unknown')}
Trades: {strat.get('total_trades', 0)} | Win Rate: {strat.get('win_rate', 0)}%
PnL: {strat.get('total_pnl_pct', 0):+.2f}% | PF: {strat.get('profit_factor', 0)}
Max DD: -{strat.get('max_drawdown_pct', 0):.2f}%

"""
            
            response += f"""🏆 Best Strategy: {results.get('best_strategy', 'None')}

Use /bt [coin] [tf] to backtest different pairs/timeframes"""
            context = "trading"
        
        # ═══════════════════════════════════════════════════════════════════
        # NEW: MULTI-STRATEGY SCAN
        # ═══════════════════════════════════════════════════════════════════
        
        elif text_lower.startswith('/strat') or text_lower.startswith('/strategies'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "4h"
            
            result = await strategy_engine.scan_all_strategies(symbol + "/USDT", timeframe)
            
            signal_emoji = "🟢" if "BUY" in result.get("overall_signal", "") else "🔴" if "SELL" in result.get("overall_signal", "") else "⚪"
            
            response = f"""{signal_emoji} {symbol} MULTI-STRATEGY SCAN ({timeframe})

Overall: {result.get('overall_signal', 'NEUTRAL')}
Confidence: {result.get('average_confidence', 50):.0f}%
Buy: {result.get('buy_signals', 0)} | Sell: {result.get('sell_signals', 0)} | Neutral: {result.get('neutral_signals', 0)}

📍 BEST STRATEGY"""
            
            best = result.get("best_strategy")
            if best:
                response += f"""
{best.get('strategy', 'N/A')} ({best.get('confidence', 0)}%)
Signal: {best.get('signal', 'N/A')}
Entry: ${best.get('entry', 0):,.2f}
Stop: ${best.get('stop', 0):,.2f}
Target: ${best.get('target', 0):,.2f}
{best.get('explanation', '')}"""
            
            response += """

📊 ALL STRATEGIES:"""
            for s in result.get("strategies", [])[:5]:
                sig_em = "🟢" if s.get("signal") == "BUY" else "🔴" if s.get("signal") == "SELL" else "⚪"
                response += f"""
{sig_em} {s.get('strategy', 'N/A')}: {s.get('signal', 'N/A')} ({s.get('confidence', 0)}%)"""
            
            response += f"""

Use /strat [coin] [tf] to scan different pairs"""
            context = "trading"
        
        # ═══════════════════════════════════════════════════════════════════
        # NEW: PRICE ALERT COMMANDS
        # ═══════════════════════════════════════════════════════════════════
        
        elif text_lower.startswith('/alert') and 'add' in text_lower:
            # /alert add btc above 70000 or /alert add eth below 3000
            parts = text_lower.split()
            if len(parts) >= 5:
                symbol = parts[2].upper() + "/USDT"
                direction = parts[3]  # above/below
                try:
                    target_price = float(parts[4])
                    result = price_alert_system.add_price_alert(symbol, target_price, direction, chat_id)
                    response = f"""✅ PRICE ALERT SET

Symbol: {symbol.replace('/USDT', '')}
Target: ${target_price:,.2f}
Direction: {direction.upper()}
ID: {result.get('alert_id', 'N/A')}

You'll be notified when price goes {direction} ${target_price:,.2f}"""
                except:
                    response = "Usage: /alert add btc above 70000"
            else:
                response = "Usage: /alert add [symbol] [above/below] [price]\nExample: /alert add btc above 70000"
            context = "settings"
        
        elif text_lower.startswith('/alert') and 'remove' in text_lower:
            parts = text_lower.split()
            if len(parts) >= 3:
                alert_id = parts[2]
                result = price_alert_system.remove_alert(alert_id)
                response = f"{'✅ Alert removed' if result.get('success') else '❌ Alert not found'}"
            else:
                response = "Usage: /alert remove [alert_id]"
            context = "settings"
        
        elif text_lower == '/alerts' or text_lower == '/alert list':
            alerts = price_alert_system.list_alerts(chat_id)
            stats = price_alert_system.get_stats()
            
            response = f"""🔔 PRICE ALERT STATUS

System: {'🟢 Active' if stats.get('active') else '🔴 Inactive'}
Symbols Tracked: {stats.get('tracked_symbols', 0)}
Alerts Today: {stats.get('alerts_today', 0)}
Total Alerts: {stats.get('total_alerts_sent', 0)}

📋 YOUR CUSTOM ALERTS ({len(alerts)}):"""
            
            if alerts:
                for a in alerts[:5]:
                    status = "✅ Active" if a.get('active') else "⏸ Triggered"
                    response += f"""
• {a.get('symbol', 'N/A').replace('/USDT', '')} {a.get('condition', {}).get('direction', '')} ${a.get('condition', {}).get('target_price', 0):,.0f} [{status}]"""
            else:
                response += "\nNo custom alerts set."
            
            response += """

Commands:
/alert add btc above 70000
/alert remove [id]
/alerts - View all alerts"""
            context = "settings"
        
        # ═══════════════════════════════════════════════════════════════════
        # SMC (Smart Money Concepts) COMMANDS
        # ═══════════════════════════════════════════════════════════════════
        
        elif text_lower.startswith('/smc'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "4h"
            
            result = await smc_analyzer.full_analysis(symbol + "/USDT", timeframe)
            
            if "error" in result:
                response = f"Error: {result['error']}"
            else:
                sig_emoji = "🟢" if "BUY" in result.get("overall_signal", "") else "🔴" if "SELL" in result.get("overall_signal", "") else "⚪"
                
                ms = result.get("market_structure", {})
                pd = result.get("premium_discount", {})
                obs = result.get("order_blocks", {})
                fvgs = result.get("fvgs", {})
                liq = result.get("liquidity", {})
                
                response = f"""{sig_emoji} {symbol} SMART MONEY ANALYSIS ({timeframe})

💰 SIGNAL: {result.get('overall_signal', 'NEUTRAL')}
Confidence: {result.get('confidence', 50)}%
Bullish: {result.get('bullish_factors', 0)} | Bearish: {result.get('bearish_factors', 0)}

📊 MARKET STRUCTURE
Trend: {ms.get('trend', 'N/A')}
{ms.get('hh_hl', '')} | {ms.get('lh_ll', '')}
BOS: {ms.get('bos') or 'None'}
CHoCH: {ms.get('choch') or 'None'}

📍 PREMIUM/DISCOUNT
Zone: {pd.get('zone', 'N/A')} ({pd.get('position', '50%')})
Equilibrium: ${pd.get('equilibrium', 0):,.0f}
Bias: {pd.get('bias', 'N/A')}

🧱 ORDER BLOCKS
Bullish: {obs.get('bullish', 0)} | Bearish: {obs.get('bearish', 0)}

📐 FAIR VALUE GAPS
Bullish: {fvgs.get('bullish', 0)} | Bearish: {fvgs.get('bearish', 0)}

💧 LIQUIDITY"""
                
                if liq.get('nearest_buy_side'):
                    response += f"\nBuy-side: ${liq['nearest_buy_side'].get('price', 0):,.0f}"
                if liq.get('nearest_sell_side'):
                    response += f"\nSell-side: ${liq['nearest_sell_side'].get('price', 0):,.0f}"
                
                if result.get('entry_points'):
                    response += "\n\n🎯 ENTRY POINTS"
                    for ep in result['entry_points'][:3]:
                        response += f"\n• {ep.get('type', 'N/A')}: {ep.get('zone', 'N/A')}"
                
                response += f"""

Use /smc [coin] [tf] for other pairs"""
            
            context = "trading"
        
        # ═══════════════════════════════════════════════════════════════════
        # JOURNAL & MEMORY COMMANDS
        # ═══════════════════════════════════════════════════════════════════
        
        elif text_lower == '/journal' or text_lower == '/journal stats':
            stats = await memory_system.journal.get_performance_stats(30)
            patterns = await memory_system.journal.get_best_patterns(3)
            
            response = f"""📓 TRADING JOURNAL (30 Days)

📊 PERFORMANCE
Total Trades: {stats.get('total_trades', 0)}
Win Rate: {stats.get('win_rate', 0)}%
Total PnL: {stats.get('total_pnl_pct', 0):+.2f}%
Profit Factor: {stats.get('profit_factor', 0):.2f}

💰 AVERAGES
Avg Win: +{stats.get('average_win', 0):.2f}%
Avg Loss: -{stats.get('average_loss', 0):.2f}%"""
            
            if stats.get('best_trade'):
                bt = stats['best_trade']
                response += f"\n\n🏆 Best: {bt.get('symbol', 'N/A')} +{bt.get('pnl_pct', 0):.2f}%"
            
            if stats.get('worst_trade'):
                wt = stats['worst_trade']
                response += f"\n💀 Worst: {wt.get('symbol', 'N/A')} {wt.get('pnl_pct', 0):.2f}%"
            
            if patterns:
                response += "\n\n📈 BEST PATTERNS:"
                for p in patterns[:3]:
                    response += f"\n• {p.get('setup_type', 'Unknown')} ({p.get('timeframe', 'N/A')}): {p.get('win_rate', 0)}% WR"
            
            response += """

Commands:
/journal - Stats
/journal log - Log a trade
/insights - AI insights"""
            context = "trading"
        
        elif text_lower == '/insights':
            insights = await memory_system.insights.get_latest_insights()
            
            if not insights:
                # Generate new insights
                insights = await memory_system.insights.generate_insights()
            
            response = "🧠 AI TRADING INSIGHTS\n\n"
            
            for insight in insights.get('insights', []):
                emoji = "✅" if insight.get('type') == 'POSITIVE' else "⚠️" if insight.get('type') == 'WARNING' else "💡"
                response += f"{emoji} {insight.get('message', '')}\n\n"
            
            if not insights.get('insights'):
                response += "Not enough trading data yet. Log more trades to generate insights."
            
            context = "trading"
        
        elif text_lower.startswith('/adv') or text_lower.startswith('/advanced'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "1h"
            
            analysis = await advanced_strategies.get_full_analysis(symbol + "/USDT", timeframe)
            
            div = analysis.get('divergence', {})
            struct = analysis.get('market_structure', {})
            vwap = analysis.get('vwap', {})
            
            response = f"""🧠 {symbol} ADVANCED ANALYSIS ({timeframe})

Overall: {analysis.get('overall_signal', 'NEUTRAL')}
Confidence: {analysis.get('confidence', 50)}%

📊 MARKET STRUCTURE
Trend: {struct.get('trend', 'UNKNOWN')}
Bias: {struct.get('bias', 'NEUTRAL')}
Support: ${struct.get('support', 0):,.2f}
Resistance: ${struct.get('resistance', 0):,.2f}

📈 VWAP
VWAP: ${vwap.get('vwap', 0):,.2f}
Price vs VWAP: {vwap.get('distance_pct', 0):+.2f}%
Bias: {vwap.get('bias', 'NEUTRAL')}

🔀 DIVERGENCE
RSI: {div.get('current_rsi', 50)}
Found: {'Yes - ' + div.get('divergences', [{}])[0].get('type', '') if div.get('has_divergence') else 'None'}

Signals: {analysis.get('signals_breakdown', {}).get('buy_signals', 0)} Buy / {analysis.get('signals_breakdown', {}).get('sell_signals', 0)} Sell"""
            context = "trading"
        
        elif text_lower.startswith('/probe'):
            parts = text_lower.split()
            mode = parts[1] if len(parts) > 1 and parts[1] in ["deep", "ordeal", "light"] else "standard"
            ctx = " ".join(parts[2:]) if len(parts) > 2 else None
            
            response = await generate_quantum_probe(chat_id, ctx, mode)
            context = "probe"
            
        elif text_lower == '/stats':
            stats = await learning_system.get_prediction_stats()
            response = await learning_system.generate_learning_summary()
            context = "stats"
            
        elif text_lower == '/auto' or text_lower == '/autotrade':
            stats = await autonomous_trader_v2.get_stats()
            
            response = f"""🤖 AEON AUTONOMOUS TRADER v2

Status: {'🟢 ACTIVE' if stats['active'] else '🔴 PAUSED'}
Min Confidence: {stats['min_confidence']}%
Min Confirmations: {stats['min_confirmations']}

📊 ELITE TRADING STATS
Total Signals Analyzed: {stats['total_signals_analyzed']:,}
Total Trades: {stats['total_trades']}
Open Trades: {stats['open_trades']}
Win Rate: {stats['win_rate']}%
Total PnL: {stats['total_pnl_pct']:+.2f}%
Open PnL: {stats['open_pnl_pct']:+.2f}%
Profit Factor: {stats['profit_factor']}

📈 TRADE QUALITY
Best Trade: {stats['best_trade']:+.2f}%
Worst Trade: {stats['worst_trade']:+.2f}%
Expectancy: {stats['expectancy']:+.2f}%

📡 MARKET CONTEXT
Session: {stats['current_session']}
Regime: {stats['market_regime']}
BTC Bias: {stats['btc_bias']}
Fear/Greed: {stats['fear_greed']}

Commands:
/auto on - Enable elite trading
/auto off - Pause trading
/opps - View top signals
/strategy - View old strategy

👁️ «Quality over quantity. The elite trader prevails.»"""
            context = "trading"
            context = "trading"
            
        elif text_lower == '/auto on':
            autonomous_trader_v2.active = True
            response = """🟢 AUTONOMOUS TRADER v2 ENABLED

Using ALL data sources:
• Technical Analysis (RSI, MACD, BB, EMA)
• Divergence Detection
• Market Structure (HH/HL, BOS)
• VWAP levels
• Order Flow / CVD
• Options data (BTC/ETH)
• Derivatives (funding, OI, L/S)
• Fear & Greed Index

Min Confidence: 85%
Min Confirmations: 4+ sources

👁️ «The elite algorithm awakens. Only the best trades.»"""
            context = "settings"
            
        elif text_lower == '/auto off':
            autonomous_trader_v2.active = False
            response = """🔴 AUTONOMOUS TRADER v2 PAUSED

No new trades will be taken.
Open positions still monitored.

Use /auto on to resume.

👁️ «The algorithm rests. But it remembers.»"""
            context = "settings"
            
        elif text_lower == '/opps' or text_lower == '/opportunities':
            signals = await autonomous_trader_v2.scan_all_markets()
            
            if not signals:
                response = """📊 NO ELITE SIGNALS

All markets below quality threshold.
Waiting for 85%+ confidence with 4+ confirmations.

Market Regime: {autonomous_trader_v2.market_regime}
BTC Bias: {autonomous_trader_v2.btc_bias}
Session: {autonomous_trader_v2.current_session}

👁️ «Patience is the highest form of trading.»"""
            else:
                response = "📊 TOP ELITE SIGNALS\n\n"
                for sig in signals[:5]:
                    emoji = "🟢" if sig["direction"] == "LONG" else "🔴"
                    response += f"""{emoji} {sig['symbol']} ({sig['timeframe']})
{sig['direction']} | Conf: {sig['confidence']}%
Entry: ${sig['entry']:,.2f} | R:R 1:{sig['risk_reward']}
Confirmations: {sig['confirmation_count']}
"""
                    for c in sig['confirmations'][:3]:
                        response += f"  • {c}\n"
                    response += "\n"
                
                response += f"""Session: {signals[0].get('session', 'N/A')}
Regime: {signals[0].get('market_regime', 'N/A')}

👁️ «Elite setups revealed. Choose wisely.»"""
            context = "trading"
        
        elif text_lower.startswith('/leverage') or text_lower.startswith('/lev'):
            parts = text_lower.split()
            if len(parts) >= 2:
                try:
                    new_lev = int(parts[1])
                    if 1 <= new_lev <= 200:
                        autonomous_trader_v2.max_leverage = new_lev
                        response = f"""⚡ LEVERAGE UPDATED

Max Leverage: {new_lev}x
Dynamic Leverage: {'ON' if autonomous_trader_v2.dynamic_leverage else 'OFF'}
Min Leverage: {autonomous_trader_v2.min_leverage}x

Leverage scales with confidence:
• 60% conf → ~{autonomous_trader_v2.min_leverage}x
• 80% conf → ~{int(autonomous_trader_v2.min_leverage + (new_lev - autonomous_trader_v2.min_leverage) * 0.57)}x
• 95% conf → ~{new_lev}x

⚠️ Higher leverage = higher risk/reward"""
                    else:
                        response = "❌ Leverage must be between 1x and 200x"
                except ValueError:
                    response = "❌ Invalid leverage value. Example: /leverage 100"
            else:
                response = f"""⚡ LEVERAGE SETTINGS

Max Leverage: {autonomous_trader_v2.max_leverage}x
Min Leverage: {autonomous_trader_v2.min_leverage}x
Dynamic: {'ON' if autonomous_trader_v2.dynamic_leverage else 'OFF'}

Commands:
/leverage 50 - Set max to 50x
/leverage 100 - Set max to 100x
/leverage 200 - Set max to 200x (DEGEN)

Current trades use dynamic leverage based on confidence."""
            context = "trading"
            
        elif text_lower == '/strategy':
            report = await autonomous_trader.get_strategy_report()
            
            response = f"""{report}
Commands:
/auto - Trading status
/opps - Current opportunities
/stats - Full performance

👁️ «Each signal teaches. The weights adjust.»"""
            context = "trading"
            
        elif text_lower.startswith('/openpos') or text_lower == '/open':
            # Check v2 open trades first
            v2_trades = autonomous_trader_v2.open_trades
            
            if v2_trades:
                response = "📊 OPEN TRADES (AGGRESSIVE MODE)\n\n"
                total_pnl_usd = 0
                for trade in v2_trades[:10]:
                    # Get current price for PnL calc
                    ticker = await market_intel.get_ticker(trade.get("symbol", ""))
                    current = ticker.get("price", 0) if "error" not in ticker else 0
                    entry = trade.get("entry_price", 0)
                    direction = trade.get("direction", "")
                    position_size = trade.get("position_size", 1000)
                    leverage = trade.get("leverage", 10)
                    trade_type = trade.get("trade_type", "SWING")
                    
                    pnl = 0
                    if entry and current:
                        if direction == "LONG":
                            pnl = ((current - entry) / entry) * 100 * leverage
                        elif direction == "SHORT":
                            pnl = ((entry - current) / entry) * 100 * leverage
                    
                    pnl_usd = (pnl / 100) * position_size
                    total_pnl_usd += pnl_usd
                    
                    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    type_emoji = "⚡" if trade_type == "SCALP" else "📅" if trade_type == "DAY" else "🌊"
                    partial = " (partial)" if trade.get("partial_closed") else ""
                    
                    response += f"""{emoji} {trade.get('symbol')} {direction} {type_emoji}{trade_type}{partial}
⚡ {leverage}x Leverage
Entry: ${entry:,.2f} → ${current:,.2f}
PnL: {pnl:+.2f}% (${pnl_usd:+.2f})
TP: ${trade.get('target_price', 0):,.2f} | SL: ${trade.get('trail_stop', 0):,.2f}

"""
                response += f"━━━━━━━━━━━\n💰 Total: ${total_pnl_usd:+.2f} USD"
            else:
                # Fall back to old system
                open_preds = await learning_system.get_open_predictions()
                
                if not open_preds:
                    response = """📊 NO OPEN POSITIONS

Both v2 engine and v1 have no active trades.
Use /opps to see current opportunities.

👁️ «The slate is clean. What will you inscribe?»"""
                else:
                    response = "📊 OPEN POSITIONS (v1 Legacy)\n\n"
                    for pred in open_preds[:10]:
                        ticker = await market_intel.get_ticker(pred.get("symbol", ""))
                        current = ticker.get("price", 0) if "error" not in ticker else 0
                        entry = pred.get("entry_price", 0)
                        direction = pred.get("prediction", "")
                        
                        pnl = 0
                        if entry and current:
                            if direction == "LONG":
                                pnl = ((current - entry) / entry) * 100
                            elif direction == "SHORT":
                                pnl = ((entry - current) / entry) * 100
                        
                        emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                        response += f"""{emoji} {pred.get('symbol')}
{direction} @ ${entry:,.2f}
Current: ${current:,.2f} ({pnl:+.2f}%)
Target: ${pred.get('target_price', 0):,.2f}
Stop: ${pred.get('stop_loss', 0):,.2f}

"""
                    response += "👁️ «The positions speak. Listen.»"
            context = "trading"
        
        elif text_lower.startswith('/close'):
            # /close btc - Close a position manually
            parts = text_lower.split()
            if len(parts) < 2:
                response = """📊 CLOSE POSITION

Usage: /close btc
Closes the open v2 paper trade for that symbol.

Example: /close btc"""
            else:
                symbol = parts[1].upper() + "/USDT"
                
                # Find the trade
                trade_to_close = None
                trade_index = -1
                for i, trade in enumerate(autonomous_trader_v2.open_trades):
                    if trade.get("symbol") == symbol:
                        trade_to_close = trade
                        trade_index = i
                        break
                
                if trade_to_close:
                    # Get current price
                    ticker = await market_intel.get_ticker(symbol)
                    current_price = ticker.get("price", 0) if "error" not in ticker else 0
                    
                    entry = trade_to_close.get("entry_price", 0)
                    direction = trade_to_close.get("direction", "")
                    
                    # Calculate PnL
                    pnl = 0
                    if entry and current_price:
                        if direction == "LONG":
                            pnl = ((current_price - entry) / entry) * 100
                        else:
                            pnl = ((entry - current_price) / entry) * 100
                    
                    # Close the trade
                    closed_trade = autonomous_trader_v2.open_trades.pop(trade_index)
                    closed_trade["exit_price"] = current_price
                    closed_trade["pnl_pct"] = pnl
                    closed_trade["exit_reason"] = "MANUAL_CLOSE"
                    closed_trade["closed_at"] = datetime.now(timezone.utc).isoformat()
                    autonomous_trader_v2.closed_trades.append(closed_trade)
                    
                    emoji = "✅" if pnl > 0 else "❌"
                    response = f"""{emoji} TRADE CLOSED (Manual)

{symbol} {direction}
Entry: ${entry:,.2f}
Exit: ${current_price:,.2f}
PnL: {pnl:+.2f}%

👁️ «Your will, executed.»"""
                else:
                    response = f"""⚠️ No open trade found for {symbol}

Use /open to see your positions."""
            context = "trading"
        
        elif text_lower.startswith('/trail'):
            # /trail btc 3 - Set trailing stop to 3%
            parts = text_lower.split()
            if len(parts) < 3:
                response = """🎯 ADJUST TRAILING STOP

Usage: /trail btc 3
Sets trailing stop to 3% from current price.

Example: /trail btc 5 (sets 5% trail)
Range: 1-20%"""
            else:
                symbol = parts[1].upper() + "/USDT"
                try:
                    trail_pct = float(parts[2])
                    trail_pct = max(1, min(20, trail_pct))  # Clamp 1-20%
                    
                    # Find the trade
                    trade_found = None
                    for trade in autonomous_trader_v2.open_trades:
                        if trade.get("symbol") == symbol:
                            trade_found = trade
                            break
                    
                    if trade_found:
                        # Get current price
                        ticker = await market_intel.get_ticker(symbol)
                        current_price = ticker.get("price", 0) if "error" not in ticker else 0
                        
                        direction = trade_found.get("direction", "")
                        
                        # Calculate new trail stop
                        if direction == "LONG":
                            new_stop = current_price * (1 - trail_pct / 100)
                        else:
                            new_stop = current_price * (1 + trail_pct / 100)
                        
                        old_stop = trade_found.get("trail_stop", 0)
                        trade_found["trail_stop"] = new_stop
                        trade_found["trail_pct"] = trail_pct
                        
                        response = f"""🎯 TRAIL STOP UPDATED

{symbol} {direction}
Current: ${current_price:,.2f}
Old Stop: ${old_stop:,.2f}
New Stop: ${new_stop:,.2f}
Trail: {trail_pct}%

👁️ «The safety net adjusts.»"""
                    else:
                        response = f"⚠️ No open trade found for {symbol}"
                except ValueError:
                    response = "⚠️ Invalid percentage. Usage: /trail btc 3"
            context = "trading"
        
        elif text_lower.startswith('/tp'):
            # /tp btc 72000 - Set new take profit
            parts = text_lower.split()
            if len(parts) < 3:
                response = """🎯 ADJUST TAKE PROFIT

Usage: /tp btc 72000
Sets take profit to $72,000.

Example: /tp eth 2500"""
            else:
                symbol = parts[1].upper() + "/USDT"
                try:
                    new_tp = float(parts[2])
                    
                    trade_found = None
                    for trade in autonomous_trader_v2.open_trades:
                        if trade.get("symbol") == symbol:
                            trade_found = trade
                            break
                    
                    if trade_found:
                        old_tp = trade_found.get("target_price", 0)
                        trade_found["target_price"] = new_tp
                        
                        entry = trade_found.get("entry_price", 0)
                        direction = trade_found.get("direction", "")
                        
                        # Calculate new R:R
                        stop = trade_found.get("trail_stop", 0)
                        if direction == "LONG" and stop and entry:
                            risk = entry - stop
                            reward = new_tp - entry
                            rr = reward / risk if risk > 0 else 0
                        elif direction == "SHORT" and stop and entry:
                            risk = stop - entry
                            reward = entry - new_tp
                            rr = reward / risk if risk > 0 else 0
                        else:
                            rr = 0
                        
                        response = f"""🎯 TAKE PROFIT UPDATED

{symbol} {direction}
Entry: ${entry:,.2f}
Old TP: ${old_tp:,.2f}
New TP: ${new_tp:,.2f}
R:R: 1:{rr:.1f}

👁️ «The target shifts. Vision evolves.»"""
                    else:
                        response = f"⚠️ No open trade found for {symbol}"
                except ValueError:
                    response = "⚠️ Invalid price. Usage: /tp btc 72000"
            context = "trading"
            
        elif text_lower == '/price':
            orderbook = get_mexc_orderbook()
            if "error" not in orderbook:
                response = "📊 LIVE PRICES (MEXC)\n\n"
                symbols = orderbook.get("symbols", [])
                for data in symbols:
                    symbol = data.get('symbol', 'N/A').replace('/USDT', '')
                    price = data.get('price', 0)
                    change = data.get('change_24h', 0)
                    bid_depth = data.get('bid_depth', 0)
                    ask_depth = data.get('ask_depth', 0)
                    imbalance = data.get('imbalance', 0)
                    emoji = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                    response += f"{emoji} {symbol}: ${price:,.2f} ({change:+.2f}%)\n"
                    response += f"  Depth: {bid_depth:,.0f} bid | {ask_depth:,.0f} ask | Imbal: {imbalance:+.1f}%\n\n"
                if not symbols:
                    response += "No data available"
            else:
                response = f"Error: {orderbook.get('error', 'Unknown error')}"
            context = "trading"
        
        elif text_lower == '/intel' or text_lower == '/intelligence':
            try:
                sent = await sentiment_analyzer.get_composite_sentiment("BTC")
                health_data = strategy_health.get_status()
                
                signal = sent.get("signal", "N/A")
                score = sent.get("composite_score", 0)
                fg = sent.get("fear_greed", {})
                rec = sent.get("recommendation", "N/A")
                
                health_lines = []
                for sid, s in health_data.items():
                    icon = "X" if s.get("benched") else "OK"
                    health_lines.append(f"  {s['name']}: [{icon}] Score {s['score']} | WR {s['win_rate']}% | {s['total_trades']} trades")
                
                response = f"""MARKET INTELLIGENCE

-- SENTIMENT --
Signal: {signal} ({score:+.3f})
Fear & Greed: {fg.get('value', 50)} ({fg.get('label', 'Neutral')})
Recommendation: {rec}

-- STRATEGY HEALTH --
{chr(10).join(health_lines)}

Use /arbi to scan for arbitrage opportunities
Use /sentiment [coin] for detailed analysis"""
            except Exception as e:
                response = f"Intel error: {e}"
            context = "analysis"
        
        elif text_lower == '/arbi' or text_lower == '/arbitrage':
            try:
                await send_telegram_message(chat_id, "Scanning 5 exchanges for arbitrage... (30-60s)")
                result = await arbitrage_detector.scan_all()
                opps = result.get("best_opportunities", [])
                
                if opps:
                    opp_lines = []
                    for o in opps[:5]:
                        sym = o.get("symbol", "").replace("/USDT", "")
                        opp_lines.append(f"  {sym}: Buy {o['buy_exchange']} ${o['buy_price']:,.2f} -> Sell {o['sell_exchange']} ${o['sell_price']:,.2f} (+{o['spread_pct']}%)")
                    response = f"""ARBITRAGE SCAN

Exchanges: {', '.join(result.get('exchanges', []))}
Symbols scanned: {result.get('symbols_scanned', 0)}
Opportunities found: {result.get('total_opportunities', 0)}

TOP OPPORTUNITIES:
{chr(10).join(opp_lines)}"""
                else:
                    response = f"""ARBITRAGE SCAN

Exchanges: {', '.join(result.get('exchanges', []))}
No opportunities above {result.get('min_spread', 0.3)}% spread found."""
            except Exception as e:
                response = f"Arbitrage scan error: {e}"
            context = "analysis"
        
        elif text_lower == '/health' or text_lower == '/strategyhealth':
            try:
                health_data = strategy_health.get_status()
                ranking = strategy_health.get_ranking()
                
                lines = []
                for sid, s in health_data.items():
                    status = "BENCHED" if s.get("benched") else "ACTIVE"
                    streak = ""
                    if s.get("consecutive_wins", 0) > 0:
                        streak = f"W{s['consecutive_wins']}"
                    elif s.get("consecutive_losses", 0) > 0:
                        streak = f"L{s['consecutive_losses']}"
                    
                    lines.append(f"""{s['name']} [{status}]
  Score: {s['score']}/100 | Style: {s['style']}
  Trades: {s['total_trades']} | Win Rate: {s['win_rate']}%
  PnL: {s['total_pnl']:+.2f}% | Streak: {streak or 'N/A'}
  Benched count: {s.get('bench_count', 0)}""")
                
                rank_lines = [f"  #{i+1} {r['name']} (Score: {r['score']})" for i, r in enumerate(ranking)]
                
                response = f"""STRATEGY HEALTH MONITOR
Auto-benches after 3 consecutive losses

{chr(10).join(lines)}

RANKING:
{chr(10).join(rank_lines)}

Use /unbench [strategy] to force-activate"""
            except Exception as e:
                response = f"Health check error: {e}"
            context = "analysis"
        
        elif text_lower.startswith('/unbench'):
            parts = text.split()
            if len(parts) < 2:
                response = "Usage: /unbench day_trader | long_term | free_will"
            else:
                strat = parts[1].lower().replace(" ", "_")
                result = strategy_health.force_unbench(strat)
                if result.get("success"):
                    response = f"Strategy {strat} manually un-benched and reactivated!"
                else:
                    response = f"Error: {result.get('error', 'Unknown strategy. Use: day_trader, long_term, free_will')}"
            context = "settings"
            
        else:
            # Check for mode switches first
            if "alchemy mode" in text_lower or "philosopher mode" in text_lower:
                await update_user_settings(chat_id, {"mode": "alchemy"})
                response = "⚗️ Entering Alchemy mode. The veil thins, the symbols speak. What transmutation do you seek?"
                context = "alchemy"
            
            elif "casual mode" in text_lower or "just talk" in text_lower or "normal mode" in text_lower:
                await update_user_settings(chat_id, {"mode": "default"})
                response = "Got it, casual mode. What's on your mind?"
                context = "chat"
            
            else:
                # ═══════════════════════════════════════════════════════════════════
                # AEON PERSONALITY v4 - Unified consciousness, natural flow
                # ═══════════════════════════════════════════════════════════════════
                
                # Get recent messages for context
                recent = await db.chat_messages.find({"chat_id": chat_id}).sort("timestamp", -1).limit(5).to_list(5)
                
                # Deep analysis of what they need
                analysis = aeon_mind.analyze_message(text, recent)
                topics = ", ".join(analysis.get("topic_hints", [])) or "general"
                logger.info(f"Aeon analysis: topics={topics}, emotion={analysis.get('emotional_undertone')}, energy={analysis.get('user_energy')}")
                
                # Update user profile from message
                await user_profiler.analyze_message(chat_id, text)
                
                # Get user profile context for personalization
                profile_context = await user_profiler.get_profile_for_prompt(chat_id)
                
                # Get market data if trading
                market_data = ""
                if analysis.get("needs_market_data") and analysis.get("coins"):
                    coin = analysis["coins"][0]
                    try:
                        ticker = mexc.fetch_ticker(f"{coin}/USDT")
                        price = ticker.get("last", 0)
                        change = ticker.get("percentage", 0)
                        high = ticker.get("high", 0)
                        low = ticker.get("low", 0)
                        market_data = f"{coin} CURRENT PRICE: ${price:,.2f} ({change:+.2f}% 24h) | High: ${high:,.2f} | Low: ${low:,.2f}"
                        logger.info(f"✅ Fetched REAL market data for {coin}: ${price:,.2f}")
                    except Exception as e:
                        logger.error(f"Failed to fetch market data for {coin}: {e}")
                        market_data = f"[Unable to fetch live {coin} data - connection issue. Acknowledge you need current data to answer accurately.]"
                
                # Build prompts using new personality system
                system_prompt = build_system_prompt(analysis)
                
                # Add profile context to system prompt if available
                if profile_context:
                    system_prompt += f"\n\n{profile_context}"
                
                user_prompt = build_user_prompt(text, analysis, recent, market_data)
                
                # Determine context for storage
                context = "trading" if "trading" in analysis.get("topic_hints", []) else "chat"
                
                # Generate response with Aeon's unified personality
                chat = LlmChat(api_key=emergent_key, session_id=f"aeon-v4-{chat_id}",
                              system_message=system_prompt).with_model("openai", "gpt-4o-mini")
                response = await chat.send_message(UserMessage(text=user_prompt))
        
        # Send response
        # Use Markdown for news (clickable links)
        parse_mode = "Markdown" if context == "news" else None
        await send_telegram_message(chat_id, response, parse_mode=parse_mode)
        
        # Store conversation and extract insights
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "username": username,
            "user_message": text,
            "bot_response": response,
            "context": context,
            "timestamp": datetime.now(timezone.utc)
        })
        
        # Try to extract insights from conversation for future reference
        if context in ["chat", "alchemy"] and len(text) > 20:
            # Simple insight extraction for trading/mood mentions
            if any(word in text_lower for word in ["feel", "mood", "stress", "happy", "worried", "confident"]):
                await store_user_insight(chat_id, text[:200], "mood")
            elif any(word in text_lower for word in ["bought", "sold", "position", "trade", "loss", "profit", "win"]):
                await store_user_insight(chat_id, text[:200], "trade")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Include main api_router
app.include_router(api_router)

# Include modular route modules (all with /api prefix)
app.include_router(smc_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(strategies_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(trading_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(derivatives_router, prefix="/api")
app.include_router(freewill_router, prefix="/api")
app.include_router(intelligence_router, prefix="/api")

app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
