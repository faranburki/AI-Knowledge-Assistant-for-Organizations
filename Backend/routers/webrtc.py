import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from Backend.Services.voice_runtime import runtime_manager
from Backend.Services.webrtc_manager import webrtc_manager
from Backend.core.security import get_current_user_ws

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/{session_id}/webrtc")
async def webrtc_signaling(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...)
):
    """
    WebSocket endpoint strictly for WebRTC Signaling (Trickle ICE).
    """
    await websocket.accept()
    
    try:
        # Authenticate via token query param
        current_user = await get_current_user_ws(token)
    except HTTPException:
        logger.warning("WebSocket unauthorized.")
        await websocket.close(code=1008)
        return
        
    # Verify session exists in runtime
    runtime = runtime_manager.get_runtime(session_id)
    if not runtime:
        logger.warning(f"WebSocket rejected. No active runtime for session {session_id}")
        await websocket.close(code=1008)
        return
        
    if runtime.user_id != current_user["user_id"]:
        logger.warning(f"WebSocket rejected. User {current_user['user_id']} does not own session {session_id}")
        await websocket.close(code=1008)
        return
        
    logger.info(f"WebSocket signaling connected for session {session_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Pass everything directly to the WebRTC Manager.
            # The WebSocket stays thin and owns zero business logic.
            await webrtc_manager.handle_signaling_message(runtime, message, websocket)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket signaling disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket signaling error: {e}")
        await websocket.close(code=1011)
