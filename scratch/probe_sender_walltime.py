"""Probe: wall-time rate of the real-paced TTSAudioTrack."""
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

    # read only the clip: stop once mark_audio_complete fired at least once
    complete_at = None
    t0 = time.time()
    n = 0
    while time.time() - t0 < dur * 2:
        f = await track.recv()
        n += 1
        if rt.audio_out_queue.qsize() == 0 and complete_at is None and n > 200:
            # qsize 0 after clip pulled means the clip was consumed entirely
            complete_at = time.time() - t0
            break
    # count frames until buffer drained actually: simpler, just run dur+0.2s
    # and frame-rate averages
    wall = time.time() - t0
    print(f"frames read: {n} in {wall:.2f}s -> {n / wall:.1f} fps (target 50)")
    await rt.shutdown()


asyncio.run(main())