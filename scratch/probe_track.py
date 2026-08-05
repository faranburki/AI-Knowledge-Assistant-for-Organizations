import asyncio
import io
import os
import sys
import wave
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "voice_probe_test")

import av
import numpy as np
from Backend.Services.voice_service import generate_speech_bytes
from Backend.Services.voice_runtime import VoiceSessionRuntime
from Backend.Services.webrtc_manager import TTSAudioTrack
from Backend.models.voice_session import VoiceRuntimeState


class FakeModel:
    def encode(self, texts):
        return np.random.rand(len(texts), 384).tolist()


def make_runtime():
    rt = VoiceSessionRuntime("probe", "u1", "o1", "c1", "org_member", [], FakeModel())
    rt.start()
    return rt


def frame_rms(f):
    arr = f.to_ndarray().tobytes()
    samples = np.frombuffer(arr, dtype=np.int16).astype(np.float64)
    return float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0


async def test_single_clip():
    print("=== TEST 1: single long clip completeness ===")
    rt = make_runtime()
    text = " ".join([
        "The quarterly financial review shows that revenue increased by twelve percent year over year.",
        "The marketing department launched three new campaigns focused on customer retention.",
    ])
    audio = await generate_speech_bytes(text)
    await rt.audio_out_queue.put(audio)

    track = TTSAudioTrack(rt)
    total_samples = 0
    real_samples = 0
    completes = []
    t0 = time.time()
    while time.time() - t0 < 60:
        f = await track.recv()
        total_samples += f.samples
        rms = frame_rms(f)
        if rms > 1.0:
            real_samples += f.samples
        if rt.state == VoiceRuntimeState.LISTENING and real_samples > 0:
            completes.append((total_samples, real_samples, rt.state.value))
            break
        if total_samples / 48000 > 55:
            break

    with wave.open(io.BytesIO(audio), 'rb') as wf:
        truth_frames = wf.getnframes() / wf.getframerate()
    truth_48k = int(truth_frames * 48000)
    print(f"truth_48k_samples={truth_48k}")
    print(f"total_samples={total_samples} real_samples={real_samples}")
    print(f"state_at_complete={completes[-1] if completes else 'never'}")
    missing = truth_48k - real_samples
    print(f"missing={missing} samples = {missing/48000*1000:.1f} ms" if missing else "COMPLETE - no missing audio")
    await rt.shutdown()


async def test_two_clips_back_to_back():
    print("=== TEST 2: two clips queued back-to-back (continuity) ===")
    rt = make_runtime()
    a1 = await generate_speech_bytes("First response, short.")
    a2 = await generate_speech_bytes("Second response, also short.")
    await rt.audio_out_queue.put(a1)
    await rt.audio_out_queue.put(a2)

    track = TTSAudioTrack(rt)
    t0 = time.time()
    last_real_pts = None
    gap_detected = False
    clip_ends = 0
    last_state = None
    delivered = 0
    while time.time() - t0 < 30:
        f = await track.recv()
        pts = f.pts
        rms = frame_rms(f)
        if rms > 1.0:
            delivered += f.samples
            if last_real_pts is not None and pts - last_real_pts > 960 + 2:
                gap_detected = True
                print(f"GAP: pts jumped {last_real_pts} -> {pts}")
            last_real_pts = pts
        if rt.state != last_state:
            print(f"state -> {rt.state.value} at pts={pts}")
            last_state = rt.state
        if rt.state == VoiceRuntimeState.LISTENING:
            clip_ends += 1
        if clip_ends >= 3:
            break
    print(f"delivered_real_samples={delivered} gap_detected={gap_detected} clip_ends={clip_ends}")
    with wave.open(io.BytesIO(a1), 'rb') as wf:
        t1 = wf.getnframes() / wf.getframerate()
    with wave.open(io.BytesIO(a2), 'rb') as wf:
        t2 = wf.getnframes() / wf.getframerate()
    truth = int((t1 + t2) * 48000)
    print(f"truth={truth} diff={truth - delivered}")
    await rt.shutdown()


async def main():
    await test_single_clip()
    print()
    await test_two_clips_back_to_back()


if __name__ == "__main__":
    asyncio.run(main())
