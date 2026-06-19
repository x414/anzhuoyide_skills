#!/bin/bash
# Installation script for video-summary skill
# Run this script to set up all dependencies

set -e  # Exit on error

echo "=================================="
echo "Video Summary Skill Installation"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MINOR" -lt 8 ]; then
    echo "✗ Python 3.8+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt
echo "✓ Python dependencies installed"
echo ""

# Check ffmpeg
echo "Checking ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "✗ ffmpeg not found"
    echo ""
    echo "Please install ffmpeg:"
    echo "  macOS: brew install ffmpeg"
    echo "  Ubuntu/Debian: sudo apt-get install ffmpeg"
    echo "  Windows: Download from https://ffmpeg.org/download.html"
    exit 1
fi
echo "✓ ffmpeg found"
echo ""

# Run setup check
echo "Running setup verification..."
python3 scripts/check_setup.py
echo ""

echo "=================================="
echo "Installation complete!"
echo "=================================="
echo ""
echo "You can now use the video-summary skill."
echo "Try: 'Summarize this video: <URL>'"
