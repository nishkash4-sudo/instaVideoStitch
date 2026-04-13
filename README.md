# InstaStitch

A local web app that downloads Instagram Reels and merges them into a single **MP3** or **MP4** file — all in one click.

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?style=flat-square&logo=flask)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red?style=flat-square)
![ffmpeg](https://img.shields.io/badge/ffmpeg-required-green?style=flat-square)

---

## Features

- 🎵 **Audio mode** — extracts and merges audio tracks into one MP3 (192kbps, 44.1kHz stereo)
- 🎬 **Video mode** — normalizes and stitches full Reels into one MP4 (1080×1920, 30fps, H.264/AAC)
- 📋 **Bulk paste** — dump up to 30 links at once, separated by newlines, spaces, or commas
- ➕ **Manual entry** — 5 default URL fields with an Add link button (up to 30)
- 📡 **Live log** — real-time streaming progress via SSE so you can see every step
- 🧹 **Auto cleanup** — all intermediate files deleted after the final output is created
- 💻 **Runs fully locally** — no uploads, no cloud, no costs

---

## Requirements

- macOS (or any system with Python 3.9+)
- [Homebrew](https://brew.sh) (Mac)
- `ffmpeg`
- `yt-dlp`
- `flask`

---

## Installation

```bash
# 1. Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Add Homebrew to PATH (Apple Silicon Macs)
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc

# 3. Install ffmpeg and yt-dlp
brew install ffmpeg yt-dlp

# 4. Clone the repo
git clone https://github.com/nishkash4-sudo/instaVideoStitch.git
cd instaVideoStitch

# 5. Create a virtual environment and install Flask
python3 -m venv venv
venv/bin/pip install flask
```

---

## Usage

```bash
cd ~/Desktop/instaVideoStitch
venv/bin/python app.py
```

Then open **http://localhost:8080** in your browser.

1. Choose **Audio (MP3)** or **Video (MP4)** output
2. Paste links individually — or use **Bulk Paste** to import up to 30 at once
3. Click **✦ Stitch Audio / Stitch Video**
4. Watch the live log, then download your file when it's ready

---

## How It Works

```
Instagram Reel URLs
       ↓
  yt-dlp download
  (audio-only for MP3 / full video for MP4)
       ↓
  ffmpeg normalize
  (consistent codec, bitrate, resolution)
       ↓
  ffmpeg concat
  (single output file)
       ↓
  Cleanup intermediates
       ↓
  output.mp3 / output.mp4
```

### Audio normalization
| Setting | Value |
|---------|-------|
| Codec | MP3 (`libmp3lame`) |
| Bitrate | 192 kbps |
| Sample rate | 44,100 Hz |
| Channels | Stereo |

### Video normalization
| Setting | Value |
|---------|-------|
| Resolution | 1080 × 1920 (portrait) |
| Frame rate | 30 fps |
| Video codec | H.264 (`libx264`, CRF 23) |
| Audio codec | AAC 128kbps |

---

## Project Structure

```
instaVideoStitch/
├── app.py              # Flask server + download/normalize/merge pipeline
├── templates/
│   └── index.html      # Single-page UI
├── venv/               # Python virtual environment (not committed)
└── .claude/
    └── launch.json     # Dev server config
```

---

## Notes

- This tool is intended for **personal local use only**
- Instagram may update their platform — if downloads fail, update yt-dlp: `brew upgrade yt-dlp`
- Output files are saved to the project root and overwritten on each new run
