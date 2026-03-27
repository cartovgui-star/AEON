"""
AEON VOICE MODULE v2 - Enhanced TTS + STT
Uses Edge TTS (free) for text-to-speech
Uses OpenAI Whisper for speech-to-text (natural transcription)
"""

import asyncio
import base64
import logging
import os
import tempfile
import uuid

import edge_tts
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Voice options for TTS
VOICES = {
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural", 
    "british": "en-GB-RyanNeural",
    "australian": "en-AU-WilliamNeural"
}

# Whisper STT (if available)
try:
    from emergentintegrations.llm.openai import OpenAISpeechToText
    WHISPER_AVAILABLE = True
    stt_client = OpenAISpeechToText(api_key=os.getenv("EMERGENT_LLM_KEY"))
    logger.info("OpenAI Whisper STT initialized")
except ImportError:
    WHISPER_AVAILABLE = False
    stt_client = None
    logger.warning("OpenAI Whisper not available - using browser STT only")


async def generate_speech(text: str, voice: str = "guy") -> dict:
    """Generate speech from text using Edge TTS"""
    try:
        voice_id = VOICES.get(voice, VOICES["guy"])
        temp_path = os.path.join(tempfile.gettempdir(), f"aeon_{uuid.uuid4()}.mp3")
        
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(temp_path)
        
        with open(temp_path, "rb") as f:
            audio_data = f.read()
        
        os.remove(temp_path)
        
        return {
            "success": True,
            "audio": base64.b64encode(audio_data).decode("utf-8"),
            "format": "mp3"
        }
        
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"success": False, "error": str(e)}


async def transcribe_audio(audio_data: bytes, language: str = "en") -> dict:
    """
    Transcribe audio using OpenAI Whisper for natural, accurate transcription.
    Falls back to browser STT if Whisper is not available.
    """
    if not WHISPER_AVAILABLE or not stt_client:
        return {"success": False, "error": "Whisper not available", "use_browser": True}
    
    try:
        # Save audio to temp file
        temp_path = os.path.join(tempfile.gettempdir(), f"aeon_stt_{uuid.uuid4()}.webm")
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        
        # Transcribe with Whisper
        with open(temp_path, "rb") as audio_file:
            response = await stt_client.transcribe(
                file=audio_file,
                model="whisper-1",
                language=language,
                response_format="json",
                prompt="This is a conversation about cryptocurrency trading, market analysis, and trading signals."
            )
        
        os.remove(temp_path)
        
        return {
            "success": True,
            "text": response.text,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"STT error: {e}")
        return {"success": False, "error": str(e), "use_browser": True}


def get_voice_info() -> dict:
    """Get available voices and STT status"""
    return {
        "tts_voices": list(VOICES.keys()),
        "stt_available": WHISPER_AVAILABLE,
        "stt_provider": "whisper-1" if WHISPER_AVAILABLE else "browser"
    }
