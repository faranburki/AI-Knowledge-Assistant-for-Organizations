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
from Backend.models.voice_session import VoiceRuntimeState


class FakeModel:
    def encode(self, texts):
        return np.random.rand(len(texts), 384).tolist()


async def main():
    rt = VoiceSessionRuntime("probe", "u1", "o1", "c1", "org_member", [], FakeModel())
    rt.start()
    text = " ".join([
        "The quarterly financial review shows that revenue increased by twelve percent year over year.",
        "The marketing department launched three new campaigns focused on customer retention.",
    ])
    audio = await generate_speech_bytes(text)

    with wave.open(io.BytesIO(audio), 'rb') as wf:
        truth = wf.getnframes() / wf.getframerate()

    await rt.audio_out_queue.put(audio)

    # Re-implement the TTSAudioTrack recv() with instrumentation
    FRAME_SIZE = 960
    BYTES_PER_FRAME = 3840
    buf = bytearray()
    container = None
    stream = None
    iterator = None
    resampler = None
    pts = 0
    events = []

    decoded_frames = 0
    stop_iters = 0
    real_returns = 0
    padded_returns = 0
    silence_returns = 0
    exception_details = None

    def log(msg):
        events.append(f"pts={pts} {msg}")

    t0 = time.time()
    while time.time() - t0 < 40:
        while len(buf) < BYTES_PER_FRAME:
            if iterator is None:
                try:
                    audio_bytes = rt.audio_out_queue.get_nowait()
                    log(f"NEW CLIP len={len(audio_bytes)}")
                    container = av.open(io.BytesIO(audio_bytes))
                    stream = container.streams.audio[0]
                    iterator = container.decode(stream)
                    resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
                except asyncio.QueueEmpty:
                    if len(buf) > 0:
                        log(f"PAD partial buffer {len(buf)}")
                        pad = BYTES_PER_FRAME - len(buf)
                        buf.extend(b'\x00' * pad)
                        padded_returns += 1
                        break
                    silence_returns += 1
                    log("SILENCE")
                    # emulate silence return
                    pts += FRAME_SIZE
                    break
            try:
                frame = next(iterator)
                decoded_frames += 1
                n_out = 0
                for rf in resampler.resample(frame):
                    n_out += 1
                    buf.extend(rf.to_ndarray().tobytes())
                if n_out == 0:
                    pass
            except Exception as e:
                stop_iters += 1
                exception_details = f"{type(e).__name__}: {e}"
                log(f"ITERATOR END ({exception_details})")
                for rf in resampler.resample(None):
                    buf.extend(rf.to_ndarray().tobytes())
                iterator = None
                container = None
                break
        if len(buf) >= BYTES_PER_FRAME:
            real_returns += 1
            del buf[:BYTES_PER_FRAME]
            pts += FRAME_SIZE
        if stop_iters > 0 and len(buf) == 0:
            # after clip fully drained + silence frames
            n = 0
            while n < 3:
                n += 1
                if iterator is None:
                    try:
                        rt.audio_out_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                pts += FRAME_SIZE
            break
        if pts / 48000 > 30:
            break

    print(f"truth={truth:.2f}s pts_end={pts/48000:.2f}s")
    print(f"decoded_frames={decoded_frames} stop_iters={stop_iters} real_returns={real_returns} "
          f"padded_returns={padded_returns} silence_returns={silence_returns}")
    if exception_details:
        print(f"iterator end exception: {exception_details}")
    for e in events:
        print(" ", e)
    await rt.shutdown()


asyncio.run(main())