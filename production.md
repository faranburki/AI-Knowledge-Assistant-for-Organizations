# Production Transition Plan (Voice Integration)

While Phase 1 utilizes `pyttsx3` to guarantee zero-latency execution on an i5 CPU, true "production-level" audio requires shifting to neural text-to-speech models. The architecture implemented in Phase 1 (Abstract Factory `BaseVoiceProvider`) is explicitly designed to support this swap with zero changes to the routing or text generation logic.

## Recommended Production Voice Models (CPU-Optimized)
When you are ready to upgrade the voice quality, select one of the following:

### 1. Piper TTS (Highly Recommended)
Piper is specifically optimized for running real-time, human-quality neural TTS on weak CPUs (including Raspberry Pi). 
- **Implementation:** Create a `PiperVoiceProvider` that inherits from `BaseVoiceProvider`.
- **Requirements:** Download `.onnx` voice models (~20-50MB).
- **Pros:** Extremely fast on i5, human-like, multi-lingual, offline.

### 2. Kokoro TTS (State-of-the-art)
Kokoro is an 82M parameter ONNX model that currently leads the open-source community for ultra-realistic voice cloning on CPU.
- **Implementation:** Create a `KokoroVoiceProvider`.
- **Requirements:** `onnxruntime` and model weights.
- **Pros:** Best quality available offline.

## Scaling Architecture
- **Caching:** Audio files generated for specific RAG answers should be cached (using an MD5 hash of the text) to prevent regenerating the same audio twice if a user replays it.
- **Streaming:** Instead of waiting for the full audio file to generate, the `VoiceProvider` should yield bytes so the frontend can begin playing the audio while the rest of the sentence is still rendering.

Keep this document as a reference for Phase 2 of the Voice Integration.
