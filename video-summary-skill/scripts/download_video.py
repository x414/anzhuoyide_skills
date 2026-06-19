#!/usr/bin/env python3
"""Download video/audio from URL with platform-specific handling.

Supports: Douyin, Weibo, YouTube, Apple Podcasts, Bilibili, and any direct URL.

Usage:
  python3 download_video.py <url> [output_path]
"""
import sys, os, subprocess, re, json, urllib.request, time

URL = sys.argv[1]
OUTPUT_PATH = sys.argv[2] if len(sys.argv) > 2 else None

def detect_platform(url):
    """Detect the platform from URL."""
    if "douyin.com" in url or "iesdouyin.com" in url:
        return "douyin"
    elif "weibo.com" in url or "weibocdn.com" in url:
        return "weibo"
    elif "podcasts.apple.com" in url:
        return "apple"
    elif "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    else:
        return "direct"

def get_ytdlp_info(url):
    """Get video info from yt-dlp --dump-json. Returns parsed dict or None."""
    cmd = ["yt-dlp", "--simulate", "--dump-json", "--no-check-certificates", url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0 and result.stdout.strip():
        return json.loads(result.stdout)
    return None

def download_apple_podcast(url, output_path):
    """Download Apple Podcasts audio using yt-dlp.

    Apple Podcasts natively provides m4a audio files that yt-dlp can extract directly.
    No special authentication or visitor system needed.
    """
    info = get_ytdlp_info(url)
    if not info:
        print("  yt-dlp --dump-json failed")
        return False

    title = info.get("title", "audio")
    ext = info.get("ext", "m4a")
    print(f"  Title: {title}")
    print(f"  Duration: {info.get('duration', 'unknown')}s")
    print(f"  Format: {ext}")

    output_path = output_path or f"audio.{ext}"

    return download_ytdlp(url, output_path)

def download_weibo(url, output_path):
    """Download Weibo video/audio using yt-dlp to extract CDN URL, then direct download.

    yt-dlp's direct download fails for Weibo (returns HTML redirect page).
    Instead, extract the CDN URL from --dump-json, then download with urllib.
    """
    info = get_ytdlp_info(url)
    if not info:
        print("  yt-dlp --dump-json failed")
        return False

    cdn_url = info.get("url")
    if not cdn_url:
        print("  No CDN URL found in yt-dlp info")
        return False

    # Determine output extension
    ext = info.get("ext", "mp4")
    if ext == "mp3":
        output_path = output_path or "audio.mp3"
    elif output_path and not output_path.endswith(ext):
        output_path = output_path.rsplit(".", 1)[0] + "." + ext
    else:
        output_path = output_path or f"video.{ext}"

    # Set proper headers for Weibo CDN
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://weibo.com/',
        'Accept': 'video/*,*/*;q=0.9',
    }

    # The CDN URL may have an Expires parameter that becomes stale.
    # If download fails, re-fetch with a fresh yt-dlp call.
    for attempt in range(3):
        if attempt > 0:
            print(f"  CDN URL expired, re-fetching (attempt {attempt})...")
            time.sleep(2)
            info = get_ytdlp_info(url)
            if not info:
                continue
            cdn_url = info.get("url", cdn_url)

        try:
            req = urllib.request.Request(cdn_url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=600)
            downloaded = 0
            with open(output_path, 'wb') as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (10 * 1024 * 1024) < 1024 * 1024:
                        print(f"  {downloaded/1024/1024:.1f} MB")

            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print(f"  Downloaded: {size_mb:.1f} MB ({ext})")

            # Verify it's not an HTML redirect page
            if size_mb < 0.1:
                with open(output_path, 'rb') as f:
                    first_bytes = f.read(100)
                if b'<html' in first_bytes or b'<!DOCTYPE' in first_bytes:
                    print("  File is an HTML redirect page, retrying...")
                    os.remove(output_path)
                    continue
            return True

        except Exception as e:
            print(f"  Download attempt failed: {e}")
            if os.path.exists(output_path):
                os.remove(output_path)
            continue

    return False

def download_ytdlp(url, output_path):
    """Download using yt-dlp directly (for YouTube, Bilibili, Apple Podcasts, etc.)."""
    cmd = ["yt-dlp", "--no-check-certificates", "-o", output_path, url]
    print(f"  Downloading with yt-dlp...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if result.returncode != 0:
        print(f"  yt-dlp stderr: {result.stderr[-500:]}")
        return False

    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"  Downloaded: {size_mb:.1f} MB")
        return True

    # yt-dlp may have created a slightly different filename
    base = os.path.basename(output_path).rsplit(".", 1)[0]
    d = os.path.dirname(output_path) or "."
    for f in os.listdir(d):
        if f.startswith(base):
            full = os.path.join(d, f)
            size_mb = os.path.getsize(full) / 1024 / 1024
            print(f"  Downloaded: {full} ({size_mb:.1f} MB)")
            return True

    return False

def download_direct(url, output_path):
    """Download directly with urllib (for direct video/audio URLs)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Accept': 'video/*,*/*;q=0.9',
    }
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=3600)
    downloaded = 0
    with open(output_path, 'wb') as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded % (10 * 1024 * 1024) < 1024 * 1024:
                print(f"  {downloaded/1024/1024:.1f} MB")
    print(f"Downloaded: {os.path.getsize(output_path) / 1024/1024:.1f} MB")

def main():
    platform = detect_platform(URL)
    print(f"Platform: {platform}")

    if OUTPUT_PATH is None:
        if platform == "weibo":
            info = get_ytdlp_info(URL)
            if info and info.get("ext"):
                OUTPUT_PATH = f"weibo_audio.{info['ext']}"
            else:
                OUTPUT_PATH = "video.mp4"
        elif platform == "apple":
            info = get_ytdlp_info(URL)
            if info and info.get("ext"):
                OUTPUT_PATH = f"audio.{info['ext']}"
            else:
                OUTPUT_PATH = "audio.m4a"
        else:
            OUTPUT_PATH = "video.mp4"

    if platform == "apple":
        download_apple_podcast(URL, OUTPUT_PATH)
    elif platform == "weibo":
        success = download_weibo(URL, OUTPUT_PATH)
        if not success:
            print("  Weibo download failed, trying yt-dlp fallback...")
            success = download_ytdlp(URL, OUTPUT_PATH)
    elif platform in ("youtube", "bilibili"):
        download_ytdlp(URL, OUTPUT_PATH)
    elif platform == "douyin":
        download_direct(URL, OUTPUT_PATH)
    else:
        download_direct(URL, OUTPUT_PATH)

if __name__ == "__main__":
    main()
