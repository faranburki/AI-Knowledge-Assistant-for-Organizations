import logging
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Any
import numpy as np

logger = logging.getLogger(__name__)

class VADState(Enum):
    WAITING = "waiting"
    COLLECTING = "collecting"

@dataclass
class Utterance:
    frames: List[Any]
    duration_ms: float
    sample_rate: int
    channels: int
    frame_count: int
    
    def to_wav_bytes(self) -> bytes:
        """
        Converts the raw av.AudioFrame packets into an in-memory 16-bit PCM
        WAV byte stream. Audio is downmixed to MONO at 16 kHz, which is the
        standard input profile for speech-to-text engines.
        """
        import io
        import wave
        import av

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2) # 16-bit PCM
            wf.setframerate(16000)

            resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)

            for frame in self.frames:
                resampled = resampler.resample(frame)
                for rf in resampled:
                    wf.writeframes(rf.to_ndarray().tobytes())

        return buf.getvalue()


class VoiceActivityDetector:
    """
    Adaptive-energy Voice Activity Detector.

    Design notes (production hardening):
      * The energy threshold adapts to a slowly tracked noise floor, so quiet
        speech is still detected while a noisy room does not flood the system
        with false utterances.
      * Audio is ONLY buffered after speech onset. Previously the entire
        session's silence accumulated into the WAV handed to STT, which made
        transcriptions slow and inconsistent.
      * A minimum voiced-frame count discards short noise pops.
      * Frame gating is handled by the owning runtime (half-duplex while the
        assistant is speaking); this class simply stays stateless between
        utterances so multiple sessions cannot interfere with each other.
    """
    def __init__(
        self,
        energy_threshold: float = 400.0,
        silence_duration_seconds: float = 1.0,
        max_duration_ms: float = 15000.0,
        min_voiced_frames: int = 3,
        noise_floor_alpha: float = 0.02,
    ):
        self.abs_threshold = float(energy_threshold)
        self.silence_duration_seconds = float(silence_duration_seconds)
        self.max_duration_ms = float(max_duration_ms)
        self.min_voiced_frames = max(1, int(min_voiced_frames))
        self.noise_floor_alpha = float(noise_floor_alpha)
        self.max_noise_floor = 800.0

        self.state = VADState.WAITING
        self.frames_buffer: List[Any] = []
        self.silence_duration_ms = 0.0
        self.utterance_duration_ms = 0.0
        self.voiced_frames = 0
        self.noise_floor: Optional[float] = None

    def reset(self) -> None:
        """Discard any partially collected utterance (e.g. before playback)."""
        self.state = VADState.WAITING
        self.frames_buffer.clear()
        self.silence_duration_ms = 0.0
        self.utterance_duration_ms = 0.0
        self.voiced_frames = 0

    def _frame_energy(self, frame: Any) -> float:
        arr = frame.to_ndarray()
        samples = arr.astype(np.float32).ravel()
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples ** 2)))

    def _current_threshold(self, energy: float) -> float:
        if self.noise_floor is None:
            # Seed the floor conservatively: never from a loud first frame.
            self.noise_floor = (
                float(energy) if energy < self.abs_threshold * 0.5
                else self.abs_threshold * 0.5
            )
        elif energy < self.abs_threshold * 1.5:
            # Update the floor only while the signal looks like background.
            self.noise_floor = min(
                self.max_noise_floor,
                (1.0 - self.noise_floor_alpha) * self.noise_floor
                + self.noise_floor_alpha * float(energy),
            )
        # Speech must exceed an absolute floor AND a multiple of the noise floor.
        return max(self.abs_threshold, self.noise_floor * 3.0)

    def process_frame(self, frame: Any) -> Optional[Utterance]:
        """
        Processes a single audio frame.
        Returns a complete Utterance when speech ends, otherwise None.
        """
        energy = self._frame_energy(frame)
        threshold = self._current_threshold(energy)
        frame_duration_ms = (frame.samples / frame.sample_rate) * 1000.0

        if self.state == VADState.WAITING:
            if energy >= threshold:
                # Speech started
                self.state = VADState.COLLECTING
                self.frames_buffer.append(frame)
                self.utterance_duration_ms += frame_duration_ms
                self.voiced_frames = 1
                self.silence_duration_ms = 0.0
                logger.info("Speech detected (energy: %.2f). Collecting audio...", energy)
            return None

        # VADState.COLLECTING
        self.frames_buffer.append(frame)
        self.utterance_duration_ms += frame_duration_ms

        if energy >= threshold:
            self.voiced_frames += 1
            self.silence_duration_ms = 0.0
        else:
            self.silence_duration_ms += frame_duration_ms

        emit = False
        if self.utterance_duration_ms >= self.max_duration_ms:
            logger.info("VAD: max duration %.0fms reached. Emitting utterance.", self.max_duration_ms)
            emit = True
        elif self.silence_duration_ms >= (self.silence_duration_seconds * 1000.0):
            logger.info("VAD: silence threshold reached. Speech ended.")
            emit = True

        if not emit:
            return None

        channels = len(frame.layout.channels) if hasattr(frame, 'layout') and hasattr(frame.layout, 'channels') else 1

        voiced_frames = self.voiced_frames

        utterance = Utterance(
            frames=list(self.frames_buffer),
            duration_ms=self.utterance_duration_ms,
            sample_rate=frame.sample_rate,
            channels=channels,
            frame_count=len(self.frames_buffer),
        )

        self.reset()

        # Discard noise pops that passed the energy gate but have no substance.
        if voiced_frames < self.min_voiced_frames:
            logger.info("VAD: discarded short burst (%d voiced frames).", voiced_frames)
            return None

        logger.info("VAD: utterance complete (%.0fms, %d frames).", utterance.duration_ms, utterance.frame_count)
        return utterance
