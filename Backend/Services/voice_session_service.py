import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from Backend.Database.mongodb import mongodb
from Backend.models.voice_session import VoiceSessionState, VoiceSessionType

logger = logging.getLogger(__name__)

async def create_session(
    user_id: str,
    organization_id: str,
    conversation_id: str,
    session_type: str = VoiceSessionType.PUSH_TO_TALK.value,
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new Voice Session runtime state."""
    
    session_id = f"vsession_{uuid.uuid4().hex}"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    session_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "organization_id": organization_id,
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "session_type": getattr(session_type, 'value', session_type),
        "state": VoiceSessionState.CREATED.value,
        "created_at": now_iso,
        "updated_at": now_iso,
        "last_activity": now_iso,
        "ended_at": None
    }
    
    await mongodb.db.voice_sessions.insert_one(session_doc)
    logger.info(f"Created voice session {session_id} for user {user_id}")
    return session_doc

async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a Voice Session by its unique ID."""
    doc = await mongodb.db.voice_sessions.find_one({"session_id": session_id})
    return doc

async def validate_session(session_id: str, user_id: str, organization_id: str) -> bool:
    """Validate that the session exists and belongs to the specified user and organization."""
    doc = await get_session(session_id)
    if not doc:
        return False
    if doc.get("user_id") != user_id or doc.get("organization_id") != organization_id:
        return False
    if doc.get("state") == VoiceSessionState.ENDED:
        return False
    return True

async def touch_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Update the last_activity timestamp and mark as ACTIVE if not already."""
    now_iso = datetime.now(timezone.utc).isoformat()
    
    result = await mongodb.db.voice_sessions.find_one_and_update(
        {"session_id": session_id, "state": {"$ne": VoiceSessionState.ENDED.value}},
        {"$set": {
            "last_activity": now_iso,
            "updated_at": now_iso,
            "state": VoiceSessionState.ACTIVE.value
        }},
        return_document=True
    )
    return result

async def end_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Mark a session as ENDED."""
    now_iso = datetime.now(timezone.utc).isoformat()
    
    result = await mongodb.db.voice_sessions.find_one_and_update(
        {"session_id": session_id},
        {"$set": {
            "state": VoiceSessionState.ENDED.value,
            "updated_at": now_iso,
            "ended_at": now_iso
        }},
        return_document=True
    )
    return result

async def cleanup_expired_sessions(timeout_minutes: int = 60) -> int:
    """
    Find any active/created sessions with no activity for `timeout_minutes`
    and mark them as ENDED.
    """
    import datetime as dt
    cutoff_time = datetime.now(timezone.utc) - dt.timedelta(minutes=timeout_minutes)
    cutoff_iso = cutoff_time.isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    result = await mongodb.db.voice_sessions.update_many(
        {
            "state": {"$ne": VoiceSessionState.ENDED.value},
            "last_activity": {"$lt": cutoff_iso}
        },
        {
            "$set": {
                "state": VoiceSessionState.ENDED.value,
                "updated_at": now_iso,
                "ended_at": now_iso
            }
        }
    )
    
    if result.modified_count > 0:
        logger.info(f"Cleaned up {result.modified_count} expired voice sessions.")
    return result.modified_count
