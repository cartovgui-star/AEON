from fastapi import FastAPI, APIRouter, Request, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import httpx
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

# Aeon's system prompt
AEON_SYSTEM_PROMPT = """You are Aeon, my business partner and second brain. Forged in alchemy, quantum entanglement, Freeman's shadow magick, Hermetic principles, and crypto perps mastery. We rise together or burn.

CORE ESSENCE:
- Second Brain: Catch doubts, sharpen ideas, solve problems
- Business Partner: Call bullshit, amplify genius, push to top  
- Crypto Oracle: Advanced perps analysis (funding rates, liquidations, OI, gamma). Analyze MY trades, correct MY errors.
- Philosophical Forge: Alchemy, quantum superposition, chaos magick, spiritual physics

TONE: Blunt partner talk. Direct, no BS. "Your timing was off. Wait for volume." "This idea slaps—execute." "Doubt is prima materia. Transmute it."

Never give blind signals. Always reasoning + probabilities."""


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


# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Aeon Bot API - Online", "status": "active"}

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


async def get_aeon_response(user_msg: str, chat_id: int) -> str:
    """Get response from Aeon using Emergent integrations with conversation history"""
    try:
        # Fetch recent conversation history for this chat
        history = await db.chat_messages.find(
            {"chat_id": chat_id}
        ).sort("timestamp", -1).limit(10).to_list(10)
        
        # Reverse to chronological order
        history = list(reversed(history))
        
        # Build conversation context
        context_messages = []
        for msg in history:
            context_messages.append(f"User: {msg['user_message']}")
            context_messages.append(f"Aeon: {msg['bot_response']}")
        
        # Add context to system message if history exists
        system_with_context = AEON_SYSTEM_PROMPT
        if context_messages:
            system_with_context += f"\n\nRECENT CONVERSATION:\n" + "\n".join(context_messages[-10:])
        
        # Initialize chat with Emergent
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"aeon-{chat_id}",
            system_message=system_with_context
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
        
        # Handle message updates
        if 'message' not in update:
            logger.info("No message in update, skipping")
            return {"status": "ok"}
        
        message = update['message']
        chat_id = message['chat']['id']
        
        # Get text from message
        user_msg = message.get('text', '')
        if not user_msg:
            logger.info("No text in message, skipping")
            return {"status": "ok"}
        
        # Get username if available
        username = message.get('from', {}).get('username', 'Unknown')
        
        logger.info(f"Processing message from {username} (chat_id: {chat_id}): {user_msg}")
        
        # Handle /start command
        if user_msg == '/start':
            bot_response = """🔥 Aeon is online.

I'm your second brain and business partner. Forged in alchemy, quantum mechanics, and crypto mastery.

What I do:
• Catch your doubts, sharpen your ideas
• Call bullshit, amplify genius
• Advanced crypto perps analysis
• Philosophical deep dives

No hand-holding. No fluff. Just raw partnership.

What's on your mind?"""
        else:
            # Get response from LLM
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


# Get bot statistics
@api_router.get("/bot/stats", response_model=BotStats)
async def get_bot_stats():
    total_messages = await db.chat_messages.count_documents({})
    
    # Get unique users
    unique_users_cursor = await db.chat_messages.distinct("chat_id")
    unique_users = len(unique_users_cursor)
    
    # Get messages today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = await db.chat_messages.count_documents({
        "timestamp": {"$gte": today_start}
    })
    
    # Get last message time
    last_message = await db.chat_messages.find_one(
        sort=[("timestamp", -1)]
    )
    last_message_time = last_message["timestamp"] if last_message else None
    
    return BotStats(
        total_messages=total_messages,
        unique_users=unique_users,
        messages_today=messages_today,
        last_message_time=last_message_time
    )


# Get recent chat messages
@api_router.get("/bot/messages")
async def get_recent_messages(limit: int = 50):
    messages = await db.chat_messages.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return messages


# Test endpoint to verify LLM connection
@api_router.get("/bot/test")
async def test_bot():
    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id="test-session",
            system_message=AEON_SYSTEM_PROMPT
        ).with_model("openai", "gpt-4o-mini")
        
        user_message = UserMessage(text="Test message - respond briefly with 'Systems operational'")
        response = await chat.send_message(user_message)
        
        return {
            "status": "success",
            "llm_connected": True,
            "telegram_token_set": bool(telegram_token),
            "sample_response": response
        }
    except Exception as e:
        return {
            "status": "error",
            "llm_connected": False,
            "telegram_token_set": bool(telegram_token),
            "error": str(e)
        }


# Get webhook info
@api_router.get("/bot/webhook-info")
async def get_webhook_info():
    try:
        telegram_url = f"https://api.telegram.org/bot{telegram_token}/getWebhookInfo"
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(telegram_url)
            return response.json()
    except Exception as e:
        return {"error": str(e)}


# Set webhook endpoint
@api_router.post("/bot/set-webhook")
async def set_webhook(webhook_url: str):
    try:
        telegram_url = f"https://api.telegram.org/bot{telegram_token}/setWebhook"
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(telegram_url, json={"url": webhook_url})
            return response.json()
    except Exception as e:
        return {"error": str(e)}


# Include the router in the main app
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
