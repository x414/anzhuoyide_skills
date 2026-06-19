#!/usr/bin/env python3
"""Full transcription pipeline: split audio, parallel whisper, merge.

Auto-detects system resources and chooses concurrency level.

Modes:
  default: Auto-detects resources and runs optimal concurrent workers (2 for 15GB RAM).
  --fast:  Same as default but can manually override worker count.

Usage:
  python3 transcribe_pipeline.py audio.wav [output_dir]
  python3 transcribe_pipeline.py audio.wav /output --fast  (auto-detect workers)
  python3 transcribe_pipeline.py audio.wav /output --fast 4  (force 4 workers)
"""
import sys, os, subprocess, time, re

AUDIO = sys.argv[1] if len(sys.argv) > 1 else "audio.wav"
OUTPUT_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(AUDIO))
FAST_MODE = "--fast" in sys.argv

SCRIPTS_DIR = os.path.expanduser("~/.claude/skills/video-summary-skill/scripts")
TRANSCRIBE = os.path.join(SCRIPTS_DIR, "transcribe_audio.py")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

# --- Resource detection ---

def detect_resources():
    """Detect CPU cores, available RAM, and GPU info."""
    ncpu = os.cpu_count() or 4
    ram_gb = 8
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    ram_gb = int(line.split()[1]) / 1024 / 1024
                    break
    except:
        pass
    gpu_name = None
    gpu_mem = 0
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            gpu_name = parts[0].strip()
            gpu_mem = int(parts[1].strip().replace(" MiB", ""))
    except:
        pass
    return ncpu, ram_gb, gpu_name, gpu_mem

def recommend_workers(ncpu, ram_gb, gpu_name, gpu_mem):
    """Recommend concurrent workers based on resources."""
    if gpu_name and gpu_mem >= 8000:
        return 4, "gpu"
    elif gpu_name and gpu_mem >= 4000:
        return 2, "gpu"
    elif ram_gb >= 24:
        return min(4, ncpu // 2), "cpu"
    elif ram_gb >= 10:
        return 2, "cpu"
    elif ram_gb >= 6:
        return 1, "cpu"
    else:
        return 1, "cpu"

# --- Chunking ---

MAX_CHUNK_DURATION = 45 * 60  # 45 minutes max per chunk for whisper stability

def calculate_chunks(total_seconds):
    """Calculate number of chunks so each is <= MAX_CHUNK_DURATION."""
    num = max(1, total_seconds // MAX_CHUNK_DURATION + (1 if total_seconds % MAX_CHUNK_DURATION > 0 else 0))
    chunk_dur = total_seconds // num
    return num, chunk_dur

# --- Helpers ---

def get_chunk_duration(chunk_path):
    """Get actual duration of a wav file."""
    result = subprocess.run([FFMPEG, "-i", chunk_path], capture_output=True, text=True)
    dur = result.stderr.split("Duration:")[1].split(",")[0].strip()
    parts = dur.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))

def get_last_timestamp(t_file):
    """Get the last timestamp in seconds from a transcript file."""
    if not os.path.exists(t_file) or os.path.getsize(t_file) == 0:
        return 0
    lines = open(t_file).readlines()
    if not lines:
        return 0
    m = re.match(r'\[(\d+):(\d+)\]', lines[-1])
    if not m:
        return 0
    return int(m.group(1)) * 60 + int(m.group(2))

COVERAGE_THRESHOLD = 0.8  # Transcript must cover at least 80% of chunk duration
RETRY_TIMEOUT = 45 * 60  # Kill worker if no output after 45 minutes
MAX_RETRIES = 2  # Max restart attempts per chunk
PROGRESS_INTERVAL = 30  # Seconds between progress reports

# --- Main ---

ncpu, ram_gb, gpu_name, gpu_mem = detect_resources()

print(f"Resources: {ncpu} cores, {ram_gb:.0f}GB RAM", end="")
if gpu_name:
    print(f", GPU: {gpu_name} ({gpu_mem}MB)")
else:
    print(", No GPU detected")

if FAST_MODE:
    workers, mode = recommend_workers(ncpu, ram_gb, gpu_name, gpu_mem)
    for arg in sys.argv:
        if arg.isdigit():
            workers = min(int(arg), ncpu)
else:
    workers, mode = recommend_workers(ncpu, ram_gb, gpu_name, gpu_mem)

print(f"Mode: {'FAST' if FAST_MODE else 'default'} - {workers} concurrent worker(s), {mode} inference")

result = subprocess.run([FFMPEG, "-i", AUDIO], capture_output=True, text=True)
dur = result.stderr.split("Duration:")[1].split(",")[0].strip()
parts = dur.split(":")
total = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
print(f"Audio: {total}s ({total//60}m{total%60}s)")

# Dynamic chunk calculation
num_chunks, chunk_dur = calculate_chunks(total)
print(f"Chunks: {num_chunks} ({chunk_dur}s / {chunk_dur//60}m each, max {MAX_CHUNK_DURATION//60}m)")

