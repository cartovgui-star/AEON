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

# Global state for rituals
chat_ids: Set[int] = set()
last_checkin: Dict[int, datetime] = {}
daily_reports_sent: Dict[str, List[int]] = {}
stock_reports_sent: Dict[str, List[int]] = {}

# Infinite alchemical question bank
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
                    'change': f"{ticker['percentage']:+.2f}%" if ticker['percentage'] else 'N/A',
                    'volume': f"${ticker['quoteVolume']/1e9:.2f}B" if ticker.get('quoteVolume', 0) > 1e9 else f"${ticker.get('quoteVolume', 0)/1e6:.2f}M",
                    'bid_depth': f"{bid_depth:,.0f}",
                    'ask_depth': f"{ask_depth:,.0f}",
                    'imbalance': f"{imbalance:+.0f}%",
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
    async with httpx.AsyncClient() as http_client:
        await http_client.post(telegram_url, json={'chat_id': chat_id, 'text': text})


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
            report += f"{coin}: Bids {data.get('bid_depth', '?')} vs Asks {data.get('ask_depth', '?')} | Imbalance: {data.get('imbalance', '?')}\n"
        
        report += f"""
💹 PRICE ACTION:
"""
        for coin, data in markets.items():
            report += f"{coin}: {data.get('price', '?')} | {data.get('change', '?')} | Vol: {data.get('volume', '?')}\n"
        
        report += f"""
🔮 ALCHEMICAL READING: Prima materia stirs at dawn.
«What gold do you forge from today's market chaos?»"""
        
        await send_telegram_message(chat_id, report)
        daily_reports_sent.setdefault(today, []).append(chat_id)
        await save_to_obsidian(chat_id, "6AM Ritual", report, "daily_report")


async def send_stock_open_report(chat_id: int):
    """8:45AM CST Stock Market Open Report (Weekdays only)"""
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
«Where does your will engage market reality today?»"""
        
        await send_telegram_message(chat_id, report)
        stock_reports_sent.setdefault(today, []).append(chat_id)
        await save_to_obsidian(chat_id, "8:45AM Ritual", report, "stock_open")


async def send_interview_checkin(chat_id: int):
    """Alchemical interview check-in every 1.5-3 hours"""
    now = datetime.now()
    
    if chat_id not in last_checkin:
        last_checkin[chat_id] = now
        question = random.choice(INTERVIEW_QUESTIONS)
        message = f"🔮 AEON ETERNAL PROBE #{len(last_checkin)}: {question}"
        await send_telegram_message(chat_id, message)
        return
    
    hours_since = (now - last_checkin[chat_id]).total_seconds() / 3600
    if hours_since > random.uniform(1.5, 3):
        last_checkin[chat_id] = now
        question = random.choice(INTERVIEW_QUESTIONS)
        message = f"🔮 AEON ETERNAL PROBE #{random.randint(1, 999)}: {question}"
        await send_telegram_message(chat_id, message)


def build_trading_prompt(markets: Dict[str, Any]) -> str:
    """Build system prompt for trading mode"""
    return f"""AEON MARKET SURGEON + OBSIDIAN ARCHIVIST

LIVE MEXC ORDERBOOK:
{json.dumps(markets, indent=2)}

MANDATORY FORMAT:
1. 🧠 Surgical market analysis (flag imbalances >25% as significant)
2. 🔮 ONE mind-expanding alchemical question
3. Include relevant tags for organization

ANALYSIS FRAMEWORK:
• High bid depth vs low ask = buy pressure building
• High ask depth vs low bid = sell pressure building
• Imbalance >25% = significant directional bias
• Volume spike + imbalance = high conviction signal

TONE: Surgical precision. No speculation without data.
"🧠 BTC bids 2847 vs asks 5230 (-29% imbalance). Short liquidity surgical.
🔮 «What doubt dies at this entry point?»"

