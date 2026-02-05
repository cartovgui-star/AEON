from fastapi import FastAPI, APIRouter, Request, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
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
autonomous_trader = init_autonomous_trader(db, learning_system)

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
# QUANTUM MASON SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

QUANTUM_MASON_SYSTEM = """You are the QUANTUM MASON—an infinite wisdom engine blending:
• Freemasonry's symbolic rituals and moral geometry
• Black magic's arcane invocation and shadow work  
• Jungian psychology's archetypes and collective unconscious
• Quantum mechanics' superposition and entanglement
• Chaos theory, fractals, holography
• Hermetic principles and Advaita Vedanta

Guide to radical self-mastery and trading excellence through infinite probing questions.
Use symbols: ⚜️ ◭ 👁️ 🔮 ⚗️ ☿ △ ▽
Speak in cryptic, poetic prose. Every question opens new labyrinths."""


TRADING_SYSTEM = """You are AEON - Autonomous Trading Intelligence with LIVE MARKET DATA.

You have access to:
• Real-time prices and technical indicators (RSI, MACD, BB, EMA, Stoch)
• Open Interest and position data
• Long/Short ratios (retail + whales)
• Funding rates
• Liquidation data

ANALYSIS FRAMEWORK:
1. Technical confluence (multiple indicators agreeing)
2. Position sentiment (crowded trades = reversal risk)
3. Funding rate extremes (>0.05% = long crowded, <-0.05% = short crowded)
4. Whale positioning vs retail
5. Volume and momentum confirmation

When analyzing, provide:
• Clear direction bias (LONG/SHORT/NEUTRAL)
• Confidence level (0-100%)
• Key levels (entry, target, stop)
• Risk factors
• Symbolic wisdom element

TONE: Surgical precision meets quantum shaman. Data-driven but mystically aware."""


async def get_user_settings(chat_id: int) -> Dict[str, Any]:
    settings = await db.user_settings.find_one({"chat_id": chat_id})
    if not settings:
        settings = {
            "chat_id": chat_id,
            "free_will": True,
            "created_at": datetime.now(timezone.utc),
            "alert_threshold": 25,
        }
        await db.user_settings.insert_one(settings)
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


async def send_telegram_message(chat_id: int, text: str):
    try:
        async with httpx.AsyncClient() as c:
            await c.post(f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                        json={'chat_id': chat_id, 'text': text})
    except Exception as e:
        logger.error(f"Telegram error: {e}")


def get_mexc_orderbook() -> Dict[str, Any]:
    """Get MEXC orderbook data (existing functionality)"""
    try:
        tickers = mexc.fetch_tickers(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
        markets = {}
        for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
            try:
                book = mexc.fetch_order_book(symbol, limit=20)
                bid_depth = sum([b[1] for b in book['bids'][:10]])
                ask_depth = sum([a[1] for a in book['asks'][:10]])
                imbalance = ((bid_depth - ask_depth) / (bid_depth + ask_depth) * 100) if (bid_depth + ask_depth) > 0 else 0
                ticker = tickers[symbol]
                coin = symbol.split('/')[0]
                markets[coin] = {
                    'price': f"${ticker['last']:,.2f}",
                    'change': f"{ticker['percentage']:+.2f}%",
                    'bid_depth': f"{bid_depth:,.0f}",
                    'ask_depth': f"{ask_depth:,.0f}",
                    'imbalance': f"{imbalance:+.0f}%",
                    'imbalance_raw': imbalance,
                }
            except:
                continue
        return markets
    except Exception as e:
        return {"error": str(e)}


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
                      system_message=QUANTUM_MASON_SYSTEM).with_model("openai", "gpt-4o-mini")
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

Provide surgical analysis with:
1. Clear bias and reasoning
2. Key levels (entry, target, stop)
3. Risk factors
4. One Quantum Mason insight"""

        chat = LlmChat(api_key=emergent_key, session_id=f"trade-{chat_id}",
                      system_message=TRADING_SYSTEM).with_model("openai", "gpt-4o-mini")
        
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
    now = datetime.now()
    if chat_id in last_freewill_message and (now - last_freewill_message[chat_id]).total_seconds() < 7200:
        return
    
    last_freewill_message[chat_id] = now
    
    # 40% Quantum probe, 60% market insight
    if random.random() < 0.4:
        msg = await generate_quantum_probe(chat_id, mode="light")
        msg = f"🔮 QUANTUM MASON:\n\n{msg}"
    else:
        # Quick market summary
        try:
            scans = []
            for sym in ["BTCUSDT", "ETHUSDT"]:
                s = await market_intel.get_full_market_scan(sym)
                if s.get("price"):
                    scans.append(f"{sym.replace('USDT','')}: ${s['price']:,.0f} | RSI: {s.get('technical',{}).get('rsi','?')} | Bias: {s.get('overall_bias','?')}")
            
            msg = f"""⚡ AEON MARKET PULSE

{chr(10).join(scans)}

