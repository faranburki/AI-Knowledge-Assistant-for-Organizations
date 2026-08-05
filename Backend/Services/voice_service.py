import abc
import asyncio
import os
import tempfile
import logging

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
        import pyttsx3
        # Initialize engine inside the thread to avoid COM context issues across threads
        engine = pyttsx3.init()
        # Adjust properties for a more professional tone
        engine.setProperty('rate', 170)
        engine.save_to_file(text, filepath)
        engine.runAndWait()


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
                audio_bytes = f.read()
            return audio_bytes
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
    def transcribe_audio(self, filepath: str) -> str:
        """Transcribe audio from a file and return the text."""
        pass

class GoogleSTTProvider(BaseSTTProvider):
    """Lightweight STT provider using SpeechRecognition (Google STT)."""
    def transcribe_audio(self, filepath: str) -> str:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.AudioFile(filepath) as source:
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
        # Web browsers often record in webm or ogg format.
        # SpeechRecognition library expects WAV, AIFF, or FLAC.
        # If the user sends webm, we might need ffmpeg to convert it, but SpeechRecognition
        # can sometimes read it if the internal format is PCM. We will write it directly
        # and let the AudioFile class attempt to read it.
        # NOTE: For a robust system, we would use ffmpeg here to convert to WAV.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            temp_path = tmp.name
        
        try:
            return provider.transcribe_audio(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    text = await asyncio.to_thread(_transcribe)
    return text
