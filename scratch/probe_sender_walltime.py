"""Probe: wall-time behaviour of the real-paced TTSAudioTrack (like the
aiortc sender loop does) and of aiortc's Opus encoder path."""
import asyncio
import io
import os
import sys
import time
import wave

sys.path.insert(0, os.getcwd())
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "voice_output_validation")

import av
import numpy as np

from Backend.Services.voice_runtime import VoiceSessionRuntime
from Backend.Services.webrtc_manager import TTSAudioTrack
from Backend.Services.voice_service import generate_speech_bytes


class FakeModel:
    def encode(self, texts):
        return np.random.rand(len(texts), 384).tolist()


async def main():
    rt = VoiceSessionRuntime("probe", "u1", "o1", "c1", "org_member", [], FakeModel())
    audio = await generate_speech_bytes("The price of Chicken Kadhai is PKR 1,450.")
    with wave.open(io.BytesIO(audio), 'rb') as wf:
        dur = wf.getnframes() / wf.getframerate()
    print(f"clip duration: {dur:.2f}s")
    await rt.audio_out_queue.put(audio)
    track = TTSAudioTrack(rt)

    # --- track-only wall time ---
    t0 = time.time()
    frames = 0
    nframes = 0
    while time.time() - t0 < dur * 2:
        f = await track.recv()
        if rt.audio_out_queue.qsize() == 0 and nframes and frames > 0:
            pass
        nframes += 1
        if nframes > 500:
            break
    wall = time.time() - t0
    print(f"track-only: {nframes} frames in {wall:.2f}s (expect ~{dur:.2f}s)")

    # --- aiortc Opus encoder behaviour on the same frames ---
    from aiortc.codecs import get_encoder
    from aiortc.rtcrtpparameters import RTCRtpCodecParameters
    from aiortc.rtp import rtp_utils

    enc = get_encoder(RTCRtpCodecParameters(mimeType="audio/opus"))
    t0 = time.time()
    done = 0
    for _ in range(255):
        f = await track.recv()
        payloads, timestamp = await asyncio.get_event_loop().run_in_executor(
            None, enc.encode, f, False
        )
        done += 1 if payloads else 0
    wall2 = time.time() - t0
    print(f"sender path: 255 frames in {wall2:.2f}s, encoded payloads={done}")
    await rt.shutdown()


asyncio.run(main())
