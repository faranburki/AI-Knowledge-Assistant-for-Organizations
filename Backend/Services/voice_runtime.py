import asyncio
import time
import logging
from typing import Dict, Optional, Any
from Backend.models.voice_session import VoiceRuntimeState
from Backend.Services.voice_service import transcribe_audio_bytes, generate_speech_bytes
from Backend.Services.rag_pipeline import handle_query
from Backend.routers.query import classifier  # Reusing the existing classifier instance
from Backend.Services.vad import VoiceActivityDetector, Utterance

logger = logging.getLogger(__name__)

class VoiceSessionRuntime:
    # Seconds after playback finishes during which mic input is still gated,
    # so the tail of the AI's own speech cannot re-trigger a new turn.
    ASSISTANT_ECHO_TAIL_SECONDS = 0.6

    def __init__(self, session_id: str, user_id: str, org_id: str, conversation_id: str, role: str, subscribed_org_ids: list, embedding_model: Any):
        self.session_id = session_id
        self.user_id = user_id
        self.org_id = org_id
        self.conversation_id = conversation_id
        self.role = role
        self.subscribed_org_ids = subscribed_org_ids
        self.embedding_model = embedding_model
        
        self.state = VoiceRuntimeState.IDLE
        self.created_at = time.time()
        self.last_activity = time.time()
        
        # WebRTC PeerConnection owned by the runtime
        self.pc = None
        
        # VAD & Utterances
        self.vad = VoiceActivityDetector(energy_threshold=400.0, silence_duration_seconds=1.0)
        self.latest_utterance: Optional[Utterance] = None
        self.latest_transcript: Optional[str] = None
        self.latest_response: Optional[str] = None
        self.latest_audio: Optional[bytes] = None

        # Half-duplex playback gate: True while a TTS clip is queued/playing.
        self._assistant_active = False
        # Timestamp before which mic frames are ignored after playback ends.
        self._vad_armed_at: Optional[float] = None
        
        self.metrics = {
            "stt_latency_ms": 0,
            "llm_latency_ms": 0,
            "tts_latency_ms": 0,
            "total_latency_ms": 0,
            "stt_count": 0,
            "llm_count": 0,
            "tts_count": 0,
            "avg_response_time": 0
        }
        
        # Explicit Pipeline Queues
        self.audio_in_queue = asyncio.Queue()
        self.transcript_queue = asyncio.Queue()
        self.llm_response_queue = asyncio.Queue()
        # Bounded: if the client stops consuming (e.g. transport down), stale
        # clips are dropped instead of accumulating unbounded memory.
        self.audio_out_queue = asyncio.Queue(maxsize=4)
        
        self._tasks = []
        self._is_running = False

    def start(self):
        if self._is_running: return
        self._is_running = True

        # Reset half-duplex gate and VAD state for a fresh session
        self._assistant_active = False
        self._vad_armed_at = None
        self.vad.reset()
        self.state = VoiceRuntimeState.IDLE
        self._tasks.append(asyncio.create_task(self._stt_worker()))
        self._tasks.append(asyncio.create_task(self._llm_worker()))
        self._tasks.append(asyncio.create_task(self._tts_worker()))
        logger.info(f"Voice Runtime started for session {self.session_id}")

    async def touch(self):
        """Update last activity heartbeat."""
        self.last_activity = time.time()

    def set_assistant_active(self, active: bool):
        """
        Half-duplex gate: True while a TTS clip is queued or playing, so the
        assistant can never be re-triggered by its own playback (echo feedback).
        When released, mic input stays gated for a short echo tail.
        """
        self._assistant_active = bool(active)
        if active:
            self._vad_armed_at = None
            self.vad.reset()
        else:
            self._vad_armed_at = time.time() + self.ASSISTANT_ECHO_TAIL_SECONDS

    def disconnect(self):
        """Handle a transport disconnect event."""
        logger.info(f"Transport disconnected for session {self.session_id}")
        self.touch()
        # For HTTP, a disconnect during a request might mean we just idle.
        # For WebRTC, this might trigger a timeout. The runtime decides.

    async def shutdown(self):
        """Gracefully shut down the runtime, cancel workers, drain queues."""
        logger.info(f"[{self.session_id}] Shutting down Voice Runtime (Stop Transport -> Cancel Workers -> Flush Queues -> Release Buffers -> DB Update)")
        self._is_running = False
        
        # 1. Stop Transport
        if self.pc:
            await self.pc.close()
            self.pc = None
            
        # 2. Cancel workers
        for t in self._tasks:
            t.cancel()
            
        # 3. Flush queues
        while not self.audio_in_queue.empty(): self.audio_in_queue.get_nowait(); self.audio_in_queue.task_done()
        while not self.transcript_queue.empty(): self.transcript_queue.get_nowait(); self.transcript_queue.task_done()
        while not self.llm_response_queue.empty(): self.llm_response_queue.get_nowait(); self.llm_response_queue.task_done()
        while not self.audio_out_queue.empty(): self.audio_out_queue.get_nowait(); self.audio_out_queue.task_done()
            
        # 4. Release buffers
        self.latest_audio = None
        self.latest_transcript = None
        self.latest_response = None
        
        self.state = VoiceRuntimeState.ENDED
        
        # 5. Update Mongo
        try:
            from Backend.Services.voice_session_service import end_session
            await end_session(self.session_id)
            logger.info(f"[{self.session_id}] Updated DB state to ENDED")
        except Exception as e:
            logger.warning(f"[{self.session_id}] Failed to update DB state: {e}")
        
        duration = time.time() - self.created_at
        logger.info(f"[{self.session_id}] Destroyed. Duration: {int(duration)}s, STT: {self.metrics['stt_count']}, LLM: {self.metrics['llm_count']}, TTS: {self.metrics['tts_count']}")


    def process_audio_frame(self, frame):
        """
        Called continuously by the WebRTC transport for every mic frame.
        Routes frames through the adaptive VAD; completed utterances are
        submitted to the STT pipeline.
        Half-duplex: while the assistant is speaking (or during the echo
        tail), mic frames are dropped so playback can never re-trigger.
        """
        if self._assistant_active:
            return

        if self._vad_armed_at is not None:
            if time.time() < self._vad_armed_at:
                return
            self._vad_armed_at = None

        utterance = self.vad.process_frame(frame)
        if utterance:
            logger.info(f"[{self.session_id}] VAD emitted complete utterance "
                        f"({utterance.duration_ms:.0f}ms, {utterance.frame_count} frames)")
            self.latest_utterance = utterance
            self.state = VoiceRuntimeState.TRANSCRIBING
            wav_bytes = utterance.to_wav_bytes()
            asyncio.create_task(self.submit_audio(wav_bytes))
            # Lock the mic immediately: from the instant the user's sentence
            # is handed to the pipeline, no further mic data is accepted until
            # the assistant's speech has fully finished playing.
            self.set_assistant_active(True)


    async def submit_audio(self, audio_bytes: bytes):
        """External entry point for audio buffers."""
        await self.touch()
        await self.audio_in_queue.put(audio_bytes)
        self.state = VoiceRuntimeState.LISTENING

    async def _stt_worker(self):
        while self._is_running:
            try:
                audio_bytes = await self.audio_in_queue.get()
                await self.touch()
                self.state = VoiceRuntimeState.TRANSCRIBING
                
                t0 = time.time()
                transcript = await transcribe_audio_bytes(audio_bytes)
                latency = int((time.time() - t0) * 1000)
                
                self.metrics["stt_latency_ms"] = latency
                self.metrics["stt_count"] += 1
                await self.touch()
                logger.info(f"[{self.session_id}] STT complete: '{transcript}' in {latency}ms")
                
                if transcript and transcript.strip():
                    await self.transcript_queue.put(transcript.strip())
                else:
                    self.state = VoiceRuntimeState.IDLE
                    # No speech will be generated for this capture; re-open
                    # the mic so the session does not stay muted.
                    self.set_assistant_active(False)
                
                self.audio_in_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.session_id}] STT Worker error: {e}")
                self.state = VoiceRuntimeState.IDLE
                self.set_assistant_active(False)

    async def _llm_worker(self):
        while self._is_running:
            try:
                transcript = await self.transcript_queue.get()
                await self.touch()
                self.state = VoiceRuntimeState.THINKING
                
                t0 = time.time()
                
                org_ids = None if self.role != "public_user" else self.subscribed_org_ids
                
                result = await handle_query(
                    question=transcript,
                    user_id=self.user_id,
                    embedding_model=self.embedding_model,
                    role=self.role,
                    org_id=self.org_id,
                    org_ids=org_ids,
                    subscribed_org_ids=self.subscribed_org_ids,
                    classifier=classifier,
                    top_k=4,
                    conversation_id=self.conversation_id
                )
                
                latency = int((time.time() - t0) * 1000)
                self.metrics["llm_latency_ms"] = latency
                logger.info(f"[{self.session_id}] LLM complete in {latency}ms")
                
                answer = result["answer"]
                self.latest_response = answer
                logger.info(f"[{self.session_id}] AI Response: \"{answer}\"")
                
                # Phase 10: Feed the response into the TTS queue
                await self.llm_response_queue.put(answer)
                
                self.transcript_queue.task_done()
                
                # Return to listening state after AI finishes thinking
                self.state = VoiceRuntimeState.LISTENING

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.session_id}] LLM Worker error: {e}")
                self.state = VoiceRuntimeState.IDLE

    async def _tts_worker(self):
        while self._is_running:
            try:
                text = await self.llm_response_queue.get()
                await self.touch()
                self.state = VoiceRuntimeState.GENERATING_SPEECH
                logger.info(f"[{self.session_id}] Generating speech...")
                
                # Generate with one retry: transient pyttsx3/subprocess failures
                # must not silently drop the AI response.
                audio_bytes = None
                t0 = time.time()
                for attempt in range(1, 3):
                    try:
                        audio_bytes = await generate_speech_bytes(text)
                        break
                    except Exception as e:
                        logger.error(f"[{self.session_id}] TTS attempt {attempt} failed: {e}")
                        audio_bytes = None
                
                self.llm_response_queue.task_done()
                
                if audio_bytes is None:
                    logger.error(f"[{self.session_id}] TTS failed after retries; response spoken as text only.")
                    self.state = VoiceRuntimeState.LISTENING
                    # No clip will play for this turn; release the mic lock.
                    self.set_assistant_active(False)
                    continue
                
                latency = int((time.time() - t0) * 1000)
                
                self.metrics["tts_latency_ms"] = latency
                self.metrics["tts_count"] += 1
                
                total = self.metrics["stt_latency_ms"] + self.metrics["llm_latency_ms"] + self.metrics["tts_latency_ms"]
                self.metrics["total_latency_ms"] = total
                
                if self.metrics["avg_response_time"] == 0:
                    self.metrics["avg_response_time"] = total
                self.metrics["avg_response_time"] = (self.metrics["avg_response_time"] + total) // 2
                    
                await self.touch()               
                
                # Calculate Duration
                import io, wave
                try:
                    with wave.open(io.BytesIO(audio_bytes), 'rb') as wf:
                        duration = wf.getnframes() / float(wf.getframerate())
                except Exception:
                    duration = 0.0
                    
                size_kb = len(audio_bytes) / 1024.0
                
                logger.info(f"[{self.session_id}] Speech generated successfully.")
                logger.info(f"[{self.session_id}] Audio Duration: {duration:.1f} seconds")
                logger.info(f"[{self.session_id}] Audio Size: {size_kb:.0f} KB")
                
                self.latest_audio = audio_bytes
                
                # Gate the mic while this clip is (or will be) playing, so the
                # assistant can never be triggered by its own voice.
                self.set_assistant_active(True)
                
                # Bounded push: drop the oldest clip if the transport has
                # stopped consuming, instead of blocking or growing unbounded.
                try:
                    self.audio_out_queue.put_nowait(audio_bytes)
                except asyncio.QueueFull:
                    try:
                        dropped = self.audio_out_queue.get_nowait()
                        self.audio_out_queue.task_done()
                        logger.warning(f"[{self.session_id}] audio_out_queue full; dropped stale clip ({len(dropped)} bytes)")
                    except asyncio.QueueEmpty:
                        pass
                    self.audio_out_queue.put_nowait(audio_bytes)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.session_id}] TTS Worker error: {e}")
                self.state = VoiceRuntimeState.LISTENING

    async def get_next_audio_bytes(self) -> bytes:
        """Called by the WebRTC transport layer to pull generated audio."""
        audio_bytes = await self.audio_out_queue.get()
        self.state = VoiceRuntimeState.STREAMING_AUDIO
        return audio_bytes
        
    def mark_audio_complete(self):
        """Called by WebRTC transport when a clip's playback finishes."""
        self.state = VoiceRuntimeState.LISTENING
        self.latest_audio = None
        self.audio_out_queue.task_done()
        # Only re-open the mic if no further clip is queued; otherwise the
        # assistant is still talking and must remain gated.
        if self.audio_out_queue.empty():
            self.set_assistant_active(False)


