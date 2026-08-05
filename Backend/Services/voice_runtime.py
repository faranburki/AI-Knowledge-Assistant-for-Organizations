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
        self.vad = VoiceActivityDetector(energy_threshold=300.0, silence_duration_seconds=1.0)
        self.latest_utterance: Optional[Utterance] = None
        self.latest_transcript: Optional[str] = None
        self.latest_response: Optional[str] = None
        self.latest_audio: Optional[bytes] = None
        
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
        self.audio_out_queue = asyncio.Queue()
        
        self._tasks = []
        self._is_running = False

    def process_audio_frame(self, frame):
        """Called directly by the WebRTC Transport when a raw audio frame arrives."""
        utterance = self.vad.process_frame(frame)
        if utterance:
            logger.info(f"[{self.session_id}] VAD emitted complete utterance!")
            logger.info(f"  -> Duration: {utterance.duration_ms:.1f}ms")
            logger.info(f"  -> Frames collected: {utterance.frame_count}")
            
            self.latest_utterance = utterance
            self.state = VoiceRuntimeState.TRANSCRIBING
            
            async def _transcribe_task():
                try:
                    logger.info(f"[{self.session_id}] Transcribing...")
                    wav_bytes = utterance.to_wav_bytes()
                    transcript = await transcribe_audio_bytes(wav_bytes)
                    
                    if transcript:
                        logger.info(f"[{self.session_id}] Transcript: \"{transcript}\"")
                        self.latest_transcript = transcript
                        await self.transcript_queue.put(transcript)
                    else:
                        logger.info(f"[{self.session_id}] Transcript was empty or unintelligible.")
                        self.state = VoiceRuntimeState.LISTENING
                except Exception as e:
                    logger.error(f"[{self.session_id}] Transcription error: {e}")
                finally:
                    self.state = VoiceRuntimeState.LISTENING
            
            asyncio.create_task(_transcribe_task())

    def start(self):
        if self._is_running: return
        self._is_running = True
        self.state = VoiceRuntimeState.IDLE
        self._tasks.append(asyncio.create_task(self._stt_worker()))
        self._tasks.append(asyncio.create_task(self._llm_worker()))
        self._tasks.append(asyncio.create_task(self._tts_worker()))
        logger.info(f"Voice Runtime started for session {self.session_id}")

    async def touch(self):
        """Update last activity heartbeat."""
        self.last_activity = time.time()

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
            from Backend.Services.voice_session_service import update_voice_session_status
            await update_voice_session_status(self.session_id, "ENDED")
            logger.info(f"[{self.session_id}] Updated DB state to ENDED")
        except Exception as e:
            logger.warning(f"[{self.session_id}] Failed to update DB state: {e}")
        
        duration = time.time() - self.created_at
        logger.info(f"[{self.session_id}] Destroyed. Duration: {int(duration)}s, STT: {self.metrics['stt_count']}, LLM: {self.metrics['llm_count']}, TTS: {self.metrics['tts_count']}")


    async def submit_audio(self, audio_bytes: bytes):
        """External entry point for audio buffers."""
        self.touch()
        await self.audio_in_queue.put(audio_bytes)
        self.state = VoiceRuntimeState.LISTENING

    async def _stt_worker(self):
        while self._is_running:
            try:
                audio_bytes = await self.audio_in_queue.get()
                self.touch()
                self.state = VoiceRuntimeState.TRANSCRIBING
                
                t0 = time.time()
                transcript = await transcribe_audio_bytes(audio_bytes)
                latency = int((time.time() - t0) * 1000)
                
                self.metrics["llm_latency_ms"] = latency
                self.metrics["llm_count"] += 1
                self.touch()
                self.metrics["stt_count"] += 1
                self.touch()
                logger.info(f"[{self.session_id}] STT complete: '{transcript}' in {latency}ms")
                
                if transcript and transcript.strip():
                    await self.transcript_queue.put(transcript.strip())
                else:
                    self.state = VoiceRuntimeState.IDLE
                
                self.audio_in_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.session_id}] STT Worker error: {e}")
                self.state = VoiceRuntimeState.IDLE

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
                
                t0 = time.time()
                audio_bytes = await generate_speech_bytes(text)
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
                
                # Phase 11: Push to audio_out_queue, keep state as GENERATING_SPEECH.
                await self.audio_out_queue.put(audio_bytes)
                
                self.llm_response_queue.task_done()
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
        """Called by WebRTC transport when streaming finishes."""
        self.state = VoiceRuntimeState.LISTENING
        self.audio_out_queue.task_done()
        self.latest_audio = None


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
