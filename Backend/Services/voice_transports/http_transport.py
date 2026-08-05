import logging
import asyncio
from typing import AsyncGenerator
from Backend.Services.voice_transports.base import BaseVoiceTransport

logger = logging.getLogger(__name__)

class HttpVoiceTransport(BaseVoiceTransport):
    """
    Simulated WebRTC streaming transport over standard HTTP POST/Response.
    """
    
    async def connect(self, session_id: str, **kwargs):
        # HTTP is stateless, nothing to persist natively across requests
        pass

    async def receive_audio(self, session_id: str, audio_bytes: bytes):
        """Push uploaded audio into the runtime."""
        runtime = self.runtime_manager.get_runtime(session_id)
        if not runtime:
            raise ValueError(f"Runtime not found for session {session_id}")
            
        await runtime.submit_audio(audio_bytes)

    async def stream_audio_out(self, session_id: str) -> AsyncGenerator[bytes, None]:
        """Reap the audio_out_queue and yield to StreamingResponse."""
        runtime = self.runtime_manager.get_runtime(session_id)
        if not runtime:
            logger.error(f"Cannot stream, runtime missing for session {session_id}")
            yield b""
            return
            
        try:
            # For HTTP, we expect a single turn (one STT -> one LLM -> one TTS chunk)
            audio_chunk = await asyncio.wait_for(runtime.audio_out_queue.get(), timeout=30.0)
            yield audio_chunk
            runtime.audio_out_queue.task_done()
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for audio out on session {session_id}")
            yield b""
        except asyncio.CancelledError:
            logger.warning(f"Client disconnected during streaming for session {session_id}")
            runtime.disconnect()
            raise
        except Exception as e:
            logger.error(f"Error streaming audio out: {e}")
            runtime.disconnect()
            raise e

    async def disconnect(self, session_id: str):
        pass
        
    async def close(self):
        pass