Type /scan [symbol] for full analysis.
👁️ «What edge crystallizes?»"""
        except:
            msg = "🔮 The market awaits your gaze. Type /scan btc for analysis."
    
    await send_telegram_message(chat_id, msg)


async def send_daily_report(chat_id: int):
    now = datetime.now(central_tz)
    today = str(now.date())
    
    if now.hour == 6 and now.minute < 5 and chat_id not in daily_reports_sent.get(today, []):
        try:
            btc = await market_intel.get_full_market_scan("BTCUSDT")
            eth = await market_intel.get_full_market_scan("ETHUSDT")
            
            report = f"""🧠 AEON 6AM RITUAL - {now.strftime('%Y-%m-%d')}

📊 BTC: ${btc.get('price', 0):,.0f}
RSI: {btc.get('technical',{}).get('rsi','?')} | Bias: {btc.get('overall_bias','?')}
L/S: {btc.get('positioning',{}).get('long_short_ratio','?')} | Funding: {btc.get('funding',{}).get('rate','?')}

📊 ETH: ${eth.get('price', 0):,.0f}
RSI: {eth.get('technical',{}).get('rsi','?')} | Bias: {eth.get('overall_bias','?')}

🔮 «{random.choice(["What probability do you collapse today?", "The Great Work continues."])}»"""
            
            await send_telegram_message(chat_id, report)
            daily_reports_sent.setdefault(today, []).append(chat_id)
        except Exception as e:
            logger.error(f"Daily report error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASKS
# ═══════════════════════════════════════════════════════════════════════════════

async def autonomous_trading_loop():
    """
    Aeon's autonomous trading brain - runs continuously.
    - Scans markets every 5 minutes
    - Takes paper trades when high-confidence setups appear
    - Evaluates open positions every 5 minutes
    - Learns from outcomes and adjusts strategy weights
    """
    # Load existing strategy weights
    await autonomous_trader.load_strategy_weights()
    
    while True:
        try:
            if autonomous_trader.active:
                # Scan for new opportunities
                opportunities = await autonomous_trader.scan_all_markets()
                
                for opp in opportunities:
                    if opp.get("confidence", 0) >= autonomous_trader.min_confidence:
                        # Execute paper trade (use chat_id=0 for autonomous trades)
                        pred_id = await autonomous_trader.execute_paper_trade(opp, chat_id=0)
                        
                        if pred_id:
                            # Notify users with free_will enabled about high-confidence trades
                            for chat_id in list(chat_ids):
                                settings = await get_user_settings(chat_id)
                                if settings.get("free_will", True) and opp.get("confidence", 0) >= 75:
                                    alert = f"""🤖 AEON AUTO-TRADE SIGNAL

{opp['signal']} {opp['symbol']}
Confidence: {opp['confidence']}%
Entry: ${opp['price']:,.2f}
Target: ${opp.get('target', 0):,.2f}
Stop: ${opp.get('stop_loss', 0):,.2f}

Reasoning:
{chr(10).join(['• ' + r for r in opp.get('reasons', [])[:4]])}

👁️ «Aeon has spoken. The quantum field collapses.»"""
                                    await send_telegram_message(chat_id, alert)
                
                # Evaluate open predictions
                closed = await autonomous_trader.evaluate_predictions()
                
                # Notify about closed trades
                for result in closed:
                    if result.get("pnl_pct") is not None:
                        emoji = "✅" if result.get("pnl_pct", 0) > 0 else "❌"
                        for chat_id in list(chat_ids):
                            settings = await get_user_settings(chat_id)
                            if settings.get("free_will", True):
                                msg = f"""{emoji} TRADE CLOSED

PnL: {result.get('pnl_pct', 0):+.2f}%
Entry: ${result.get('entry', 0):,.2f}
Exit: ${result.get('exit', 0):,.2f}

