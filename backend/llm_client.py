"""
LLM client utilities — Claude (Anthropic) and Gemini (Google) support.

Handles:
- Model configuration and aliases
- Per-user model preferences (DB-backed, in-memory cache)
- Unified call_llm() interface
"""

import os
import logging
from typing import Dict

import anthropic as _anthropic
from google import genai as google_genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# ── Model registry ────────────────────────────────────────────────────────────

MODEL_CONFIGS: Dict[str, Dict] = {
    "claude": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.5",
        "description": "Deep analysis, nuanced reasoning - great for complex market reads",
    },
    "gemini": {
        "provider": "google",
        "model": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "description": "Fast, broad context - great for quick answers and news summaries",
    },
}

MODEL_ALIASES: Dict[str, str] = {
    "anthropic": "claude",
    "sonnet": "claude",
    "google": "gemini",
    "flash": "gemini",
}

DEFAULT_MODEL = "claude"

# In-memory cache — keyed by chat_id, value is resolved model key
user_model_cache: Dict[int, str] = {}

# ── API clients ───────────────────────────────────────────────────────────────

anthropic_client = _anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
gemini_client = google_genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

# ── Public helpers ────────────────────────────────────────────────────────────


def resolve_model_key(key: str) -> str:
    return MODEL_ALIASES.get(key, key)


def get_model_config(model_key: str) -> Dict:
    resolved = resolve_model_key(model_key)
    return MODEL_CONFIGS.get(resolved, MODEL_CONFIGS[DEFAULT_MODEL])


async def _call_claude(system_message: str, user_message: str, model: str) -> str:
    """Call Claude (Anthropic)."""
    msg = await anthropic_client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_message,
        messages=[{"role": "user", "content": user_message}],
    )
    return msg.content[0].text


async def _call_gemini(system_message: str, user_message: str, model: str) -> str:
    """Call Gemini (Google). Raises on 429/quota errors."""
    response = await gemini_client.aio.models.generate_content(
        model=model,
        contents=user_message,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_message,
            max_output_tokens=2048,
        ),
    )
    return response.text


async def call_llm(system_message: str, user_message: str, model_key: str = "claude") -> str:
    """
    Call Claude or Gemini based on user preference.
    If Gemini hits rate limits (429/quota), automatically falls back to Claude.
    """
    model_config = get_model_config(model_key)
    provider = model_config["provider"]
    model = model_config["model"]

    if provider == "google":
        try:
            return await _call_gemini(system_message, user_message, model)
        except Exception as e:
            err_str = str(e)
            # Gemini quota/rate-limit — fall back to Claude silently
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                logger.warning("Gemini quota exceeded — falling back to Claude automatically")
                claude_model = MODEL_CONFIGS["claude"]["model"]
                return await _call_claude(system_message, user_message, claude_model)
            raise  # re-raise other Gemini errors
    else:
        return await _call_claude(system_message, user_message, model)


async def get_user_model(chat_id: int) -> str:
    """Get user's preferred AI model from cache or DB."""
    import app_state

    if chat_id in user_model_cache:
        return user_model_cache[chat_id]

    try:
        pref = await app_state.db.user_preferences.find_one({"chat_id": chat_id})
        if pref and "model" in pref:
            model = pref["model"]
            resolved = resolve_model_key(model)
            if resolved in MODEL_CONFIGS:
                user_model_cache[chat_id] = resolved
                return resolved
        user_model_cache[chat_id] = DEFAULT_MODEL
        return DEFAULT_MODEL
    except Exception as e:
        logger.error(f"Error getting user model: {e}")
        return DEFAULT_MODEL


async def set_user_model(chat_id: int, model: str) -> bool:
    """Set user's preferred AI model in DB and cache."""
    import app_state
    from datetime import datetime, timezone

    resolved = resolve_model_key(model)
    if resolved not in MODEL_CONFIGS:
        return False

    try:
        await app_state.db.user_preferences.update_one(
            {"chat_id": chat_id},
            {"$set": {"model": resolved, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        user_model_cache[chat_id] = resolved
        logger.info(f"User {chat_id} switched to model: {resolved}")
        return True
    except Exception as e:
        logger.error(f"Error setting user model: {e}")
        return False
