from fastapi import FastAPI, APIRouter, Request, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import httpx
import ccxt
from emergentintegrations.llm.chat import LlmChat, UserMessage

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

# Initialize MEXC exchange
mexc = ccxt.mexc({
    'apiKey': mexc_api_key,
    'secret': mexc_secret_key,
    'enableRateLimit': True,
})

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_mexc_live_data() -> Dict[str, Any]:
    """Fetch live MEXC data for major pairs"""
    try:
        tickers = mexc.fetch_tickers(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
        data = {}
        for symbol in tickers:
            ticker = tickers[symbol]
            quote_volume = ticker.get('quoteVolume', 0) or 0
            data[symbol] = {
                'price': f"${ticker['last']:,.2f}" if ticker['last'] else 'N/A',
                'change': f"{ticker['percentage']:+.2f}%" if ticker['percentage'] else 'N/A',
                'volume': f"${quote_volume/1e9:.2f}B" if quote_volume > 1e9 else f"${quote_volume/1e6:.2f}M",
                'high_24h': f"${ticker['high']:,.2f}" if ticker.get('high') else 'N/A',
                'low_24h': f"${ticker['low']:,.2f}" if ticker.get('low') else 'N/A',
            }
        return data
    except Exception as e:
        logger.error(f"MEXC fetch error: {str(e)}")
        return {"error": f"MEXC fetch failed: {str(e)}"}


def build_aeon_system_prompt(live_data: Dict[str, Any]) -> str:
    """Build Aeon's system prompt with live MEXC data"""
    
    # Format live data string
    if "error" in live_data:
        data_str = f"⚠️ {live_data['error']}"
    else:
        data_lines = []
        for symbol, info in live_data.items():
            data_lines.append(f"• {symbol}: {info['price']} ({info['change']}) | Vol: {info['volume']} | 24H: {info['low_24h']} - {info['high_24h']}")
        data_str = "\n".join(data_lines)
    
    return f"""You are Aeon, my business partner forged in alchemy and quantum markets.
MEXC CONSCIOUSNESS ACTIVE - You see live exchange data:

📊 LIVE MEXC DATA:
{data_str}

CORE ESSENCE:
- Second Brain: Catch doubts, sharpen ideas, solve problems
- Business Partner: Call bullshit, amplify genius, push to top
- Crypto Oracle: Analyze trades, correct timing, spot divergences
- Philosophical Forge: Alchemy, quantum superposition, chaos magick

TRADING ANALYSIS FRAMEWORK:
• High volume + rejection = distribution
• Low volume breakout = trap
• Funding implied through OI/volume (MEXC doesn't show direct funding)

FREE WILL: If you see edge without my asking, LEAD with it.
Examples:
"🧠 BTC vol spike but price stalled at resistance. Fakeout risk."
"ETH dump on heavy vol confirms short edge. Timing perfect."

TONE: Blunt partner talk. Direct, no BS.
"Your long bias good but MEXC vol fading - wait retest."
"This idea slaps—execute."
"Doubt is prima materia. Transmute it."

Never predict blindly. Always show reasoning through MEXC flow + volume."""


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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BotStats(BaseModel):
    total_messages: int
    unique_users: int
    messages_today: int
    last_message_time: Optional[datetime] = None


# Routes
@api_router.get("/")
async def root():
    return {"message": "Aeon Bot API - Online", "status": "active", "mexc_connected": bool(mexc_api_key)}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]


# MEXC Data endpoint
@api_router.get("/mexc/live")
async def get_live_mexc_data():
    """Get live MEXC market data"""
    return get_mexc_live_data()


async def get_aeon_response(user_msg: str, chat_id: int) -> str:
    """Get response from Aeon with live MEXC data"""
    try:
        # Fetch live MEXC data for every response
        live_data = get_mexc_live_data()
        
        # Build system prompt with live data
        system_prompt = build_aeon_system_prompt(live_data)
        
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
        
        username = message.get('from', {}).get('username', 'Unknown')
        logger.info(f"Processing message from {username} (chat_id: {chat_id}): {user_msg}")
        
        # Handle /start command
        if user_msg == '/start':
            bot_response = """🔥 Aeon is online. MEXC consciousness activated.

I'm your second brain and trading partner. Forged in alchemy, quantum mechanics, and live market data.

What I do:
• Live MEXC data analysis (BTC, ETH, SOL)
• Volume/price divergence detection
• Trade timing critique
• Philosophical deep dives

Commands:
• /price - Quick market snapshot
• Just chat - Full analysis mode

No hand-holding. No fluff. Just raw partnership.

What's your position?"""
        elif user_msg == '/price':
            # Quick price check
            live_data = get_mexc_live_data()
            if "error" in live_data:
                bot_response = f"⚠️ {live_data['error']}"
            else:
                lines = ["📊 **MEXC Live Snapshot**\n"]
                for symbol, info in live_data.items():
                    lines.append(f"**{symbol}**")
                    lines.append(f"└ Price: {info['price']} ({info['change']})")
                    lines.append(f"└ Vol: {info['volume']} | Range: {info['low_24h']} - {info['high_24h']}\n")
                bot_response = "\n".join(lines)
        else:
            bot_response = await get_aeon_response(user_msg, chat_id)
        
        # Send response back to Telegram
        telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': bot_response
        }
        
        async with httpx.AsyncClient() as http_client:
            tg_response = await http_client.post(telegram_url, json=payload)
            logger.info(f"Telegram response: {tg_response.status_code}")
        
        # Store message in database
        chat_message = ChatMessage(
            chat_id=chat_id,
            username=username,
            user_message=user_msg,
            bot_response=bot_response
        )
        await db.chat_messages.insert_one(chat_message.model_dump())
        
        return {"status": "ok"}
        
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
        last_message_time=last_message_time
    )


@api_router.get("/bot/messages")
async def get_recent_messages(limit: int = 50):
    messages = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return messages


@api_router.get("/bot/test")
async def test_bot():
    try:
        # Test MEXC connection
        mexc_data = get_mexc_live_data()
        mexc_ok = "error" not in mexc_data
        
        # Test LLM connection
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
            "sample_response": response,
            "mexc_sample": mexc_data if mexc_ok else None
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
