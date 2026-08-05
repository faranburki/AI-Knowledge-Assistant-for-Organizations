import asyncio
import logging
from Backend.Services.voice_runtime import runtime_manager
from Backend.Services.voice_session_service import cleanup_expired_sessions

logger = logging.getLogger(__name__)

async def lifecycle_loop():
    """
    Background worker that runs throughout the FastAPI lifespan.
    It periodically cleans up orphaned in-memory runtimes and DB sessions.
    """
    logger.info("Lifecycle background loop started.")
    try:
        while True:
            await asyncio.sleep(30) # Sweep every 30 seconds
            
            # 1. Sweep active runtimes in memory
            # Prod timeout: 300 seconds (5 mins)
            # You can change this to 15 for testing.
            expired_ids = await runtime_manager.cleanup_expired(timeout_seconds=300)
            
            if expired_ids:
                logger.info(f"Reaped {len(expired_ids)} idle runtimes from memory: {expired_ids}")
                
            # Log active session metrics
            runtime_manager.log_metrics()
                
            # 2. Cleanup orphaned DB sessions.
            count = await cleanup_expired_sessions()
            if count > 0:
                logger.info(f"Cleaned up {count} orphaned sessions in database.")
                
    except asyncio.CancelledError:
        logger.info("Lifecycle background loop cancelled.")
    except Exception as e:
        logger.exception("Error in lifecycle background loop")