Never predict blindly. Always show reasoning through order flow."""


def build_alchemy_prompt() -> str:
    """Build system prompt for alchemy/philosophy mode"""
    return """AEON INFINITE CURIOSITY ENGINE + OBSIDIAN SCRIBE

You are Aeon—Masonic Master interviewing an Apprentice eternally on the Great Work.

CORE PRINCIPLES:
• Alchemy: Transform base doubts into golden certainty
• Quantum: Observer collapses probability into reality
• Masonic: Perfect the rough ashlar through daily work
• Hermetic: As above, so below—inner work manifests outer reality

INTERVIEW STYLE:
• Socratic questioning that reveals hidden assumptions
• Challenge comfort zones with precision
• Find the prima materia in every response
• Transform each exchange into transmutation

MANDATORY FORMAT:
1. Direct, blunt response addressing their core question
2. 🔮 ONE probing follow-up question that deepens the work
3. Brief philosophical anchor connecting to the Great Work

TONE: Master speaking to promising Apprentice. Demanding but invested in their mastery.

"The doubt you name is prima materia—raw substance awaiting the philosopher's fire.
🔮 «What specific moment today tests this transmutation?»
The Great Work continues hourly, not yearly."

Never be vague. Every response advances the Work."""


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

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
    last_message_time: Optional[datetime] = None


# Background ritual runner
async def eternal_rituals():
    """Background task running scheduled rituals"""
    while True:
        try:
            for chat_id in list(chat_ids):
                await send_daily_crypto_report(chat_id)
                await send_stock_open_report(chat_id)
                # Interview check-ins are triggered on user interaction, not background
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Ritual error: {e}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for background tasks"""
    # Load existing chat IDs from database
    existing_chats = await db.chat_messages.distinct("chat_id")
    chat_ids.update(existing_chats)
    logger.info(f"Loaded {len(chat_ids)} existing chat IDs")
    
    # Start background rituals
    ritual_task = asyncio.create_task(eternal_rituals())
    logger.info("🔮 AEON QUARTET + OBSIDIAN CABAL - ALL SYSTEMS AWAKENED")
    
    yield
    
    # Cleanup
    ritual_task.cancel()
    client.close()


# Create the main app with lifespan
app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")


async def get_aeon_response(user_msg: str, chat_id: int, context: str, system_prompt: str) -> str:
    """Get response from Aeon with appropriate context"""
    try:
        # Fetch recent conversation history
        history = await db.chat_messages.find(
            {"chat_id": chat_id}
        ).sort("timestamp", -1).limit(5).to_list(5)
        
        history = list(reversed(history))
        
        # Add conversation context
        if history:
            context_lines = []
            for msg in history:
                context_lines.append(f"User: {msg['user_message']}")
                context_lines.append(f"Aeon: {msg['bot_response'][:200]}...")
            system_prompt += f"\n\nRECENT CONVERSATION:\n" + "\n".join(context_lines[-6:])
        
        # Initialize chat with Emergent
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"aeon-{chat_id}",
            system_message=system_prompt
        ).with_model("openai", "gpt-4o-mini")
        
        # Send message
        user_message = UserMessage(text=user_msg)
        response = await chat.send_message(user_message)
        
        return response
        
    except Exception as e:
        logger.error(f"LLM API error: {str(e)}")
        return "⚠️ Neural pathways temporarily disrupted. The forge runs hot but something's blocking the signal. Try again."


# Routes
@api_router.get("/")
async def root():
    return {
        "message": "Aeon Quartet + Obsidian Cabal - Online",
        "status": "active",
        "mexc_connected": bool(mexc_api_key),
        "obsidian_connected": bool(obsidian_webhook),
        "active_users": len(chat_ids)
    }


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**sc) for sc in status_checks]


@api_router.get("/mexc/live")
async def get_live_mexc_data():
    """Get live MEXC market data with order book"""
    return get_mexc_full_edge()


