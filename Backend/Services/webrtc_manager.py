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

    Production hardening:
      * Frames are paced to real time (20ms per 960-sample frame), matching
        how aiortc's own MediaPlayer behaves. Without pacing the RTP sender
        bursts the whole clip onto the wire, which causes jitter/packet loss
        on real networks.
      * Decode/container failures are isolated: a corrupt clip is skipped,
        the stream keeps running, and the session is never silently killed.
      * Playback-complete is reported only after the final buffered audio has
        actually been handed to the RTP layer, so the runtime never returns
        to the listening state while audio is still in flight.
    """
    kind = "audio"

    # 960 samples @ 48 kHz = 20 ms of audio per RTP frame
    FRAME_SIZE = 960
    BYTES_PER_FRAME = 3840

    def __init__(self, runtime: VoiceSessionRuntime):
        super().__init__()
        self.runtime = runtime
        self._container = None
        self._stream = None
        self._iterator = None
        self._resampler = None
        self._pts = 0
        self._audio_buffer = bytearray()
        self._clip_finishing = False

    def _make_silence_frame(self):
        silence = av.AudioFrame(format="s16", layout="stereo", samples=self.FRAME_SIZE)
        silence.sample_rate = 48000
        silence.planes[0].update(b"\x00" * self.BYTES_PER_FRAME)
        silence.pts = self._pts
        self._pts += self.FRAME_SIZE
        silence.time_base = fractions.Fraction(1, 48000)
        return silence

    async def _pace(self):
        """Throttle the sender to real time (20 ms per frame)."""
        await asyncio.sleep(0.02)

    def _open_clip(self) -> bool:
        """Try to open the next queued clip. Returns True on success."""
        try:
            audio_bytes = self.runtime.audio_out_queue.get_nowait()
            logger.info(f"[{self.runtime.session_id}] TTSAudioTrack received "
                        f"{len(audio_bytes)} bytes. Starting stream.")
            self._container = av.open(io.BytesIO(audio_bytes))
            self._stream = self._container.streams.audio[0]
            self._iterator = self._container.decode(self._stream)
            self._resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
            return True
        except asyncio.QueueEmpty:
            return False
        except Exception as e:
            # A corrupt/empty clip must never kill the whole RTP stream.
            # Skip it and keep streaming silence.
            logger.error(f"[{self.runtime.session_id}] Failed to open TTS clip "
                         f"(skipping): {type(e).__name__}: {e}")
            self._container = None
            self._stream = None
            self._iterator = None
            self._resampler = None
            self.runtime.audio_out_queue.task_done()
            return False

    async def recv(self):
        while len(self._audio_buffer) < self.BYTES_PER_FRAME:
            # A clip has finished decoding but its tail is still buffered.
            # Only report playback-complete once the tail has been fully
            # handed to the RTP layer (buffer empty), never before.
            if self._clip_finishing:
                if len(self._audio_buffer) == 0:
                    self._clip_finishing = False
                    logger.info(f"[{self.runtime.session_id}] TTSAudioTrack finished streaming clip.")
                    self.runtime.mark_audio_complete()
                    # fall through: pick up the next clip / stream silence
                else:
                    padding = self.BYTES_PER_FRAME - len(self._audio_buffer)
                    self._audio_buffer.extend(b"\x00" * padding)
                    break

            if self._iterator is None:
                if not self._open_clip():
                    if len(self._audio_buffer) > 0:
                        padding = self.BYTES_PER_FRAME - len(self._audio_buffer)
                        self._audio_buffer.extend(b"\x00" * padding)
                        break
                    silence = self._make_silence_frame()
                    await self._pace()
                    return silence

            try:
                frame = next(self._iterator)
                for resampled_frame in self._resampler.resample(frame):
                    self._audio_buffer.extend(resampled_frame.to_ndarray().tobytes())
            except StopIteration:
                # Normal end of clip: flush the resampler and finish.
                for resampled_frame in self._resampler.resample(None):
                    self._audio_buffer.extend(resampled_frame.to_ndarray().tobytes())
                self._clip_finishing = True
                self._container = None
                self._iterator = None
                self._resampler = None
            except Exception as e:
                # Decode error mid-clip: skip the rest of this clip without
                # killing the stream; completion is still reported normally.
                logger.warning(f"[{self.runtime.session_id}] TTS clip decode error "
                               f"(clip truncated): {type(e).__name__}: {e}")
                try:
                    for resampled_frame in self._resampler.resample(None):
                        self._audio_buffer.extend(resampled_frame.to_ndarray().tobytes())
                except Exception:
                    pass
                self._clip_finishing = True
                self._container = None
                self._iterator = None
                self._resampler = None

        frame_bytes = bytes(self._audio_buffer[:self.BYTES_PER_FRAME])
        del self._audio_buffer[:self.BYTES_PER_FRAME]

        new_frame = av.AudioFrame(format="s16", layout="stereo", samples=self.FRAME_SIZE)
        new_frame.sample_rate = 48000
        new_frame.planes[0].update(frame_bytes)
        new_frame.pts = self._pts
        self._pts += self.FRAME_SIZE
        new_frame.time_base = fractions.Fraction(1, 48000)

        # Pace to real time so the sender never floods the network.
        await self._pace()

        return new_frame

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
