"""
AEON VOICE CHAT MODULE
Real-time voice conversation with Aeon

Uses:
- OpenAI Whisper (via Emergent key) for Speech-to-Text
- Edge TTS (free) for Text-to-Speech
- WebSocket for real-time communication
"""

import asyncio
import base64
import io
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional

import edge_tts
from dotenv import load_dotenv
from emergentintegrations.llm.openai import OpenAISpeechToText

load_dotenv()

logger = logging.getLogger(__name__)

# Aeon voice options (Edge TTS voices)
AEON_VOICES = {
    "guy": "en-US-GuyNeural",           # Confident male (default)
    "davis": "en-US-DavisNeural",       # Deep male
    "tony": "en-US-TonyNeural",         # Casual male
    "jason": "en-US-JasonNeural",       # Professional male
    "aria": "en-US-AriaNeural",         # Female option
    "jenny": "en-US-JennyNeural",       # Female casual
    "british": "en-GB-RyanNeural",      # British male
    "australian": "en-AU-WilliamNeural" # Australian male
}

# Default voice for Aeon
DEFAULT_VOICE = "guy"


class AeonVoiceChat:
    """
    Voice chat handler for Aeon
    
    Features:
    - Transcribe user audio with Whisper
    - Generate Aeon's voice responses with Edge TTS
    - Support for different voice personas
    """
    
    def __init__(self):
        self.stt = OpenAISpeechToText(api_key=os.getenv("EMERGENT_LLM_KEY"))
        self.current_voice = AEON_VOICES[DEFAULT_VOICE]
        self.conversation_history = []
        self.temp_dir = tempfile.gettempdir()
    
    def set_voice(self, voice_name: str) -> str:
        """Set Aeon's voice"""
        if voice_name.lower() in AEON_VOICES:
            self.current_voice = AEON_VOICES[voice_name.lower()]
            return f"Voice set to {voice_name}"
        return f"Unknown voice. Options: {', '.join(AEON_VOICES.keys())}"
    
    def get_available_voices(self) -> dict:
        """Get list of available voices"""
        return {
            "voices": list(AEON_VOICES.keys()),
            "current": [k for k, v in AEON_VOICES.items() if v == self.current_voice][0],
            "descriptions": {
                "guy": "Confident American male (default)",
                "davis": "Deep American male",
                "tony": "Casual American male", 
                "jason": "Professional American male",
                "aria": "American female",
                "jenny": "Casual American female",
                "british": "British male",
                "australian": "Australian male"
            }
        }
    
    async def transcribe_audio(self, audio_data: bytes, format: str = "webm") -> dict:
        """
        Transcribe audio using Whisper
        
        Args:
            audio_data: Raw audio bytes
            format: Audio format (webm, mp3, wav, etc.)
        
        Returns:
            dict with transcribed text or error
        """
        try:
            # Save to temp file
            temp_path = os.path.join(self.temp_dir, f"voice_{uuid.uuid4()}.{format}")
            
            with open(temp_path, "wb") as f:
                f.write(audio_data)
            
            # Transcribe with Whisper
            with open(temp_path, "rb") as audio_file:
                response = await self.stt.transcribe(
                    file=audio_file,
                    model="whisper-1",
                    response_format="json",
                    language="en",
                    prompt="This is a conversation about crypto trading, market analysis, and life advice."
                )
            
            # Cleanup
            os.remove(temp_path)
            
            text = response.text.strip()
            logger.info(f"Transcribed: {text[:100]}...")
            
            return {
                "success": True,
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_speech(self, text: str, voice: str = None) -> dict:
        """
        Generate speech audio from text using Edge TTS
        
        Args:
            text: Text to convert to speech
            voice: Optional voice override
        
        Returns:
            dict with base64 audio data or error
        """
        try:
            voice_to_use = voice if voice else self.current_voice
            
            # Generate audio with Edge TTS
            communicate = edge_tts.Communicate(text, voice_to_use)
            
            # Collect audio chunks
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            # Combine chunks
            audio_data = b"".join(audio_chunks)
            
            # Convert to base64 for easy transport
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
            
            logger.info(f"Generated speech: {len(audio_data)} bytes")
            
            return {
                "success": True,
                "audio_base64": audio_base64,
                "format": "mp3",
                "voice": voice_to_use,
                "text_length": len(text),
                "audio_size": len(audio_data)
            }
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_speech_file(self, text: str, voice: str = None) -> str:
        """
        Generate speech and save to file
        
        Returns:
            Path to generated audio file
        """
        try:
            voice_to_use = voice if voice else self.current_voice
            
            # Generate unique filename
            filename = f"aeon_voice_{uuid.uuid4()}.mp3"
            filepath = os.path.join(self.temp_dir, filename)
            
            # Generate audio
            communicate = edge_tts.Communicate(text, voice_to_use)
            await communicate.save(filepath)
            
            logger.info(f"Saved speech to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"TTS file error: {e}")
            return None
    
    def add_to_history(self, role: str, content: str):
        """Add message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep last 20 exchanges
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]
    
    def get_history(self) -> list:
        """Get conversation history"""
        return self.conversation_history
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []


# Global instance
aeon_voice = AeonVoiceChat()


async def list_edge_voices():
    """List all available Edge TTS voices (for reference)"""
    voices = await edge_tts.list_voices()
    english_voices = [v for v in voices if v["Locale"].startswith("en-")]
    return english_voices
