# Video Content Analyzer

**name:** video-summary
**description:** Extract and analyze video content by capturing frames OR downloading + transcribing audio with faster-whisper, then producing structured summaries. Use when the user provides a video URL and wants a summary, transcript, or analysis. Trigger on "summarize this video", "analyze this video", "转述视频内容", or any video link with a request to understand it.

**compatibility:** Requires Playwright browser (MCP) AND `faster-whisper` (CTranslate2) + `ffmpeg` installed locally. Must have network access to the video URL.

> **Version**: 1.0  
> **Author**: Victor  
> **公众号**: 安卓一得  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流

---

## Installation & Setup

### System Requirements

- **Python:** 3.8 or higher
- **RAM:** Minimum 8GB (15GB+ recommended for long videos)
- **Disk:** 10GB+ free space
- **OS:** Linux, macOS, or Windows (with WSL)

### Quick Install

```bash
# 1. Navigate to skill directory
cd ~/.claude/skills/video-summary-skill

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install system dependencies (if not already installed)
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (WSL)
sudo apt-get install ffmpeg

# 4. Install Playwright (for frame capture method)
playwright install chromium
```

### Verify Installation

```bash
# Check if faster-whisper is installed
python3 -c "from faster_whisper import WhisperModel; print('✓ faster-whisper OK')"

# Check if ffmpeg is installed
ffmpeg -version

# Run setup check script
python3 scripts/check_setup.py
```

---

## Strategy Selection

Choose one of two approaches based on video characteristics:

| Criteria | Audio Transcription | Frame Capture |
|----------|---------------------|---------------|
| Primary content | Spoken dialogue (interviews, talks, podcasts) | Visual content (whiteboards, slides, demos) |
| Duration | Any length (uses chunking) | Under ~30 min (frame count grows linearly) |
| Language | Any (auto-detected) | Any |
| Speed | ~4x real-time per chunk on CPU | 2-5 min total |

**Default:** For long-form interviews/talks (1hr+), always use audio transcription. For visual-first content, use frame capture.

---

## Pipeline A: Audio Transcription (for interviews, talks, podcasts)

### Overview
Download video → extract audio → transcribe (auto-split + merge) → TOC analysis → structured summary.

### Output Directory Naming

**CRITICAL: Identify the guest name BEFORE creating the output directory.**

Steps:
1. Download the audio/video first
2. **Identify the guest/speaker** from metadata, page title, or a quick 30-second transcription preview
3. Create the output directory using `{guest}_{platform}` format

Examples:
- `hexiaopeng_weibo/` — 何小鹏访谈（微博平台）
- `yusen_weibo/` — 雨森访谈（微博平台）
- `fusheng_apple/` — 傅盛访谈（Apple Podcasts）

**Never use vague names like `weibo_new/` or `output/`.** If the guest name is genuinely unidentifiable (e.g., anonymous panel), use a descriptive keyword like `ai_panel_weibo/`, but this should be rare.

### Prerequisites

```bash
pip install faster-whisper aiohttp
```

### Step A1: Download Video

**For Douyin URLs:** Video URLs expire quickly. Use Playwright to intercept the actual `.mp4` URL from network requests:

1. Navigate to the Douyin URL with `browser_navigate`
2. Take a snapshot, click play if needed
3. Use `browser_network_requests` to find the actual video CDN URL (look for `video/tos/` in the path)
4. Download with Python script:

```bash
python3 scripts/download_video.py <fresh_cdn_url> video.mp4
```

**If the URL expires:** Re-navigate in browser, get fresh URL from `browser_network_requests`, restart download.

**For Weibo URLs:** `yt-dlp` natively supports Weibo. It extracts MP3 for audio-only content or MP4 for video:
```bash
python3 scripts/download_video.py <weibo_url> output.mp3 --prefer-audio
```

**For YouTube/Bilibili/other platforms:** Use `yt-dlp` or platform-specific methods.

### Step A2: Extract Audio

```bash
ffmpeg -y -i video.mp4 -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
# For audio-only input (MP3, M4A, etc.):
ffmpeg -y -i audio.mp3 -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

16kHz mono WAV, ~104MB per hour. If `download_video.py` extracts an MP3 directly (e.g. Weibo podcasts), use the second command.

### Step A3: Transcribe (recommended: one-command pipeline)

The `transcribe_pipeline.py` script handles everything: auto-splits audio, transcribes chunks, merges results.

```bash
# Default mode — auto-detects resources, runs optimal parallel workers (2 for 15GB RAM)
python3 scripts/transcribe_pipeline.py audio.wav /output

