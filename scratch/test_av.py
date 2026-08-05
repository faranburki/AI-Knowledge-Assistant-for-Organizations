import av
import io
import pyttsx3
import tempfile
import os

# Generate audio
text = "The Spice Garden Restaurant is located in Blue Area, Islamabad, Pakistan."
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
    temp_path = f.name

engine = pyttsx3.init()
engine.setProperty("rate", 170)
engine.save_to_file(text, temp_path)
engine.runAndWait()

with open(temp_path, "rb") as f:
    audio_bytes = f.read()

os.remove(temp_path)

print("Original bytes:", len(audio_bytes))

container = av.open(io.BytesIO(audio_bytes))
stream = container.streams.audio[0]
resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)

total_bytes = 0
for frame in container.decode(stream):
    for r_frame in resampler.resample(frame):
        total_bytes += len(r_frame.to_ndarray().tobytes())

for r_frame in resampler.resample(None):
    total_bytes += len(r_frame.to_ndarray().tobytes())

print("Resampled total bytes:", total_bytes)
print("Duration in ms:", total_bytes / (48000 * 2 * 2) * 1000)
