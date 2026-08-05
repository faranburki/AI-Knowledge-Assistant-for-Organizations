import abc
from typing import AsyncGenerator

class BaseVoiceTransport(abc.ABC):
    """
    Abstract base class for any voice transport mechanism.
    Decouples the business logic (VoiceSessionRuntime) from 
    how audio enters and exits the system (HTTP, WebRTC, WebSocket).
    """
    
    def __init__(self, runtime_manager):
        self.runtime_manager = runtime_manager

    @abc.abstractmethod
    async def connect(self, session_id: str, **kwargs):
        """Establish the connection (if required) and resolve the runtime."""
        pass

    @abc.abstractmethod
    async def receive_audio(self, session_id: str, *args, **kwargs):
        """Handle incoming audio and push to the runtime's audio_in_queue."""
        pass

    @abc.abstractmethod
    async def stream_audio_out(self, session_id: str) -> AsyncGenerator[bytes, None]:
        """Pull from the runtime's audio_out_queue and stream to the client."""
        pass
        
    @abc.abstractmethod
    async def disconnect(self, session_id: str):
        """Handle graceful disconnection and resource cleanup."""
        pass
        
    @abc.abstractmethod
    async def close(self):
        """Hard close for all connections managed by this transport."""
        pass