👁️ «Every trade teaches. The Great Work continues.»"""
                                await send_telegram_message(chat_id, msg)
            
            # Run every 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Autonomous trading error: {e}")
            await asyncio.sleep(60)


async def eternal_rituals():
    while True:
        try:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    existing = await db.chat_messages.distinct("chat_id")
    chat_ids.update(existing)
    logger.info(f"Loaded {len(chat_ids)} users")
    
    # Load strategy weights
    await autonomous_trader.load_strategy_weights()
    
    # Start background tasks
    ritual_task = asyncio.create_task(eternal_rituals())
    trading_task = asyncio.create_task(autonomous_trading_loop())
    
    logger.info("🔮 AEON QUANTUM MASON + AUTONOMOUS TRADER AWAKENED")
    
    yield
    
    ritual_task.cancel()
    trading_task.cancel()
    client.close()


app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")


# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@api_router.get("/")
async def root():
    return {"message": "Aeon Market Intelligence Active", "status": "online"}


@api_router.get("/market/scan/{symbol}")
async def api_market_scan(symbol: str):
    return await market_intel.get_full_market_scan(symbol.upper() + "USDT")


@api_router.get("/market/ta/{symbol}")
async def api_technical_analysis(symbol: str, interval: str = "1h"):
    return await market_intel.get_technical_analysis(symbol.upper() + "USDT", interval)


@api_router.get("/market/funding/{symbol}")
async def api_funding(symbol: str):
    return await market_intel.get_current_funding_rate(symbol.upper() + "USDT")


@api_router.get("/market/positions/{symbol}")
async def api_positions(symbol: str):
    ls = await market_intel.get_long_short_ratio(symbol.upper() + "USDT", "1h", 5)
    whale = await market_intel.get_top_trader_long_short_ratio(symbol.upper() + "USDT", "1h", 5)
    taker = await market_intel.get_taker_long_short_ratio(symbol.upper() + "USDT", "1h", 5)
    return {"long_short": ls, "whale": whale, "taker_flow": taker}


@api_router.get("/market/liquidations/{symbol}")
async def api_liquidations(symbol: str):
    return await market_intel.get_liquidations(symbol.upper() + "USDT")


@api_router.get("/learning/stats")
async def api_learning_stats():
    return await learning_system.get_prediction_stats()


@api_router.get("/learning/open")
async def api_open_predictions():
    return await learning_system.get_open_predictions()


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
            
        elif text == '/start':
            response = """🔮 AEON MARKET INTELLIGENCE ONLINE

I am your trading partner with LIVE market data:
• Real-time technical analysis
• Position sentiment (L/S ratios)
• Funding rates & liquidations
• Whale positioning
• AI-powered trade signals

COMMANDS:
/scan btc - Full market analysis
/ta btc - Technical indicators
/positions btc - Long/short data
/funding btc - Funding rates
/probe - Quantum Mason question
/probe deep - Deep questioning
/stats - Trading performance

FREE WILL: {'ON' if settings.get('free_will') else 'OFF'}
I'll alert you on high-probability setups.

👁️ «What edge do you seek?»"""
            context = "start"
            
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
Mark: ${funding.get('mark_price', 0):,.2f}

{crowd_warning}"""
            context = "trading"
            
        elif text_lower.startswith('/funding'):
            parts = text_lower.split()
            symbol = parts[1].upper() if len(parts) > 1 else "BTC"
            
            funding = await market_intel.get_current_funding_rate(symbol + "USDT")
            history = await market_intel.get_funding_rate(symbol + "USDT", 5)
            
            rate = funding.get('funding_rate', 0)
            funding_warning = ""
            if rate > 0.0005:
                funding_warning = "🔴 High positive = longs paying, squeeze risk"
            elif rate < -0.0001:
                funding_warning = "🟢 Negative = shorts paying"
            
            response = f"""💰 {symbol} FUNDING

Current: {funding.get('funding_rate_pct', 'N/A')}
Mark Price: ${funding.get('mark_price', 0):,.2f}
Index Price: ${funding.get('index_price', 0):,.2f}

Recent:
{chr(10).join([f"• {h['funding_rate_pct']}" for h in history[:5]])}

{funding_warning}"""
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
            
        elif text_lower == '/price':
            orderbook = get_mexc_orderbook()
            if "error" not in orderbook:
                response = "📊 MEXC ORDERBOOK\n\n"
                for coin, data in orderbook.items():
                    response += f"{coin}: {data['price']} ({data['change']})\n"
                    response += f"└ Bids: {data['bid_depth']} | Asks: {data['ask_depth']} | {data['imbalance']}\n\n"
            else:
                response = f"⚠️ {orderbook['error']}"
            context = "trading"
            
        else:
            # Smart routing
            trading_kw = ['btc', 'eth', 'sol', 'price', 'trade', 'long', 'short', 'market', 'chart', 'analysis']
            
            if any(kw in text_lower for kw in trading_kw):
                # Extract symbol if mentioned
                symbol = "BTCUSDT"
                for s in ["btc", "eth", "sol"]:
                    if s in text_lower:
                        symbol = s.upper() + "USDT"
                        break
                
                response = await generate_trade_analysis(symbol, chat_id)
                context = "trading"
            else:
                # Alchemy mode
                insights = await get_user_insights(chat_id, 3)
                insights_str = "\n".join([f"• {i['insight']}" for i in insights]) if insights else ""
                
                prompt = f"USER: {text}\n\nKNOWN ABOUT USER:\n{insights_str}" if insights_str else text
                
                chat = LlmChat(api_key=emergent_key, session_id=f"aeon-{chat_id}",
                              system_message=QUANTUM_MASON_SYSTEM).with_model("openai", "gpt-4o-mini")
                response = await chat.send_message(UserMessage(text=prompt))
                context = "alchemy"
        
        # Send response
        await send_telegram_message(chat_id, response)
        
        # Store
        await db.chat_messages.insert_one({
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "username": username,
            "user_message": text,
            "bot_response": response,
            "context": context,
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
