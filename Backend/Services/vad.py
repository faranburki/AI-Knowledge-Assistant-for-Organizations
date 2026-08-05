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
        Converts the raw av.AudioFrame packets into an in-memory 16-bit PCM WAV byte stream.
        """
        import io
        import wave
        import av

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2) # 16-bit PCM
            wf.setframerate(self.sample_rate)
            
            layout = 'stereo' if self.channels == 2 else 'mono'
            resampler = av.AudioResampler(format='s16', layout=layout, rate=self.sample_rate)
            
            for frame in self.frames:
                resampled = resampler.resample(frame)
                for rf in resampled:
                    wf.writeframes(rf.to_ndarray().tobytes())
                    
        return buf.getvalue()

class VoiceActivityDetector:
    """
    Lightweight Voice Activity Detector that processes continuous av.AudioFrame packets,
    tracks energy, and emits completed Utterance objects upon detecting silence.
    """
    def __init__(self, energy_threshold: float = 300.0, silence_duration_seconds: float = 1.0, max_duration_ms: float = 15000.0):
        self.energy_threshold = energy_threshold
        self.silence_duration_seconds = silence_duration_seconds
        self.max_duration_ms = max_duration_ms
        
        self.state = VADState.WAITING
        self.frames_buffer = []
        self.silence_duration_ms = 0.0
        self.utterance_duration_ms = 0.0

    def process_frame(self, frame: Any) -> Optional[Utterance]:
        """
        Processes a single audio frame.
        Returns a complete Utterance if the end of speech is detected, else None.
        """
        # Convert to numpy array and compute RMS energy
        arr = frame.to_ndarray()
        energy = np.sqrt(np.mean(arr.astype(np.float32)**2))
        
        # Calculate frame duration
        frame_duration_ms = (frame.samples / frame.sample_rate) * 1000.0
        
        if self.state == VADState.WAITING:
            if energy >= self.energy_threshold:
                # Speech started
                self.state = VADState.COLLECTING
                self.frames_buffer.append(frame)
                self.utterance_duration_ms += frame_duration_ms
                self.silence_duration_ms = 0.0
                logger.info(f"Speech detected (energy: {energy:.2f}). Collecting audio...")
                
        elif self.state == VADState.COLLECTING:
            self.frames_buffer.append(frame)
            self.utterance_duration_ms += frame_duration_ms
            
            if self.utterance_duration_ms >= self.max_duration_ms:
                logger.info(f"VAD: Max duration {self.max_duration_ms}ms reached. Emitting utterance.")
                
                # Determine channels safely
                channels = len(frame.layout.channels) if hasattr(frame, 'layout') and hasattr(frame.layout, 'channels') else 1
                
                utterance = Utterance(
                    frames=list(self.frames_buffer),
                    duration_ms=self.utterance_duration_ms,
                    sample_rate=frame.sample_rate,
                    channels=channels,
                    frame_count=len(self.frames_buffer)
                )
                self.state = VADState.WAITING
                self.frames_buffer.clear()
                self.silence_duration_ms = 0.0
                self.utterance_duration_ms = 0.0
                return utterance
            
            # Check for silence
            if energy < self.energy_threshold:
                self.silence_duration_ms += frame_duration_ms
            else:
                self.silence_duration_ms = 0.0
                
            # If silence threshold exceeded, finalize utterance
            if self.silence_duration_ms >= (self.silence_duration_seconds * 1000.0):
                logger.info("Speech ended.")
                
                # Determine channels safely
                channels = len(frame.layout.channels) if hasattr(frame, 'layout') and hasattr(frame.layout, 'channels') else 1
                
                utterance = Utterance(
                    frames=list(self.frames_buffer),
                    duration_ms=self.utterance_duration_ms,
                    sample_rate=frame.sample_rate,
                    channels=channels,
                    frame_count=len(self.frames_buffer)
                )
                
                # Reset state
                self.frames_buffer.clear()
                self.utterance_duration_ms = 0.0
                self.silence_duration_ms = 0.0
                self.state = VADState.WAITING
                
                return utterance
                
        return None
