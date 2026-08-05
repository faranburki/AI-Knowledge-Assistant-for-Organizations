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


async def trace_playback():
    rt = VoiceSessionRuntime("probe", "u1", "o1", "c1", "org_member", [], FakeModel())
    rt.start()
    text = " ".join([
        "The quarterly financial review shows that revenue increased by twelve percent year over year.",
        "The marketing department launched three new campaigns focused on customer retention.",
    ])
    audio = await generate_speech_bytes(text)
    await rt.audio_out_queue.put(audio)

    with wave.open(io.BytesIO(audio), 'rb') as wf:
        truth = wf.getnframes() / wf.getframerate()
    print(f"truth duration = {truth:.3f}s  data_size={len(audio)}")

    track = TTSAudioTrack(rt)

    # monkeypatch mark_audio_complete to record timing
    done_marker = {}
    orig = rt.mark_audio_complete
    def wrapped():
        done_marker["pts"] = track._pts
        done_marker["state_was"] = rt.state.value
        done_marker["buffer_left"] = len(track._audio_buffer)
        orig()
    rt.mark_audio_complete = wrapped

    t0 = time.time()
    last_real_pts = None
    max_pts = 0
    frames = 0
    silence_streak = 0
    real_frames = 0
    events = []
    while time.time() - t0 < 60:
        f = await track.recv()
        frames += 1
        pts = f.pts
        max_pts = pts
        rms = frame_rms(f)
        if rms > 1.0:
            last_real_pts = pts
            real_frames += 1
            silence_streak = 0
        else:
            silence_streak += 1
            if silence_streak == 5 and last_real_pts is not None:
                break
        if "pts" in done_marker and frames > 10:
            pass
    end_t = time.time()

    print(f"total recv frames={frames} real_frames={real_frames}")
    print(f"last real audio pts={last_real_pts} ({last_real_pts/48000:.3f}s)")
    print(f"mark_audio_complete fired at pts={done_marker.get('pts')} "
          f"({done_marker.get('pts',0)/48000:.3f}s), buffer_left={done_marker.get('buffer_left')}")
    print(f"diff (last real audio - mark): {(last_real_pts - done_marker.get('pts',0))/48000*1000:.1f} ms")
    print(f"missing vs truth: {last_real_pts - int(truth*48000)} samples "
          f"= {(int(truth*48000) - last_real_pts)/48000*1000:.1f} ms")
    await rt.shutdown()


asyncio.run(trace_playback())