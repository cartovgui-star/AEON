"""
Voice Conversation API Routes
TTS, STT, and voice interaction
"""

import os
import base64
import logging
from fastapi import APIRouter, Request
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/respond")
async def api_voice_respond(request: Request):
    """
    Get Aeon's voice response to user text
    Browser handles speech recognition, we handle LLM + TTS
    """
    try:
        from voice_tts import generate_speech
        
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


@router.post("/transcribe")
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


@router.get("/info")
async def api_voice_info():
    """Get available voices and STT status"""
    from voice_tts import get_voice_info
    return get_voice_info()
