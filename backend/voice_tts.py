"""
AEON VOICE MODULE - Simple TTS only
Uses Edge TTS (free) for text-to-speech
"""

import asyncio
import base64
import logging
import os
import tempfile
import uuid

import edge_tts

logger = logging.getLogger(__name__)

# Voice options
VOICES = {
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural", 
    "british": "en-GB-RyanNeural",
    "australian": "en-AU-WilliamNeural"
}


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
