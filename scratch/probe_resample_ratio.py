"""Probe: count actual resampled output samples for a real pyttsx3 clip."""
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

from Backend.Services.voice_service import generate_speech_bytes


async def main():
    text = "The price of Chicken Kadhai is PKR 1,450."
    audio = await generate_speech_bytes(text)
    with wave.open(io.BytesIO(audio), 'rb') as wf:
        print(f"wav: rate={wf.getframerate()} ch={wf.getnchannels()} frames={wf.getnframes()} "
              f"dur={wf.getnframes() / wf.getframerate():.3f}s")

    container = av.open(io.BytesIO(audio))
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
    total_in = 0
    total_out = 0
    rates = set()
    for frame in container.decode(stream):
        total_in += frame.samples
        rates.add(frame.sample_rate)
        for rf in resampler.resample(frame):
            total_out += rf.samples
    for rf in resampler.resample(None):
        total_out += rf.samples

    expect = total_in * 48000 / max(rates)
    print(f"decoded in: {total_in} @ {rates}")
    print(f"resampled out: {total_out}  (expect {expect:.0f})  ratio={total_out / expect:.4f}")
    print(f"frames at 48k: {total_out / 960:.2f} -> wall time @20ms = {total_out / 960 * 0.02:.2f}s")


asyncio.run(main())
