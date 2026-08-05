import asyncio
import io
import os
import sys
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "voice_probe_test")

import numpy as np
from Backend.Services.voice_service import generate_speech_bytes

async def main():
    text = " ".join([
        "The quarterly financial review shows that revenue increased by twelve percent year over year.",
        "The marketing department launched three new campaigns focused on customer retention.",
    ])
    audio = await generate_speech_bytes(text)

    with wave.open(io.BytesIO(audio), 'rb') as wf:
        n = wf.getnframes()
        rate = wf.getframerate()
        raw = wf.readframes(n)
        ch = wf.getnchannels()
    print(f"header: frames={n} rate={rate} ch={ch} duration={n/rate:.3f}s")

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    if ch > 1:
        samples = samples.reshape(-1, ch).mean(axis=1)
    win = int(rate * 0.1)
    n_windows = len(samples) // win
    envelope = [np.sqrt(np.mean(samples[i*win:(i+1)*win]**2)) for i in range(n_windows)]

    # find last window with real signal
    voiced = [i for i, r in enumerate(envelope) if r > 100.0]
    last_voiced = voiced[-1] if voiced else -1
    first_voiced = voiced[0] if voiced else 0
    print(f"envelope windows (100ms each): {len(envelope)}")
    print(f"first voiced at {first_voiced*0.1:.2f}s, last voiced at {last_voiced*0.1:.2f}s")
    print(f"actual speech span = {(last_voiced-first_voiced)*0.1:.2f}s")
    print(f"trailing silence = {(n_windows-1-last_voiced)*0.1:.2f}s")

    # dump every 10th window rms
    compressed = " ".join(f"{envelope[i]:5.0f}" for i in range(0, len(envelope), 5))
    print(f"rms@100ms every 500ms:\n{compressed}")

asyncio.run(main())