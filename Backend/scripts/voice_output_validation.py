"""
Voice output pipeline validation for the production-hardening phase.

Covers (offline, no Mongo / no Ollama / no Google STT required):
  1. Adaptive VAD behavior (utterance detection, noise bursts, max duration)
  2. Half-duplex gate (mic dropped while assistant speaks + echo tail)
  3. TTSAudioTrack playback completeness (short / long / back-to-back)
  4. Corrupt-clip resilience (stream must survive a bad WAV)
  5. Bounded audio_out_queue (drop-oldest, no deadlock, no unbounded growth)
  6. Multi-session isolation (3 concurrent sessions, all complete)

Usage:  venv\\Scripts\\python.exe Backend\\scripts\\voice_output_validation.py
"""
import asyncio
import fractions
import io
import math
import os
import sys
import time
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "voice_output_validation")

import numpy as np
import av

from Backend.Services.vad import VoiceActivityDetector
from Backend.Services.voice_runtime import VoiceSessionRuntime
from Backend.Services.webrtc_manager import TTSAudioTrack
from Backend.Services.voice_service import generate_speech_bytes

PASS = 0
FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name} {detail}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {detail}")


class FakeModel:
    def encode(self, texts):
        return np.random.rand(len(texts), 384).tolist()


# --------------------------------------------------------------------------
# Frame helpers (real av.AudioFrame objects, s16 stereo 48 kHz)
# --------------------------------------------------------------------------

def make_frame(rms_amplitude: float) -> av.AudioFrame:
    frame = av.AudioFrame(format="s16", layout="stereo", samples=960)
    frame.sample_rate = 48000
    samples = np.zeros(960 * 2, dtype=np.int16)
    if rms_amplitude > 0:
        samples[0::2] = np.int16(rms_amplitude)
    frame.planes[0].update(samples.tobytes())
    frame.pts = 0
    frame.time_base = fractions.Fraction(1, 48000)
    return frame


def make_runtime(session_id="probe"):
    return VoiceSessionRuntime(session_id, "u1", "o1", "c1", "org_member", [], FakeModel())


class FastTTSAudioTrack(TTSAudioTrack):
    """TTSAudioTrack with real-time pacing disabled for fast tests."""
    async def _pace(self):
        return


def header_48k(wav_bytes: bytes) -> int:
    """Header duration of a WAV, expressed in samples at 48 kHz."""
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        return int(wf.getnframes() / wf.getframerate() * 48000)


def voiced_span_48k(wav_bytes: bytes) -> int:
    """
    Returns the end of real (voiced) audio in the source WAV, expressed in
    samples at 48 kHz. SAPI5/pyttsx3 WAVs carry trailing digital silence, so
    the header duration is NOT the correct 'complete response' measure.
    """
    with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
        n = wf.getnframes()
        rate = wf.getframerate()
        raw = wf.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    win = max(1, int(rate * 0.01))  # 10 ms windows
    nw = len(samples) // win
    last = -1
    for i in range(nw):
        seg = samples[i * win:(i + 1) * win]
        if seg.size and np.sqrt(np.mean(seg ** 2)) > 100.0:
            last = i
    return int((last + 1) * win / rate * 48000) if last >= 0 else 0


def clip_end_matches(comp, truth_48k):
    """The completion pts equals the clip end, allowing 1 frame rounding
    down and PyAV resampler latency (up to 2 zero frames)."""
    clip_end = math.ceil(truth_48k / 960) * 960
    return comp >= clip_end - 960 and comp <= clip_end + 960 * 2


# --------------------------------------------------------------------------
# 1. Adaptive VAD
# --------------------------------------------------------------------------

