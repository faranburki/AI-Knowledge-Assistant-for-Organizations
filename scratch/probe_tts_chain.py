import asyncio
import io
import os
import sys
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Backend.Services.voice_service import generate_speech_bytes


async def main():
    samples = [
        ("short", "Hello."),
        ("medium", "The Spice Garden Restaurant is located in Blue Area, Islamabad, Pakistan. It serves excellent food and has a wonderful atmosphere."),
        ("long", " ".join([
            "The quarterly financial review shows that revenue increased by twelve percent year over year.",
            "The marketing department launched three new campaigns focused on customer retention and brand awareness.",
            "Customer satisfaction scores improved across all regions, particularly in the European market where we saw the strongest growth.",
            "The operations team successfully reduced average order processing time from forty five minutes to thirty minutes.",
            "Looking ahead, the board approved an additional budget for research and development in the next fiscal year.",
            "Human resources will begin the annual performance review cycle next month, with training sessions scheduled for all managers.",
        ])),
    ]

    for name, text in samples:
        audio = await generate_speech_bytes(text)
        print(f"[{name}] text_len={len(text)} audio_len={len(audio)} bytes")
        print(f"[{name}] head={audio[:4]!r} data_idx={audio.find(b'data')}")
        try:
            with wave.open(io.BytesIO(audio), 'rb') as wf:
                print(f"[{name}] channels={wf.getnchannels()} rate={wf.getframerate()} frames={wf.getnframes()} "
                      f"duration={wf.getnframes()/wf.getframerate():.2f}s sampwidth={wf.getsampwidth()}")

            # Now decode via PyAV (what TTSAudioTrack does)
            import av
            container = av.open(io.BytesIO(audio))
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
            total = 0
            frames_decoded = 0
            errors = 0
            for frame in container.decode(stream):
                frames_decoded += 1
                try:
                    for rf in resampler.resample(frame):
                        total += len(rf.to_ndarray().tobytes())
                except Exception as e:
                    errors += 1
                    print(f"[{name}] resample error: {e}")
            for rf in resampler.resample(None):
                total += len(rf.to_ndarray().tobytes())
            print(f"[{name}] PyAV: frames={frames_decoded} out_bytes={total} "
                  f"out_duration={total/(48000*2*2):.2f}s errors={errors}")
        except Exception as e:
            print(f"[{name}] ERROR: {e!r}")


if __name__ == "__main__":
    asyncio.run(main())
