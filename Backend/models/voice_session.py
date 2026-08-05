from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class VoiceSessionState(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    FAILED = "FAILED"

class VoiceRuntimeState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    GENERATING_SPEECH = "GENERATING_SPEECH"
    STREAMING_AUDIO = "STREAMING_AUDIO"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    ENDED = "ENDED"

class VoiceSessionType(str, Enum):
    PUSH_TO_TALK = "push_to_talk"
    # Documented for future:
    # WEBRTC = "webrtc"
    # PHONE = "phone"
    # API = "api"

class VoiceSessionCreate(BaseModel):
    """Schema for initializing a new voice session."""
    organization_id: str
    conversation_id: str
    session_type: VoiceSessionType = VoiceSessionType.PUSH_TO_TALK
    agent_id: Optional[str] = None

class VoiceSessionResponse(BaseModel):
    """Schema for returning voice session details."""
    session_id: str
    user_id: str
    organization_id: str
    conversation_id: str
    agent_id: Optional[str] = None
    session_type: str
    state: str
    created_at: datetime
    updated_at: datetime
    last_activity: datetime
    ended_at: Optional[datetime] = None