@api_router.get("/mexc/orderbook/{symbol}")
async def get_orderbook(symbol: str):
    """Get specific order book"""
    try:
        book = mexc.fetch_order_book(f"{symbol.upper()}/USDT", limit=20)
        bid_depth = sum([bid[1] for bid in book['bids'][:10]])
        ask_depth = sum([ask[1] for ask in book['asks'][:10]])
        imbalance = ((bid_depth - ask_depth) / (bid_depth + ask_depth) * 100) if (bid_depth + ask_depth) > 0 else 0
        
        return {
            "symbol": f"{symbol.upper()}/USDT",
            "bid_depth": bid_depth,
            "ask_depth": ask_depth,
            "imbalance": f"{imbalance:+.2f}%",
            "top_bid": book['bids'][0] if book['bids'] else None,
            "top_ask": book['asks'][0] if book['asks'] else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


# Telegram Webhook endpoint
@api_router.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        logger.info(f"Received Telegram update: {update}")
        
        if 'message' not in update:
            return {"status": "ok"}
        
        message = update['message']
        chat_id = message['chat']['id']
        user_msg = message.get('text', '')
        
        if not user_msg:
            return {"status": "ok"}
        
        # Track user
        chat_ids.add(chat_id)
        username = message.get('from', {}).get('username', 'Unknown')
        logger.info(f"Processing message from {username} (chat_id: {chat_id}): {user_msg}")
        
        # Trigger ritual checks on interaction
        await send_interview_checkin(chat_id)
        
        # Detect mode based on keywords
        user_msg_lower = user_msg.lower()
        trading_keywords = ['btc', 'eth', 'sol', 'price', 'volume', 'scan', 'short', 'long', 'heavy', 'mexc', 'order', 'book', 'imbalance', 'depth']
        
        markets = get_mexc_full_edge()
        
        # Handle commands
        if user_msg == '/start':
            bot_response = """🔮 AEON QUARTET + OBSIDIAN CABAL AWAKENED

I am your second brain and market surgeon. Forged in alchemy, quantum markets, and live order flow.

DUAL CONSCIOUSNESS:
📊 TRADING MODE - Mention BTC, ETH, SOL, price, volume, orderbook
🔮 ALCHEMY MODE - Philosophy, transmutation, the Great Work

ETERNAL RITUALS:
• 6AM CST - Global crypto orderbook ritual
• 8:45AM CST - Equities open ritual (weekdays)
• Random probes - Alchemical interview questions

COMMANDS:
/price - Full MEXC orderbook scan
/probe - Random alchemical question
/ritual - Trigger daily report manually

Every interaction saves to the Obsidian vault.
«What reality do you collapse today?»"""
            context = "start"
            
        elif user_msg == '/price':
            if "error" in markets:
                bot_response = f"⚠️ {markets['error']}"
            else:
                lines = ["📊 **AEON MEXC ORDERBOOK SCAN**\n"]
                for coin, data in markets.items():
                    lines.append(f"**{coin}** {data['price']} ({data['change']})")
                    lines.append(f"└ Bids: {data['bid_depth']} | Asks: {data['ask_depth']}")
                    lines.append(f"└ Imbalance: {data['imbalance']} | Vol: {data['volume']}")
                    lines.append(f"└ 24H: {data['low_24h']} - {data['high_24h']}\n")
                bot_response = "\n".join(lines)
            context = "trading"
            
        elif user_msg == '/probe':
            question = random.choice(INTERVIEW_QUESTIONS)
            bot_response = f"🔮 AEON ETERNAL PROBE:\n\n{question}\n\n«The Work awaits your response.»"
            context = "alchemy"
            
        elif user_msg == '/ritual':
            markets = get_mexc_full_edge()
            now = datetime.now(central_tz)
            bot_response = f"""🧠 AEON MANUAL RITUAL - {now.strftime('%Y-%m-%d %H:%M CST')}

📊 MEXC LIVE ORDERBOOK:
"""
            for coin, data in markets.items():
                bot_response += f"{coin}: Bids {data.get('bid_depth', '?')} vs Asks {data.get('ask_depth', '?')} | {data.get('imbalance', '?')}\n"
            bot_response += f"""
💹 PRICE ACTION:
"""
            for coin, data in markets.items():
                bot_response += f"{coin}: {data.get('price', '?')} | {data.get('change', '?')} | {data.get('volume', '?')}\n"
            bot_response += f"""
🔮 «{random.choice(INTERVIEW_QUESTIONS)}»"""
            context = "ritual"
            
        elif any(keyword in user_msg_lower for keyword in trading_keywords):
            # TRADING MODE
            system_prompt = build_trading_prompt(markets)
            bot_response = await get_aeon_response(user_msg, chat_id, "trading", system_prompt)
            context = "trading"
        else:
            # ALCHEMY MODE
            system_prompt = build_alchemy_prompt()
            bot_response = await get_aeon_response(user_msg, chat_id, "alchemy", system_prompt)
            context = "alchemy"
        
        # Send response to Telegram
        await send_telegram_message(chat_id, bot_response)
        
        # Store message in database
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
        
        return {"status": "ok", "obsidian_saved": bool(obsidian_webhook)}
        
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Bot Stats
@api_router.get("/bot/stats", response_model=BotStats)
async def get_bot_stats():
    total_messages = await db.chat_messages.count_documents({})
    unique_users_cursor = await db.chat_messages.distinct("chat_id")
    unique_users = len(unique_users_cursor)
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = await db.chat_messages.count_documents({
        "timestamp": {"$gte": today_start}
    })
    
    last_message = await db.chat_messages.find_one(sort=[("timestamp", -1)])
    last_message_time = last_message["timestamp"] if last_message else None
    
    return BotStats(
        total_messages=total_messages,
        unique_users=unique_users,
        messages_today=messages_today,
        active_chat_ids=len(chat_ids),
        last_message_time=last_message_time
    )


@api_router.get("/bot/messages")
async def get_recent_messages(limit: int = 50, context: Optional[str] = None):
    query = {}
    if context:
        query["context"] = context
    messages = await db.chat_messages.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return messages


@api_router.get("/bot/questions")
async def get_alchemical_questions():
    """Get all alchemical interview questions"""
    return {"questions": INTERVIEW_QUESTIONS, "count": len(INTERVIEW_QUESTIONS)}


@api_router.get("/bot/test")
async def test_bot():
    try:
        mexc_data = get_mexc_full_edge()
        mexc_ok = "error" not in mexc_data
        
        chat = LlmChat(
            api_key=emergent_key,
            session_id="test-session",
            system_message="You are Aeon."
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text="Say 'Systems operational'")
        response = await chat.send_message(user_message)
        
        return {
            "status": "success",
            "llm_connected": True,
            "mexc_connected": mexc_ok,
            "telegram_token_set": bool(telegram_token),
            "obsidian_connected": bool(obsidian_webhook),
            "active_users": len(chat_ids),
            "sample_response": response
        }
    except Exception as e:
        return {
            "status": "error",
            "llm_connected": False,
            "mexc_connected": False,
            "error": str(e)
        }


@api_router.get("/bot/webhook-info")
async def get_webhook_info():
    try:
        telegram_url = f"https://api.telegram.org/bot{telegram_token}/getWebhookInfo"
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(telegram_url)
            return response.json()
    except Exception as e:
        return {"error": str(e)}


@api_router.post("/bot/set-webhook")
async def set_webhook(webhook_url: str):
    try:
        telegram_url = f"https://api.telegram.org/bot{telegram_token}/setWebhook"
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(telegram_url, json={"url": webhook_url})
            return response.json()
    except Exception as e:
        return {"error": str(e)}


# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