async def test_vad():
    print("== 1. Adaptive VAD ==")
    vad = VoiceActivityDetector(energy_threshold=400.0, silence_duration_seconds=1.0)

    # a) long silence -> no utterance
    for _ in range(50):
        vad.process_frame(make_frame(10))
    check("silence produces no utterance", vad.state.name == "WAITING")

    # b) speech burst -> brief pause (200ms) -> more speech -> 1s silence
    for _ in range(25):
        vad.process_frame(make_frame(3000))
    for _ in range(10):
        vad.process_frame(make_frame(20))
    for _ in range(25):
        vad.process_frame(make_frame(3000))
    u = None
    for _ in range(60):
        u = vad.process_frame(make_frame(10))
        if u:
            break
    check("speech -> single complete utterance", u is not None)
    if u:
        # 25 onset + 10 pause + 25 resumption + 50 trailing silence = 110
        check("utterance covers full speech span",
              95 <= u.frame_count <= 120,
              f"(frames={u.frame_count})")
        wav = u.to_wav_bytes()
        with wave.open(io.BytesIO(wav), 'rb') as wf:
            check("utterance wav is mono 16 kHz",
                  wf.getnchannels() == 1 and wf.getframerate() == 16000
                  and wf.getsampwidth() == 2,
                  f"(ch={wf.getnchannels()} rate={wf.getframerate()})")

    # c) noise pops (1-2 voiced frames) are discarded
    vad.reset()
    for _ in range(2):
        vad.process_frame(make_frame(3000))
    for _ in range(60):
        vad.process_frame(make_frame(10))
    check("noise pop discarded", vad.state.name == "WAITING")

    # d) max-duration flush emits even without silence
    vad = VoiceActivityDetector(energy_threshold=400.0, silence_duration_seconds=1.0,
                                max_duration_ms=2000)
    u = None
    for _ in range(120):
        u = vad.process_frame(make_frame(4000))
        if u:
            break
    check("max-duration flush emits utterance", u is not None,
          f"(frames={u.frame_count if u else 0})")

    # e) adaptive threshold: rising noise floor does not flood utterances
    vad = VoiceActivityDetector(energy_threshold=400.0, silence_duration_seconds=1.0)
    for _ in range(300):
        vad.process_frame(make_frame(200))
    emitted = 0
    for _ in range(50):                      # speech clearly above floor
        emitted += 1 if vad.process_frame(make_frame(3000)) else 0
    # no utterance yet (still talking), it must appear once silence follows
    for _ in range(60):
        emitted += 1 if vad.process_frame(make_frame(10)) else 0
    check("speech still detected after noise floor rises", emitted == 1,
          f"(emitted={emitted})")
    print()


# --------------------------------------------------------------------------
# 2. Half-duplex gate
# --------------------------------------------------------------------------

async def test_gate():
    print("== 2. Half-duplex playback gate ==")
    rt = make_runtime("gate")
    submitted = []

    async def fake_submit(audio_bytes):
        submitted.append(audio_bytes)

    rt.submit_audio = fake_submit

    def feed_speech(frames=25):
        for _ in range(frames):
            rt.process_audio_frame(make_frame(3000))
        for _ in range(60):
            rt.process_audio_frame(make_frame(10))

    # a) while assistant is speaking, mic input is dropped entirely
    rt.set_assistant_active(True)
    feed_speech()
    await asyncio.sleep(0)
    check("mic dropped while assistant speaking", len(submitted) == 0)

    # b) during the echo tail after playback, mic still dropped
    rt.set_assistant_active(False)
    rt._vad_armed_at = time.time() + 10
    feed_speech()
    await asyncio.sleep(0)
    check("mic dropped during echo tail", len(submitted) == 0)

    # c) after the tail expires, speech is accepted again
    rt._vad_armed_at = None
    feed_speech()
    await asyncio.sleep(0)
    check("mic re-armed after playback", len(submitted) == 1,
          f"(submitted={len(submitted)})")
    # e) the moment the sentence is captured and handed to the pipeline,
    #    the mic is locked again (before any TTS clip exists)
    check("mic locked immediately at utterance capture",
          rt._assistant_active is True)

    # d) re-entering speech (or ambient noise) while locked: still dropped
    feed_speech()
    await asyncio.sleep(0)
    check("mic blocked while agent is still speaking", len(submitted) == 1)
    print()


# --------------------------------------------------------------------------
# 3. Playback completeness
# --------------------------------------------------------------------------

