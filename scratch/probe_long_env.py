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


async def envelope(label, text):
    audio = await generate_speech_bytes(text)
    with wave.open(io.BytesIO(audio), 'rb') as wf:
        n = wf.getnframes(); rate = wf.getframerate(); raw = wf.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    win = int(rate * 0.1)
    nw = len(samples) // win
    env = [np.sqrt(np.mean(samples[i*win:(i+1)*win]**2)) for i in range(nw)]
    voiced = [i for i, r in enumerate(env) if r > 100.0]
    last = voiced[-1] if voiced else 0
    # count gaps > 0.3s of digital silence inside the spoken span
    gaps = 0
    sil_len = 0
    for i in range(1, last + 1):
        if env[i] > 100.0:
            if sil_len >= 3:
                gaps += 1
            sil_len = 0
        else:
            sil_len += 1
    print(f"[{label}] text_words={len(text.split())} header_dur={n/rate:.2f}s "
          f"speech_span={last*0.1:.2f}s tail_silence={(nw-1-last)*0.1:.2f}s internal_gaps>=0.3s={gaps}")
    print(f"    rms@500ms: {' '.join(f'{env[i]:4.0f}' for i in range(0, min(nw, len(env)), 5))}")


async def main():
    await envelope("short", "Very short.")
    await envelope("long", "Hello. " * 30)
    await envelope("verylong", " ".join([
        "The quarterly financial review shows that revenue increased by twelve percent year over year.",
        "The marketing department launched three new campaigns focused on customer retention and brand awareness.",
        "Customer satisfaction scores improved across all regions, particularly in the European market.",
        "The operations team successfully reduced average order processing time from forty five minutes to thirty minutes.",
        "Looking ahead, the board approved an additional budget for research and development.",
        "Human resources will begin the annual performance review cycle next month.",
    ]) + " " + "Hello. " * 15)


asyncio.run(main())