"""Transcribe audio with faster-whisper (CTranslate2 optimized).

Auto-detects dominant language by sampling at multiple points in the audio,
then transcribes with the detected language locked.
"""
import sys
import os
import subprocess
import tempfile
from faster_whisper import WhisperModel

# Accept audio path as argument, or use default
AUDIO_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK_DIR, "audio.wav")
WORK_DIR = os.path.dirname(os.path.abspath(AUDIO_PATH))
# Derive output prefix from audio filename (e.g. "chunk_00" from "chunk_00.wav")
CHUNK_PREFIX = os.path.splitext(os.path.basename(AUDIO_PATH))[0]
TRANSCRIPT_PATH = os.path.join(WORK_DIR, f"{CHUNK_PREFIX}_transcript.txt")
FULL_PATH = os.path.join(WORK_DIR, f"{CHUNK_PREFIX}_full.txt")
FFMPEG = "/home/xuchao/.local/bin/ffmpeg"

# Auto-detect GPU availability with robust testing
def detect_device():
    """Detect if GPU is available and return device config.

    Tests actual GPU functionality, not just hardware presence.
    Falls back to CPU if GPU test fails.
    """
    MIN_VRAM_GB = 6.0  # Minimum VRAM for large-v3 model (with safety margin)

    # Try PyTorch CUDA detection
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3

            # Check VRAM requirement
            if gpu_mem < MIN_VRAM_GB:
                print(f"✗ GPU detected but insufficient VRAM: {gpu_mem:.1f}GB < {MIN_VRAM_GB}GB required")
                print("→ Falling back to CPU")
                return "cpu", "int8"

            # Test actual GPU functionality with a small tensor operation
            try:
                test_tensor = torch.randn(100, 100, device='cuda')
                _ = test_tensor @ test_tensor.T  # Matrix multiplication test
                del test_tensor
                torch.cuda.empty_cache()

                print(f"✓ GPU detected and tested: {gpu_name} ({gpu_mem:.1f}GB)")
                return "cuda", "float16"
            except Exception as e:
                print(f"✗ GPU test failed: {e}")
                print("→ Falling back to CPU")
                return "cpu", "int8"
    except ImportError:
        print("→ PyTorch not installed, skipping CUDA detection")
    except Exception as e:
        print(f"✗ CUDA detection error: {e}")

    # nvidia-smi fallback (only checks hardware, not functionality)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            gpu_name = parts[0].strip()
            gpu_mem_str = parts[1].strip().replace(" MiB", "")
            gpu_mem = int(gpu_mem_str) / 1024  # Convert MiB to GB

            if gpu_mem < MIN_VRAM_GB:
                print(f"✗ GPU detected but insufficient VRAM: {gpu_mem:.1f}GB < {MIN_VRAM_GB}GB required")
                print("→ Falling back to CPU")
                return "cpu", "int8"

            print(f"✓ GPU detected (nvidia-smi): {gpu_name} ({gpu_mem:.1f}GB)")
            print("  Note: PyTorch CUDA not available, using CTranslate2 CUDA backend")
            return "cuda", "float16"
    except Exception as e:
        pass

    print("→ Using CPU (no suitable GPU available)")
    return "cpu", "int8"

device, compute_type = detect_device()
print(f"Loading large model with CTranslate2 (device={device}, compute_type={compute_type})...")

# Test model loading with error handling
try:
    model = WhisperModel("large-v3", device=device, compute_type=compute_type)
except Exception as e:
    print(f"✗ Model loading failed on {device}: {e}")
    if device == "cuda":
        print("→ Retrying on CPU...")
        device, compute_type = "cpu", "int8"
        model = WhisperModel("large-v3", device=device, compute_type=compute_type)
    else:
        raise

# Step 1: Detect language by sampling at multiple points
print("Step 1: Detecting dominant language (sampling 3 points)...")
# Use PID-specific temp dir to avoid conflicts when running in parallel
clip_dir = tempfile.mkdtemp(prefix=f"whisper_clips_{os.getpid()}_")

# Get audio duration
result = subprocess.run([FFMPEG, "-i", AUDIO_PATH], capture_output=True, text=True)
duration_str = result.stderr.split("Duration:")[1].split(",")[0].strip()
parts = duration_str.split(":")
total_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
print(f"  Audio duration: {total_seconds}s ({total_seconds//60}m{total_seconds%60}s)")

# Extract 30s clips at beginning (20s in), middle, and end
clip_points = [
    max(10, total_seconds // 3),
    total_seconds // 2,
    max(0, total_seconds * 2 // 3),
]
lang_votes = {}
for i, t in enumerate(clip_points):
    clip_path = os.path.join(clip_dir, f"clip_{i}.wav")
    subprocess.run([
        FFMPEG, "-y", "-ss", str(t), "-i", AUDIO_PATH,
        "-t", "30", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        clip_path
    ], capture_output=True, check=True)
    _, info = model.transcribe(clip_path, language=None, beam_size=1, vad_filter=False)
    lang = info.language
    lang_votes[lang] = lang_votes.get(lang, 0) + 1
    print(f"  Clip at {t}s: detected {lang} (prob: {info.language_probability:.1%})")
    os.remove(clip_path)

os.rmdir(clip_dir)

# Pick dominant language
detected_lang = max(lang_votes, key=lang_votes.get)
lang_name = {
    "en": "English", "zh": "Chinese", "ja": "Japanese",
    "ko": "Korean", "fr": "French", "de": "German", "es": "Spanish",
}.get(detected_lang, detected_lang)
print(f"  -> Dominant language: {lang_name}")

# Step 2: Transcribe with detected language locked
print(f"Step 2: Transcribing with language={detected_lang}...")
segments, info = model.transcribe(
    AUDIO_PATH,
    language=detected_lang,
    beam_size=5,
    vad_filter=True,
    vad_parameters=dict(min_silence_duration_ms=500),
)

segments_list = []
t_file = open(TRANSCRIPT_PATH, "w", encoding="utf-8")
f_file = open(FULL_PATH, "w", encoding="utf-8")
try:
    for seg in segments:
        print(f"  [{seg.start:.1f}s-{seg.end:.1f}s] {seg.text.strip()}", flush=True)
        segments_list.append(seg)
        m, s = divmod(int(seg.start), 60)
        t_file.write(f"[{m:02d}:{s:02d}] {seg.text.strip()}\n")
        t_file.flush()
        f_file.write(seg.text.strip() + " ")
        f_file.flush()
        if len(segments_list) % 100 == 0:
            print(f"  ... {len(segments_list)} segments so far", flush=True)
finally:
    t_file.close()
    f_file.close()

print(f"\nDone. {len(segments_list)} segments written.")
full_text = " ".join(seg.text.strip() for seg in segments_list)
print(f"Full text: {len(full_text)} chars → {FULL_PATH}")
