"""
AI Model Switching Command Handlers
Commands: /openai, /claude, /gpt, /model
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Model configurations
MODEL_CONFIGS = {
    "openai": {
        "display_name": "OpenAI GPT-4o",
        "provider": "openai",
        "model": "gpt-4o",
        "description": "Fast, direct responses - good for quick answers and general tasks.",
        "emoji": "🤖"
    },
    "claude": {
        "display_name": "Claude Sonnet 4.5",
        "provider": "anthropic", 
        "model": "claude-sonnet-4-5-20241022",
        "description": "Detailed, nuanced responses - great for complex analysis and reasoning.",
        "emoji": "🧠"
    }
}

DEFAULT_MODEL = "openai"

# Model key aliases
MODEL_ALIASES = {
    "gpt": "openai",
    "gpt4": "openai",
    "gpt-4": "openai",
    "gpt4o": "openai",
    "gpt-4o": "openai",
    "openai": "openai",
    "claude": "claude",
    "anthropic": "claude",
    "sonnet": "claude",
    "sonnet4": "claude",
    "sonnet-4": "claude",
}


def resolve_model_key(key: str) -> str:
    """Resolve model alias to canonical key"""
    return MODEL_ALIASES.get(key.lower(), key.lower())


def get_model_config(model_key: str) -> dict:
    """Get model configuration by key"""
    resolved = resolve_model_key(model_key)
    return MODEL_CONFIGS.get(resolved, MODEL_CONFIGS[DEFAULT_MODEL])


# In-memory cache for user model preferences
user_model_cache = {}


async def get_user_model(chat_id: int, db=None) -> str:
    """Get user's preferred AI model"""
    # Check cache first
    if chat_id in user_model_cache:
        return user_model_cache[chat_id]
    
    # Try database
    if db:
        try:
            pref = await db.user_preferences.find_one({"chat_id": chat_id})
            if pref and pref.get("model"):
                resolved = resolve_model_key(pref["model"])
                if resolved in MODEL_CONFIGS:
                    user_model_cache[chat_id] = resolved
                    return resolved
        except Exception as e:
            logger.error(f"Error getting user model from DB: {e}")
    
    return DEFAULT_MODEL


async def set_user_model(chat_id: int, model: str, db=None) -> bool:
    """Set user's preferred AI model"""
    resolved = resolve_model_key(model)
    
    if resolved not in MODEL_CONFIGS:
        return False
    
    # Update cache
    user_model_cache[chat_id] = resolved
    
    # Update database
    if db:
        try:
            await db.user_preferences.update_one(
                {"chat_id": chat_id},
                {"$set": {"model": resolved}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving user model to DB: {e}")
    
    return True


async def handle_openai_switch(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /openai or /gpt command"""
    db = context.get('db')
    success = await set_user_model(chat_id, "openai", db)
    
    if success:
        response = """✅ SWITCHED TO OPENAI GPT-4o

Fast, direct responses - good for quick answers.

Switch back: /claude"""
    else:
        response = "❌ Failed to switch. Try again."
    
    return response, "settings"


async def handle_claude_switch(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /claude or /anthropic command"""
    db = context.get('db')
    success = await set_user_model(chat_id, "claude", db)
    
    if success:
        response = """✅ SWITCHED TO CLAUDE SONNET 4.5

Detailed, nuanced responses - great for analysis.

Switch back: /openai"""
    else:
        response = "❌ Failed to switch. Try again."
    
    return response, "settings"


async def handle_model_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /model command"""
    db = context.get('db')
    parts = text.lower().split()
    
    if len(parts) == 1:
        # Show current model
        current_model = await get_user_model(chat_id, db)
        config = get_model_config(current_model)
        
        response = f"""{config['emoji']} CURRENT AI: {config['display_name']}

{config['description']}

SWITCH: /openai or /claude"""
    else:
        # Try to switch model
        requested = parts[1]
        resolved = resolve_model_key(requested)
        
        if resolved in MODEL_CONFIGS:
            success = await set_user_model(chat_id, resolved, db)
            if success:
                config = get_model_config(resolved)
                response = f"✅ Switched to {config['display_name']}"
            else:
                response = "❌ Failed to switch. Try /openai or /claude"
        else:
            response = "❌ Unknown model. Use /openai or /claude"
    
    return response, "settings"


# Export handlers
MODEL_HANDLERS = {
    '/openai': handle_openai_switch,
    '/gpt': handle_openai_switch,
    '/claude': handle_claude_switch,
    '/anthropic': handle_claude_switch,
    '/model': handle_model_status,
}


async def route_model_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route model commands"""
    text_lower = text.lower().strip()
    
    if text_lower == '/openai' or text_lower == '/gpt':
        return await handle_openai_switch(text, chat_id, context)
    elif text_lower == '/claude' or text_lower == '/anthropic':
        return await handle_claude_switch(text, chat_id, context)
    elif text_lower.startswith('/model'):
        return await handle_model_status(text, chat_id, context)
    
    return None
