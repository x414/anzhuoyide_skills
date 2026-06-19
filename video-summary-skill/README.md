# Video Summary Skill

A comprehensive skill for extracting and analyzing video content through audio transcription or frame capture, then producing structured summaries.

> **Version**: 1.0  
> **Author**: Victor  
> **公众号**: 安卓一得  
> **公众号简介**: 分享各种Agent实战经验，欢迎交流

## Features

- **Multi-platform support**: Douyin (抖音), Weibo (微博), YouTube, Bilibili, Apple Podcasts, and more
- **Two processing methods**:
  - **Audio Transcription**: For interviews, talks, podcasts (any length)
  - **Frame Capture**: For visual content like whiteboards, slides, demos (<30 min)
- **Intelligent chunking**: Automatically splits long videos for efficient processing
- **Time-accurate transcripts**: Preserves timestamps for easy navigation
- **Structured output**: Generates TOC (Table of Contents) and comprehensive summaries

## Quick Start

### 1. Installation

```bash
# Navigate to skill directory
cd ~/.claude/skills/video-summary-skill

# Install Python dependencies
pip install -r requirements.txt

# Install system dependencies (ffmpeg)
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Verify installation
python3 scripts/check_setup.py
```

### 2. Usage

Simply provide a video URL to Claude with a request like:
- "Summarize this video"
- "Analyze this video"
- "转述视频内容" (Chinese)
- "Extract key points from this video"

Claude will automatically:
1. Download the video/audio
2. Transcribe or capture frames
3. Build a Table of Contents (TOC)
4. Generate a comprehensive summary

## System Requirements

- **Python**: 3.8 or higher
- **RAM**: Minimum 8GB (15GB+ recommended for long videos)
- **Disk**: 10GB+ free space
- **OS**: Linux, macOS, or Windows (with WSL)

## GPU Acceleration

The skill automatically detects and uses GPU with **robust validation**:

### Detection Flow

1. **PyTorch CUDA Detection** (Primary)
   - Checks `torch.cuda.is_available()`
   - Verifies VRAM ≥ 6GB (required for large-v3 model)
   - Tests actual GPU functionality with tensor operations
   - Uses `float16` compute type for optimal performance

2. **nvidia-smi Detection** (Fallback)
   - Used if PyTorch not installed or CUDA unavailable
   - Checks hardware presence and VRAM
   - Still validates VRAM requirements

3. **CPU Fallback** (Default)
   - Automatically used if GPU detection fails
   - Uses `int8` quantization for reasonable speed
   - Works on any system without GPU

### Smart Fallback Mechanisms

- **Insufficient VRAM**: Falls back to CPU with clear message
  ```
  ✗ GPU detected but insufficient VRAM: 4.0GB < 6.0GB required
  → Falling back to CPU
  ```

- **GPU Test Failed**: Falls back to CPU if CUDA operations fail
  ```
  ✗ GPU test failed: CUDA error
  → Falling back to CPU
  ```

- **Model Loading Failed**: Automatically retries on CPU
  ```
  ✗ Model loading failed on cuda: Out of memory
  → Retrying on CPU...
  ```

### Performance

- **With GPU (8GB+ VRAM)**: 5-10x faster transcription
- **Without GPU**: Still works well, just slower

### Installation

```bash
# Optional: Install PyTorch with CUDA support for GPU acceleration
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**Note**: GPU support is optional. The skill works perfectly on CPU-only systems.

## Architecture

```
video-summary-skill/
├── SKILL.md              # Main skill documentation
├── requirements.txt      # Python dependencies
├── check_setup.py        # Setup verification script
├── README.md            # This file
└── scripts/
    ├── download_video.py        # Download videos from various platforms
    ├── transcribe_audio.py      # Transcribe single audio file
    ├── transcribe_pipeline.py   # Full pipeline (split + transcribe + merge)
    └── merge_transcripts.py     # Merge chunk transcripts with time offsets
```

## Time Format Convention

All timestamps in TOC and summary headers use **total minutes:seconds** format (`M:SS`):

| Correct | Incorrect |
|---------|-----------|
| `0:00-17:00` | `00:00-17:00` |
| `68:00-94:00` | `01:08-01:34` |
| `205:00-218:00` | `03:25-03:38` |

This ensures consistency and clarity for videos over 1 hour.

## Platform-Specific Notes

### Douyin (抖音)
- URLs expire quickly; skill automatically refreshes
- Uses Playwright to intercept actual CDN URLs

### Weibo (微博)
- Supports both video and audio-only content
- Handles authentication via yt-dlp

### Apple Podcasts
- Direct audio download support
- No authentication required

### YouTube/Bilibili
- Uses yt-dlp for downloads
- Supports subtitles and chapter markers

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'faster_whisper'"**
```bash
pip install faster-whisper
```

**"ffmpeg not found"**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg
```

**"Transcription process OOM"**
- Reduce parallel workers: use `--fast 1` or no `--fast` flag
- Each worker uses ~3-4GB RAM

**"Worker stuck — no output after 45 minutes"**
- Pipeline auto-retries up to 2 times
- Manual fix: kill the process and re-run

## Examples

### Example 1: Weibo Interview (3h38min)

**Input**: `https://video.weibo.com/show?fid=...`

**Output**:
```
yangmeng_weibo/
├── audio.wav
├── transcript.txt          # Full transcript with timestamps
├── toc.md                  # Table of contents
└── summary.md              # Comprehensive summary
```

### Example 2: Short Video (5min)

**Input**: Douyin video URL

**Output**:
```
{guest}_douyin/
├── video.mp4
├── transcript.txt
├── toc.md
└── summary.md
```

## Contributing

Contributions welcome! Areas for improvement:
- Additional platform support (TikTok, Twitter/X, etc.)
- GPU acceleration optimizations
- Alternative transcription backends (OpenAI Whisper API, etc.)
- UI/UX improvements

## License

MIT License - feel free to use, modify, and distribute.

## Credits

Developed and maintained by the Claude Code community.

Special thanks to:
- faster-whisper team for the transcription backend
- yt-dlp team for video download support
- Playwright team for browser automation
