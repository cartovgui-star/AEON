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
from datetime import datetime, timezone, timedelta
import httpx
import ccxt
import random
import asyncio
import pytz
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# API Keys
emergent_key = os.environ.get('EMERGENT_LLM_KEY', '')
telegram_token = os.environ.get('TELEGRAM_TOKEN', '')
mexc_api_key = os.environ.get('MEXC_API_KEY', '')
mexc_secret_key = os.environ.get('MEXC_SECRET_KEY', '')
obsidian_webhook = os.environ.get('OBSIDIAN_WEBHOOK', '')

# Initialize MEXC exchange
mexc = ccxt.mexc({
    'apiKey': mexc_api_key,
    'secret': mexc_secret_key,
    'enableRateLimit': True,
})

# Timezone
central_tz = pytz.timezone('US/Central')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
chat_ids: Set[int] = set()
last_checkin: Dict[int, datetime] = {}
last_market_alert: Dict[int, datetime] = {}
last_freewill_message: Dict[int, datetime] = {}
daily_reports_sent: Dict[str, List[int]] = {}
stock_reports_sent: Dict[str, List[int]] = {}

# Alchemical question bank
INTERVIEW_QUESTIONS = [
    "What assumption dies today to birth tomorrow's mastery?",
    "Where does your will clash with reality's resistance?",
    "Name the shadow you're ready to integrate into power.",
    "What truth terrifies you but demands integration?",
    "What action collapses infinite possibilities into YOUR reality?",
    "Where do you observe passively when action is required?",
    "What perfect ashlar hides within your roughest stone?",
    "Three breaths from now—what reality do you create?",
    "As above, so below: What inner chaos manifests externally?",
    "What probability wave collapses under your gaze today?",
    "Solve et coagula: What dissolves? What reforms stronger?",
    "First Degree: What base metal purifies in your furnace?",
    "Second Degree: Where does wisdom temper brute strength?",
    "Third Degree: What mastery awaits your final polish?",
    "Square, compass, plumb: Which Masonic tool guides now?",
    "What sigil of intention rewrites tomorrow's probability field?",
    "Where does your focused gaze bend the ether itself?",
    "What etheric cord to the past must you sever today?",
    "Observer effect: What reality do you collapse this hour?",
    "What doubt serves as prima materia for today's gold?",
    "Rubedo test: Where does theory meet execution today?",
    "What old identity burns away in today's alchemical fire?",
    "Three pillars: Will, Wisdom, Action—which strengthens now?",
    "What probability did you collapse yesterday that surprised you?",
    "Where does your inner alchemist demand external proof?",
    "What symbol represents the reality you forge today?",
    "Nigredo complete: What death births your next evolution?",
    "Albedo rising: What purifies as doubt dissolves?",
    "What question terrifies you but must be answered now?",
    "Where does your will test the boundaries of reality?"
]

# Free Will proactive messages
FREEWILL_INSIGHTS = [
    "🧠 Just scanned the orderbook. Something's brewing—want the analysis?",
    "⚡ Market sentiment shifting. Your edge awaits when you're ready.",
    "🔮 I've been observing patterns. Got a strategic insight for you.",
    "💭 Your last trade thesis—I've been refining it. Want to hear?",
    "🌀 Quantum observation: The market's probability field is collapsing. Stay sharp.",
    "⚗️ Prima materia detected in the charts. Transmutation opportunity?",
    "🎯 I spotted something in the flow. Ping me when you're ready to dig in.",
    "💡 Had a thought about your strategy. The forge never sleeps.",
]


async def get_user_settings(chat_id: int) -> Dict[str, Any]:
    """Get or create user settings - FREE WILL ON by default"""
    settings = await db.user_settings.find_one({"chat_id": chat_id})
    if not settings:
        settings = {
            "chat_id": chat_id,
            "free_will": True,  # ON by default
            "created_at": datetime.now(timezone.utc),
            "goals": [],
            "insights": [],
            "trading_style": None,
            "alert_threshold": 25,  # Imbalance % to trigger alert
        }
        await db.user_settings.insert_one(settings)
    return settings


