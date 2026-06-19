#!/usr/bin/env python3
"""
Check if all required dependencies are installed for video-summary skill.
Run this script to verify your setup before using the skill.
"""

import sys
import subprocess
import shutil

def check_python_version():
    """Check if Python version is 3.8 or higher."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
        return False

def check_module(module_name, import_name=None):
    """Check if a Python module is installed."""
    import_name = import_name or module_name
    print(f"Checking {module_name}...")
    try:
        __import__(import_name)
        print(f"✓ {module_name}")
        return True
    except ImportError:
        print(f"✗ {module_name} not found")
        return False

def check_executable(exec_name):
    """Check if an executable is in PATH."""
    print(f"Checking {exec_name}...")
    if shutil.which(exec_name):
        print(f"✓ {exec_name}")
        return True
    else:
        print(f"✗ {exec_name} not found in PATH")
        return False

def main():
    print("=" * 60)
    print("Video Summary Skill - Setup Check")
    print("=" * 60)
    print()

    all_ok = True

    # Check Python version
    if not check_python_version():
        all_ok = False
    print()

    # Check Python modules
    modules = [
        ("faster-whisper", "faster_whisper"),
        ("aiohttp", None),
        ("requests", None),
        ("numpy", None),
    ]

    for module in modules:
        if not check_module(*module):
            all_ok = False
    print()

    # Check executables
    executables = [
        "ffmpeg",
        "python3",
    ]

    for exe in executables:
        if not check_executable(exe):
            all_ok = False
    print()

    # Check ffmpeg version
    if check_executable("ffmpeg"):
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version_line = result.stdout.split('\n')[0]
            print(f"  Version: {version_line}")
        except Exception as e:
            print(f"  Could not get version: {e}")
    print()

    # Summary
    print("=" * 60)
    if all_ok:
        print("✓ All checks passed! Setup is complete.")
        print()
        print("You can now use the video-summary skill.")
        return 0
    else:
        print("✗ Some checks failed. Please install missing dependencies.")
        print()
        print("Quick install:")
        print("  pip install -r requirements.txt")
        print("  brew install ffmpeg  # macOS")
        print("  sudo apt-get install ffmpeg  # Ubuntu/Debian")
        return 1

if __name__ == "__main__":
    sys.exit(main())
