import abc
import asyncio
import os
import tempfile
import logging
from typing import Any

logger = logging.getLogger(__name__)

class BaseVoiceProvider(abc.ABC):
    """Abstract base class for all Voice (TTS) providers."""
    
    @abc.abstractmethod
    def generate_audio(self, text: str, filepath: str) -> None:
        """Generate audio from text and save to the given filepath."""
        pass


class Pyttsx3VoiceProvider(BaseVoiceProvider):
    """Local CPU-optimized fallback provider using OS native voices."""
    def generate_audio(self, text: str, filepath: str) -> None:
        import subprocess
        import tempfile
        import os
        import sys
        
        # Pyttsx3 on Windows (SAPI5) leaks COM state and speech queues across threads.
        # If a previous generation fails, its text stays in the queue and plays later!
        # We MUST run it in a completely isolated subprocess to guarantee statelessness.
        script = f'''import pyttsx3
engine = pyttsx3.init()
engine.setProperty("rate", 170)
engine.save_to_file({repr(text)}, r"{filepath}")
engine.runAndWait()
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            script_path = f.name
            
        try:
            subprocess.run([sys.executable, script_path], check=True, capture_output=True)
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)


# We use a factory pattern to allow easy swapping to Piper/Kokoro in the future
def get_voice_provider() -> BaseVoiceProvider:
    return Pyttsx3VoiceProvider()


async def generate_speech_bytes(text: str) -> bytes:
    """
    Generate speech completely out of the event loop.
    Returns the raw wav bytes so the endpoint can stream it seamlessly.
    """
    provider = get_voice_provider()
    
    # We use a temporary file to guarantee multi-user isolation
    # and statelessness. No two users will overwrite the same file.
    def _generate():
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            temp_path = tmp.name
        
        try:
            provider.generate_audio(text, temp_path)
            with open(temp_path, "rb") as f:
                audio_bytes = bytearray(f.read())
                
            # Pyttsx3 on Windows often writes malformed WAV headers with incorrect chunk sizes.
            # PyAV (FFmpeg) will strictly obey the incorrect size and truncate the audio to 1-2 words!
            # We must manually patch the RIFF and 'data' chunk sizes in the raw bytes.
            if audio_bytes.startswith(b"RIFF"):
                import struct
                # Fix RIFF total size
                struct.pack_into('<I', audio_bytes, 4, len(audio_bytes) - 8)
                
                # Scan for the 'data' chunk and fix its size
                data_idx = audio_bytes.find(b"data")
                if data_idx != -1 and data_idx < 1024:
                    actual_data_size = len(audio_bytes) - (data_idx + 8)
                    struct.pack_into('<I', audio_bytes, data_idx + 4, actual_data_size)
                    
            return bytes(audio_bytes)
        finally:
            # Clean up the file to prevent storage leaks
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # Run the entire IO/CPU bound process in a separate thread
    audio_data = await asyncio.to_thread(_generate)
    return audio_data

# ---------------------------------------------------------------------------
# Speech-to-Text (STT) Providers
# ---------------------------------------------------------------------------

class BaseSTTProvider(abc.ABC):
    """Abstract base class for all Speech-to-Text (STT) providers."""
    
    @abc.abstractmethod
    def transcribe_audio(self, audio_source: Any) -> str:
        """Transcribe audio from a file or file-like object and return the text."""
        pass

class GoogleSTTProvider(BaseSTTProvider):
    """Lightweight STT provider using SpeechRecognition (Google STT)."""
    def transcribe_audio(self, audio_source: Any) -> str:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_source) as source:
            audio_data = recognizer.record(source)
            try:
                # Using Google Web Speech API for fast, zero-dependency transcription
                text = recognizer.recognize_google(audio_data)
                return text
            except sr.UnknownValueError:
                logger.warning("Google Speech Recognition could not understand audio")
                return ""
            except sr.RequestError as e:
                logger.error(f"Could not request results from Google Speech Recognition service; {e}")
                raise Exception("STT Service unavailable")

def get_stt_provider() -> BaseSTTProvider:
    # Future: Swap this with WhisperSTTProvider for a 100% offline GPU-based implementation
    return GoogleSTTProvider()

async def transcribe_audio_bytes(audio_bytes: bytes) -> str:
    """
    Transcribe raw audio bytes into text.
    Handles the temporary file lifecycle and runs blocking IO in a thread.
    """
    provider = get_stt_provider()
    
    def _transcribe():
        import io
        # Use an in-memory BytesIO buffer instead of temp files
        file_obj = io.BytesIO(audio_bytes)
        return provider.transcribe_audio(file_obj)

    text = await asyncio.to_thread(_transcribe)
    return text
