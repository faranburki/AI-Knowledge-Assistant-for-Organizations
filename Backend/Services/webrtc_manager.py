import logging
import asyncio
import json
from typing import Dict, Any
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.mediastreams import MediaStreamTrack
import av
import io
import fractions
from Backend.Services.voice_runtime import VoiceSessionRuntime

logger = logging.getLogger(__name__)

class TTSAudioTrack(MediaStreamTrack):
    """
    A WebRTC audio track that continuously consumes generated TTS audio
    from the VoiceSessionRuntime and streams it back to the client.
    """
    kind = "audio"

    def __init__(self, runtime: VoiceSessionRuntime):
        super().__init__()
        self.runtime = runtime
        self._container = None
        self._stream = None
        self._iterator = None
        self._resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
        self._pts = 0
        self._frame_buffer = []

    async def recv(self):
        # If we aren't currently decoding a clip, block and wait for the next one
        if self._iterator is None:
            audio_bytes = await self.runtime.get_next_audio_bytes()
            logger.info(f"[{self.runtime.session_id}] TTSAudioTrack received {len(audio_bytes)} bytes. Starting stream.")
            self._container = av.open(io.BytesIO(audio_bytes))
            self._stream = self._container.streams.audio[0]
            self._iterator = self._container.decode(self._stream)

        # Buffer frames if empty
        while not self._frame_buffer:
            try:
                frame = next(self._iterator)
                for resampled_frame in self._resampler.resample(frame):
                    self._frame_buffer.append(resampled_frame)
            except StopIteration:
                # Flush the resampler
                for resampled_frame in self._resampler.resample(None):
                    self._frame_buffer.append(resampled_frame)
                
                if not self._frame_buffer:
                    logger.info(f"[{self.runtime.session_id}] TTSAudioTrack finished streaming clip.")
                    self._iterator = None
                    self._container = None
                    self.runtime.mark_audio_complete()
                    return await self.recv()

        # Pop from buffer
        frame = self._frame_buffer.pop(0)
        frame.pts = self._pts
        self._pts += frame.samples
        frame.time_base = fractions.Fraction(1, frame.sample_rate)
        return frame

class WebRTCManager:
    """
    Manages WebRTC PeerConnections for VoiceSessionRuntimes.
    Strictly handles signaling (Offer/Answer/ICE), keeps no state itself.
    """
    
    async def handle_signaling_message(self, runtime: VoiceSessionRuntime, message: dict, websocket):
        """Process incoming WebSocket JSON messages."""
        msg_type = message.get("type")
        
        if msg_type == "offer":
            logger.info(f"[{runtime.session_id}] Offer received.")
            
            if runtime.pc:
                logger.warning(f"[{runtime.session_id}] Overwriting existing PeerConnection!")
                await runtime.pc.close()
                
            pc = RTCPeerConnection()
            runtime.pc = pc
            
            # Attach the outbound audio track
            audio_out_track = TTSAudioTrack(runtime)
            pc.addTrack(audio_out_track)
            
            @pc.on("iceconnectionstatechange")
            async def on_iceconnectionstatechange():
                logger.info(f"[{runtime.session_id}] ICE Connection State: {pc.iceConnectionState}")
                if pc.iceConnectionState in ["failed", "closed"]:
                    logger.info(f"[{runtime.session_id}] ICE {pc.iceConnectionState}. Triggering graceful cleanup.")
                    from Backend.Services.voice_runtime import runtime_manager
                    # We create a background task to prevent blocking the ICE event handler
                    asyncio.create_task(runtime_manager.remove_runtime(runtime.session_id))
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"[{runtime.session_id}] Connection State: {pc.connectionState}")
                if pc.connectionState == "connected":
                    logger.info(f"[{runtime.session_id}] WebRTC fully connected!")
                elif pc.connectionState in ["failed", "closed"]:
                    logger.warning(f"[{runtime.session_id}] WebRTC connection closed/failed.")
            
            @pc.on("track")
            def on_track(track):
                logger.info(f"[{runtime.session_id}] Track received: {track.kind}")
                if track.kind == "audio":
                    async def read_frames():
                        try:
                            while True:
                                frame = await track.recv()
                                runtime.process_audio_frame(frame)
                        except Exception as e:
                            logger.info(f"[{runtime.session_id}] Track reading stopped: {e}")
                    
                    asyncio.create_task(read_frames())
            
            offer = RTCSessionDescription(sdp=message["sdp"], type=message["type"])
            await pc.setRemoteDescription(offer)
            
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            logger.info(f"[{runtime.session_id}] Answer created. Sending back to client.")
            await websocket.send_json({
                "type": pc.localDescription.type,
                "sdp": pc.localDescription.sdp
            })
            
        elif msg_type == "candidate":
            logger.info(f"[{runtime.session_id}] ICE candidate received.")
            if runtime.pc and message.get("candidate"):
                cand_data = message["candidate"]
                cand_str = cand_data.get("candidate", "")
                if cand_str:
                    try:
                        from aiortc.sdp import candidate_from_sdp
                        # Strip "candidate:" prefix if present
                        if cand_str.startswith("candidate:"):
                            cand_str = cand_str[10:]
                        candidate = candidate_from_sdp(cand_str)
                        candidate.sdpMid = cand_data.get("sdpMid")
                        candidate.sdpMLineIndex = cand_data.get("sdpMLineIndex")
                        await runtime.pc.addIceCandidate(candidate)
                    except Exception as e:
                        logger.error(f"[{runtime.session_id}] Failed to parse ICE candidate: {e}")
        else:
            logger.warning(f"[{runtime.session_id}] Unknown signaling message type: {msg_type}")

webrtc_manager = WebRTCManager()
