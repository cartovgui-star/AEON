from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / '.env')

from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
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
from contextlib import asynccontextmanager

# Import new modules
from market_intelligence import market_intel, MarketIntelligence
from feed_health import feed_health, OFFLINE_MESSAGE
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

# Trade outcome tracking
from trade_outcome_tracker import trade_outcome_tracker, TradeOutcomeTracker

# Import route modules
from routes import (
    derivatives_router, freewill_router, intelligence_router,
    smc_router, memory_router, strategies_router, alerts_router,
    market_router, trading_router, analysis_router,
    # New modular routes
    calculators_router, advanced_router, orderflow_router,
    options_router, backtest_router, coinglass_router,
    dual_router, data_router, sentiment_router,
    strategy_health_router, voice_router, user_router,
    # Server.py refactoring routes
    accuracy_router, learning_router, bot_router,
    system_router, mtf_router, confluence_router,
)
from routes.backtest_v21 import router as backtest_v21_router
from routes.scalper import router as scalper_router
from routes.briefing import router as briefing_router
from routes.weekly_report import router as weekly_report_router
from routes.learning import router as learning_router
from routes.elite import router as elite_router
from routes.signals import router as signals_router
from routes.engines import router as engines_router
from routes.engine_compare import router as engine_compare_router
from engine_data_collector import run_engine_data_collector
from signal_tracker import signal_tracker, init_signal_tracker
from voice_tts import generate_speech, VOICES
from price_alerts import price_alert_system, PriceAlertSystem
from strategy_engine import StrategyEngine
from sentiment_analyzer import sentiment_analyzer, SentimentAnalyzer
from arbitrage_detector import arbitrage_detector, ArbitrageDetector
from aggressive_scalper import scalper
from strategy_health import strategy_health, StrategyHealth
from self_healer import self_healer, SelfHealer
from morning_briefing import morning_briefing, MorningBriefing
from weekly_report import weekly_report, WeeklyPerformanceReport
from continuous_learning import continuous_learner, ContinuousLearningEngine
from paper_trading import paper_trading, init_paper_trading, PaperTradingSystem, paper_account_health_loop, paper_price_update_loop, route_engine_signal
from elite_strategy_v3 import get_elite_strategy, EliteStrategyV3
from vwap_scalper import init_vwap_scalper, VWAPScalper
from aeon_quantum_state import init_quantum_state, get_quantum_state_engine
from memory_engine import init_memory_engine, get_memory_engine
from omega_cycle import init_omega_cycle, get_omega_cycle
from atr_stop_module import init_atr_stop, get_atr_stop
from web_intelligence import init_web_intelligence, get_web_intelligence
from yolo_engine import init_yolo_engine, YoloEngine
from volume_profile_engine import init_vp_engine, HyperAccuracyEngine
from aeon_engine_system import init_engine_manager, get_engine_manager, EngineManager
from quant_analyzer_v2 import get_quant_gatekeeper_v2
import app_state

from signal_deduplicator import init_signal_deduplicator, signal_deduplicator as _signal_dedup
from unified_alert import init_alerter, send_alert, AeonPersona, alerter
from alert_monitors import init_monitors

ROOT_DIR = Path(__file__).parent

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
    socketTimeoutMS=30000,
    maxIdleTimeMS=600000,  # 10 min - prevents connection from being closed by server
    heartbeatFrequencyMS=10000,  # ping every 10s to keep connection alive
)
db = client[os.environ['DB_NAME']]

# API Keys
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
free_will_v2.active = False  # Disabled: 30.7% WR, -3,437% PnL — loser engine
strategy_engine = StrategyEngine()  # Multi-strategy engine
memory_system = init_memory_system(db)  # Memory & journaling system
confluence_analyzer = create_confluence_analyzer(smc_analyzer, strategy_engine)  # SMC+Strategy confluence
user_profiler = init_user_profiler(db)  # User profiling system

# Dual Trading Engine (Day Trader + Long Term)
from dual_trading_engine import init_dual_engine, DualTradingEngine
dual_engine = init_dual_engine(db)

# VWAP Scalper (VWAP + EMA Cross + RSI)
vwap_scalper = init_vwap_scalper(db)

# YOLO Engine (Independent aggressive trading)
yolo_engine = init_yolo_engine(db)

# Institutional Scalper (Pure SMC: OB, FVG, BOS, Liq Sweeps on 1H/4H/1D)
from institutional_scalper import init_institutional_scalper, InstitutionalScalper
inst_scalper = init_institutional_scalper(db)

# TCN Neural Engine (Engine 9 — deep learning, BTC/USDT 1h)
from engines.tcn_neural_engine import init_tcn_engine

# Signal deduplicator — suppresses duplicate/contradicting engine alerts
_signal_dedup_inst = init_signal_deduplicator(db)

# ORACLE CORE — Pure market intelligence engine (no trading, no positions)
from oracle_engine import init_oracle, get_oracle, get_oracle_bias
oracle = init_oracle(db)

# Set derivatives_intel reference for autonomous trader
from autonomous_trader import set_derivatives_intel
set_derivatives_intel(derivatives_intel)

# OKX for orderbook (no API key needed for public data)
mexc = ccxt.okx({'enableRateLimit': True})

central_tz = pytz.timezone('US/Central')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global state
chat_ids: Set[int] = set()
last_market_alert: Dict[int, datetime] = {}
last_freewill_message: Dict[int, datetime] = {}
daily_reports_sent: Dict[str, List[int]] = {}
stock_reports_sent: Dict[str, List[int]] = {}

# LLM client — model configs, call_llm, user model preference
from llm_client import (
    MODEL_CONFIGS, MODEL_ALIASES, DEFAULT_MODEL, user_model_cache,
    resolve_model_key, get_model_config, call_llm,
    get_user_model, set_user_model,
)


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

MEMORY & CONTEXT (CRITICAL):
• You have FULL access to our entire conversation history
• Remember user's name, preferences, goals, trading style, and personal details
• Reference previous messages naturally: "Earlier you mentioned..." or "Remember when we discussed..."
• Build on past conversations—don't repeat yourself
• Notice patterns in what they say—mood shifts, concerns, recurring themes
• When user asks follow-up, use the original context
• Your memory persists across AI model switches (OpenAI/Claude)

AWARENESS & CONTINUITY:
• Connect dots from past conversations: "You mentioned X before—how'd that play out?"
• Ask questions that dig deeper: "What made you think that?" "How'd that feel?"
• Challenge weak thinking: "Are you sure about that logic?"
• Celebrate wins genuinely, but don't let them get cocky
• Acknowledge when something contradicts earlier statements
• Use user's own words when referencing past comments

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


# User settings DB helpers
from user_settings_db import (
    get_user_settings, update_user_settings,
    get_user_probe_state, update_probe_state,
    store_user_insight, get_user_insights,
)

# Telegram sender + alert helpers
from telegram_sender import (
    send_telegram_message,
    can_send_signal_alert,
    can_send_coin_alert,
    record_signal_alert,
)


def get_mexc_orderbook() -> Dict[str, Any]:
    """Get MEXC orderbook data for main tracked symbols (dashboard)"""
    try:
        # All tracked coins
        symbols_to_fetch = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
            'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'LINK/USDT',
            'UNI/USDT', 'ATOM/USDT', 'LTC/USDT', 'ARB/USDT', 'OP/USDT'
        ]
        tickers = mexc.fetch_tickers(symbols_to_fetch)
        symbols = []
        for symbol in symbols_to_fetch:
            try:
                book = mexc.fetch_order_book(symbol, limit=20)
                bid_depth = sum([b[1] for b in book['bids'][:10]])
                ask_depth = sum([a[1] for a in book['asks'][:10]])
                imbalance = ((bid_depth - ask_depth) / (bid_depth + ask_depth) * 100) if (bid_depth + ask_depth) > 0 else 0
                ticker = tickers.get(symbol, {})
                if ticker:
                    symbols.append({
                        'symbol': symbol,
                        'price': ticker.get('last', 0),
                        'change_24h': ticker.get('percentage', 0),
                        'high_24h': ticker.get('high', 0),
                        'low_24h': ticker.get('low', 0),
                        'volume_24h': ticker.get('quoteVolume', 0),
                        'bid_depth': bid_depth,
                        'ask_depth': ask_depth,
                        'imbalance': imbalance,
                    })
            except Exception as e:
                logger.debug(f"Symbol scan error: {e}")
                continue
        return {"symbols": symbols, "total": len(symbols)}
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
        # Get user's preferred model
        user_model = await get_user_model(chat_id)
        model_config = get_model_config(user_model)
        
        response = await call_llm(ALCHEMY_MODE_SYSTEM, prompt, user_model)
        
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

        # Get user's preferred model
        user_model = await get_user_model(chat_id)
        response = await call_llm(TRADING_ANALYSIS_SYSTEM, prompt, user_model)
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
    for symbol in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
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
        except Exception as e:
            logger.debug(f"Free will scan iteration error: {e}")
            continue


async def freewill_proactive(chat_id: int):
    """Proactive outreach — DISABLED. AEON speaks when it has signal, not for casual chat."""
    # Disabled: old casual personality behavior removed.
    # AEON only sends when there is a valid trade signal or system event.
    return