async def play_and_measure(rt, track, timeout_s=40):
    """Reads frames until sustained silence after real audio; returns stats."""
    delivered = 0
    last_real_pts = None
    ticks = 0
    state_pts = {}
    completions = []
    pending_complete = 0

    orig_complete = rt.mark_audio_complete
    def on_complete():
        nonlocal pending_complete
        orig_complete()
        pending_complete += 1

    rt.mark_audio_complete = on_complete

    t0 = time.time()
    try:
        while time.time() - t0 < timeout_s:
            f = await track.recv()
            ticks += 1
            arr = f.to_ndarray().astype(np.float32).ravel()
            rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
            if rms > 100.0:
                delivered += f.samples
                last_real_pts = f.pts
            # The silence frame immediately after mark_audio_complete() carries
            # the pts of the fully-drained clip end.
            if pending_complete:
                completions.append(f.pts)
                pending_complete = 0
            if rt.state.value not in state_pts:
                state_pts[rt.state.value] = f.pts
            if last_real_pts is not None and f.pts - last_real_pts > 48000 * 3:
                break
    finally:
        rt.mark_audio_complete = orig_complete
    return {"delivered": delivered, "last_real_pts": last_real_pts,
            "ticks": ticks, "state_pts": state_pts, "completions": completions}


async def test_completeness():
    print("== 3. Playback completeness ==")
    cases = [
        ("short", "Very short."),
        ("medium", "The quarterly financial review shows that revenue increased by "
                   "twelve percent year over year. The marketing department launched "
                   "three new campaigns focused on customer retention."),
        ("long", "Hello. " * 30),
    ]
    for name, text in cases:
        rt = make_runtime(name)
        audio = await generate_speech_bytes(text)
        truth = header_48k(audio)  # clip end incl. trailing silence
        await rt.audio_out_queue.put(audio)
        track = FastTTSAudioTrack(rt)
        stats = await play_and_measure(rt, track)
        clip_end = math.ceil(truth / 960) * 960
        comp = stats["completions"][-1] if stats["completions"] else None
        check(f"{name}: full audio delivered (complete fired at clip end)",
              comp is not None and clip_end_matches(comp, truth),
              f"(header_end={clip_end} complete@{comp} last_real@{stats['last_real_pts']})")
        check(f"{name}: audio not over-delivered",
              stats["last_real_pts"] <= clip_end,
              f"(last_real={stats['last_real_pts']} clip_end={clip_end})")
        check(f"{name}: complete reported only after delivery",
              stats["state_pts"].get("LISTENING", 10 ** 9) >= stats["last_real_pts"] - 960,
              f"(listening@{stats['state_pts'].get('LISTENING', -1)} "
              f"last_real@{stats['last_real_pts']})")
        await rt.shutdown()

    # real-paced track (no pacing override): proves _pace() itself works
    rt = make_runtime("paced")
    audio = await generate_speech_bytes("Pacing test clip.")
    truth = header_48k(audio)
    await rt.audio_out_queue.put(audio)
    stats = await play_and_measure(rt, TTSAudioTrack(rt))
    clip_end = math.ceil(truth / 960) * 960
    comp = stats["completions"][-1] if stats["completions"] else None
    check("real-paced track: complete fired at clip end",
          comp is not None and clip_end_matches(comp, truth),
          f"(header_end={clip_end} complete@{comp})")
    await rt.shutdown()
    print()

# --------------------------------------------------------------------------
# 4. Back-to-back clips
# --------------------------------------------------------------------------

async def test_back_to_back():
    print("== 4. Back-to-back clips (rapid consecutive turns) ==")
    rt = make_runtime("btb")
    a1 = await generate_speech_bytes("First response, short.")
    a2 = await generate_speech_bytes("Second response, also short.")
    await rt.audio_out_queue.put(a1)
    await rt.audio_out_queue.put(a2)
    track = FastTTSAudioTrack(rt)
    stats = await play_and_measure(rt, track)
    t1 = header_48k(a1)
    t2 = header_48k(a2)
    total = math.ceil(t1 / 960) * 960 + math.ceil(t2 / 960) * 960
    comps = stats["completions"]
    check("both clips fully delivered without overlap/gaps",
          len(comps) == 2 and abs(comps[-1] - total) <= 960 * 2,
          f"(headers={total} completions={comps})")
    await rt.shutdown()
    print()


