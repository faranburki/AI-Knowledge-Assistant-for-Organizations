import asyncio
import io
import os
import sys
import wave
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "voice_probe_test")

import numpy as np
from Backend.Services.voice_service import generate_speech_bytes
from Backend.Services.voice_runtime import VoiceSessionRuntime
from Backend.Services.webrtc_manager import TTSAudioTrack
from Backend.models.voice_session import VoiceRuntimeState


class FakeModel:
    def encode(self, texts):
        return np.random.rand(len(texts), 384).tolist()


def frame_rms(f):
    arr = f.to_ndarray().tobytes()
    samples = np.frombuffer(arr, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0


async def verify_complete(rt, audio, label):
    await rt.audio_out_queue.put(audio)
    with wave.open(io.BytesIO(audio), 'rb') as wf:
        truth = int(wf.getnframes() / wf.getframerate() * 48000)

    track = TTSAudioTrack(rt)
    delivered_real = 0
    last_real_pts = None
    ticks = 0
    state_changes = []
    prev_state = None
    max_pts = 0
    t0 = time.time()
    while time.time() - t0 < 60:
        f = await track.recv()
        ticks += 1
        max_pts = max(max_pts, f.pts)
        rms = frame_rms(f)
        if rms > 1.0:
            delivered_real += f.samples
            last_real_pts = f.pts
        if rt.state != prev_state:
            state_changes.append((rt.state.value, f.pts))
            prev_state = rt.state
        if last_real_pts is not None:
            # stop once we've been in sustained silence for 3s AFTER having real audio
            if f.pts - last_real_pts > 48000 * 3:
                break
        if ticks / 50 > 55:
            break
    print(f"[{label}] truth={truth} delivered_real={delivered_real} "
          f"delta={truth-delivered_real} ({ (truth-delivered_real)/48000*1000:.1f} ms)")
    print(f"[{label}] last_real_pts={last_real_pts} ({last_real_pts/48000:.2f}s) max_pts={max_pts} ({max_pts/48000:.2f}s)")
    print(f"[{label}] state_changes={state_changes}")
    await rt.shutdown()


async def main():
    rt1 = VoiceSessionRuntime("p1", "u1", "o1", "c1", "org_member", [], FakeModel()); rt1.start()
    await verify_complete(rt1, await generate_speech_bytes(
        "The quarterly financial review shows that revenue increased by twelve percent year over year. "
        "The marketing department launched three new campaigns focused on customer retention."
    ), "medium-with-pause")

    rt2 = VoiceSessionRuntime("p2", "u1", "o1", "c1", "org_member", [], FakeModel()); rt2.start()
    await verify_complete(rt2, await generate_speech_bytes("Very short."), "short")

    rt3 = VoiceSessionRuntime("p3", "u1", "o1", "c1", "org_member", [], FakeModel()); rt3.start()
    await verify_complete(rt3, await generate_speech_bytes(
        "Hello. " * 30
    ), "long-60plus")


asyncio.run(main())