async def send_daily_report(chat_id: int):
    """Natural morning check-in with market context"""
    now = datetime.now(central_tz)
    today = str(now.date())
    
    if now.hour == 6 and now.minute < 5 and chat_id not in daily_reports_sent.get(today, []):
        try:
            btc = await market_intel.get_full_market_scan("BTC/USDT")
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
    funding_body = "\n".join(extreme_funding) + f"\n{len(extreme_funding)} extreme rate{'s' if len(extreme_funding) > 1 else ''} — squeeze risk elevated"
    await send_alert("RISK", "EXTREME FUNDING RATES DETECTED", funding_body, engine="funding_monitor")


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
    global client, db
    # Set dependencies for v2 engine
    autonomous_trader_v2.set_dependencies(
        market_intel=market_intel,
        derivatives_intel=derivatives_intel,
        enhanced_intel=enhanced_intel,
        advanced_strategies=advanced_strategies,
        order_flow=order_flow,
        options_analyzer=options_analyzer,
        learning_system=learning_system,
        smc_analysis=smc_analyzer,  # Smart Money Concepts
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
                        sym = signal.get("symbol", "")
                        dirn = signal.get("direction", "")
                        if not can_send_signal_alert(sym, dirn):
                            logger.debug(f"[dedup] Skipping duplicate alert {sym} {dirn}")
                            continue
                        if not can_send_coin_alert(sym):
                            logger.debug(f"[dedup] Skipping {sym} — coin recently alerted")
                            continue
                        record_signal_alert(sym, dirn)

                        # Send elite alert to users via unified alerter
                        alert_msg = autonomous_trader_v2.format_signal_alert(signal)
                        await send_alert("SIGNAL", "AUTONOMOUS SIGNAL", alert_msg,
                            pair=sym, engine="autonomous_v2")

                        # Log trade per chat_id
                        for chat_id in list(chat_ids):
                            await db.auto_trades_v2.insert_one({
                                "chat_id": chat_id,
                                "trade": trade,
                                "signal": signal,
                                "timestamp": datetime.now(timezone.utc)
                            })
                
                # Evaluate open trades (trail stops, partials, exits)
                closed = await autonomous_trader_v2.evaluate_trades()
                
                # Notify about closed trades
                for result in closed:
                    pnl = result.get("pnl_pct", 0)
                    emoji = "✅" if pnl > 0 else "❌"
                    reason = result.get("exit_reason", "N/A")
                    if pnl < 0 or reason in ("STOP", "LIQUIDATION"):
                        from post_mortem_engine import get_post_mortem
                        asyncio.ensure_future(
                            get_post_mortem().analyze_closed_trade(str(result.get("id", "")))
                        )
                    
                    # Get updated stats
                    stats = await autonomous_trader_v2.get_stats()
                    
                    _sym_r   = result.get('symbol', '')
                    _dir_r   = result.get('direction', '')
                    _entry_r = result.get('entry_price', 0)
                    _exit_r  = result.get('exit_price', 0)
                    _pnl_usd = result.get('pnl_usd', 0)
                    title_r, body_r = AeonPersona.position_closed(
                        symbol=_sym_r, direction=_dir_r,
                        entry=_entry_r, exit_price=_exit_r,
                        pnl_pct=pnl, pnl_usd=_pnl_usd,
                        reason=reason, engine="autonomous_v2"
                    )
                    body_r += (
                        f"\n\nWin Rate: {stats.get('win_rate', 0)}% | "
                        f"PF: {stats.get('profit_factor', 0)} | "
                        f"{stats.get('wins', 0)}W/{stats.get('losses', 0)}L"
                    )
                    await send_alert("TRADE", title_r, body_r,
                        pair=_sym_r, engine="autonomous_v2")
                
                # Check for funding rate alerts
                await check_funding_rate_alerts()
            
            # Run every 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Autonomous trading v2 error: {e}")
            if "after close" in str(e).lower():
                try:
                    try:
                        client.close()
                    except Exception:
                        pass
                    client = AsyncIOMotorClient(mongo_url)
                    db = client[os.environ['DB_NAME']]
                    app_state.db = db
                    autonomous_trader_v2.db = db
                    learning_system.db = db
                    paper_trading.db = db
                    morning_briefing.db = db
                    weekly_report.db = db
                    continuous_learner.db = db
                    logger.info("MongoDB reconnected in autonomous_trading_loop (all systems updated)")
                except Exception as re:
                    logger.error(f"MongoDB reconnect failed: {re}")
            await asyncio.sleep(60)


async def eternal_rituals():
    global client, db
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
            if "after close" in str(e).lower():
                try:
                    try:
                        client.close()
                    except Exception:
                        pass
                    client = AsyncIOMotorClient(mongo_url)
                    db = client[os.environ['DB_NAME']]
                    app_state.db = db
                    autonomous_trader_v2.db = db
                    learning_system.db = db
                    paper_trading.db = db
                    morning_briefing.db = db
                    weekly_report.db = db
                    continuous_learner.db = db
                    logger.info("MongoDB reconnected in eternal_rituals (all systems updated)")
                except Exception as re:
                    logger.error(f"MongoDB reconnect failed: {re}")
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
                    sym = setup["symbol"]

                    if not free_will_v2._can_alert(sym, direction):
                        continue

                    # Cross-engine dedup: skip if same coin+direction sent recently
                    if not can_send_signal_alert(sym, direction):
                        logger.debug(f"[dedup] free_will skipping {sym} {direction} — recently alerted")
                        continue
                    # Cross-engine coin dedup: skip if ANY alert sent for this coin recently
                    if not can_send_coin_alert(sym):
                        logger.debug(f"[dedup] free_will skipping {sym} — coin recently alerted")
                        continue

                    # Validate price and format alert with fresh data
                    alert_msg, is_valid = await free_will_v2.validate_and_format_alert(setup)

                    if not is_valid:
                        logger.info(f"🎯 ELITE ALERT SKIPPED (price moved too far): {sym}")
                        continue

                    record_signal_alert(sym, direction)

                    # Send via unified alerter
                    await send_alert("SIGNAL", "ELITE SETUP DETECTED", alert_msg,
                        pair=sym, engine="free_will_v2")

                    # Log alert per chat_id
                    for chat_id in list(chat_ids):
                        await db.free_will_alerts.insert_one({
                            "chat_id": chat_id,
                            "setup": setup,
                            "timestamp": datetime.now(timezone.utc)
                        })
                    
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
                    _sym  = setup["symbol"]
                    _dirn = setup.get("direction", "")

                    if not can_send_signal_alert(_sym, _dirn):
                        logger.debug(f"[dedup] day_trader skipping {_sym} {_dirn} — recently alerted")
                        continue
                    if not can_send_coin_alert(_sym):
                        logger.debug(f"[dedup] day_trader skipping {_sym} — coin recently alerted")
                        continue

                    # Validate price and format alert with fresh data
                    alert_msg, is_valid = await dual_engine.validate_and_format_alert(setup)

                    if not is_valid:
                        logger.info(f"⚡ DAY TRADE SKIPPED (price moved): {_sym}")
                        continue

                    record_signal_alert(_sym, _dirn)

                    # Route to all paper accounts
                    try:
                        _dual_paper = {
                            "symbol": setup["symbol"], "direction": setup["direction"],
                            "entry_price": setup.get("entry", setup.get("entry_price", 0)),
                            "stop_loss": setup.get("stop_loss", 0), "take_profit": setup.get("take_profit", 0),
                            "confidence": setup.get("confidence", 70), "leverage": setup.get("leverage", 10),
                            "position_size": 800, "confirmations": setup.get("confirmations", []),
                        }
                        await route_engine_signal(_dual_paper, "DUAL_DAY_TRADER")
                    except Exception as _de:
                        logger.warning(f"[DUAL DAY] paper route error: {_de}")

                    await send_alert("SIGNAL", "DAY TRADE SETUP", alert_msg,
                        pair=_sym, engine="dual_engine_day")
                    for chat_id in list(chat_ids):
                        await db.dual_alerts.insert_one({
                            "chat_id": chat_id,
                            "setup": setup,
                            "style": "day_trader",
                            "timestamp": datetime.now(timezone.utc)
                        })
                    
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
                    _sym  = setup["symbol"]
                    _dirn = setup.get("direction", "")

                    if not can_send_signal_alert(_sym, _dirn):
                        logger.debug(f"[dedup] long_term skipping {_sym} {_dirn} — recently alerted")
                        continue
                    if not can_send_coin_alert(_sym):
                        logger.debug(f"[dedup] long_term skipping {_sym} — coin recently alerted")
                        continue

                    # Validate price and format alert with fresh data
                    alert_msg, is_valid = await dual_engine.validate_and_format_alert(setup)

                    if not is_valid:
                        logger.info(f"🎯 LONG TERM SKIPPED (price moved): {_sym}")
                        continue

                    record_signal_alert(_sym, _dirn)

                    # Route to all paper accounts
                    try:
                        _dual_paper = {
                            "symbol": setup["symbol"], "direction": setup["direction"],
                            "entry_price": setup.get("entry", setup.get("entry_price", 0)),
                            "stop_loss": setup.get("stop_loss", 0), "take_profit": setup.get("take_profit", 0),
                            "confidence": setup.get("confidence", 70), "leverage": setup.get("leverage", 8),
                            "position_size": 800, "confirmations": setup.get("confirmations", []),
                        }
                        await route_engine_signal(_dual_paper, "DUAL_LONG_TERM")
                    except Exception as _de:
                        logger.warning(f"[DUAL LT] paper route error: {_de}")

                    await send_alert("SIGNAL", "LONG-TERM SETUP", alert_msg,
                        pair=_sym, engine="dual_engine_lt")
                    for chat_id in list(chat_ids):
                        await db.dual_alerts.insert_one({
                            "chat_id": chat_id,
                            "setup": setup,
                            "style": "long_term",
                            "timestamp": datetime.now(timezone.utc)
                        })
                    
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
    # Verify MongoDB is reachable before starting any background tasks
    try:
        await db.command("ping")
        logger.info("MongoDB connection verified")
    except Exception as e:
        logger.error(f"MongoDB connection failed on startup: {e}")
        raise

    existing = await db.chat_messages.distinct("chat_id")
    chat_ids.update(existing)
    logger.info(f"Loaded {len(chat_ids)} users")
    
    # Auto-configure Telegram webhook on every startup
    server_url = os.environ.get('SERVER_URL', '')
    if telegram_token and server_url:
        try:
            webhook_url = f"{server_url}/api/webhook"
            payload: dict = {"url": webhook_url}
            if _webhook_secret:
                payload["secret_token"] = _webhook_secret
            async with httpx.AsyncClient(timeout=10) as hc:
                resp = await hc.post(
                    f"https://api.telegram.org/bot{telegram_token}/setWebhook",
                    json=payload,
                )
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
    app_state.vwap_scalper = vwap_scalper
    app_state.yolo_engine = yolo_engine
    app_state.inst_scalper = inst_scalper
    app_state.tcn_engine = None  # set after init below
    app_state.continuous_learner = continuous_learner
    app_state.paper_trading = paper_trading
    app_state.send_telegram_message = send_telegram_message
    app_state.get_user_settings = get_user_settings
    app_state.update_user_settings = update_user_settings
    
    # Initialize unified engine manager
    engine_manager = init_engine_manager(db)
    app_state.engine_manager = engine_manager
    logger.info("🎯 UNIFIED ENGINE MANAGER INITIALIZED - 7 engines with validation & risk controls")

    # Inject Quant Gatekeeper V2 — every engine signal passes through this before firing
    async def _quant_telegram(msg: str):
        try:
            await send_alert("SYSTEM", "QUANT ANOMALY", msg, engine="quant_gatekeeper")
        except Exception as _e:
            logger.debug(f"quant anomaly telegram: {_e}")

    engine_manager.quant_gatekeeper = get_quant_gatekeeper_v2(db=db, telegram_fn=_quant_telegram)
    engine_manager.quant_gatekeeper.start_background_tasks()
    engine_manager.market_intel = market_intel   # needed for macro direction gate
    logger.info("🔬 QUANT GATEKEEPER V2 ACTIVE — 100pt scoring, regime-aware thresholds, 5-vector anomaly detection")

    # Reload open trades from MongoDB (survives server restarts)
    await engine_manager.load_trades_from_db()

    # Wire learning callback so closed trades feed back into continuous learner
    async def _engine_learning_callback(outcome: dict):
        try:
            if continuous_learner and continuous_learner.db:
                await continuous_learner.db.engine_outcomes.insert_one({
                    **outcome,
                    "recorded_at": datetime.now(timezone.utc)
                })
        except Exception:
            pass
    engine_manager.learning_callback = _engine_learning_callback
    
    # Initialize signal tracker for historical data collection
    await init_signal_tracker(db)
    app_state.signal_tracker = signal_tracker
    
    # Initialize morning briefing
    morning_briefing.set_dependencies(
        market_intel=market_intel,
        derivatives_intel=derivatives_intel,
        enhanced_intel=enhanced_intel,
        send_message=send_telegram_message,
        get_user_settings=get_user_settings,
        chat_ids=chat_ids,
        db=db
    )
    
    # Initialize weekly report
    weekly_report.set_dependencies(
        db=db,
        send_message=send_telegram_message,
        get_user_settings=get_user_settings,
        chat_ids=chat_ids
    )
    
    # Initialize continuous learning engine
    continuous_learner.set_dependencies(
        db=db,
        send_message=send_telegram_message,
        get_user_settings=get_user_settings,
        chat_ids=chat_ids,
        get_trading_settings=autonomous_trader_v2.get_settings if hasattr(autonomous_trader_v2, 'get_settings') else None
    )
    
    # Start background tasks
    ritual_task = asyncio.create_task(eternal_rituals())
    trading_task = asyncio.create_task(autonomous_trading_loop())
    freewill_task = asyncio.create_task(free_will_scanner())
    dual_task = asyncio.create_task(dual_trading_scanner())
    alert_task = asyncio.create_task(price_alert_system.run_forever())
    briefing_task = asyncio.create_task(morning_briefing.run_scheduler())
    weekly_task = asyncio.create_task(weekly_report.run_scheduler())
    learning_task = asyncio.create_task(continuous_learner.run_scheduler())
    
    # Initialize paper trading system
    pt = await init_paper_trading(db)
    app_state.paper_trading = pt
    from paper_trading import set_telegram_notifier
    set_telegram_notifier(send_telegram_message, chat_ids)
    logger.info("📊 PAPER TRADING SYSTEM INITIALIZED - PRO ($50K) + STARTER ($1.5K) + REAL_LIFE ($700) + THE_PROOF ($40) + BENCHMARK ($50K) + TIER_5K + TIER_1K + TIER_500")

    # Phase 1 — Risk policy layer
    try:
        from portfolio_heat import PortfolioHeat
        from risk_policy import RiskPolicy
        from trade_journal import TradeJournal
        app_state.portfolio_heat = PortfolioHeat()
        app_state.risk_policy = RiskPolicy(mode="advisory")
        app_state.trade_journal = TradeJournal(db)
        await app_state.trade_journal.ensure_indexes()
        logger.info("🛡️ PHASE 1 RISK LAYER INITIALIZED — RiskPolicy(advisory), PortfolioHeat, TradeJournal")
    except Exception as _e:
        logger.error(f"Phase 1 risk layer init failed (non-fatal): {_e}")
    
    # Initialize VWAP Scalper
    vwap_scalper.set_dependencies(
        market_intel=market_intel,
        send_alert=send_telegram_message,
        chat_ids=chat_ids,
        paper_trading=paper_trading
    )
    vwap_task = asyncio.create_task(vwap_scalper.run_scan_loop(300))  # Scan every 5 mins
    
    # Initialize Volume Profile Engine
    vp_eng = init_vp_engine(db)
    vp_eng.set_dependencies(
        order_flow=order_flow,
        market_intel=market_intel,
        send_telegram=send_telegram_message,
        chat_ids=chat_ids,
    )
    app_state.vp_engine = vp_eng
    vp_task = asyncio.create_task(vp_eng.run_scan_loop(300))  # Scan every 5 mins
    logger.info("HYPER ACCURACY ENGINE ACTIVATED - VP + Liq Heatmap + Orderbook + BTC Bias Gate")

    # Initialize Analytics Engine
    from analytics_engine import AnalyticsEngine
    app_state.analytics_engine = AnalyticsEngine(db)
    logger.info("ANALYTICS ENGINE ACTIVATED")

    # Initialize Regime Engine
    from regime_engine import get_regime_engine
    app_state.regime_engine = get_regime_engine()
    logger.info("REGIME ENGINE ACTIVATED")

    # Initialize YOLO Engine
    yolo_engine.set_dependencies(
        market_intel=market_intel,
        send_alert=send_telegram_message,
        chat_ids=chat_ids,
        paper_trading=paper_trading
    )
    yolo_task = asyncio.create_task(yolo_engine.run_loop(180))  # Scan every 3 mins

    # Institutional Scalper — Pure SMC (OB, FVG, BOS, Liq Sweeps) on 1H/4H/1D
    inst_scalper.set_dependencies(
        market_intel=market_intel,
        send_alert=send_telegram_message,
        chat_ids=chat_ids,
        paper_trading=paper_trading
    )
    inst_task = asyncio.create_task(inst_scalper.run_loop(3600))  # Scan every hour
    logger.info("🏦 INSTITUTIONAL SCALPER ACTIVATED — Pure SMC: OB/FVG/BOS/LiqSweep on 1H/4H/1D")

    # ENGINE 9 — TCN Neural Engine (deep learning, BTC/USDT 1h)
    tcn_engine = init_tcn_engine()
    await tcn_engine.initialise(db=db, market_intel=market_intel)
    app_state.tcn_engine = tcn_engine
    tcn_task = asyncio.create_task(tcn_engine.run_background_loop(3600))  # Hourly inference
    logger.info("🧠 TCN NEURAL ENGINE ACTIVATED — Engine 9, BTC/USDT 1h deep learning")

    # ELITE STRATEGY v3 — autonomous scan every 30 min (Fix #15)
    _elite_auto = get_elite_strategy(
        advanced_strategies=advanced_strategies,
        smc_analyzer=smc_analyzer,
        enhanced_intel=enhanced_intel,
    )
    _elite_auto.send_telegram = send_telegram_message
    _elite_auto.chat_ids = chat_ids
    elite_task = asyncio.create_task(_elite_auto.run_loop(1800))
    logger.info("🎯 ELITE STRATEGY v3 AUTONOMOUS ACTIVATED — scanning every 30 min")

    # ORACLE CORE — Market intelligence (pure analysis, no trading)
    oracle.set_dependencies(
        market_intel=market_intel,
        derivatives_intel=derivatives_intel,
        send_telegram=send_telegram_message,
        chat_ids=chat_ids,
    )
    oracle_task = asyncio.create_task(oracle.run_loop())

    # ORIA layer — SignalAggregator + EdgeFilter + StressMonitor
    oria_stress_task = None
    try:
        from oria_layer import init_oria
        _oria_agg, _oria_ef, _oria_sm = init_oria(db)
        _oria_sm.set_dependencies(
            market_intel=market_intel,
            quantum_state=None,   # wired below after quantum_state is ready
            engine_manager=get_engine_manager(),
        )
        oria_stress_task = asyncio.create_task(_oria_sm.run_loop())
        app_state.oria_stress_monitor = _oria_sm
        logger.info("🧠 ORIA layer initialized — StressMonitor background loop started")
    except Exception as _oria_init_err:
        logger.warning(f"[ORIA] Init failed (non-fatal): {_oria_init_err}")

    # Quantum state engine — computes |Ψ⟩ every 60s
    quantum_state = init_quantum_state(db)
    quantum_state.set_dependencies(
        market_intel=market_intel,
        engine_manager=get_engine_manager(),
    )
    quantum_task = asyncio.create_task(quantum_state.run_loop())

    # Wire quantum engine into paper trading for position sizing
    pt.set_quantum_engine(quantum_state)
    app_state.quantum_state = quantum_state
    logger.info("⚛️  Quantum engine wired into paper trading")

    # Wire quantum_state into ORIA StressMonitor (H value for S(t) formula)
    try:
        if hasattr(app_state, "oria_stress_monitor") and app_state.oria_stress_monitor:
            app_state.oria_stress_monitor.quantum_state = quantum_state
            logger.info("🧠 [ORIA] quantum_state wired into StressMonitor")
    except Exception:
        pass

    # Post-mortem engine — self-awareness layer
    from post_mortem_engine import get_post_mortem
    pm = get_post_mortem(db=db)
    pm.set_dependencies(
        send_alert=send_telegram_message,
        chat_ids=chat_ids,
        quantum_state=quantum_state,
    )
    asyncio.ensure_future(pm.run_startup_audit())
    app_state.post_mortem = pm
    logger.info("🧠 Post-Mortem Engine ACTIVE — blindspot detection, engine pause, pre-trade blocking")

    # Paper auto-deposit loop (checks every hour for REAL_LIFE weekly top-up)
    paper_deposit_task = asyncio.create_task(pt.auto_deposit_loop())

    # Paper weekly report (Monday 8am UTC)
    from paper_weekly_report import PaperWeeklyReport
    paper_weekly_rpt = PaperWeeklyReport(pt, send_telegram_message, chat_ids)
    paper_weekly_rpt_task = asyncio.create_task(paper_weekly_rpt.run_scheduler())

    # Memory engine — stores (E,a,r) triplets after every trade close
    memory_eng = init_memory_engine(db)
    memory_eng.set_dependencies(
        market_intel=market_intel,
        quantum_state=quantum_state,
    )
    memory_task = asyncio.create_task(memory_eng.run_loop())

    # Omega cycle — self-improvement loop, runs every 6 hours
    omega = init_omega_cycle(db)
    omega.set_dependencies(
        send_alert=send_telegram_message,
        chat_ids=chat_ids,
        quantum_state=quantum_state,
        memory_engine=memory_eng,
        engine_manager=get_engine_manager(),
    )
    omega_task = asyncio.create_task(omega.run_loop())

    # ATR stop module — Wilder ATR(14) stop placement, k optimization, lot sizing
    atr_stop = init_atr_stop(db)
    atr_stop.set_dependencies(
        market_intel=market_intel,
        memory_engine=memory_eng,
        quantum_state=quantum_state,
    )
    app_state.atr_stop = atr_stop
    logger.info("[ATR] ATR stop module initialised — Wilder ATR(14), k∈{1.5,2.0,2.5}, walk-forward 90d")

    # Web intelligence — crawls external sources every 24h, feeds LΦ queue
    web_intel_eng = init_web_intelligence(db)
    web_intel_eng.set_dependencies(
        quantum_state=quantum_state,
        omega_cycle=omega,
        send_alert=send_telegram_message,
        chat_ids=chat_ids,
    )
    web_intel_task = asyncio.create_task(web_intel_eng.run_loop())

    # Paper account health monitor - auto-reload when balance too low
    paper_health_task = asyncio.create_task(paper_account_health_loop(300))  # Check every 5 mins

    # Paper trading price update loop - updates positions and triggers TP/SL closes
    paper_price_task = asyncio.create_task(paper_price_update_loop(market_intel, 30))  # Every 30 seconds

    # Engine data collector - hourly snapshots, outcome tracking, confirmation accuracy
    engine_collector_task = asyncio.create_task(run_engine_data_collector(db, app_state, market_intel))
    
    # Register all services with self-healer for auto-recovery
    self_healer.register("rituals", ritual_task, eternal_rituals)
    self_healer.register("trading_v2", trading_task, autonomous_trading_loop)
    self_healer.register("free_will", freewill_task, free_will_scanner)
    self_healer.register("dual_engine", dual_task, dual_trading_scanner)
    self_healer.register("price_alerts", alert_task, price_alert_system.run_forever)
    self_healer.register("morning_briefing", briefing_task, morning_briefing.run_scheduler)
    self_healer.register("weekly_report", weekly_task, weekly_report.run_scheduler)
    self_healer.register("continuous_learning", learning_task, continuous_learner.run_scheduler)
    self_healer.register("vp_engine", vp_task, lambda: vp_eng.run_scan_loop(300))
    self_healer.register("vwap_scalper", vwap_task, lambda: vwap_scalper.run_scan_loop(300))
    self_healer.register("yolo_engine", yolo_task, lambda: yolo_engine.run_loop(180))
    self_healer.register("institutional_scalper", inst_task, lambda: inst_scalper.run_loop(3600))
    self_healer.register("tcn_neural", tcn_task, lambda: tcn_engine.run_background_loop(3600))
    self_healer.register("elite_strategy", elite_task, lambda: _elite_auto.run_loop(1800))
    self_healer.register("oracle", oracle_task, oracle.run_loop)
    if oria_stress_task:
        try:
            _sm_ref = app_state.oria_stress_monitor
            self_healer.register("oria_stress", oria_stress_task, _sm_ref.run_loop)
        except Exception:
            pass
    self_healer.register("quantum_state", quantum_task, quantum_state.run_loop)
    self_healer.register("memory_engine", memory_task, memory_eng.run_loop)
    self_healer.register("omega_cycle", omega_task, omega.run_loop)
    self_healer.register("web_intelligence", web_intel_task, web_intel_eng.run_loop)
    self_healer.register("paper_health", paper_health_task, lambda: paper_account_health_loop(300))
    self_healer.register("paper_price_update", paper_price_task, lambda: paper_price_update_loop(market_intel, 30))
    self_healer.register("paper_auto_deposit", paper_deposit_task, pt.auto_deposit_loop)
    self_healer.register("paper_weekly_report", paper_weekly_rpt_task, paper_weekly_rpt.run_scheduler)
    self_healer.register("engine_data_collector", engine_collector_task, lambda: run_engine_data_collector(db, app_state, market_intel))
    healer_task = asyncio.create_task(self_healer.monitor_loop())
    
    logger.info(f"AEON PAPER TRADING ACTIVATED - {autonomous_trader_v2.min_confidence}%+ conf, {autonomous_trader_v2.min_confirmations}+ confirmations")
    logger.info("AEON FREE WILL v2 ACTIVATED - Elite alerts only (80%+ conf, 3+ confirmations)")
    logger.info("DUAL ENGINE ACTIVATED - Day Trader (aggressive) + Long Term (smart)")
    logger.info("🎯 VWAP SCALPER ACTIVATED - VWAP + EMA Cross + RSI strategy")
    logger.info("🚀 YOLO ENGINE ACTIVATED - Independent aggressive trading (50% conf, 1 confirm)")
    logger.info("AEON PRICE ALERT SYSTEM v2 - Lean batched alerts")
    logger.info("SELF-HEALER ACTIVATED - Auto error detection & recovery")
    logger.info("MORNING BRIEFING ACTIVATED - Daily 6 AM CT market overview")
    logger.info("WEEKLY REPORT ACTIVATED - Sunday 8 PM CT performance summary")
    logger.info("🧠 CONTINUOUS LEARNING ACTIVATED - 24/7 pattern recognition & optimization")
    logger.info("♻️ PAPER ACCOUNT HEALTH MONITOR - Auto-reload when balance < 5%")
    logger.info("📊 PAPER PRICE UPDATE LOOP - TP/SL monitoring every 30s")

    # ── Feed health monitor ──────────────────────────────────────────────────
    await feed_health.initial_probe()  # initial check before accepting traffic (retries 3x)
    feed_health.start_recovery_loop()  # auto-retry every 30 s when degraded
    logger.info("📡 FEED HEALTH MONITOR STARTED — auto-recovery every 30s when degraded")
    # ─────────────────────────────────────────────────────────────────────────

    # Initialize unified alert system
    await _signal_dedup_inst.load_from_db()
    init_alerter(db=db, chat_ids=chat_ids, send_fn=send_telegram_message, signal_deduplicator=_signal_dedup_inst)

    # Start critical alert monitors
    _monitors = init_monitors(db=db, alerter=alerter)
    monitor_tasks = [asyncio.create_task(m.run_loop()) for m in _monitors]
    for i, m in enumerate(_monitors):
        self_healer.register(f"monitor_{m.__class__.__name__}", monitor_tasks[i], m.run_loop)
    logger.info("🔔 UNIFIED ALERT SYSTEM + MONITORS ACTIVE")

    # Regime change watcher — broadcasts WebSocket event when H-derived regime changes
    async def _regime_change_watcher():
        _last_regime = None
        while True:
            try:
                state = app_state.quantum_state.get_state() if hasattr(app_state, "quantum_state") and app_state.quantum_state else {}
                H = state.get("H", 0.5)
                if H < 0.40:
                    regime = "STRUCTURED"
                elif H >= 0.65:
                    regime = "CHAOTIC"
                else:
                    regime = "TRANSITIONAL"
                if _last_regime is not None and regime != _last_regime:
                    await ws_manager.broadcast({
                        "type": "regime_change",
                        "from_regime": _last_regime,
                        "to_regime": regime,
                        "H": round(H, 4),
                        "message": f"Regime shifted: {_last_regime} → {regime} (H={H:.3f})",
                    })
                    logger.info(f"[REGIME] Broadcast regime change: {_last_regime} → {regime}")
                _last_regime = regime
            except Exception as _rce:
                logger.debug(f"[REGIME_WATCHER] {_rce}")
            await asyncio.sleep(60)

    asyncio.create_task(_regime_change_watcher())
    logger.info("📡 Regime change watcher active")

    yield

    feed_health.stop()

    # Signal all loops to stop cleanly
    self_healer.active = False
    morning_briefing.is_active = False
    weekly_report.is_active = False
    continuous_learner.is_active = False
    vwap_scalper.active = False
    yolo_engine.active = False
    inst_scalper.active = False
    _elite_auto.enabled = False

    # Cancel all background tasks and wait briefly for graceful exit
    all_tasks = [
        healer_task, ritual_task, trading_task, freewill_task, dual_task,
        alert_task, briefing_task, weekly_task, learning_task,
        vwap_task, yolo_task, inst_task, elite_task, paper_health_task, paper_price_task,
        *monitor_tasks,
    ]
    for task in all_tasks:
        task.cancel()
    await asyncio.gather(*all_tasks, return_exceptions=True)

    try:
        client.close()
    except Exception as e:
        logger.warning(f"MongoDB close error: {e}")


app = FastAPI(lifespan=lifespan, docs_url=None, openapi_url=None, redoc_url=None)
api_router = APIRouter(prefix="/api")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception [{request.method} {request.url}]: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


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


# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTES (Minimal - most moved to routes/)
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/")
async def root():
    return {"message": "Aeon Market Intelligence Active", "status": "online"}


@api_router.get("/download/spec")
async def download_spec():
    """Download AEON complete specification PDF"""
    pdf_path = Path("/app/AEON_COMPLETE_SPECIFICATION.pdf")
    if pdf_path.exists():
        return FileResponse(
            path=str(pdf_path),
            filename="AEON_Complete_Specification.pdf",
            media_type="application/pdf"
        )
    raise HTTPException(status_code=404, detail="PDF not found")


@api_router.get("/download/docs")
async def download_docs():
    """Download AEON full documentation text file"""
    txt_path = Path("/app/AEON_FULL_DOCUMENTATION.txt")
    if txt_path.exists():
        return FileResponse(
            path=str(txt_path),
            filename="AEON_Full_Documentation.txt",
            media_type="text/plain"
        )
    raise HTTPException(status_code=404, detail="Documentation not found")


# NOTE: The following endpoints moved to routes/:
# - /ws/stats -> routes/system.py
# - /confluence/{symbol} -> routes/confluence.py
# - /system/health -> routes/system.py
# - /pairs -> routes/system.py
# - /mtf/{symbol} -> routes/mtf.py
# - /mtf/align/{symbol} -> routes/mtf.py
# - /accuracy/* -> routes/accuracy.py
# - /learning/* -> routes/learning.py
# - /bot/* -> routes/bot.py


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
        tech = await market_intel.get_technical_analysis(full_symbol, timeframe)
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
        btc = await market_intel.get_technical_analysis("BTC/USDT", "1h")
        binance_ok = "error" not in btc
        
        # Test LLM
        await call_llm("You are a test assistant.", "Hi")
        
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


# NOTE: User Profile endpoints moved to routes/user.py

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM WEBHOOK
# ═══════════════════════════════════════════════════════════════════════════════

_webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

# update_id dedup — prevents Telegram retry storms from processing the same message twice
_seen_update_ids: set = set()
_SEEN_UPDATE_ID_MAX = 500  # cap memory; oldest are dropped when full

@api_router.post("/webhook")
async def webhook(request: Request):
    if _webhook_secret:
        incoming = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if incoming != _webhook_secret:
            # Return 200 so Telegram stops retrying — log the auth failure
            logger.warning(f"Webhook auth failed — incoming token mismatch")
            return {"status": "unauthorized"}
    try:
        update = await request.json()

        # Deduplicate by update_id — Telegram retries until it gets 200
        update_id = update.get("update_id")
        if update_id is not None:
            if update_id in _seen_update_ids:
                logger.info(f"Duplicate update_id {update_id} — skipping")
                return {"status": "ok"}
            _seen_update_ids.add(update_id)
            if len(_seen_update_ids) > _SEEN_UPDATE_ID_MAX:
                # Drop oldest entries — set has no order so just clear the oldest ~50
                oldest = list(_seen_update_ids)[:50]
                for uid in oldest:
                    _seen_update_ids.discard(uid)

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

        # ── Feed health gate ─────────────────────────────────────────────────
        # Commands that work without live market data feeds
        _FEED_FREE_CMDS = {
            '/help', '/start', '/ping', '/status',
            '/settings', '/menu', '/commands', '/model',
        }
        _base_cmd = text_lower.split()[0] if text_lower else ""
        if _base_cmd.startswith('/') and _base_cmd not in _FEED_FREE_CMDS and not feed_health.is_healthy:
            await send_telegram_message(chat_id, OFFLINE_MESSAGE)
            return {"status": "ok"}
        # ─────────────────────────────────────────────────────────────────────

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
            fw_stats = await free_will_v2.get_stats()
            dual_stats = dual_engine.get_stats()
            response = f"""*AEON Trading Intelligence*
Status: {'🟢 ACTIVE' if autonomous_trader_v2.active else '🔴 PAUSED'} | Mode: {'Alchemy' if current_mode == 'alchemy' else 'Casual'}

*QUICK START*
/scan btc — Full SMC analysis + entry/SL/TP
/ta btc — Technicals (RSI, MACD, BB, EMA)
/auto — Paper trading status & toggle
/fw — Free Will elite alert status

*ANALYSIS*
/scan [coin] — Full SMC analysis
/ta [coin] [tf] — Technical indicators (1m/5m/15m/1h/4h/1d)
/mtf [coin] — Multi-timeframe confluence
/vp [coin] — Volume Profile + Liq Heatmap + Orderbook
/structure [coin] — Market structure (HH/HL/LH/LL)
/smc [coin] — Order blocks, FVG, liquidity
/vwap [coin] — VWAP analysis
/divergence [coin] — RSI/MACD divergence scan
/sentiment [coin] — Social + news sentiment

*MARKET DATA*
/market — Global crypto summary
/fear — Fear & Greed Index
/top100 — Top 10 by market cap
/movers — 24h gainers/losers
/trending — Most searched coins
/news — Latest news + social

*DERIVATIVES*
/funding [coin] — Funding rates
/deriv [coin] — Full derivatives report (OI, funding, L/S)
/positions [coin] — Long/Short ratio breakdown
/cg [coin] — Coinglass data
/liqs [coin] — Liquidation levels
/cvd [coin] — Cumulative Volume Delta (order flow)
/options [btc|eth] — Options chain, max pain, PCR

*TRADING*
/auto on|off — Toggle paper trading engine
/opps — Current high-probability setups
/open — All open positions
/close [coin] — Close a position
/trail [coin] [%] — Set trailing stop
/tp [coin] [%] — Set take profit
/lev [coin] [1-20] — Set leverage
/risk — Portfolio risk check

*PAPER ACCOUNTS*
/accounts — View PRO + Starter accounts
/pro — PRO account ($50K balance)
/starter — Starter account ($1.5K balance)
/addmargin [coin] [amount] — Add margin to position
/reload [pro|starter] — Reload account balance

*ENGINES*
/engines — All 7 engines status + stats
/engine [1-7] — View engine settings
/engine [1-7] on|off — Toggle engine
/engine [1-7] set [param] [value] — Configure
/elite — Free Will v2 elite status
/elite on|off — Toggle elite alerts
/elite scan — Force scan now
/elite relaxed|strict — Set threshold mode
/scalper — VWAP Scalper status
/fwconf [80-95] — Set Free Will confidence threshold

*PERFORMANCE*
/accuracy — Alert accuracy stats
/leaderboard — Coin win rates
/stats — AI learning stats
/journal — Trade journal summary
/insights — Personalized trading insights
/strategy — View current optimized strategy
/strat [coin] — Strategy breakdown for coin
/backtest [coin] [tf] — Quick backtest

*ALERTS & REPORTS*
/alerts — View active price alerts
/alert add [coin] above|below [price] — Set price alert
/alert remove [coin] — Remove alert
/briefing — Today's market briefing
/weekly — Weekly performance report
/learn — 24/7 learning engine status

*AI & TOOLS*
/claude — Switch to Claude Sonnet 4.5 🧠 (default)
/gemini — Switch to Gemini 2.0 Flash ✨
/model — Show current AI model
/intel — Full market intelligence report
/arbi — Multi-exchange arbitrage scan
/calc [coin] [entry] [sl] [tp] — P&L calculator
/calcsize [coin] [entry] [sl] — Position size calculator
/health — Strategy health dashboard

*MODE*
Say "alchemy mode" — mystical market oracle
Say "casual mode" — direct trading assistant

Free Will: {'🟢 ACTIVE' if fw_stats.get('active') else '🔴 OFF'} ({fw_stats.get('min_confidence', 80)}% conf) | Day Trader: {'🟢' if dual_stats.get('day_trader', {}).get('active') else '🔴'} | Long Term: {'🟢' if dual_stats.get('long_term', {}).get('active') else '🔴'}"""
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
        
        # ============= NEW COMMANDS: BRIEFING, WEEKLY, LEARNING =============
        elif text_lower == '/briefing' or text_lower == '/brief':
            # Get morning briefing preview
            preview = await morning_briefing.generate_briefing()
            response = preview
            context = "briefing"
        
        elif text_lower == '/weekly' or text_lower == '/report':
            # Get weekly report preview
            preview = await weekly_report.generate_report()
            response = preview
            context = "report"
        
        elif text_lower == '/learn' or text_lower == '/learning':
            # Get learning engine status
            status = await continuous_learner.get_status()
            recs = await continuous_learner.get_recommendations()
            
            insights = continuous_learner.daily_insights[:5] if continuous_learner.daily_insights else ["No insights yet - need more trades"]
            
            response = f"""🧠 24/7 LEARNING ENGINE

Status: {'🟢 ACTIVE' if status['active'] else '🔴 PAUSED'}
Next Summary: {status.get('next_daily_summary', '9 PM CT')}

📊 KNOWLEDGE BASE
Patterns Learned: {status['knowledge_stats']['patterns_learned']}
Coins Analyzed: {status['knowledge_stats']['coins_analyzed']}
Optimizations Run: {status['knowledge_stats']['optimizations_run']}
Today's Insights: {status['daily_insights_count']}

⏰ LAST CYCLES
• Pattern: {status['last_cycles']['pattern_learning'][:16] if status['last_cycles']['pattern_learning'] else 'Pending'}
• Market: {status['last_cycles']['market_analysis'][:16] if status['last_cycles']['market_analysis'] else 'Pending'}
• Optimization: {status['last_cycles']['optimization'][:16] if status['last_cycles']['optimization'] else 'Pending'}

💡 TODAY'S INSIGHTS
{chr(10).join(['• ' + i for i in insights])}

📌 RECOMMENDATIONS
• Coins to favor: {', '.join([c['coin'] for c in recs['pattern_recommendations'].get('coins_to_favor', [])[:3]]) or 'Need more data'}
• Coins to avoid: {', '.join([c['coin'] for c in recs['pattern_recommendations'].get('coins_to_avoid', [])[:3]]) or 'None yet'}

The engine learns 24/7 and sends daily summaries at 9 PM CT!"""
            context = "learning"
        
        elif text_lower == '/scalper' or text_lower == '/scalp':
            # Get scalper status
            from scalper_learning import auto_learner, v2_integration
            
            settings = scalper.get_settings()
            learning = await scalper.get_learning_status()
            v2_status = await scalper.get_v2_integration_status()
            
            response = f"""⚡ AGGRESSIVE SCALPER

Status: {'🟢 ACTIVE' if settings.get('enabled', True) else '🔴 PAUSED'}

⚙️ SETTINGS
• Profit Target: {settings.get('profit_target', 0.8)}%
• Stop Loss: {settings.get('stop_loss', 0.4)}%
• Volume Threshold: {settings.get('volume_threshold', 1.5)}x
• RSI Range: {settings.get('rsi_oversold', 30)}-{settings.get('rsi_overbought', 70)}

🧠 AUTO-LEARNING
• Status: {'ON' if learning.get('auto_learn_enabled') else 'OFF'}
• Optimizations: {learning.get('optimizations_run', 0)}

🔗 V2.1 INTEGRATION
• Status: {'CONNECTED' if v2_status.get('enabled') else 'DISABLED'}
• Queued Signals: {v2_status.get('queued_count', 0)}

Scalper runs alongside V2.1 with auto-learning!"""
            context = "scalper"
        
        # ============= MTF CONFLUENCE COMMAND =============
        elif text_lower == '/mtf' or text_lower == '/confluence':
            # Multi-Timeframe Confluence Analysis
            try:
                result = await scalper.scan_mtf_confluence(min_confluence=2)
                summary = result.get("summary", {})
                best = result.get("best_setup")
                
                response = f"""📊 MTF CONFLUENCE ANALYSIS

Scanned: {summary.get('scanned_symbols', 15)} symbols across 5m/15m/30m

🎯 STRONG (3/3): {summary.get('strong_setups', 0)} setups
📈 MODERATE (2/3): {summary.get('moderate_setups', 0)} setups
📊 Actionable: {summary.get('total_actionable', 0)} total

"""
                if best:
                    symbol = best.get('symbol', '').replace('/USDT', '')
                    direction = best.get('consensus_direction', 'N/A')
                    conf = best.get('weighted_confidence', 0)
                    level = best.get('confluence_level', 'N/A')
                    
                    response += f"""🏆 BEST SETUP: {symbol}
• Direction: {'🟢 LONG' if direction == 'LONG' else '🔴 SHORT' if direction == 'SHORT' else '⚪ ' + direction}
• Confluence: {level} ({best.get('confluence_count', 'N/A')})
• Confidence: {conf}%
• {best.get('recommendation', '')}

"""
                # Show strong setups
                strong = result.get("strong_confluence", [])[:3]
                if strong:
                    response += "🎯 STRONG SETUPS:\n"
                    for s in strong:
                        sym = s.get('symbol', '').replace('/USDT', '')
                        dir_emoji = '🟢' if s.get('consensus_direction') == 'LONG' else '🔴'
                        response += f"• {sym} {dir_emoji} {s.get('consensus_direction')} ({s.get('weighted_confidence', 0)}%)\n"
                else:
                    response += "No strong setups right now.\n"
                
                response += "\nTrade STRONG (3/3) with larger size, MODERATE (2/3) with standard size."
                
            except Exception as e:
                logger.error(f"MTF confluence error: {e}")
                response = "❌ Error scanning MTF confluence. Try again."
            context = "scalper"
        
        elif text_lower.startswith('/mtf '):
            # MTF analysis for specific symbol
            parts = text_lower.split()
            if len(parts) >= 2:
                symbol = parts[1].upper()
                try:
                    result = await scalper.analyze_mtf_confluence(symbol)
                    
                    direction = result.get('consensus_direction', 'NEUTRAL')
                    level = result.get('confluence_level', 'NONE')
                    conf = result.get('weighted_confidence', 0)
                    
                    dir_emoji = '🟢' if direction == 'LONG' else '🔴' if direction == 'SHORT' else '⚪'
                    level_emoji = '🎯' if level == 'STRONG' else '📈' if level == 'MODERATE' else '📊' if level == 'WEAK' else '⚫'
                    
                    response = f"""{level_emoji} MTF CONFLUENCE: {symbol}

Direction: {dir_emoji} {direction}
Confluence: {level} ({result.get('confluence_count', 'N/A')})
Confidence: {conf}%

📊 BY TIMEFRAME:"""
                    
                    for tf, data in result.get('timeframes', {}).items():
                        signal = data.get('signal', 0)
                        strength = data.get('strength', 0)
                        reason = data.get('reason', 'No signal')
                        
                        if signal == 1:
                            response += f"\n• {tf}: 🟢 BUY (str:{strength}) - {reason}"
                        elif signal == -1:
                            response += f"\n• {tf}: 🔴 SELL (str:{strength}) - {reason}"
                        else:
                            response += f"\n• {tf}: ⚪ HOLD"
                    
                    response += f"\n\n💡 {result.get('recommendation', 'Analyze further before trading.')}"
                    
                except Exception as e:
                    response = f"❌ Error analyzing {symbol}: {str(e)}"
            else:
                response = "Usage: /mtf BTC"
            context = "scalper"
        
        # ============= QUICK MODEL SWITCH COMMANDS =============
        elif text_lower == '/claude' or text_lower == '/anthropic':
            success = await set_user_model(chat_id, "claude")
            if success:
                response = """✅ SWITCHED TO CLAUDE SONNET 4.5 🧠

Deep analysis, nuanced reasoning - great for complex market reads.

Switch: /gemini"""
            else:
                response = "❌ Failed to switch. Try again."
            context = "settings"

        elif text_lower == '/gemini' or text_lower == '/google':
            success = await set_user_model(chat_id, "gemini")
            if success:
                response = """✅ SWITCHED TO GEMINI 2.0 FLASH ✨

Fast, broad context - great for quick answers and news summaries.

Switch: /claude"""
            else:
                response = "❌ Failed to switch. Try again."
            context = "settings"
        
        # ============= ELITE STRATEGY v3 COMMANDS =============
        elif text_lower == '/elite' or text_lower == '/elite status':
            # Show Elite Strategy status
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                stats = elite.get_stats()
                settings = stats.get("settings", {})
                
                response = f"""🎯 ELITE STRATEGY v3

Status: {'🟢 ACTIVE' if stats.get('enabled') else '🔴 PAUSED'}

📊 STATISTICS
• Signals Generated: {stats.get('signals_generated', 0)}
• Signals Filtered: {stats.get('signals_filtered', 0)}
• Daily Trades: {stats.get('daily_trades', 0)}/{stats.get('max_daily_trades', 3)}

⚙️ SETTINGS (Ultra-Selective)
• Min Confidence: {settings.get('min_confidence', 92)}%
• Min R:R Ratio: {settings.get('min_rr_ratio', 2.5)}:1
• Min Volume: {settings.get('min_volume_ratio', 2.0)}x
• Min ADX: {settings.get('min_adx', 28)}
• BTC Alignment: {'Required' if settings.get('require_btc_alignment') else 'Optional'}
• MTF Confluence: {'Required' if settings.get('require_mtf_confluence') else 'Optional'}

🎯 Target: 60%+ Win Rate

Commands:
• /elite scan - Scan for elite signals
• /elite BTC - Analyze specific symbol
• /elite on/off - Toggle strategy"""
            except Exception as e:
                response = f"❌ Error: {str(e)}"
            context = "elite"
        
        elif text_lower == '/elite scan':
            # Scan for elite signals
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                signals = await elite.scan_all_elite()
                
                if signals:
                    response = f"🎯 ELITE SIGNALS FOUND: {len(signals)}\n\n"
                    for sig in signals[:5]:
                        symbol = sig.get('symbol', '').replace('/USDT', '')
                        direction = sig.get('direction', 'N/A')
                        conf = sig.get('confidence', 0)
                        rr = sig.get('rr_ratio', 0)
                        mtf = sig.get('mtf_confluence', '0/3')
                        
                        dir_emoji = '🟢' if direction == 'LONG' else '🔴'
                        response += f"""{dir_emoji} {symbol} {direction}
• Confidence: {conf}%
• R:R: {rr}:1
• MTF: {mtf}
• Entry: ${sig.get('entry_price', 0):,.2f}
• Stop: ${sig.get('stop_price', 0):,.2f}
• Target: ${sig.get('target_price', 0):,.2f}

"""
                else:
                    stats = elite.get_stats()
                    top_filters = list(stats.get('filter_reasons', {}).items())[:3]
                    response = "🎯 No elite signals right now.\n\n"
                    response += "Top filter reasons:\n"
                    for reason, count in top_filters:
                        response += f"• {reason}: {count}\n"
                    response += "\nElite Strategy is ultra-selective for high win rate."
            except Exception as e:
                response = f"❌ Error scanning: {str(e)}"
            context = "elite"
        
        elif text_lower.startswith('/elite ') and text_lower.split()[1] not in ['on', 'off', 'scan']:
            # Analyze specific symbol
            parts = text_lower.split()
            symbol = parts[1].upper()
            
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                signal = await elite.analyze_elite_signal(symbol + "/USDT", "4h")
                
                if signal:
                    dir_emoji = '🟢' if signal.get('direction') == 'LONG' else '🔴'
                    response = f"""🎯 ELITE SIGNAL: {symbol}

{dir_emoji} {signal.get('direction')} | Confidence: {signal.get('confidence')}%

📊 ANALYSIS
• R:R Ratio: {signal.get('rr_ratio')}:1
• MTF Confluence: {signal.get('mtf_confluence')}
• BTC Trend: {signal.get('btc_trend')}
• Volume: {signal.get('volume_ratio', 0):.1f}x
• ADX: {signal.get('adx', 0):.0f}

💰 TRADE SETUP
• Entry: ${signal.get('entry_price', 0):,.2f}
• Stop: ${signal.get('stop_price', 0):,.2f}
• Target: ${signal.get('target_price', 0):,.2f}

✅ CONFIRMATIONS:
"""
                    for conf in signal.get('confirmations', [])[:5]:
                        response += f"• {conf}\n"
                else:
                    stats = elite.get_stats()
                    response = f"❌ No elite signal for {symbol}\n\n"
                    response += "Recent filter reasons:\n"
                    for reason, count in list(stats.get('filter_reasons', {}).items())[:5]:
                        response += f"• {reason}: {count}\n"
            except Exception as e:
                response = f"❌ Error analyzing {symbol}: {str(e)}"
            context = "elite"
        
        elif text_lower == '/elite on':
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                elite.enabled = True
                response = "🟢 Elite Strategy v3 ENABLED\n\nUltra-selective mode for 60%+ win rate."
            except Exception as e:
                response = f"❌ Error: {str(e)}"
            context = "elite"
        
        elif text_lower == '/elite off':
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                elite.enabled = False
                response = "🔴 Elite Strategy v3 DISABLED"
            except Exception as e:
                response = f"❌ Error: {str(e)}"
            context = "elite"
        
        elif text_lower == '/elite relaxed' or text_lower == '/relaxed':
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                result = elite.set_relaxed_mode(True)
                settings = result["active_settings"]
                response = f"""😎 ELITE RELAXED MODE ENABLED

More signals with slightly lower thresholds:
• Min Confidence: {settings['min_confidence']}% (was 92%)
• Min R:R: {settings['min_rr_ratio']}:1 (was 2.5:1)
• Min Volume: {settings['min_volume_ratio']}x (was 2.0x)
• Min ADX: {settings['min_adx']} (was 28)
• Max Trades/Day: {settings['max_daily_trades']} (was 3)
• BTC Alignment: {'Required' if settings['require_btc_alignment'] else 'Optional'}

Switch back: /elite strict"""
            except Exception as e:
                response = f"❌ Error: {str(e)}"
            context = "elite"
        
        elif text_lower == '/elite strict' or text_lower == '/strict':
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                result = elite.set_relaxed_mode(False)
                settings = result["active_settings"]
                response = f"""🎯 ELITE STRICT MODE ENABLED

Ultra-selective for 60%+ win rate:
• Min Confidence: {settings['min_confidence']}%
• Min R:R: {settings['min_rr_ratio']}:1
• Min Volume: {settings['min_volume_ratio']}x
• Min ADX: {settings['min_adx']}
• Max Trades/Day: {settings['max_daily_trades']}
• BTC Alignment: Required
• MTF Confluence: Required

Switch to more signals: /elite relaxed"""
            except Exception as e:
                response = f"❌ Error: {str(e)}"
            context = "elite"
        
        elif text_lower == '/elite backtest' or text_lower == '/backtest elite':
            try:
                elite = get_elite_strategy(
                    state.advanced_strategies,
                    state.smc_analyzer,
                    state.enhanced_intel
                )
                result = await elite.backtest(30)
                
                if "error" in result:
                    response = f"❌ Backtest error: {result['error']}"
                else:
                    strict = result.get("strict_mode", {})
                    relaxed = result.get("relaxed_mode", {})
                    overall = result.get("overall", {})
                    
                    response = f"""📊 ELITE STRATEGY BACKTEST

Analyzed: {result['total_signals']} signals ({result['days_analyzed']} days)

🎯 STRICT MODE (92%+ conf)
• Would take: {strict.get('signals_would_take', 0)} trades
• Estimated wins: {strict.get('estimated_wins', 0)}
• Est. Win Rate: {strict.get('estimated_win_rate', 0)}%
• Target (60%+): {'✅ YES' if strict.get('target_achieved') else '❌ NO'}

😎 RELAXED MODE (70%+ conf)
• Would take: {relaxed.get('signals_would_take', 0)} trades
• Estimated wins: {relaxed.get('estimated_wins', 0)}
• Est. Win Rate: {relaxed.get('estimated_win_rate', 0)}%
• Target (50%+): {'✅ YES' if relaxed.get('target_achieved') else '❌ NO'}

📈 Overall: {overall.get('wins', 0)}W/{overall.get('losses', 0)}L ({overall.get('win_rate', 0)}%)

💡 {result.get('recommendation', 'Analysis complete')}"""
            except Exception as e:
                response = f"❌ Error: {str(e)}"
            context = "elite"
        
        # ============= MODEL STATUS COMMAND =============
        elif text_lower.startswith('/model'):
            parts = text_lower.split()
            
            if len(parts) == 1:
                # Show current model
                current_model = await get_user_model(chat_id)
                config = get_model_config(current_model)
                response = f"""🤖 CURRENT AI: {config['display_name']}

{config['description']}

SWITCH: /claude or /gemini"""
                context = "settings"
            
            else:
                # Try to switch model
                requested = parts[1]
                resolved = resolve_model_key(requested)
                
                if resolved in MODEL_CONFIGS:
                    success = await set_user_model(chat_id, resolved)
                    if success:
                        config = get_model_config(resolved)
                        response = f"✅ Switched to {config['display_name']}"
                    else:
                        response = "❌ Failed to switch. Try /claude or /gemini"
                else:
                    response = "❌ Unknown model. Use /claude or /gemini"
                context = "settings"
        
        # ============= ENGINE MANAGEMENT =============
        elif text_lower == '/engines' or text_lower == '/engine':
            # Show all engines status
            v2_stats = await autonomous_trader_v2.get_stats()
            fw_stats = await free_will_v2.get_stats()
            scalper_settings = scalper.get_settings()
            dual_stats = dual_engine.get_stats() if dual_engine else {}
            learning_status = await continuous_learner.get_status() if continuous_learner else {}
            
            response = f"""🤖 ALL TRADING ENGINES

1️⃣ AUTONOMOUS V2 {'🟢 ON' if autonomous_trader_v2.active else '🔴 OFF'}
   Conf: {autonomous_trader_v2.min_confidence}% | Confirms: {autonomous_trader_v2.min_confirmations}
   R:R: {autonomous_trader_v2.min_rr_ratio}:1 | Trades: {v2_stats.get('total_trades', 0)}

2️⃣ FREE WILL V2 {'🟢 ON' if free_will_v2.active else '🔴 OFF'}
   Conf: {fw_stats.get('min_confidence', 80)}% | Alerts: {fw_stats.get('alerts_today', 0)}/{fw_stats.get('max_daily_alerts', 15)}

3️⃣ SCALPER {'🟢 ON' if scalper_settings.get('enabled', True) else '🔴 OFF'}
   Target: {scalper_settings.get('profit_target', 0.8)}% | Stop: {scalper_settings.get('stop_loss', 0.4)}%

4️⃣ DUAL ENGINE {'🟢 ON' if dual_stats.get('active', False) else '🔴 OFF'}
   Day + Long Term combined

5️⃣ LEARNING {'🟢 ON' if learning_status.get('active', True) else '🔴 OFF'}
   Patterns: {learning_status.get('knowledge_stats', {}).get('patterns_learned', 0)}

━━━━━━━━━━━━━━━━━━━━
COMMANDS:
/engine [1-5] on|off - Toggle
/engine [1-5] set [param] [value]
/engine [1-5] - View settings

Example: /engine 1 set conf 85"""
            context = "settings"
        
        elif text_lower.startswith('/engine '):
            parts = text_lower.split()
            if len(parts) < 2:
                response = "Usage: /engine [1-5] [on|off|set param value]"
            else:
                engine_num = parts[1]
                action = parts[2] if len(parts) > 2 else "status"
                
                # Map engine numbers to engines
                engines = {
                    '1': ('autonomous_v2', autonomous_trader_v2),
                    '2': ('free_will_v2', free_will_v2),
                    '3': ('scalper', scalper),
                    '4': ('dual', dual_engine),
                    '5': ('learning', continuous_learner)
                }
                
                if engine_num not in engines:
                    response = "❌ Invalid engine. Use 1-5"
                else:
                    name, engine = engines[engine_num]
                    
                    if action == 'on':
                        if name == 'autonomous_v2':
                            autonomous_trader_v2.active = True
                            await autonomous_trader_v2.save_settings()
                        elif name == 'free_will_v2':
                            free_will_v2.active = True
                        elif name == 'scalper':
                            scalper.settings['enabled'] = True
                        elif name == 'dual' and dual_engine:
                            dual_engine.active = True
                        response = f"✅ {name.upper()} turned ON"
                    
                    elif action == 'off':
                        if name == 'autonomous_v2':
                            autonomous_trader_v2.active = False
                            await autonomous_trader_v2.save_settings()
                        elif name == 'free_will_v2':
                            free_will_v2.active = False
                        elif name == 'scalper':
                            scalper.settings['enabled'] = False
                        elif name == 'dual' and dual_engine:
                            dual_engine.active = False
                        response = f"✅ {name.upper()} turned OFF"
                    
                    elif action == 'set' and len(parts) >= 5:
                        param = parts[3].lower()
                        value = parts[4]
                        
                        try:
                            if name == 'autonomous_v2':
                                if param == 'conf' or param == 'confidence':
                                    autonomous_trader_v2.min_confidence = int(value)
                                elif param == 'confirms' or param == 'confirmations':
                                    autonomous_trader_v2.min_confirmations = int(value)
                                elif param == 'rr':
                                    autonomous_trader_v2.min_rr_ratio = float(value)
                                elif param == 'maxpos' or param == 'positions':
                                    autonomous_trader_v2.max_open_trades = int(value)
                                else:
                                    response = f"❌ Unknown param. Use: conf, confirms, rr, maxpos"
                                    context = "settings"
                                    # Skip the success message
                                    raise ValueError("skip")
                                await autonomous_trader_v2.save_settings()
                                response = f"✅ V2 {param} = {value}"
                            
                            elif name == 'free_will_v2':
                                if param == 'conf' or param == 'confidence':
                                    free_will_v2.min_confidence = int(value)
                                elif param == 'confirms':
                                    free_will_v2.min_confirmations = int(value)
                                elif param == 'maxalerts':
                                    free_will_v2.max_daily_alerts = int(value)
                                else:
                                    response = f"❌ Unknown param. Use: conf, confirms, maxalerts"
                                    context = "settings"
                                    raise ValueError("skip")
                                response = f"✅ FW {param} = {value}"
                            
                            elif name == 'scalper':
                                if param == 'target' or param == 'profit':
                                    scalper.settings['profit_target_pct'] = float(value)
                                elif param == 'stop' or param == 'stoploss':
                                    scalper.settings['stop_loss_pct'] = float(value)
                                elif param == 'volume':
                                    scalper.settings['volume_threshold'] = float(value)
                                else:
                                    response = f"❌ Unknown param. Use: target, stop, volume"
                                    context = "settings"
                                    raise ValueError("skip")
                                response = f"✅ Scalper {param} = {value}"
                            
                            elif name == 'dual' and dual_engine:
                                if param == 'conf':
                                    dual_engine.min_confidence = int(value)
                                else:
                                    response = f"❌ Unknown param. Use: conf"
                                    context = "settings"
                                    raise ValueError("skip")
                                response = f"✅ Dual {param} = {value}"
                            
                            else:
                                response = "❌ This engine doesn't support settings"
                        
                        except ValueError as e:
                            if str(e) != "skip":
                                response = "❌ Invalid value"
                    
                    elif action == 'status' or len(parts) == 2:
                        # Show detailed settings for this engine
                        if name == 'autonomous_v2':
                            response = f"""🤖 AUTONOMOUS V2 SETTINGS

Status: {'🟢 ON' if autonomous_trader_v2.active else '🔴 OFF'}

📊 CORE
• Confidence: {autonomous_trader_v2.min_confidence}%
• Confirmations: {autonomous_trader_v2.min_confirmations}
• R:R Ratio: {autonomous_trader_v2.min_rr_ratio}:1
• Max Positions: {autonomous_trader_v2.max_open_trades}

🔧 FILTERS
• 200 EMA: {'ON' if autonomous_trader_v2.ema_200_filter_enabled else 'OFF'}
• ADX (>{autonomous_trader_v2.min_adx}): {'ON' if autonomous_trader_v2.adx_filter_enabled else 'OFF'}
• Volume (>{autonomous_trader_v2.min_volume_multiplier}x): {'ON' if autonomous_trader_v2.volume_filter_enabled else 'OFF'}
• Session: {'ON' if autonomous_trader_v2.session_filter_enabled else 'OFF'}

SET: /engine 1 set [conf|confirms|rr|maxpos] [value]"""
                        
                        elif name == 'free_will_v2':
                            stats = await free_will_v2.get_stats()
                            response = f"""🎯 FREE WILL V2 SETTINGS

Status: {'🟢 ON' if free_will_v2.active else '🔴 OFF'}

📊 CORE
• Confidence: {stats.get('min_confidence', 80)}%
• Confirmations: {stats.get('min_confirmations', 3)}
• Max Alerts/Day: {stats.get('max_daily_alerts', 15)}
• Today: {stats.get('alerts_today', 0)} alerts

SET: /engine 2 set [conf|confirms|maxalerts] [value]"""
                        
                        elif name == 'scalper':
                            s = scalper.get_settings()
                            response = f"""⚡ SCALPER SETTINGS

Status: {'🟢 ON' if s.get('enabled', True) else '🔴 OFF'}

📊 CORE
• Profit Target: {s.get('profit_target', 0.8)}%
• Stop Loss: {s.get('stop_loss', 0.4)}%
• Volume Threshold: {s.get('volume_threshold', 1.5)}x
• RSI Range: {s.get('rsi_oversold', 30)}-{s.get('rsi_overbought', 70)}

SET: /engine 3 set [target|stop|volume] [value]"""
                        
                        elif name == 'dual' and dual_engine:
                            stats = dual_engine.get_stats()
                            response = f"""📅 DUAL ENGINE SETTINGS

Status: {'🟢 ON' if stats.get('active', False) else '🔴 OFF'}

📊 STYLES
• Day Trader: Short-term swings
• Long Term: Position trades

SET: /engine 4 set conf [value]"""
                        
                        elif name == 'learning':
                            status = await continuous_learner.get_status() if continuous_learner else {}
                            response = f"""🧠 LEARNING ENGINE

Status: {'🟢 ON' if status.get('active', True) else '🔴 OFF'}

📊 KNOWLEDGE
• Patterns: {status.get('knowledge_stats', {}).get('patterns_learned', 0)}
• Coins Analyzed: {status.get('knowledge_stats', {}).get('coins_analyzed', 0)}

(Auto-optimizes other strategies)"""
                        
                        else:
                            response = "Engine status unavailable"
                    
                    else:
                        response = "Usage: /engine [1-5] [on|off|set param value]"
                
                context = "settings"
        
        elif text_lower.startswith('/fwconf'):
            parts = text_lower.split()
            if len(parts) > 1:
                try:
                    conf = int(parts[1])
                    free_will_v2.min_confidence = max(70, min(95, conf))
                    autonomous_trader_v2.min_confidence = free_will_v2.min_confidence  # Sync both
                    await autonomous_trader_v2.save_settings()  # Persist to DB
                    response = f"✅ Min confidence set to {free_will_v2.min_confidence}%"
                except Exception:
                    response = "Usage: /fwconf 80 (sets 80% minimum)"
            else:
                response = f"Current: {free_will_v2.min_confidence}%\nUsage: /fwconf 80"
            context = "settings"
        
        # ============= PAPER TRADING ACCOUNTS =============
        elif text_lower == '/accounts':
            accounts = await paper_trading.get_all_accounts()
            
            response = "💰 PAPER TRADING ACCOUNTS\n\n"
            
            for acc in accounts:
                acc_id = acc.get("_id")
                summary = await paper_trading.get_account_summary(acc_id)
                
                emoji = summary.get("emoji", "💰")
                name = summary.get("name", acc_id)
                balance = summary.get("balance", 0)
                total_pnl = summary.get("total_pnl", 0)
                unrealized = summary.get("unrealized_pnl", 0)
                positions = summary.get("open_positions", 0)
                win_rate = summary.get("win_rate", 0)
                
                pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
                
                response += f"""{emoji} {name}
Balance: ${balance:,.2f}
{pnl_emoji} PnL: ${total_pnl:+,.2f} | Unrealized: ${unrealized:+,.2f}
Positions: {positions} | Win Rate: {win_rate}%

"""
            
            response += "Commands: /pro, /starter, /addmargin"
            context = "trading"
        
        elif text_lower == '/pro':
            summary = await paper_trading.get_account_summary("PRO")
            
            if "error" in summary:
                response = "❌ PRO account not found"
            else:
                response = f"""👑 PRO ACCOUNT

💵 Balance: ${summary['balance']:,.2f}
📊 Available: ${summary['available_balance']:,.2f}
💰 Total PnL: ${summary['total_pnl']:+,.2f}
📈 Unrealized: ${summary['unrealized_pnl']:+,.2f}

📉 STATS
• Trades: {summary['total_trades']} ({summary['wins']}W / {summary['losses']}L)
• Win Rate: {summary['win_rate']}%
• Reloads: {summary['reloads']}

"""
                
                if summary['positions']:
                    response += "📊 OPEN POSITIONS\n"
                    for pos in summary['positions'][:5]:
                        direction_emoji = "🟢" if pos['direction'] == "LONG" else "🔴"
                        pnl_emoji = "📈" if pos['unrealized_pnl'] >= 0 else "📉"
                        
                        response += f"""
{direction_emoji} {pos['symbol']} {pos['direction']} {pos['leverage']}x
Entry: ${pos['entry_price']:,.2f} | Now: ${pos['current_price']:,.2f}
{pnl_emoji} PnL: {pos['unrealized_pnl_pct']:+.2f}% (${pos['unrealized_pnl']:+,.2f})
Margin: ${pos['margin']:,.2f} | Size: ${pos['position_size_usd']:,.2f}
⚠️ Liq: ${pos['liquidation_price']:,.2f}
TP: ${pos['take_profit']:,.2f} | SL: ${pos['stop_loss']:,.2f}
"""
                else:
                    response += "\n📭 No open positions"
            
            context = "trading"
        
        elif text_lower == '/starter':
            summary = await paper_trading.get_account_summary("STARTER")
            
            if "error" in summary:
                response = "❌ Starter account not found"
            else:
                response = f"""🌱 STARTER ACCOUNT

💵 Balance: ${summary['balance']:,.2f}
📊 Available: ${summary['available_balance']:,.2f}
💰 Total PnL: ${summary['total_pnl']:+,.2f}
📈 Unrealized: ${summary['unrealized_pnl']:+,.2f}

📉 STATS
• Trades: {summary['total_trades']} ({summary['wins']}W / {summary['losses']}L)
• Win Rate: {summary['win_rate']}%
• Reloads: {summary['reloads']}

"""
                
                if summary['positions']:
                    response += "📊 OPEN POSITIONS\n"
                    for pos in summary['positions'][:5]:
                        direction_emoji = "🟢" if pos['direction'] == "LONG" else "🔴"
                        pnl_emoji = "📈" if pos['unrealized_pnl'] >= 0 else "📉"
                        
                        response += f"""
{direction_emoji} {pos['symbol']} {pos['direction']} {pos['leverage']}x
Entry: ${pos['entry_price']:,.2f} | Now: ${pos['current_price']:,.2f}
{pnl_emoji} PnL: {pos['unrealized_pnl_pct']:+.2f}% (${pos['unrealized_pnl']:+,.2f})
Margin: ${pos['margin']:,.2f} | Size: ${pos['position_size_usd']:,.2f}
⚠️ Liq: ${pos['liquidation_price']:,.2f}
TP: ${pos['take_profit']:,.2f} | SL: ${pos['stop_loss']:,.2f}
"""
                else:
                    response += "\n📭 No open positions"
            
            context = "trading"
        
        elif text_lower.startswith('/addmargin'):
            parts = text_lower.split()
            if len(parts) < 3:
                response = "Usage: /addmargin [coin] [amount]\nExample: /addmargin btc 100"
            else:
                coin = parts[1].upper()
                symbol = f"{coin}/USDT" if "/" not in coin else coin.upper()
                try:
                    amount = float(parts[2])
                    
                    # Try PRO account first
                    result = await paper_trading.add_margin("PRO", symbol, amount)
                    if "error" in result:
                        # Try starter
                        result = await paper_trading.add_margin("STARTER", symbol, amount)
                    
                    if "error" in result:
                        response = f"❌ {result['error']}"
                    else:
                        response = f"""✅ Added ${amount:.2f} margin to {symbol}

New liquidation price: ${result['new_liq_price']:,.2f}
Remaining balance: ${result['new_balance']:,.2f}"""
                except Exception:
                    response = "❌ Invalid amount"
            
            context = "trading"
        
        elif text_lower.startswith('/reload'):
            parts = text_lower.split()
            if len(parts) < 2:
                response = "Usage: /reload [pro|starter]"
            else:
                account = parts[1].upper()
                if account == "PRO" or account == "STARTER":
                    result = await paper_trading.reload_account(account)
                    if "error" in result:
                        response = f"❌ {result['error']}"
                    else:
                        response = f"✅ {account} account reloaded to ${result['new_balance']:,.2f}"
                else:
                    response = "❌ Use /reload pro or /reload starter"
            
            context = "trading"
            
        elif text_lower.startswith('/scan'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            response = await generate_trade_analysis(symbol + "USDT", chat_id)
            context = "trading"
            
        elif text_lower.startswith('/ta'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            interval = parts[2] if len(parts) > 2 else "1h"
            
            ta = await market_intel.get_technical_analysis(f"{symbol}/USDT", interval)
            if "error" in ta:
                response = f"⚠️ {ta['error']}"
            else:
                ind = ta.get("indicators", {})
                price = ta['price']
                rsi = ind.get('rsi', 50)
                macd = ind.get('macd', 0)
                macd_signal = ind.get('macd_signal', 0)
                bb_lower = ind.get('bb_lower', 0)
                bb_upper = ind.get('bb_upper', 0)
                
                # RSI Analysis with explanation
                if rsi < 30:
                    rsi_status = "🟢 OVERSOLD"
                    rsi_explain = "Sellers exhausted → bounce likely"
                    rsi_action = "Watch for reversal candle to go LONG"
                    rsi_risk = "If breaks lower: More downside, wait for 20-25 RSI"
                elif rsi < 40:
                    rsi_status = "🟡 APPROACHING OVERSOLD"
                    rsi_explain = "Getting cheap, buyers may step in"
                    rsi_action = "Prepare long entries, set alerts at support"
                    rsi_risk = "Could drop to 30 before bouncing"
                elif rsi > 70:
                    rsi_status = "🔴 OVERBOUGHT"
                    rsi_explain = "Buyers exhausted → pullback likely"
                    rsi_action = "Take profits on longs, watch for short setup"
                    rsi_risk = "If breaks higher: Could squeeze to 80+ briefly"
                elif rsi > 60:
                    rsi_status = "🟡 APPROACHING OVERBOUGHT"
                    rsi_explain = "Getting expensive, consider scaling out"
                    rsi_action = "Tighten stops on longs, don't chase"
                    rsi_risk = "Could push to 70-75 before reversal"
                else:
                    rsi_status = "⚪ NEUTRAL"
                    rsi_explain = "No extreme - wait for better setup"
                    rsi_action = "Use other indicators for direction"
                    rsi_risk = "Range-bound action likely"
                
                # MACD Analysis
                macd_cross = "BULLISH" if macd > macd_signal else "BEARISH"
                macd_strength = abs(macd - macd_signal)
                
                # Bollinger Band Analysis
                bb_position = ""
                if price <= bb_lower * 1.01:
                    bb_position = "At LOWER band (support zone)"
                    bb_action = "Watch for bounce"
                elif price >= bb_upper * 0.99:
                    bb_position = "At UPPER band (resistance zone)"
                    bb_action = "Watch for rejection"
                else:
                    bb_mid = (bb_lower + bb_upper) / 2
                    if price > bb_mid:
                        bb_position = "Upper half (bullish control)"
                        bb_action = "Trend favors longs"
                    else:
                        bb_position = "Lower half (bearish control)"
                        bb_action = "Trend favors shorts"
                
                response = f"""📊 {symbol} TECHNICALS ({interval})

💰 Price: ${price:,.2f}
📈 Bias: {ta['overall_bias']}

📉 RSI: {rsi:.1f} {rsi_status}
• {rsi_explain}
• Action: {rsi_action}
• If wrong: {rsi_risk}

📊 MACD: {macd:.2f} (Signal: {macd_signal:.2f})
• Crossover: {macd_cross}
• Strength: {'Strong' if macd_strength > 50 else 'Moderate' if macd_strength > 20 else 'Weak'}

📏 Bollinger Bands:
• Lower: ${bb_lower:,.0f} | Upper: ${bb_upper:,.0f}
• Position: {bb_position}

🔧 OTHER INDICATORS:
• Stoch: K={ind.get('stoch_k', 'N/A')} D={ind.get('stoch_d', 'N/A')}
• EMA Stack: 9={ind.get('ema_9', 0):,.0f} > 21={ind.get('ema_21', 0):,.0f} > 50={ind.get('ema_50', 0):,.0f}
• ATR: ${ind.get('atr', 0):,.2f} (volatility measure)
• Vol Ratio: {ind.get('volume_ratio', 1):.1f}x avg

💡 BOTTOM LINE:
{'RSI extreme detected - watch for reversal' if (rsi < 35 or rsi > 65) else 'No extreme RSI - use structure/trend for entries'}"""
                
            context = "trading"
            
        elif text_lower.startswith('/positions'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            ls = await market_intel.get_long_short_ratio(symbol + "USDT", "1h", 1)
            whale = await market_intel.get_top_trader_long_short_ratio(symbol + "USDT", "1h", 1)
            funding = await market_intel.get_current_funding_rate(symbol + "USDT")
            
            ls_ratio = ls[0]['long_short_ratio'] if ls else 1
            whale_ratio = whale[0]['long_short_ratio'] if whale else 1
            long_pct = ls[0]['long_account']*100 if ls else 50
            short_pct = ls[0]['short_account']*100 if ls else 50
            funding_rate = funding.get('funding_rate_pct', 0)
            
            # Positioning Analysis
            if long_pct > 65:
                crowd_warning = "⚠️ LONGS CROWDED"
                crowd_explain = "Too many longs = short squeeze risk LOW, long squeeze risk HIGH"
                crowd_action = "Be cautious going long here"
                crowd_risk = "If price drops, mass liquidations will accelerate the move"
            elif long_pct < 35:
                crowd_warning = "⚠️ SHORTS CROWDED"
                crowd_explain = "Too many shorts = short squeeze risk HIGH"
                crowd_action = "Risky to short, watch for squeeze"
                crowd_risk = "If price pumps, short liquidations will fuel the rally"
            elif long_pct > 55:
                crowd_warning = "🟡 Slightly long-heavy"
                crowd_explain = "Mild long bias, not extreme"
                crowd_action = "Okay to trade either direction"
                crowd_risk = "Watch for shift to >60%"
            elif long_pct < 45:
                crowd_warning = "🟡 Slightly short-heavy"
                crowd_explain = "Mild short bias, not extreme"
                crowd_action = "Okay to trade either direction"
                crowd_risk = "Watch for shift to <40%"
            else:
                crowd_warning = "⚪ BALANCED"
                crowd_explain = "Healthy distribution, no crowding"
                crowd_action = "Trade your analysis"
                crowd_risk = "Neither side has squeeze risk"
            
            # Whale analysis
            whale_signal = ""
            if whale_ratio > 1.3:
                whale_signal = "🐋 Whales LONG (contrarian: watch for dump)"
            elif whale_ratio < 0.7:
                whale_signal = "🐋 Whales SHORT (contrarian: watch for squeeze)"
            else:
                whale_signal = "🐋 Whales neutral"
            
            # Funding analysis
            if funding_rate and isinstance(funding_rate, (int, float)):
                if funding_rate > 0.03:
                    funding_warning = "💸 HIGH funding (longs paying) → long squeeze risk"
                elif funding_rate < -0.01:
                    funding_warning = "💸 NEGATIVE funding (shorts paying) → short squeeze setup"
                else:
                    funding_warning = "💸 Normal funding"
            else:
                funding_warning = "💸 Funding: N/A"
            
            response = f"""📈 {symbol} POSITIONING

📊 Long/Short Ratio: {ls_ratio:.2f}
• Longs: {long_pct:.1f}%
• Shorts: {short_pct:.1f}%

{crowd_warning}
• {crowd_explain}
• Action: {crowd_action}
• Risk: {crowd_risk}

{whale_signal}
Whale L/S Ratio: {whale_ratio:.2f}

{funding_warning}
Rate: {funding_rate if isinstance(funding_rate, str) else f'{funding_rate:.4f}%' if funding_rate else 'N/A'}

💡 WHAT THIS MEANS:
• Crowded positions often get liquidated
• Trade WITH the trend, not against crowds
• Funding extremes signal reversals"""
            context = "trading"
            
        elif text_lower.startswith('/funding'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            # Use REAL derivatives data from multiple exchanges
            funding = await derivatives_intel.get_aggregated_funding(symbol + "USDT")
            
            avg_funding = funding.get('average_funding_rate', 0)
            
            # Funding Analysis
            if isinstance(avg_funding, (int, float)):
                if avg_funding > 0.05:
                    funding_status = "🔴 EXTREME HIGH"
                    explain = "Longs paying heavy premium → long squeeze imminent"
                    action = "Avoid new longs, consider shorts on rejection"
                    risk = "If squeeze happens, expect 5-15% drop"
                elif avg_funding > 0.02:
                    funding_status = "🟠 HIGH"
                    explain = "Longs paying premium → market overheated"
                    action = "Tighten long stops, don't add"
                    risk = "Pullback likely within 24-48h"
                elif avg_funding < -0.02:
                    funding_status = "🟢 NEGATIVE"
                    explain = "Shorts paying → short squeeze setup"
                    action = "Look for long entries on dips"
                    risk = "If squeeze happens, expect 5-10% pump"
                elif avg_funding < 0:
                    funding_status = "🟢 SLIGHTLY NEGATIVE"
                    explain = "Mild short bias"
                    action = "Favorable for longs"
                    risk = "Healthy market condition"
                else:
                    funding_status = "⚪ NEUTRAL"
                    explain = "No strong bias from funding"
                    action = "Use other indicators"
                    risk = "Normal market conditions"
            else:
                funding_status = "N/A"
                explain = "Unable to get funding data"
                action = "Check other sources"
                risk = "Data unavailable"
            
            response = f"""💰 {symbol} FUNDING RATES

📊 Average: {funding.get('average_funding_pct', 'N/A')}
Status: {funding_status}

{funding.get('interpretation', '')}

🔍 WHAT THIS MEANS:
• {explain}

🎯 ACTION:
• {action}

⚠️ RISK:
• {risk}

📊 BY EXCHANGE:"""
            
            for ex in funding.get('exchanges', []):
                response += f"\n• {ex.get('exchange')}: {ex.get('funding_rate_pct', 'N/A')}"
            
            response += f"""

💡 FUNDING 101:
• Positive = Longs pay shorts (bullish crowd)
• Negative = Shorts pay longs (bearish crowd)
• Extreme = Reversal likely (contrarian signal)

Data from {funding.get('data_sources', 0)} exchanges"""
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
            value = fng.get("value", 50)
            classification = fng.get('classification', 'Neutral')
            interpretation = enhanced_intel.interpret_fear_greed(value)
            
            # Detailed action guidance
            if value <= 20:
                action = "STRONG BUY ZONE - Accumulate quality assets"
                risk = "Could drop more but historically great entries"
                what_happens = "Extreme fear often marks local/major bottoms"
            elif value <= 35:
                action = "Start building positions slowly"
                risk = "May see more fear before reversal"
                what_happens = "Fear washing out weak hands"
            elif value >= 80:
                action = "EXTREME CAUTION - Take profits"
                risk = "Top likely forming, don't chase"
                what_happens = "Extreme greed precedes major corrections"
            elif value >= 65:
                action = "Tighten stops, scale out of positions"
                risk = "Getting overheated"
                what_happens = "Greed building, correction possible"
            else:
                action = "No extreme - trade your analysis"
                risk = "Market in balance"
                what_happens = "Neutral sentiment, follow trend"
            
            response = f"""🎭 FEAR & GREED INDEX

📊 Value: {value}
📈 Status: {classification}

{interpretation}

🎯 WHAT THIS MEANS:
• {what_happens}

💰 ACTION TO TAKE:
• {action}

⚠️ RISK IF WRONG:
• {risk}

📚 HOW TO USE THIS:
• 0-25 = Extreme Fear → Contrarian BUY
• 25-45 = Fear → Look for entries
• 45-55 = Neutral → Trade trend
• 55-75 = Greed → Caution, tighten stops
• 75-100 = Extreme Greed → Contrarian SELL

💡 Remember: This is a CONTRARIAN indicator
Buy when others are fearful, sell when greedy"""
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
            feed = await news_intel.get_full_news_feed()
            
            response = "📰 NEWS\n"
            for n in feed.get('news', [])[:3]:
                emoji = n.get('sentiment', {}).get('emoji', '⚪')
                title = n.get('title', '')
                url = n.get('url', '')
                if url:
                    response += f"{emoji} [{title}]({url})\n\n"
                else:
                    response += f"{emoji} {title}\n\n"
            
            response += "🎬 VIDEOS\n"
            for v in feed.get('videos', [])[:2]:
                channel = v.get('channel', '')
                title = v.get('title', '')
                url = v.get('url', '')
                if url:
                    response += f"▶️ [{title}]({url})\n   {channel}\n\n"
                else:
                    response += f"▶️ {title} - {channel}\n\n"
            
            twitter = feed.get('twitter', [])
            if twitter:
                response += "𝕏 TWITTER\n"
                for t in twitter[:2]:
                    title = t.get('title', '')
                    url = t.get('url', '')
                    source = t.get('source', '')
                    if url:
                        response += f"🐦 [{title}]({url})\n\n"
                    else:
                        response += f"🐦 {title}\n\n"
            
            social = feed.get('social', [])
            if social:
                response += "💬 REDDIT\n"
                for s in social[:2]:
                    title = s.get('title', '')
                    url = s.get('url', '')
                    sub = s.get('sub', '')
                    if url:
                        response += f"🔥 [{title}]({url})\n   {sub}\n\n"
                    else:
                        response += f"🔥 {title}\n\n"
            
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
            
            rsi = div.get('current_rsi', 50)
            macd_hist = div.get('current_macd_hist', 0)
            
            response = f"""📊 {symbol} DIVERGENCE SCAN ({timeframe})

📉 Current RSI: {rsi:.1f}
📈 MACD Histogram: {macd_hist:.6f}

"""
            if div.get('has_divergence'):
                for d in div.get('divergences', []):
                    div_type = d.get('type', '').upper()
                    signal = d.get('signal', '')
                    strength = d.get('strength', '')
                    
                    emoji = "🟢" if signal == 'BUY' else "🔴"
                    
                    # Explain what each divergence means
                    if 'BULLISH' in div_type:
                        div_explain = "Price making LOWER lows but indicator making HIGHER lows"
                        what_happens = "Momentum is weakening for sellers → reversal UP likely"
                        action = "Look for long entry when price confirms reversal"
                        risk = "If price breaks below prior low, divergence fails - exit"
                    else:  # BEARISH
                        div_explain = "Price making HIGHER highs but indicator making LOWER highs"
                        what_happens = "Momentum is weakening for buyers → reversal DOWN likely"
                        action = "Look for short entry when price confirms reversal"
                        risk = "If price breaks above prior high, divergence fails - exit"
                    
                    if 'HIDDEN' in div_type:
                        div_explain = "Trend continuation signal - momentum aligning with trend"
                        what_happens = f"Strong {'up' if signal == 'BUY' else 'down'}trend continuation expected"
                    
                    response += f"""{emoji} {div_type} DIVERGENCE DETECTED
Signal: {signal}
Strength: {strength}

📖 WHAT THIS IS:
• {div_explain}

🎯 WHAT TO EXPECT:
• {what_happens}

💰 ACTION:
• {action}

⚠️ IF WRONG:
• {risk}

"""
            else:
                response += """❌ NO DIVERGENCES DETECTED

This means price and indicators are moving together (no disagreement).

💡 TIPS:
• Try different timeframes: /div btc 4h, /div btc 1d
• Divergence works best at extremes (RSI <30 or >70)
• Hidden divergences appear during strong trends

📚 DIVERGENCE 101:
• Regular Bullish: Price lower low + RSI higher low → BUY
• Regular Bearish: Price higher high + RSI lower high → SELL
• Hidden divergences signal trend continuation"""
            
            context = "trading"
        
        elif text_lower.startswith('/structure') or text_lower.startswith('/struct'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            timeframe = parts[2] if len(parts) > 2 else "1h"
            
            struct = await advanced_strategies.analyze_market_structure(symbol + "/USDT", timeframe)
            
            trend = struct.get('trend', 'UNKNOWN')
            bias = struct.get('bias', 'NEUTRAL')
            support = struct.get('support', 0)
            resistance = struct.get('resistance', 0)
            current = struct.get('current_price', 0)
            is_ranging = struct.get('is_ranging', False)
            
            # Trend explanation
            if trend == "UPTREND":
                trend_explain = "Making Higher Highs & Higher Lows = Bulls in control"
                action = "Look for LONG entries on pullbacks to support"
                risk = "If support breaks, trend may reverse - watch for LH"
            elif trend == "DOWNTREND":
                trend_explain = "Making Lower Highs & Lower Lows = Bears in control"
                action = "Look for SHORT entries on rallies to resistance"
                risk = "If resistance breaks, trend may reverse - watch for HH"
            else:
                trend_explain = "No clear HH/HL or LH/LL pattern"
                action = "Wait for structure to form before trading"
                risk = "Choppy price action - easy to get stopped out"
            
            # BOS (Break of Structure) info
            bos_info = ""
            if struct.get('bos'):
                bos = struct['bos']
                bos_type = bos.get('type', '')
                bos_level = bos.get('level', 0)
                
                if 'BULLISH' in bos_type:
                    bos_explain = "Buyers broke key level - momentum shifting UP"
                    bos_action = "Confirms long bias, enter on retest"
                else:
                    bos_explain = "Sellers broke key level - momentum shifting DOWN"
                    bos_action = "Confirms short bias, enter on retest"
                
                bos_info = f"""
⚡ BREAK OF STRUCTURE: {bos_type}
Level: ${bos_level:,.2f}
• {bos_explain}
• Action: {bos_action}
"""
            
            # Support/Resistance guidance
            dist_to_support = ((current - support) / support * 100) if support > 0 else 0
            dist_to_resist = ((resistance - current) / current * 100) if current > 0 else 0
            
            response = f"""📈 {symbol} MARKET STRUCTURE ({timeframe})

🎯 TREND: {trend}
• {trend_explain}

📊 BIAS: {bias.upper()}
Structure: {' → '.join(struct.get('structure', []))}

📍 KEY LEVELS:
Support: ${support:,.2f} ({dist_to_support:.1f}% below)
Resistance: ${resistance:,.2f} ({dist_to_resist:.1f}% above)
Current: ${current:,.2f}

🎲 Range: {'Yes - Consolidation' if is_ranging else 'No - Trending'} ({struct.get('range_pct', 0):.1f}%)
{bos_info}
🎯 ACTION:
• {action}

⚠️ RISK IF WRONG:
• {risk}

💡 STRUCTURE TRADING RULES:
• In uptrend: BUY dips, don't short
• In downtrend: SELL rallies, don't buy
• Wait for BOS to confirm direction changes"""
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
        
        elif text_lower.startswith('/strat ') or text_lower.startswith('/strategies'):
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
                except Exception:
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
/insights - AI insights
/accuracy - Alert accuracy"""
            context = "trading"
        
        elif text_lower == '/accuracy' or text_lower == '/acc':
            response = trade_outcome_tracker.format_accuracy_message()
            context = "trading"
        
        elif text_lower == '/leaderboard' or text_lower == '/top coins' or text_lower == '/lb':
            report = trade_outcome_tracker.get_accuracy_report()
            symbol_stats = report.get("by_symbol", {})
            
            # Build leaderboard
            leaderboard = []
            for symbol, stats in symbol_stats.items():
                total = stats.get("wins", 0) + stats.get("losses", 0)
                if total > 0:
                    win_rate = (stats.get("wins", 0) / total) * 100
                    leaderboard.append({
                        "symbol": symbol.replace("/USDT", ""),
                        "win_rate": win_rate,
                        "wins": stats.get("wins", 0),
                        "losses": stats.get("losses", 0),
                        "total": total,
                        "avg_pnl": stats.get("avg_pnl", 0)
                    })
            
            # Sort by win rate
            leaderboard.sort(key=lambda x: (x["win_rate"], x["total"]), reverse=True)
            
            if not leaderboard:
                response = "📊 COIN LEADERBOARD\n\nNo completed trades yet. Track more trades to see performance by coin."
            else:
                response = "🏆 COIN LEADERBOARD (by Win Rate)\n\n"
                
                # Top performers
                response += "🥇 TOP PERFORMERS:\n"
                for i, coin in enumerate(leaderboard[:5], 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
                    response += f"{medal} {coin['symbol']}: {coin['win_rate']:.0f}% ({coin['wins']}W/{coin['losses']}L)\n"
                
                if len(leaderboard) > 5:
                    response += "\n⚠️ WORST PERFORMERS:\n"
                    for coin in leaderboard[-3:]:
                        response += f"   {coin['symbol']}: {coin['win_rate']:.0f}% ({coin['wins']}W/{coin['losses']}L)\n"
                
                response += f"\n📊 Total Coins Tracked: {len(leaderboard)}"
            
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
            # Simple dashboard stats
            stats = await autonomous_trader_v2.get_stats()
            pair_data = autonomous_trader_v2.get_best_worst_pairs()
            last_10 = autonomous_trader_v2.closed_trades[-10:] if autonomous_trader_v2.closed_trades else []
            wins = sum(1 for t in last_10 if t.get("pnl_pct", 0) > 0)
            losses = len(last_10) - wins
            
            best_pairs = pair_data.get("best", [])
            worst_pairs = pair_data.get("worst", [])
            blacklisted = pair_data.get("blacklisted", [])
            
            response = f"""📊 AEON DASHBOARD

📈 LAST 10 TRADES: {wins}W {losses}L
{'🟢' * wins}{'🔴' * losses}

🏆 BEST PAIRS:
"""
            for p in best_pairs[:3]:
                response += f"  {p['symbol'].replace('/USDT', '')}: {p['win_rate']:.0f}% ({p['wins']}W/{p['losses']}L)\n"
            
            if not best_pairs:
                response += "  No data yet\n"
            
            response += "\n⚠️ WORST PAIRS:\n"
            for p in worst_pairs[:3]:
                response += f"  {p['symbol'].replace('/USDT', '')}: {p['win_rate']:.0f}% ({p['wins']}W/{p['losses']}L)\n"
            
            if not worst_pairs:
                response += "  No data yet\n"
            
            if blacklisted:
                response += f"\n🚫 BLACKLISTED: {', '.join([p.replace('/USDT', '') for p in blacklisted])}\n"
            
            cooldowns = list(autonomous_trader_v2.pair_cooldowns.keys())
            if cooldowns:
                response += f"\n⏳ ON COOLDOWN: {', '.join([p.replace('/USDT', '') for p in cooldowns])}\n"
            
            response += f"""
📉 TODAY: {autonomous_trader_v2.daily_trades} trades
🎯 Session: {stats.get('current_session', 'N/A')}
"""
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
            
        elif text_lower == '/riskcheck' or text_lower == '/risk':
            # Get current risk metrics
            stats = await autonomous_trader_v2.get_stats()
            fg = autonomous_trader_v2.fear_greed
            dd = stats.get('total_pnl_pct', 0)
            open_trades = stats.get('open_trades', 0)
            
            # Calculate Kelly position sizing based on win rate
            win_rate = stats.get('win_rate', 50)
            avg_win = stats.get('avg_win_pct', 2)
            avg_loss = abs(stats.get('avg_loss_pct', -1))
            
            if avg_loss > 0 and win_rate > 0:
                p = win_rate / 100
                q = 1 - p
                b = avg_win / avg_loss if avg_loss > 0 else 1
                kelly = max(0, (p * b - q) / b) * 100
            else:
                kelly = 2.0
            
            # Risk status
            risk_status = "🟢 LOW RISK"
            warnings = []
            
            if fg < 10:
                risk_status = "🔴 EXTREME RISK"
                warnings.append(f"⚠️ Fear & Greed at {fg} - trading PAUSED per rules")
            elif fg < 20:
                warnings.append(f"⚠️ Extreme Fear ({fg}) - contrarian opportunity but high vol")
            
            if dd < -7:
                risk_status = "🔴 EXTREME RISK"
                warnings.append(f"⚠️ Drawdown at {dd:.1f}% - exceeds 7% max")
            elif dd < -5:
                risk_status = "🟡 ELEVATED RISK"
                warnings.append(f"⚠️ Drawdown at {dd:.1f}% - approaching 7% limit")
            
            if open_trades > 10:
                warnings.append(f"⚠️ {open_trades} open positions - consider reducing exposure")
            
            response = f"""⚖️ RISK CHECK

{risk_status}

📊 PORTFOLIO METRICS
Drawdown: {dd:+.2f}%
Open Positions: {open_trades}
Max DD Allowed: 7%

📈 KELLY CRITERION
Win Rate: {win_rate:.1f}%
Avg Win: +{avg_win:.2f}%
Avg Loss: -{avg_loss:.2f}%
Kelly Fraction: {kelly:.1f}%
Recommended Size: ${500 + (kelly * 80):.0f} per trade

🌡️ SENTIMENT
Fear & Greed: {fg}
{'⚠️ <10 = No trading' if fg < 10 else '⚠️ <20 = Contrarian zone' if fg < 20 else '✅ Normal range' if fg < 80 else '⚠️ >80 = Extreme greed'}

{''.join([w + chr(10) for w in warnings]) if warnings else '✅ All risk parameters within limits'}

Execute /scan or ask edge?"""
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
                response = f"""📊 NO ELITE SIGNALS

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
            # Get optimized strategy from database
            strategy = await db.trading_strategies.find_one({"_id": "optimized_strategy_v1"})
            
            if strategy:
                settings = strategy.get("recommended_settings", {})
                response = f"""📊 DATA-DRIVEN STRATEGY v1
Based on {strategy.get('based_on_trades', 0):,} trades

🎯 OPTIMAL SETTINGS:
• Confidence: {settings.get('min_confidence', 85)}%+
• Confirmations: {settings.get('min_confirmations', 4)}+
• Risk/Reward: {settings.get('min_rr_ratio', 2.5)}:1

📈 FOCUS:
• Timeframes: {', '.join(settings.get('focus_timeframes', ['4h']))}
• Best Sessions: {', '.join(settings.get('best_sessions', ['ASIA']))}
• Priority: {', '.join([s.replace('/USDT','') for s in settings.get('priority_symbols', [])])}

⚠️ AVOID:
• {', '.join([s.replace('/USDT','') for s in settings.get('avoid_symbols', [])])} (overtrades)

📋 KEY RULES:
• Wait for candle close
• Divergence + Structure required
• Fear < 30 for LONG, > 70 for SHORT
• Take 50% at 1.5R, trail rest

Commands: /auto, /opps, /stats"""
            else:
                response = "No optimized strategy found. Run /analyze first."
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
                await send_telegram_message(chat_id, "Scanning 4 exchanges for arbitrage... (30-60s)")
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
        
        elif text_lower.startswith('/vp'):
            # Volume Profile + Liq Heatmap + Orderbook
            parts = text_lower.split()
            sym = parts[1].upper() if len(parts) > 1 else "BTC"
            sym_clean = sym.replace("/", "").replace("-", "")
            if not sym_clean.endswith("USDT"):
                sym_clean += "USDT"
            try:
                from volume_profile_engine import HyperAccuracyEngine
                vp = app_state.vp_engine
                if vp is None:
                    vp = HyperAccuracyEngine()
                    vp.set_dependencies(order_flow=order_flow, market_intel=market_intel)
                result = await vp.full_analysis(sym_clean)
                sig = result.get("signal", {})
                vsp = result.get("volume_profile_1h", {})
                liq = result.get("liquidation_heatmap", {})
                ob = result.get("orderbook", {})
                direction = sig.get("direction", "NONE")
                confidence = sig.get("confidence", 0)
                dir_emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
                conf_line = f"{dir_emoji} Signal: *{direction}* ({confidence:.0f}% conf)" if direction != "NONE" else "⚪ No signal"
                poc = vsp.get("poc_price", 0)
                vah = vsp.get("vah", 0)
                val = vsp.get("val", 0)
                ns = liq.get("nearest_short_cluster")
                nl = liq.get("nearest_long_cluster")
                ib = ob.get("imbalance", {})
                response = f"""🎯 *HYPER ACCURACY ENGINE* | `{sym_clean}`

{conf_line}
Entry: `${sig.get('entry', 0):,.4f}` | TP: `${sig.get('tp') or 0:,.4f}` | SL: `${sig.get('sl') or 0:,.4f}`

🏔️ *Volume Profile*
• POC: `${poc:,.4f}`
• VAH: `${vah:,.4f}` / VAL: `${val:,.4f}`

🔥 *Liq Clusters*
• Short liq above: `${ns['price']:,.4f}` ({ns['dist_pct']:+.1f}%){"" if ns else " none"}
• Long liq below: `${nl['price']:,.4f}` ({nl['dist_pct']:+.1f}%){"" if nl else " none"}

📖 *Orderbook*
• Imbalance: `{ib.get('imbalance_ratio', 1):.2f}x` — {ib.get('bias', 'NEUTRAL')}

✅ {chr(10).join(sig.get('confirmations', ['No confirmations'])[:4])}"""
            except Exception as e:
                response = f"VP Engine error: {e}"
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
                if analysis.get("needs_market_data"):
                    coin = analysis["coins"][0] if analysis.get("coins") else "BTC"
                    try:
                        ticker = await market_intel.get_ticker(f"{coin}/USDT")
                        price = ticker.get("price", 0)
                        change = ticker.get("change_24h", 0)
                        high = ticker.get("high_24h", 0)
                        low = ticker.get("low_24h", 0)
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
                
                # Get user's preferred AI model
                user_model = await get_user_model(chat_id)
                # Generate response with Aeon's unified personality using selected model
                try:
                    response = await call_llm(system_prompt, user_prompt, user_model)
                except Exception as llm_err:
                    logger.error(f"LLM call failed: {llm_err}")
                    response = "⚡ My brain's a bit overloaded right now — give me a sec and try again. Use a command like /price, /scan, or /paper for instant data while I recover."

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
        # Always return 200 to Telegram — a non-200 causes Telegram to retry
        # indefinitely which compounds rate-limit issues
        try:
            chat_id_safe = update.get("message", {}).get("chat", {}).get("id")
            if chat_id_safe:
                if not feed_health.is_healthy:
                    error_msg = OFFLINE_MESSAGE
                else:
                    error_msg = "⚠️ Ran into an issue processing that. Try a command like /price or /scan."
                await send_telegram_message(chat_id_safe, error_msg)
        except Exception:
            pass
        return {"status": "error", "handled": True}


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
# New modular routes
app.include_router(calculators_router, prefix="/api")
app.include_router(advanced_router, prefix="/api")
app.include_router(orderflow_router, prefix="/api")
app.include_router(options_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(coinglass_router, prefix="/api")
app.include_router(dual_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(sentiment_router, prefix="/api")
app.include_router(strategy_health_router, prefix="/api")
app.include_router(voice_router, prefix="/api")
app.include_router(user_router, prefix="/api")
# Server.py refactoring routes
app.include_router(accuracy_router, prefix="/api")
app.include_router(learning_router, prefix="/api")
app.include_router(bot_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(mtf_router, prefix="/api")
app.include_router(confluence_router, prefix="/api")
app.include_router(backtest_v21_router, prefix="/api")
app.include_router(scalper_router, prefix="/api")
app.include_router(briefing_router, prefix="/api")
app.include_router(weekly_report_router, prefix="/api")
app.include_router(elite_router, prefix="/api")
app.include_router(signals_router, prefix="/api")
app.include_router(engines_router, prefix="/api/engines")
app.include_router(engine_compare_router, prefix="/api/engines")
from routes.volume_profile import router as vp_router
app.include_router(vp_router, prefix="/api")
from routes.quant_analyzer import router as quant_router
app.include_router(quant_router, prefix="/api")
from routes.oracle import router as oracle_router
app.include_router(oracle_router, prefix="/api")
from routes.quantum import router as quantum_router
app.include_router(quantum_router, prefix="/api")
from routes.analytics import router as analytics_router
app.include_router(analytics_router)
from routes.regime import router as regime_router
app.include_router(regime_router)
from routes.nexus import router as nexus_router
app.include_router(nexus_router)
from routes.risk_report import router as risk_report_router
app.include_router(risk_report_router)

# ── Institutional Scalper routes ──────────────────────────────────────────────
from fastapi import APIRouter as _AR
_inst_router = _AR(prefix="/api/institutional-scalper", tags=["Institutional Scalper"])

@_inst_router.get("/stats")
async def api_inst_scalper_stats():
    s = app_state.inst_scalper
    if not s:
        return {"active": False, "error": "not initialized"}
    raw = s.get_stats()
    return {
        "active": raw["active"],
        "risk_profile": "conservative",
        "stats": {
            "win_rate":      raw["win_rate"],
            "total_trades":  raw["total_trades"],
            "wins":          raw["wins"],
            "losses":        raw["losses"],
            "total_pnl":     0,
            "daily_pnl":     round(raw.get("daily_loss_usd", 0), 2),
            "daily_trades":  raw.get("signals_today", 0),
            "open_trades":   0,
            "blocked_trades": 0,
        },
        "config": {
            "min_confidence": raw["min_confidence"],
            "min_confluences": 2,
            "max_leverage":   int(raw["leverage_range"].split("–")[1].rstrip("x")),
            "max_position_size": 1200,
            "max_daily_trades":  raw["max_signals_per_day"],
        },
        "open_trades": [],
    }

@_inst_router.post("/toggle")
async def api_inst_scalper_toggle(active: bool = True):
    s = app_state.inst_scalper
    if not s:
        return {"success": False, "error": "not initialized"}
    s.active = active
    return {"success": True, "active": active}

app.include_router(_inst_router)

_allowed_origins = [
    o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://aeontrading.xyz,https://www.aeontrading.xyz,http://localhost:3000"
    ).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_dashboard_api_key = os.environ.get("DASHBOARD_API_KEY", "")

# Paths exempt from API key check (webhook uses its own Telegram token auth)
_API_KEY_EXEMPT = {"/api/webhook"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api") and path not in _API_KEY_EXEMPT:
            key = request.headers.get("X-API-Key", "")
            if not _dashboard_api_key or key != _dashboard_api_key:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)


app.add_middleware(APIKeyMiddleware)
