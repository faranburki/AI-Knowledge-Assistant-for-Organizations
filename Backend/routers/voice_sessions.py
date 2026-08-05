import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File
from typing import Dict, Any

from Backend.models.voice_session import VoiceSessionCreate, VoiceSessionResponse
from Backend.Services.voice_session_service import (
    create_session,
    get_session,
    validate_session,
    touch_session,
    end_session
)
from Backend.Services.voice_runtime import runtime_manager
from Backend.Services.voice_transports.http_transport import HttpVoiceTransport
from Backend.core.security import get_current_user
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Instantiate the abstract transport layer
http_transport = HttpVoiceTransport(runtime_manager)

@router.post("/", response_model=VoiceSessionResponse)
async def create_voice_session(
    request: VoiceSessionCreate,
    http_request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Initialize a new Voice Session.
    """
    try:
        # In the future, we can validate that the current_user belongs to request.organization_id
        session_doc = await create_session(
            user_id=current_user["user_id"],
            organization_id=request.organization_id,
            conversation_id=request.conversation_id,
            session_type=request.session_type,
            agent_id=request.agent_id
        )
        
        # Initialize the in-memory runtime
        runtime_manager.get_or_create_runtime(
            session_id=session_doc["session_id"],
            user_id=current_user["user_id"],
            org_id=request.organization_id,
            conversation_id=request.conversation_id,
            role=current_user["role"],
            subscribed_org_ids=current_user["subscribed_org_ids"],
            embedding_model=http_request.app.state.embedding_model
        )
        
        return session_doc
    except Exception as exc:
        logger.exception("Failed to create voice session")
        raise HTTPException(status_code=500, detail="Could not create voice session")

@router.get("/{session_id}", response_model=VoiceSessionResponse)
async def get_voice_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve Voice Session state.
    """
    doc = await get_session(session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if doc.get("user_id") != current_user["user_id"]:
        # Or check org admin permissions, etc.
        raise HTTPException(status_code=403, detail="Not authorized to access this session")
        
    return doc

@router.post("/{session_id}/touch", response_model=VoiceSessionResponse)
async def touch_voice_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the last_activity of the Voice Session in MongoDB.
    Also touches the in-memory runtime if active.
    """
    user_id = current_user["user_id"]
    doc = await get_session(session_id)
    if not doc or doc.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        
    updated = await touch_session(session_id)
    if not updated:
        raise HTTPException(status_code=400, detail="Cannot touch an ended session")
        
    # Touch in-memory runtime
    runtime = runtime_manager.get_runtime(session_id)
    if runtime:
        await runtime.touch()
        
    return updated

@router.post("/{session_id}/heartbeat")
async def heartbeat_voice_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Lightweight heartbeat endpoint for active streams.
    Does not write to MongoDB on every tick, just keeps the in-memory pipeline alive.
    """
    runtime = runtime_manager.get_runtime(session_id)
    if not runtime:
        # If it dropped from memory, touching MongoDB might recover it on the next real request.
        # But for heartbeat, just 404 if pipeline is dead.
        raise HTTPException(status_code=404, detail="Active pipeline not found for session")
    
    await runtime.touch()
    return {"status": "alive"}

@router.post("/{session_id}/stream")
async def stream_audio_session(
    session_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Simulate a WebRTC stream via HTTP.
    Accepts an audio file, submits it to the pipeline, and streams the TTS response back.
    """
    runtime = runtime_manager.get_runtime(session_id)
    if not runtime:
        # Lazy load if it was dropped from memory but exists in DB
        doc = await get_session(session_id)
        if not doc or doc.get("user_id") != current_user["user_id"]:
            raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        runtime = runtime_manager.get_or_create_runtime(
            session_id=session_id,
            user_id=current_user["user_id"],
            org_id=doc["organization_id"],
            conversation_id=doc["conversation_id"],
            role=current_user["role"],
            subscribed_org_ids=current_user["subscribed_org_ids"],
            embedding_model=request.app.state.embedding_model
        )

    # 1. Submit audio using Transport Abstraction
    audio_bytes = await file.read()
    await http_transport.receive_audio(session_id, audio_bytes)

    # 2. Reaping audio stream using Transport Abstraction
    return StreamingResponse(http_transport.stream_audio_out(session_id), media_type="audio/wav")

@router.post("/{session_id}/end", response_model=VoiceSessionResponse)
async def end_voice_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a Voice Session as ENDED.
    """
    doc = await get_session(session_id)
    if not doc or doc.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        
    updated = await end_session(session_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update session state")
        
    await runtime_manager.remove_runtime(session_id)
    return updated