CHUNKS = os.path.join(OUTPUT_DIR, "_chunks")
os.makedirs(CHUNKS, exist_ok=True)

for i in range(num_chunks):
    start = i * chunk_dur
    subprocess.run([
        FFMPEG, "-y", "-ss", str(start), "-i", AUDIO, "-t", str(chunk_dur),
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        f"{CHUNKS}/chunk_{i:02d}.wav"
    ], capture_output=True, check=True)
    print(f"  Split chunk_{i:02d}: {start}s-{start + chunk_dur}s")

print(f"\nTranscribing {num_chunks} chunks with {workers} worker(s)...")

def transcribe(chunk_path, log_path):
    with open(log_path, "w") as f:
        return subprocess.Popen(
            ["python3", TRANSCRIBE, chunk_path],
            stdout=f, stderr=f
        )

pending = list(range(num_chunks))
running = []
retries = {}
start_times = {}
last_report = {}  # chunk_index -> last reported line count

while pending or running:
    # Phase 1: Launch new workers
    while pending and len(running) < workers:
        i = pending.pop(0)
        chunk = f"{CHUNKS}/chunk_{i:02d}.wav"
        log = f"{CHUNKS}/transcribe_{i:02d}.log"
        p = transcribe(chunk, log)
        running.append((i, p))
        start_times[i] = time.time()
        last_report[i] = 0
        print(f"  Started chunk_{i:02d} (PID {p.pid})")

    # Phase 2: Check completed/failed workers
    any_finished = False
    for idx in range(len(running) - 1, -1, -1):
        i, p = running[idx]
        if p.poll() is not None:
            t_file = f"{CHUNKS}/chunk_{i:02d}_transcript.txt"
            lines = sum(1 for _ in open(t_file)) if os.path.exists(t_file) else 0
            chunk_dur_actual = get_chunk_duration(f"{CHUNKS}/chunk_{i:02d}.wav")
            last_ts = get_last_timestamp(t_file)
            coverage = last_ts / chunk_dur_actual if chunk_dur_actual > 0 else 0
            if coverage < COVERAGE_THRESHOLD and retries.get(i, 0) < MAX_RETRIES:
                retries[i] = retries.get(i, 0) + 1
                print(f"  chunk_{i:02d}: INCOMPLETE ({coverage:.0%} coverage, {last_ts}s/{chunk_dur_actual}s), retry {retries[i]}/{MAX_RETRIES}")
                pending.insert(0, i)
            else:
                if coverage < COVERAGE_THRESHOLD:
                    print(f"  chunk_{i:02d}: INCOMPLETE ({coverage:.0%}), max retries reached")
                print(f"  chunk_{i:02d}: DONE ({lines} lines, exit {p.returncode})")
            running.pop(idx)
            del start_times[i]
            del last_report[i]
            any_finished = True

    if any_finished:
        continue

    # Phase 3: Check stuck workers (no output after timeout)
    any_killed = False
    for idx in range(len(running) - 1, -1, -1):
        i, p = running[idx]
        t_file = f"{CHUNKS}/chunk_{i:02d}_transcript.txt"
        has_output = os.path.exists(t_file) and os.path.getsize(t_file) > 0
        runtime = time.time() - start_times.get(i, time.time())
        if runtime > RETRY_TIMEOUT and not has_output:
            if retries.get(i, 0) < MAX_RETRIES:
                retries[i] = retries.get(i, 0) + 1
                print(f"  chunk_{i:02d}: STUCK after {runtime/60:.0f}m, killing (retry {retries[i]}/{MAX_RETRIES})")
                p.kill()
                p.wait()
                pending.insert(0, i)
            else:
                print(f"  chunk_{i:02d}: STUCK after {runtime/60:.0f}m, max retries reached")
            running.pop(idx)
            del start_times[i]
            del last_report[i]
            any_killed = True

    if any_killed:
        continue

    # Phase 4: Progress report (only when lines changed)
    if running:
        time.sleep(PROGRESS_INTERVAL)
        for i, p in running:
            t_file = f"{CHUNKS}/chunk_{i:02d}_transcript.txt"
            if os.path.exists(t_file) and os.path.getsize(t_file) > 0:
                lines = sum(1 for _ in open(t_file))
                if lines != last_report.get(i, 0):
                    last_line = open(t_file).readlines()[-1].strip()[:60]
                    print(f"    chunk_{i:02d}: {lines} lines, last: {last_line}")
                    last_report[i] = lines

# Merge
print(f"\nMerging transcripts...")
merge_script = os.path.join(SCRIPTS_DIR, "merge_transcripts.py")
subprocess.run([
    "python3", merge_script, CHUNKS, OUTPUT_DIR, str(total), str(num_chunks)
])

print(f"\nDone! Transcript: {OUTPUT_DIR}/transcript.txt")