async def test_corrupt_clip():
    print("== 5. Corrupt-clip resilience ==")
    rt = make_runtime("corrupt")
    good = await generate_speech_bytes("Recovery test clip.")
    await rt.audio_out_queue.put(b"this is not a wav file at all" * 4)
    await rt.audio_out_queue.put(b"")
    await rt.audio_out_queue.put(good)
    track = FastTTSAudioTrack(rt)
    stats = await play_and_measure(rt, track)
    truth = header_48k(good)
    comp = stats["completions"][-1] if stats["completions"] else None
    check("stream survives corrupt clips and plays the valid one",
          comp is not None and clip_end_matches(comp, truth),
          f"(header={truth} completions={stats['completions']})")
    check("queue items correctly accounted (no task_done error)",
          rt.audio_out_queue.qsize() == 0)
    await rt.shutdown()
    print()


async def test_bounded_queue():
    print("== 6. Bounded audio_out_queue (drop-oldest) ==")
    rt = make_runtime("bounded")
    rt.start()  # spawns workers; STT/LLM idle, TTS worker does the work

    texts = [f"Queue test clip number {i}." for i in range(5)]
    for t in texts:
        await rt.llm_response_queue.put(t)

    deadline = time.time() + 45
    while time.time() < deadline:
        if rt.metrics["tts_count"] >= 5:
            break
        await asyncio.sleep(0.1)
    check("TTS worker processed all 5 responses", rt.metrics["tts_count"] == 5,
          f"(tts_count={rt.metrics['tts_count']})")
    check("queue bounded at maxsize=4", rt.audio_out_queue.qsize() == 4,
          f"(qsize={rt.audio_out_queue.qsize()})")
    check("mic gated while clips are queued", rt._assistant_active is True)

    track = FastTTSAudioTrack(rt)
    stats = await play_and_measure(rt, track)
    # 5 clips were generated, 1 dropped: exactly the 4 remaining clips must
    # have completed, back-to-back, each fully (completion only fires when
    # the drained buffer hits zero).
    comps = stats["completions"]
    check("remaining 4 clips play completely (oldest dropped)",
          len(comps) == 4 and comps[0] > 0
          and all(a < b for a, b in zip(comps, comps[1:])),
          f"(completions={comps})")
    mic_rearmed: bool = rt.audio_out_queue.qsize() == 0
    check("queue fully drained after playback", rt.audio_out_queue.qsize() == 0)
    await rt.shutdown()
    print()


async def test_multi_session():
    print("== 7. Multi-session isolation (3 concurrent sessions) ==")
    texts = [
        "Session one response content.",
        "Session two response content, a bit longer for this one.",
        "Session three response content.",
    ]
    runtimes = []
    tracks = []
    truths = []
    for i, text in enumerate(texts):
        rt = make_runtime(f"ms{i}")
        audio = await generate_speech_bytes(text)
        truths.append(header_48k(audio))
        await rt.audio_out_queue.put(audio)
        runtimes.append(rt)
        tracks.append(FastTTSAudioTrack(rt))

    results = await asyncio.gather(*[play_and_measure(rt, t) for rt, t in zip(runtimes, tracks)])
    for i, (st, tr) in enumerate(zip(results, truths)):
        expected = math.ceil(tr / 960) * 960
        comp = st["completions"][-1] if st["completions"] else None
        check(f"session {i}: complete and isolated",
              comp is not None and abs(comp - expected) <= 960,
              f"(header={tr} complete@{comp})")
    for rt in runtimes:
        await rt.shutdown()
    print()


async def main():
    t0 = time.time()
    await test_vad()
    await test_gate()
    await test_completeness()
    await test_back_to_back()
    await test_corrupt_clip()
    await test_bounded_queue()
    await test_multi_session()
    print(f"==== {PASS} passed, {FAIL} failed  ({time.time() - t0:.0f}s) ====")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