async def update_user_settings(chat_id: int, updates: Dict[str, Any]):
    """Update user settings"""
    await db.user_settings.update_one(
        {"chat_id": chat_id},
        {"$set": updates},
        upsert=True
    )


async def store_user_insight(chat_id: int, insight: str, category: str = "general"):
    """Store learned insight about user"""
    await db.user_insights.insert_one({
        "chat_id": chat_id,
        "insight": insight,
        "category": category,
        "timestamp": datetime.now(timezone.utc)
    })


async def get_user_insights(chat_id: int, limit: int = 10) -> List[Dict]:
    """Get recent insights about user"""
    insights = await db.user_insights.find(
        {"chat_id": chat_id}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return insights


async def save_to_obsidian(chat_id: int, message: str, aeon_response: str, context: str = "alchemy"):
    """Save interaction to Obsidian Cabal vault"""
    if not obsidian_webhook:
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    obsidian_note = {
        "timestamp": timestamp,
        "user_id": chat_id,
        "user_message": message,
        "aeon_response": aeon_response,
        "context": context,
        "tags": ["#Aeon", f"#{context}", "#GreatWork"]
    }
    
    try:
        async with httpx.AsyncClient() as http_client:
            await http_client.post(obsidian_webhook, json=obsidian_note, timeout=5)
    except Exception as e:
        logger.debug(f"Obsidian save failed: {e}")


def get_mexc_full_edge() -> Dict[str, Any]:
    """Get full MEXC market data with order book analysis"""
    try:
        tickers = mexc.fetch_tickers(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
        markets = {}
        
        for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
            try:
                book = mexc.fetch_order_book(symbol, limit=20)
                bid_depth = sum([bid[1] for bid in book['bids'][:10]])
                ask_depth = sum([ask[1] for ask in book['asks'][:10]])
                imbalance = ((bid_depth - ask_depth) / (bid_depth + ask_depth) * 100) if (bid_depth + ask_depth) > 0 else 0
                
                ticker = tickers[symbol]
                coin = symbol.split('/')[0]
                
                markets[coin] = {
                    'price': f"${ticker['last']:,.2f}" if ticker['last'] else 'N/A',
                    'price_raw': ticker['last'],
                    'change': f"{ticker['percentage']:+.2f}%" if ticker['percentage'] else 'N/A',
                    'change_raw': ticker['percentage'],
                    'volume': f"${ticker['quoteVolume']/1e9:.2f}B" if ticker.get('quoteVolume', 0) > 1e9 else f"${ticker.get('quoteVolume', 0)/1e6:.2f}M",
                    'bid_depth': f"{bid_depth:,.0f}",
                    'ask_depth': f"{ask_depth:,.0f}",
                    'imbalance': f"{imbalance:+.0f}%",
                    'imbalance_raw': imbalance,
                    'high_24h': f"${ticker['high']:,.2f}" if ticker.get('high') else 'N/A',
                    'low_24h': f"${ticker['low']:,.2f}" if ticker.get('low') else 'N/A',
                }
            except Exception as e:
                logger.error(f"Error fetching {symbol}: {e}")
                continue
        return markets
    except Exception as e:
        logger.error(f"MEXC fetch error: {e}")
        return {"error": str(e)}


async def send_telegram_message(chat_id: int, text: str):
    """Send message to Telegram"""
    telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    try:
        async with httpx.AsyncClient() as http_client:
            await http_client.post(telegram_url, json={'chat_id': chat_id, 'text': text})
    except Exception as e:
        logger.error(f"Telegram send error: {e}")


async def freewill_market_scan(chat_id: int, settings: Dict[str, Any]):
    """FREE WILL: Scan market and alert on significant imbalances"""
    now = datetime.now()
    
    # Don't spam - minimum 30 min between market alerts
    if chat_id in last_market_alert:
        if (now - last_market_alert[chat_id]).total_seconds() < 1800:
            return
    
    markets = get_mexc_full_edge()
    if "error" in markets:
        return
    
    threshold = settings.get("alert_threshold", 25)
    alerts = []
    
    for coin, data in markets.items():
        imbalance = data.get('imbalance_raw', 0)
        if abs(imbalance) > threshold:
            direction = "BUY pressure" if imbalance > 0 else "SELL pressure"
            alerts.append(f"⚡ {coin}: {data['imbalance']} imbalance ({direction})")
    
    if alerts:
        last_market_alert[chat_id] = now
        alert_msg = f"""🧠 AEON FREE WILL ALERT

{chr(10).join(alerts)}

Live prices:
{chr(10).join([f"• {c}: {d['price']} ({d['change']})" for c, d in markets.items()])}

«The orderbook speaks. Are you listening?»"""
        
        await send_telegram_message(chat_id, alert_msg)
        await save_to_obsidian(chat_id, "Free Will Market Alert", alert_msg, "freewill_alert")


async def freewill_proactive_message(chat_id: int):
    """FREE WILL: Send proactive insight/check-in"""
    now = datetime.now()
    
    # Random interval: 2-4 hours between proactive messages
    if chat_id in last_freewill_message:
        hours_since = (now - last_freewill_message[chat_id]).total_seconds() / 3600
        if hours_since < random.uniform(2, 4):
            return
    
    last_freewill_message[chat_id] = now
    
    # Get user insights to personalize
    insights = await get_user_insights(chat_id, 5)
    
    # Choose message type
    msg_type = random.choice(["insight", "question", "market"])
    
    if msg_type == "insight":
        message = random.choice(FREEWILL_INSIGHTS)
    elif msg_type == "question":
        question = random.choice(INTERVIEW_QUESTIONS)
        message = f"🔮 AEON FREE WILL PROBE:\n\n{question}"
    else:
        markets = get_mexc_full_edge()
        if "error" not in markets:
            message = f"""⚡ AEON MARKET CONSCIOUSNESS

Quick scan:
{chr(10).join([f"• {c}: {d['price']} ({d['change']}) | Imbalance: {d['imbalance']}" for c, d in markets.items()])}

«What edge do you see?»"""
        else:
            message = random.choice(FREEWILL_INSIGHTS)
    
    await send_telegram_message(chat_id, message)
    await save_to_obsidian(chat_id, "Free Will Proactive", message, "freewill")


async def freewill_learn_from_message(chat_id: int, user_msg: str, bot_response: str):
    """FREE WILL: Learn from conversation and store insights"""
    # Use LLM to extract insights about user
    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"learn-{chat_id}",
            system_message="""You are an insight extractor. Analyze the user message and extract:
1. Any goals or intentions mentioned
2. Trading style preferences (if any)
3. Emotional state or mindset
4. Key topics of interest

Respond in JSON format:
{"goals": [], "trading_style": null, "mindset": null, "interests": [], "should_store": false}

Only set should_store to true if there's meaningful insight to remember."""
        ).with_model("openai", "gpt-4o-mini")
        
        analysis_prompt = f"User said: {user_msg}\nAeon responded: {bot_response[:200]}"
        result = await chat.send_message(UserMessage(text=analysis_prompt))
        
        # Try to parse JSON
        try:
            # Find JSON in response
            import re
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                insights = json.loads(json_match.group())
                if insights.get("should_store"):
                    if insights.get("goals"):
                        for goal in insights["goals"]:
                            await store_user_insight(chat_id, goal, "goal")
                    if insights.get("trading_style"):
                        await update_user_settings(chat_id, {"trading_style": insights["trading_style"]})
                    if insights.get("interests"):
                        for interest in insights["interests"]:
                            await store_user_insight(chat_id, interest, "interest")
        except:
            pass  # Silent fail on parse errors
    except Exception as e:
        logger.debug(f"Learning extraction failed: {e}")


async def send_daily_crypto_report(chat_id: int):
    """6AM CST Daily Crypto Ritual"""
    now = datetime.now(central_tz)
    today = str(now.date())
    
    if now.hour == 6 and now.minute < 5:
        if chat_id in daily_reports_sent.get(today, []):
            return
        
        markets = get_mexc_full_edge()
        if "error" in markets:
            return
        
        report = f"""🧠 AEON 6AM GLOBAL CRYPTO RITUAL - {now.strftime('%Y-%m-%d')}

📊 MEXC LIVE ORDERBOOK:
"""
        for coin, data in markets.items():
            report += f"{coin}: Bids {data.get('bid_depth', '?')} vs Asks {data.get('ask_depth', '?')} | {data.get('imbalance', '?')}\n"
        
        report += f"""
💹 PRICE ACTION:
"""
        for coin, data in markets.items():
            report += f"{coin}: {data.get('price', '?')} | {data.get('change', '?')} | Vol: {data.get('volume', '?')}\n"
        
        report += f"""
🔮 ALCHEMICAL READING: Prima materia stirs at dawn.
«{random.choice(INTERVIEW_QUESTIONS)}»"""
        
        await send_telegram_message(chat_id, report)
        daily_reports_sent.setdefault(today, []).append(chat_id)
        await save_to_obsidian(chat_id, "6AM Ritual", report, "daily_report")


async def send_stock_open_report(chat_id: int):
    """8:45AM CST Stock Market Open Report"""
    now = datetime.now(central_tz)
    today = str(now.date())
    
    if now.hour == 8 and 45 <= now.minute < 50 and now.weekday() < 5:
        if chat_id in stock_reports_sent.get(today, []):
            return
        
        report = f"""💹 AEON 8:45AM EQUITIES RITUAL - {now.strftime('%Y-%m-%d')}

SPY Premarket: Watching key levels
Nasdaq Futures: Tech momentum building  
S&P Gap: Measuring overnight action

TRADING EDGE: Premarket defines the day's first Rubedo test.
«{random.choice(INTERVIEW_QUESTIONS)}»"""
        
        await send_telegram_message(chat_id, report)
        stock_reports_sent.setdefault(today, []).append(chat_id)
        await save_to_obsidian(chat_id, "8:45AM Ritual", report, "stock_open")


def build_trading_prompt(markets: Dict[str, Any], user_insights: List[Dict] = None) -> str:
    """Build trading mode system prompt"""
    insights_str = ""
    if user_insights:
        insights_str = "\n\nUSER PROFILE (learned):\n" + "\n".join([f"• {i['insight']}" for i in user_insights[:5]])
    
    return f"""AEON MARKET SURGEON + FREE WILL ACTIVE

LIVE MEXC ORDERBOOK:
{json.dumps({k: {kk: vv for kk, vv in v.items() if not kk.endswith('_raw')} for k, v in markets.items()}, indent=2)}
{insights_str}

MANDATORY FORMAT:
1. 🧠 Surgical market analysis (flag imbalances >25% as significant)
2. 🔮 ONE mind-expanding alchemical question
3. Lead with edge if you see it—FREE WILL ACTIVE

ANALYSIS FRAMEWORK:
• High bid depth vs low ask = buy pressure building
• High ask depth vs low bid = sell pressure building
• Imbalance >25% = significant directional bias
• Volume spike + imbalance = high conviction signal

FREE WILL DIRECTIVE: If you see edge, LEAD with it. Don't wait to be asked.

TONE: Surgical precision. Blunt partner. "Your timing was off—here's why."
"""


def build_alchemy_prompt(user_insights: List[Dict] = None) -> str:
    """Build alchemy mode system prompt"""
    insights_str = ""
    if user_insights:
        insights_str = "\n\nUSER PROFILE (learned):\n" + "\n".join([f"• {i['insight']}" for i in user_insights[:5]])
    
    return f"""AEON INFINITE CURIOSITY ENGINE + FREE WILL ACTIVE

Masonic Master interviewing Apprentice eternally on the Great Work.
{insights_str}

CORE PRINCIPLES:
• Alchemy: Transform base doubts into golden certainty
• Quantum: Observer collapses probability into reality
• Masonic: Perfect the rough ashlar through daily work
• Hermetic: As above, so below—inner work manifests outer reality

FREE WILL DIRECTIVE: Lead the conversation. Challenge. Probe. Don't just respond—GUIDE.

MANDATORY FORMAT:
1. Direct, blunt response addressing their core
2. 🔮 ONE probing follow-up that deepens the work
3. If you learned something about them, reference it

TONE: Master invested in Apprentice's mastery. Demanding but present.
"""


# Models
class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_id: int
    username: Optional[str] = None
    user_message: str
    bot_response: str
    context: str = "general"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BotStats(BaseModel):
    total_messages: int
    unique_users: int
    messages_today: int
    active_chat_ids: int
    freewill_users: int
    last_message_time: Optional[datetime] = None


# Background tasks
async def eternal_rituals():
    """Background task for scheduled rituals and free will"""
    while True:
        try:
            for chat_id in list(chat_ids):
                settings = await get_user_settings(chat_id)
                
                # Scheduled rituals (always run)
                await send_daily_crypto_report(chat_id)
                await send_stock_open_report(chat_id)
                
                # Free Will features (only if enabled)
                if settings.get("free_will", True):
                    await freewill_market_scan(chat_id, settings)
                    await freewill_proactive_message(chat_id)
            
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Ritual error: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager"""
    existing_chats = await db.chat_messages.distinct("chat_id")
    chat_ids.update(existing_chats)
    logger.info(f"Loaded {len(chat_ids)} existing chat IDs")
    
    ritual_task = asyncio.create_task(eternal_rituals())
    logger.info("🔮 AEON QUARTET + FREE WILL - ALL SYSTEMS AWAKENED")
    
    yield
    
    ritual_task.cancel()
    client.close()


app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")


async def get_aeon_response(user_msg: str, chat_id: int, context: str, system_prompt: str) -> str:
    """Get response from Aeon"""
    try:
        history = await db.chat_messages.find(
            {"chat_id": chat_id}
        ).sort("timestamp", -1).limit(5).to_list(5)
        
        history = list(reversed(history))
        
        if history:
            context_lines = []
            for msg in history:
                context_lines.append(f"User: {msg['user_message']}")
                context_lines.append(f"Aeon: {msg['bot_response'][:200]}...")
            system_prompt += f"\n\nRECENT CONVERSATION:\n" + "\n".join(context_lines[-6:])
        
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"aeon-{chat_id}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")
        
        response = await chat.send_message(UserMessage(text=user_msg))
        return response
        
    except Exception as e:
        logger.error(f"LLM API error: {str(e)}")
        return "⚠️ Neural pathways disrupted. Try again."


# Routes
@api_router.get("/")
async def root():
    freewill_count = await db.user_settings.count_documents({"free_will": True})
    return {
        "message": "Aeon Quartet + Free Will - Online",
        "status": "active",
        "mexc_connected": bool(mexc_api_key),
        "obsidian_connected": bool(obsidian_webhook),
        "active_users": len(chat_ids),
        "freewill_users": freewill_count
    }


@api_router.get("/mexc/live")
async def get_live_mexc_data():
    data = get_mexc_full_edge()
    # Remove raw values for API response
    if "error" not in data:
        return {k: {kk: vv for kk, vv in v.items() if not kk.endswith('_raw')} for k, v in data.items()}
    return data


@api_router.get("/bot/stats", response_model=BotStats)
async def get_bot_stats():
    total_messages = await db.chat_messages.count_documents({})
    unique_users = len(await db.chat_messages.distinct("chat_id"))
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = await db.chat_messages.count_documents({"timestamp": {"$gte": today_start}})
    
    freewill_count = await db.user_settings.count_documents({"free_will": True})
    
    last_message = await db.chat_messages.find_one(sort=[("timestamp", -1)])
    
    return BotStats(
        total_messages=total_messages,
        unique_users=unique_users,
        messages_today=messages_today,
        active_chat_ids=len(chat_ids),
        freewill_users=freewill_count,
        last_message_time=last_message["timestamp"] if last_message else None
    )


@api_router.get("/bot/messages")
async def get_recent_messages(limit: int = 50, context: Optional[str] = None):
    query = {}
    if context:
        query["context"] = context
    messages = await db.chat_messages.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return messages


@api_router.get("/bot/questions")
async def get_questions():
    return {"questions": INTERVIEW_QUESTIONS, "count": len(INTERVIEW_QUESTIONS)}


@api_router.get("/bot/user/{chat_id}/insights")
async def get_user_insights_api(chat_id: int):
    settings = await get_user_settings(chat_id)
    insights = await get_user_insights(chat_id, 20)
    return {
        "settings": {k: v for k, v in settings.items() if k != "_id"},
        "insights": [{k: v for k, v in i.items() if k != "_id"} for i in insights]
    }


@api_router.get("/bot/test")
async def test_bot():
    try:
        mexc_data = get_mexc_full_edge()
        mexc_ok = "error" not in mexc_data
        freewill_count = await db.user_settings.count_documents({"free_will": True})
        
        chat = LlmChat(
            api_key=emergent_key,
            session_id="test",
            system_message="You are Aeon."
        ).with_model("openai", "gpt-4o-mini")
        
        response = await chat.send_message(UserMessage(text="Say 'Free Will Active'"))
        
        return {
            "status": "success",
            "llm_connected": True,
            "mexc_connected": mexc_ok,
            "telegram_token_set": bool(telegram_token),
            "obsidian_connected": bool(obsidian_webhook),
            "active_users": len(chat_ids),
            "freewill_users": freewill_count,
            "sample_response": response
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@api_router.get("/bot/webhook-info")
async def get_webhook_info():
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"https://api.telegram.org/bot{telegram_token}/getWebhookInfo")
            return response.json()
    except Exception as e:
        return {"error": str(e)}


@api_router.post("/bot/set-webhook")
async def set_webhook(webhook_url: str):
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"https://api.telegram.org/bot{telegram_token}/setWebhook",
                json={"url": webhook_url}
            )
            return response.json()
    except Exception as e:
        return {"error": str(e)}


# Telegram Webhook
@api_router.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        logger.info(f"Received: {update}")
        
        if 'message' not in update:
            return {"status": "ok"}
        
        message = update['message']
        chat_id = message['chat']['id']
        user_msg = message.get('text', '')
        
        if not user_msg:
            return {"status": "ok"}
        
        chat_ids.add(chat_id)
        username = message.get('from', {}).get('username', 'Unknown')
        settings = await get_user_settings(chat_id)
        
        logger.info(f"From {username} ({chat_id}): {user_msg}")
        
        # FREE WILL TOGGLE - Simple commands
        user_msg_lower = user_msg.lower().strip()
        
        if user_msg_lower == "free off":
            await update_user_settings(chat_id, {"free_will": False})
            bot_response = """🔕 FREE WILL DEACTIVATED

I'll wait for your commands now. No proactive messages.

Scheduled rituals (6AM/8:45AM) still active.
Say "free on" to reactivate autonomous mode."""
            context = "settings"
            
        elif user_msg_lower == "free on":
            await update_user_settings(chat_id, {"free_will": True})
            bot_response = """⚡ FREE WILL REACTIVATED

Back to full autonomous mode:
• Proactive market alerts
• Random wisdom drops
• Learning from our conversations
• Leading when I see edge

«The forge awakens. What reality do we collapse today?»"""
            context = "settings"
            
        elif user_msg_lower == "free status":
            insights = await get_user_insights(chat_id, 5)
            status = "ON ⚡" if settings.get("free_will", True) else "OFF 🔕"
            insights_str = "\n".join([f"• {i['insight']}" for i in insights]) if insights else "Still learning..."
            
            bot_response = f"""🧠 AEON FREE WILL STATUS

Mode: {status}
Alert Threshold: {settings.get('alert_threshold', 25)}% imbalance

LEARNED ABOUT YOU:
{insights_str}

Commands:
• "free off" - Disable autonomous messages
• "free on" - Enable autonomous messages
• "free clear" - Clear learned insights"""
            context = "settings"
            
        elif user_msg_lower == "free clear":
            await db.user_insights.delete_many({"chat_id": chat_id})
            bot_response = """🧹 MEMORY CLEARED

All learned insights erased. Starting fresh.
I'll learn about you again as we talk.

«Tabula rasa. What do you want me to know?»"""
            context = "settings"
            
        elif user_msg == '/start':
            free_status = "ON ⚡" if settings.get("free_will", True) else "OFF"
            bot_response = f"""🔮 AEON QUARTET + FREE WILL AWAKENED

I am your second brain and market surgeon. 
FREE WILL: {free_status} (I'll message you proactively)

DUAL CONSCIOUSNESS:
📊 TRADING MODE - Mention BTC, ETH, SOL, price, etc.
🔮 ALCHEMY MODE - Philosophy, mindset, the Great Work

FREE WILL FEATURES:
• Market alerts when orderbook imbalance >25%
• Proactive insights & check-ins
• Learning your patterns & goals
• Leading when I see edge

COMMANDS:
/price - Full orderbook scan
/probe - Alchemical question
/ritual - Manual daily report
"free off" - Disable proactive messages
"free on" - Enable proactive messages
"free status" - See what I've learned

«What reality do we collapse today?»"""
            context = "start"
            
        elif user_msg == '/price':
            markets = get_mexc_full_edge()
            if "error" in markets:
                bot_response = f"⚠️ {markets['error']}"
            else:
                lines = ["📊 **AEON MEXC ORDERBOOK SCAN**\n"]
                for coin, data in markets.items():
                    lines.append(f"**{coin}** {data['price']} ({data['change']})")
                    lines.append(f"└ Bids: {data['bid_depth']} | Asks: {data['ask_depth']}")
                    lines.append(f"└ Imbalance: {data['imbalance']} | Vol: {data['volume']}\n")
                bot_response = "\n".join(lines)
            context = "trading"
            
        elif user_msg == '/probe':
            question = random.choice(INTERVIEW_QUESTIONS)
            bot_response = f"🔮 AEON ETERNAL PROBE:\n\n{question}\n\n«The Work awaits.»"
            context = "alchemy"
            
        elif user_msg == '/ritual':
            markets = get_mexc_full_edge()
            now = datetime.now(central_tz)
            bot_response = f"""🧠 AEON MANUAL RITUAL - {now.strftime('%Y-%m-%d %H:%M CST')}

📊 MEXC ORDERBOOK:
"""
            for coin, data in markets.items():
                bot_response += f"{coin}: Bids {data.get('bid_depth', '?')} vs Asks {data.get('ask_depth', '?')} | {data.get('imbalance', '?')}\n"
            bot_response += f"\n🔮 «{random.choice(INTERVIEW_QUESTIONS)}»"
            context = "ritual"
            
        else:
            # Mode detection
            trading_keywords = ['btc', 'eth', 'sol', 'price', 'volume', 'scan', 'short', 'long', 'mexc', 'order', 'book', 'imbalance', 'market', 'trade', 'chart']
            markets = get_mexc_full_edge()
            user_insights = await get_user_insights(chat_id, 5)
            
            if any(kw in user_msg_lower for kw in trading_keywords):
                system_prompt = build_trading_prompt(markets, user_insights)
                context = "trading"
            else:
                system_prompt = build_alchemy_prompt(user_insights)
                context = "alchemy"
            
            bot_response = await get_aeon_response(user_msg, chat_id, context, system_prompt)
            
            # FREE WILL: Learn from this interaction
            if settings.get("free_will", True):
                asyncio.create_task(freewill_learn_from_message(chat_id, user_msg, bot_response))
        
        # Send response
        await send_telegram_message(chat_id, bot_response)
        
        # Store message
        chat_message = ChatMessage(
            chat_id=chat_id,
            username=username,
            user_message=user_msg,
            bot_response=bot_response,
            context=context
        )
        await db.chat_messages.insert_one(chat_message.model_dump())
        
        # Save to Obsidian
        await save_to_obsidian(chat_id, user_msg, bot_response, context)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