class VoiceRuntimeManager:
    def __init__(self):
        self.active_runtimes: Dict[str, VoiceSessionRuntime] = {}

    def get_or_create_runtime(
        self, session_id: str, user_id: str, org_id: str, conversation_id: str, role: str, subscribed_org_ids: list, embedding_model: Any
    ) -> VoiceSessionRuntime:
        if session_id not in self.active_runtimes:
            runtime = VoiceSessionRuntime(session_id, user_id, org_id, conversation_id, role, subscribed_org_ids, embedding_model)
            runtime.start()
            self.active_runtimes[session_id] = runtime
        return self.active_runtimes[session_id]
        
    def get_runtime(self, session_id: str) -> Optional[VoiceSessionRuntime]:
        return self.active_runtimes.get(session_id)
        
    async def remove_runtime(self, session_id: str):
        if session_id in self.active_runtimes:
            runtime = self.active_runtimes[session_id]
            await runtime.shutdown()
            del self.active_runtimes[session_id]
            
    async def cleanup_expired(self, timeout_seconds: int = 300) -> list:
        """
        Sweep all runtimes, shut down ones idle beyond timeout,
        and return their IDs so Mongo can sync.
        """
        expired_ids = []
        now = time.time()
        for session_id, runtime in list(self.active_runtimes.items()):
            if now - runtime.last_activity > timeout_seconds:
                logger.info(f"Runtime {session_id} idle for > {timeout_seconds}s. Sweeping.")
                await self.remove_runtime(session_id)
                expired_ids.append(session_id)
        return expired_ids
        
    def log_metrics(self):
        """Print aggregated runtime statistics for stability monitoring."""
        if not self.active_runtimes:
            return
            
        total_runtimes = len(self.active_runtimes)
        active_pcs = sum(1 for r in self.active_runtimes.values() if r.pc is not None)
        
        q_audio_in = sum(r.audio_in_queue.qsize() for r in self.active_runtimes.values())
        q_transcript = sum(r.transcript_queue.qsize() for r in self.active_runtimes.values())
        q_llm = sum(r.llm_response_queue.qsize() for r in self.active_runtimes.values())
        q_audio_out = sum(r.audio_out_queue.qsize() for r in self.active_runtimes.values())
        
        # Averages across all runtimes
        total_stt = sum(r.metrics['stt_latency_ms'] for r in self.active_runtimes.values()) / total_runtimes
        total_llm = sum(r.metrics['llm_latency_ms'] for r in self.active_runtimes.values()) / total_runtimes
        total_tts = sum(r.metrics['tts_latency_ms'] for r in self.active_runtimes.values()) / total_runtimes
        
        logger.info(f"--- [Voice System Metrics] ---")
        logger.info(f"Active Sessions: {total_runtimes}")
        logger.info(f"Active WebRTC Connections: {active_pcs}")
        logger.info(f"Total Queued (AudioIn: {q_audio_in}, STT: {q_transcript}, LLM: {q_llm}, AudioOut: {q_audio_out})")
        logger.info(f"Avg Latency (STT: {total_stt:.0f}ms, LLM: {total_llm:.0f}ms, TTS: {total_tts:.0f}ms)")
        logger.info(f"------------------------------")
        
    async def shutdown_all(self):
        """Gracefully kill everything during server exit."""
        for session_id in list(self.active_runtimes.keys()):
            await self.remove_runtime(session_id)

# Global singleton
runtime_manager = VoiceRuntimeManager()
