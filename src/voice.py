"""
Voice transcription for MayaLite v0.4.

Handles voice messages via OpenAI Whisper API.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class VoiceTranscriber:
    """
    Transcribes voice messages using OpenAI Whisper API.
    """
    
    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.api_key = api_key
        self.model = model
        self._enabled = bool(api_key)
        
        if self._enabled:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
    
    @property
    def enabled(self) -> bool:
        """Check if voice transcription is enabled."""
        return self._enabled
    
    async def transcribe_file(self, file_path: Path) -> str:
        """
        Transcribe an audio file.
        
        Args:
            file_path: Path to audio file (ogg, mp3, wav, etc.)
            
        Returns:
            Transcribed text
        """
        if not self._enabled:
            raise ValueError("OpenAI API key not configured for voice transcription")
        
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        try:
            with open(file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text"
                )
            
            return transcript.strip()
            
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            raise
    
    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.ogg"
    ) -> str:
        """
        Transcribe audio from bytes.
        
        Args:
            audio_bytes: Raw audio bytes
            filename: Filename with extension (for format detection)
            
        Returns:
            Transcribed text
        """
        if not self._enabled:
            raise ValueError("OpenAI API key not configured for voice transcription")
        
        # Write to temp file
        suffix = Path(filename).suffix or ".ogg"
        
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = Path(tmp.name)
        
        try:
            return await self.transcribe_file(tmp_path)
        finally:
            # Clean up temp file
            try:
                tmp_path.unlink()
            except Exception:
                pass
    
    async def transcribe_telegram_voice(
        self,
        bot,
        voice_file_id: str
    ) -> str:
        """
        Download and transcribe a Telegram voice message.
        
        Args:
            bot: Telegram bot instance
            voice_file_id: Telegram file ID for the voice message
            
        Returns:
            Transcribed text
        """
        if not self._enabled:
            raise ValueError("OpenAI API key not configured for voice transcription")
        
        # Download voice file
        file = await bot.get_file(voice_file_id)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = Path(tmp.name)
        
        try:
            return await self.transcribe_file(tmp_path)
        finally:
            try:
                tmp_path.unlink()
            except Exception:
                pass
