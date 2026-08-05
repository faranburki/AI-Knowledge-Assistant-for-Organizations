import logging
from fastapi import APIRouter, HTTPException
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel

from Backend.Services.voice_service import generate_speech_bytes, transcribe_audio_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

class VoiceRequest(BaseModel):
    text: str

@router.post("/generate")
async def generate_voice(request: VoiceRequest):
    """
    Generate speech from the provided text.
    This endpoint is entirely decoupled from the RAG pipeline.
    """
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
        
    try:
        audio_bytes = await generate_speech_bytes(request.text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as exc:
        logger.exception("Failed to generate voice.")
        # Graceful degradation: we return a 500 but the app continues running.
        # The text response is completely unaffected.
        raise HTTPException(status_code=500, detail="Voice generation failed. The text response is still valid.")

@router.post("/transcribe")
async def transcribe_voice(file: UploadFile = File(...)):
    """
    Transcribe uploaded audio file to text.
    Expects a WAV file.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No audio file provided.")
        
    try:
        audio_bytes = await file.read()
        text = await transcribe_audio_bytes(audio_bytes)
        return {"text": text}
    except Exception as exc:
        logger.exception("Failed to transcribe audio.")
        raise HTTPException(status_code=500, detail="Audio transcription failed.")