# Manual worker count
python3 scripts/transcribe_pipeline.py audio.wav /output --fast 4
```

**Resource-based worker selection:**

| Available RAM | GPU VRAM | Workers | Backend |
|---------------|----------|---------|---------|
| Any | ≥ 8GB | 4 | GPU |
| Any | 4-8GB | 2 | GPU |
| ≥ 24GB | — | 4 (max ncpu//2) | CPU |
| 10-24GB | — | 2 | CPU |
| < 10GB | — | 1 | CPU |

### Step A3 (alternative): Manual step-by-step

If you need finer control, use individual scripts:

```bash
# Transcribe a single audio file
python3 scripts/transcribe_audio.py audio.wav

# Merge chunk transcripts
python3 scripts/merge_transcripts.py _chunks /output 14400 4
```

### Dynamic chunk sizing

The pipeline automatically splits audio so each chunk is **≤45 minutes**. This is critical because whisper large-v3 silently exits when processing chunks >60 minutes. A 4:21 hour audio produces ~6 chunks (each ~43 min), not 4 chunks of 65 min.

### Auto-retry stuck workers

The pipeline detects workers that run >45 minutes with no transcript output (likely stuck/hung). It kills and restarts them, up to 2 retries per chunk. This happens automatically — no user intervention needed.

### Step A4: Analyze and Summarize (see "Summary Methodology" section below)

---

## Pipeline B: Frame Capture (for visual content, whiteboards, slides)

### Overview
Open video in browser → batch-capture frames → read with vision → synthesize summary.

### Step B1: Open and Analyze the Video Page

1. Navigate to the video URL with `browser_navigate`
2. Take a snapshot to understand the page layout
3. Identify the `<video>` element and any subtitle/caption overlays
4. Check for chapter markers, AI summaries, or transcript UI elements
5. Start playing: `browser_evaluate` with `document.querySelector('video').play()`

### Step B2: Check for Built-in Subtitles

```javascript
const video = document.querySelector('video');
const tracks = video.textTracks;
// If tracks.length > 0, extract cues
```

### Step B3: Batch-Capture Frames

```javascript
async (page) => {
  const duration = Math.floor(await page.evaluate(() =>
    document.querySelector('video').duration));
  const times = [];
  for (let t = 3; t < duration; t += 10) times.push(Math.round(t));
  const results = [];
  for (const t of times) {
    await page.evaluate(time => document.querySelector('video').currentTime = time, t);
    await page.waitForTimeout(200);
    const b64 = await page.evaluate(() => {
      const v = document.querySelector('video');
      const c = document.createElement('canvas');
      c.width = v.videoWidth; c.height = v.videoHeight;
      c.getContext('2d').drawImage(v, 0, 0);
      return c.toDataURL('image/jpeg', 0.4);
    });
    results.push({ i: results.length, t, b64 });
  }
  return results;
}
```

### Step B4: Save Frames and Read with Vision

1. Save frames to disk (decode base64 → JPEG)
2. Read with vision to extract text
3. First pass: structure mapping; Second pass: detail extraction

### Step B5: Synthesize Summary

See "Summary Methodology" section below.

---

## Summary Methodology (applies to both pipelines)

**Core principle: TOC first, then write. Never write a summary without first establishing the full structural outline of the content.**

### Step 0: Determine Total Duration (MANDATORY — do this FIRST)

**CRITICAL: Before building the TOC, you MUST know the exact total duration.** Skipping this step is the #1 cause of incomplete summaries.

How to determine total duration:
- **For audio transcription:** Read the LAST 10 lines of `transcript.txt` to find the final timestamp (e.g., `[03:38:18]`). This tells you the exact total duration.
- **For frame capture:** Get `video.duration` from the `<video>` element.

Example:
```bash
tail -10 output_dir/transcript.txt
# → [03:38:16] 也欢迎你在小宇宙的评论区
# → [03:38:18] 与我们有更多的互动
# Total = 218 minutes (3h38min)
```

**If the transcript is very long (>5000 lines):** Read the first 20 lines AND the last 20 lines first. Then read the middle sections in chunks. **Never start the TOC until you know both the start and end timestamps.**

### Time Format Convention (MANDATORY)

All timestamps in TOC and summary headers must use **total minutes:seconds** format (`M:SS`), where minutes have **no leading zero** and can be any number of digits.

| Correct | Incorrect |
|---------|-----------|
| `0:00-17:00` | `00:00-17:00` (leading zero on minutes) |
| `68:00-94:00` | `01:08-01:34` (HH:MM format) |
| `129:00-168:00` | `02:09-02:48` (HH:MM format) |
| `205:00-218:00` | `03:25-03:38` (HH:MM format) |
| `221:20` | `03:41:20` (HH:MM:SS format) |

Why: `HH:MM` is visually ambiguous and becomes inconsistent for content over 1 hour (some entries show minutes, some show hours:minutes). Leading zeros on minutes (like `00:00`) make it harder to distinguish from `HH:MM` format at a glance.

Conversion from transcript timestamps:
- If transcript uses `[M:SS]` format (already total minutes): **use as-is** — e.g., `[68:00]` → `68:00`
- If transcript uses `[HH:MM:SS]` format: convert `H*60+M:SS` — e.g., `[03:25:30]` → `205:30`
- If transcript uses `[HH:MM]` format: convert `H*60+M:00` — e.g., `[01:08]` → `68:00`

### Step 1: Build Table of Contents (TOC)

Read the timestamped transcript (`transcript.txt`), identify **topic transition points**:
- Host questions typically mark new topics
- Guest's long-form answers mark topic elaboration
- Mark each topic's time range and core theme

Output format (using M:SS time format, no leading zero on minutes):
```
| # | 时间段 | 主题 | 类型 |
|---|--------|------|------|
| 1 | 0:00-17:00 | AI 在公司的推广 | 管理 |
| 2 | 17:00-38:00 | 具身智能定义与战略 | 技术 |
```

### Step 2: Verify TOC Coverage

- **The LAST TOC entry's end time MUST match the total duration found in Step 0.** If not, you missed content — go back and fill the gap.
- TOC must cover the **entire time span** from start to end — no gaps
- Each topic gets at least a one-sentence description
- **"Type" field distinguishes:** 技术/产品, 管理/组织, 哲学/个人, 市场/商业

### Step 3: Extract Content Per TOC Entry

For each TOC entry, read the corresponding section of `transcript.txt` to extract: core arguments, specific data, key examples, important conclusions.

**If transcript is long:** Read in chunks aligned with TOC entries. For a 7000-line transcript, read 1000-1500 lines at a time, covering 2-4 TOC entries per read.

### Step 4: Cross-Check

- Does every TOC entry have a corresponding section in the summary?
- Does the summary contain any "unattributed" content?
- Is soft content (philosophy, management, personal stories) given equal weight as hard content?
- **Does the summary's last section's time range match the total duration from Step 0?**

### Summary Format

1. **Title/Topic** — What is this about?
2. **Speaker/Source** — Who is presenting?
3. **Core Thesis** — Main argument
4. **Key Points** — Break down by TOC sections
5. **Details** — For each point: argument, examples, evidence
6. **Conclusion/Takeaways**
7. **Notable Quotes**

---

## Platform-Specific Notes

### Douyin (抖音)
- Video plays in `<video>` element; AI chapter summaries in sidebar
- Subtitles as `<div>` overlays; URLs expire quickly
- Login panel may block — dismiss with JS
- **Downloading:** Playwright needs X display (headless mode). If unavailable, parse playAddr from page HTML directly using Python urllib.

### Weibo (微博)
- **yt-dlp extracts metadata, urllib downloads:** `yt-dlp --simulate --dump-json` extracts the CDN URL from Weibo's visitor system. The actual download uses Python urllib (yt-dlp direct download fails — returns HTML redirect pages instead of the file).
- **Audio-only format:** Weibo podcast content is delivered as MP3. After download, convert to WAV: `ffmpeg -y -i audio.mp3 -acodec pcm_s16le -ar 16000 -ac 1 audio.wav`.
- **CDN URLs expire:** Weibo CDN URLs have short expiry (`Expires` parameter). The script retries up to 3 times, re-fetching the CDN URL each attempt.
- **No Playwright needed:** yt-dlp handles the visitor authentication internally for metadata extraction.

### Apple Podcasts
- **yt-dlp natively supports** Apple Podcasts. `yt-dlp -x` directly downloads m4a audio.
- No special authentication needed. Audio files are publicly available.
- After download, convert to WAV: `ffmpeg -y -i audio.m4a -acodec pcm_s16le -ar 16000 -ac 1 audio.wav`.
- Typically podcast episodes are 30min-2hr. Split into ~25min chunks for transcription.

### YouTube
- Try built-in subtitle tracks first (`video.textTracks`)

### Bilibili
- Subtitles may be in page data as JSON

---

## Troubleshooting

**"Douyin video URL expired"**
- Re-navigate, get fresh URL from `browser_network_requests`

**"Transcription process OOM / killed"**
- Use serial mode (no `--fast` flag) or reduce `--fast N`
- Each `large-v3 int8` process uses ~3-4GB RAM

**"Worker stuck — no output after 45 minutes"**
- Pipeline auto-kills and restarts stuck workers (max 2 retries)
- Manual fix: `kill <PID>` then re-run the chunk

**"Chunk transcript files empty"**
- Check `_chunks/transcribe_*.log` for errors
- Set `FFMPEG` env var if ffmpeg is not in PATH

**"Frame capture is empty/black"**
- Check `video.readyState` — must be 4
