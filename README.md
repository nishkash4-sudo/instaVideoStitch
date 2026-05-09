# InstaStitch

A local web app that downloads Instagram Reels and turns them into polished audio, video, or meme-format clips — all in one click, fully on your machine.

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?style=flat-square&logo=flask)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red?style=flat-square)
![ffmpeg](https://img.shields.io/badge/ffmpeg-required-green?style=flat-square)
![Pillow](https://img.shields.io/badge/Pillow-10.x-yellow?style=flat-square)

---

## Features

### ⬇ Single Download
- Download one Reel as **high-quality MP3** or **QuickTime-compatible MP4** (H.264)
- Automatically extract the **post caption** after download
- Optional **AI transcription** powered by OpenAI Whisper (`OPENAI_API_KEY` required)

### ✦ Multi Stitch
- Paste up to **30 Reel URLs** at once (newline / comma / space separated)
- Merge them into one **MP3** (192kbps, 44.1kHz stereo) or one **MP4** (1080×1920, 30fps, H.264)
- All clips are normalized to a consistent format before stitching

### 🎬 Meme Edit
- Paste a single Reel URL + your caption text
- Generates the classic **Instagram meme format**: white header with bold text above the video
- Supports **emojis** via Twemoji rendering (pilmoji)
- Choose from three fonts: **Impact**, **Helvetica**, or **Georgia**
- Add an optional **@watermark** in the bottom-right corner
- Extracts the **original post caption** alongside your meme output

### All Modes
- 📡 **Live log** — real-time streaming progress via Server-Sent Events (SSE)
- 🧹 **Auto cleanup** — all intermediate files deleted after the final output is ready
- 💻 **Runs fully locally** — no uploads, no cloud, no cost

---

## How It Works

### ⬇ Single Download

```
Instagram Reel URL
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  yt-dlp (download + --write-info-json)              │
│                                                     │
│  Audio: -x --audio-format mp3 --audio-quality 0    │
│  Video: -f bestvideo+bestaudio --merge-output-format mp4│
│                                                     │
│  --write-info-json writes metadata yt-dlp already  │
│  fetched (zero extra API calls) → single_output.   │
│  {mp3|mp4}.info.json / single_raw.info.json        │
│  Caption (description field) read from that file.  │
└─────────────────────────────────────────────────────┘
        │
        ▼  (video only)
┌───────────────────┐
│  ffmpeg           │  -c:v libx264 -crf 18  →  H.264 re-encode
│  (H.264 convert)  │  ensures QuickTime / iOS compatibility
└───────────────────┘
        │
        ▼  (optional)
┌───────────────────┐
│  OpenAI Whisper   │  POST audio to transcriptions endpoint
│  (transcription)  │  model: whisper-1, language: hi (Hinglish-aware)
└───────────────────┘
        │
        ▼
  single_output.mp3 / single_output.mp4
  + caption text
  + transcript.txt  (if requested)
```

---

### ✦ Multi Stitch

```
Up to 30 Instagram Reel URLs
        │
        ▼
┌───────────────────┐
│  yt-dlp           │  Audio: -x --audio-format mp3
│  (bulk download)  │  Video: -f bestvideo+bestaudio/best
└───────────────────┘
        │
        ▼
┌───────────────────────────────────────────┐
│  ffmpeg (normalize — per clip)            │
│                                           │
│  Audio │ codec: libmp3lame                │
│        │ bitrate: 192kbps                 │
│        │ sample rate: 44,100Hz stereo     │
│                                           │
│  Video │ resolution: 1080×1920            │
│        │ frame rate: 30fps                │
│        │ video codec: libx264, CRF 23     │
│        │ audio codec: AAC 128kbps         │
└───────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐
│  ffmpeg           │  concat demuxer → single stream
│  (merge/concat)   │  no re-encode quality loss
└───────────────────┘
        │
        ▼
  output.mp3 / output.mp4
```

---

### 🎬 Meme Edit

```
Instagram Reel URL + Meme Caption Text
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  yt-dlp (download + --write-info-json)              │
│                                                     │
│  -f bestvideo+bestaudio --merge-output-format mp4  │
│                                                     │
│  --write-info-json writes metadata yt-dlp already  │
│  fetched (zero extra API calls) → meme_raw.info.json│
│  Original post caption read from that file and     │
│  streamed to UI via SSE CAPTION: event.            │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐
│  ffmpeg           │  -c:v libx264 -crf 18  →  H.264 intermediate
│  (H.264 convert)  │  (meme_raw.mp4)
└───────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  Python (layout math)                                           │
│                                                                 │
│  wrap_text()  →  split caption into lines ≤ 22 chars           │
│  header_h     =  top_pad(60) + lines×line_h(100) + gap(28)     │
│  video_h      =  1920 − header_h                               │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  Pillow + pilmoji (header image generation)                     │
│                                                                 │
│  • Create white RGB canvas: 1080 × header_h px                 │
│  • Select font: Impact / Helvetica / Georgia (user choice)      │
│  • pilmoji renders each text line + emoji as Twemoji bitmaps    │
│  • Text is bottom-anchored → visually flush against video       │
│  • Save as header.png                                           │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  ffmpeg (filter_complex stacking)                               │
│                                                                 │
│  -loop 1 -i header.png                                         │
│  -i meme_raw.mp4                                               │
│                                                                 │
│  filter:                                                        │
│    [1:v] scale=1080:{video_h}, pad to fit, white bars [vid]    │
│    [0:v][vid] vstack [out]                                      │
│                                                                 │
│  watermark (optional):                                          │
│    drawtext @handle bottom-right, white + black shadow          │
│                                                                 │
│  output: libx264 CRF 20, AAC 192kbps, -movflags +faststart     │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
  meme_output.mp4  (1080×1920, H.264, QuickTime-compatible)
  + original post caption shown in UI
```

---

## Tool Responsibility Summary

| Tool | Role |
|------|------|
| **yt-dlp** | Download Reel video/audio; extract post metadata (caption, title) |
| **ffmpeg** | H.264 encoding, audio normalization, clip concat, video stacking (vstack) |
| **Pillow** | Generate the white header image with text layout for meme format |
| **pilmoji** | Render emoji characters as Twemoji bitmaps inside Pillow canvas |
| **OpenAI Whisper** | Transcribe audio to text (Hinglish-aware, optional) |
| **Flask** | HTTP server; SSE streaming for live progress logs |
| **Python** | Layout math (text wrapping, header height calculation), file orchestration |

---

## Output Files

| File | Created by | Mode |
|------|------------|------|
| `single_output.mp3` | yt-dlp | Single Download (audio) |
| `single_output.mp4` | yt-dlp + ffmpeg | Single Download (video) |
| `output.mp3` | ffmpeg concat | Multi Stitch (audio) |
| `output.mp4` | ffmpeg concat | Multi Stitch (video) |
| `meme_output.mp4` | Pillow + ffmpeg | Meme Edit |
| `transcript.txt` | OpenAI Whisper | Single Download (if transcription enabled) |

All files are saved to the project root and overwritten on each run.

---

## Requirements

- macOS (or any system with Python 3.9+)
- [Homebrew](https://brew.sh) (Mac)
- `ffmpeg`
- `yt-dlp`
- `flask`
- `Pillow`
- `pilmoji`
- `OPENAI_API_KEY` in a `.env` file (only needed for transcription)

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
git clone https://github.com/nishkash4-sudo/InstaStitch.git
cd InstaStitch

# 5. Create a virtual environment and install dependencies
python3 -m venv venv
venv/bin/pip install flask Pillow pilmoji

# 6. (Optional) Add OpenAI API key for transcription
echo 'OPENAI_API_KEY=sk-...' > .env
```

---

## Usage

```bash
cd ~/Desktop/InstaStitch
venv/bin/python app.py
```

Then open **http://localhost:8080** in your browser.

---

## Mode Walkthroughs

### ⬇ Single Download
1. Click the **Single Download** tab
2. Choose **Audio (MP3)** or **Video (MP4)**
3. Optionally check **Transcribe** (requires OpenAI API key)
4. Paste your Reel URL → click **Download**
5. Watch the live log, then grab your file + caption

### ✦ Multi Stitch
1. Click the **Multi Stitch** tab
2. Choose **Audio** or **Video** output
3. Paste links individually or use **Bulk Paste** (up to 30 URLs)
4. Click **Stitch Audio / Stitch Video**
5. Watch the live log, then download the merged file

### 🎬 Meme Edit
1. Click the **Meme Edit** tab
2. Paste a Reel URL
3. Type your meme caption (live preview shows line count + header height)
4. Choose a font: **Impact**, **Helvetica**, or **Georgia**
5. Optionally add a `@watermark` handle
6. Click **Create Meme Reel**
7. Download the result — white header + bold text + original video below

---

## Project Structure

```
InstaStitch/
├── app.py              # Flask server + all download/process pipelines
├── templates/
│   └── index.html      # Single-page UI (3-tab: Single / Stitch / Meme)
├── .env                # OPENAI_API_KEY (not committed)
├── venv/               # Python virtual environment (not committed)
└── .claude/
    └── launch.json     # Dev server config
```

---

## Notes

- This tool is intended for **personal local use only**
- Instagram may update their platform — if downloads fail, update yt-dlp: `brew upgrade yt-dlp`
- Output files are overwritten on each new run — download before running again
- The meme header height auto-adjusts based on how many lines your caption wraps to
- Emoji rendering requires an internet connection on first use (pilmoji fetches Twemoji assets)
