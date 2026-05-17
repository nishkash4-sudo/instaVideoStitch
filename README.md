# InstaStitch

> **Download Instagram Reels. Stitch them together. Turn them into memes. Generate audio-reactive waveforms. All on your machine — no uploads, no cloud, no cost.**

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?style=flat-square&logo=flask)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red?style=flat-square)
![ffmpeg](https://img.shields.io/badge/ffmpeg-required-green?style=flat-square)
![Pillow](https://img.shields.io/badge/Pillow-10.x-yellow?style=flat-square)
![librosa](https://img.shields.io/badge/librosa-0.10+-orange?style=flat-square)
![scipy](https://img.shields.io/badge/scipy-1.x-lightblue?style=flat-square)

---

## What is this?

InstaStitch is a local web app that runs entirely on your computer. You open it in your browser like a normal website — but everything happens on your machine. No accounts. No subscriptions. No data leaving your device. Ever.

You paste Instagram Reel links, pick what you want to do, and get back polished audio, video, or meme-format clips in seconds.

---

## The four things it does

### ⬇ Single Download
Paste one Reel URL → get the audio as MP3 or the video as MP4. The original post caption and the poster's username are automatically pulled and shown in the app. Optional: transcribe the audio to text using OpenAI Whisper.

### ✦ Multi Stitch
Paste 2 to 30 Reel URLs → get one single merged file. All clips are automatically normalized (same resolution, frame rate, audio quality) before joining, so the final result is seamless — no jumps, no glitches.

### 🎬 Meme Edit
Paste a Reel URL → crop out any unwanted parts (headers, black bars, borders) → type your caption → get the classic Instagram meme format: white header with your bold text on top, video below, all in one 1080×1920 portrait clip. Full creative control: font, text size, padding, watermark.

### 〜 Waveform
Upload any audio file (MP3, WAV, M4A, AAC, OGG, FLAC) → get a smooth, audio-reactive waveform video. Powered by a real frequency-spectrum analyser (64 log-spaced bands) so the visual reacts to the actual content of the music — bass on the left, treble on the right. Output: a black-background MP4 for InShot/CapCut and a transparent WebM for desktop editors.

---

## How to install

### Step 1 — Install Homebrew (Mac only, skip if you already have it)
Homebrew is a tool that makes installing software on Mac easy. Open your Terminal app and paste this:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

If you're on Apple Silicon (M1/M2/M3 chip), also run:
```bash
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

### Step 2 — Install ffmpeg and yt-dlp
These are the two core tools that handle video downloading and processing:
```bash
brew install ffmpeg yt-dlp
```

### Step 3 — Download InstaStitch
```bash
git clone https://github.com/nishkash4-sudo/InstaStitch.git
cd InstaStitch
```

### Step 4 — Set up Python
```bash
python3 -m venv venv
venv/bin/pip install flask Pillow pilmoji librosa scipy numpy
```

### Step 5 — (Optional) Add your OpenAI key for transcription
Only needed if you want to use the transcribe feature in Single Download:
```bash
echo 'OPENAI_API_KEY=sk-...' > .env
```

---

## How to run it

Every time you want to use InstaStitch, open your Terminal and run:
```bash
cd ~/Desktop/InstaStitch
venv/bin/python app.py
```

Then open your browser and go to: **http://localhost:8080**

That's it. You'll see the app just like a website.

To stop it, go back to Terminal and press `Ctrl + C`.

---

## Mode 1 — Single Download

### What it does
Downloads one Instagram Reel as a high-quality MP3 (audio only) or MP4 (video). Also automatically grabs the original post caption and the poster's username — no extra steps.

### How to use it
1. Click the **Single Download** tab at the top
2. Choose **Audio (MP3)** or **Video (MP4)** using the toggle
3. Optionally check **Transcribe** (needs OpenAI API key)
4. Paste your Reel URL into the input box
5. Click **Download**
6. Watch the live log — it shows every step as it happens
7. When it's done, click the download button to save your file
8. The original caption and poster handle appear below

### What happens behind the scenes

```
You paste a URL
        │
        ▼
  yt-dlp fetches the Reel from Instagram
  (like your browser would — no login needed for public posts)
        │
        ├─── Audio path ──────────────────────────────────────────
        │    Strips the video track, keeps only audio
        │    Saves as high-quality MP3 (best available bitrate)
        │
        └─── Video path ──────────────────────────────────────────
             Downloads best available quality
             Re-encodes to H.264 so it plays on iPhone / QuickTime
             │
             └─── Optional: Transcribe ───────────────────────────
                  Sends the audio to OpenAI Whisper (cloud)
                  Returns a full text transcript
                  Requires your own OpenAI API key
        │
        ▼
  ✓ File ready to download
  ✓ Original caption shown
  ✓ Poster @username shown
```

---

## Mode 2 — Multi Stitch

### What it does
Takes 2 to 30 Instagram Reel URLs and merges them into one single file — either one long MP3 or one long MP4. All clips are automatically normalized so the quality and format are consistent throughout.

### How to use it
1. Click the **Multi Stitch** tab
2. Choose **Audio** or **Video**
3. Add URLs one by one using the input box, OR click **Bulk Paste** to paste multiple at once (one URL per line)
4. Click **Stitch**
5. Watch the live log — it downloads and processes each clip in order
6. Download your merged file when done

### What happens behind the scenes

```
You paste 2–30 URLs
        │
        ▼
  yt-dlp downloads each Reel one by one
        │
        ▼
  ffmpeg normalizes every clip to the same format:

  Audio clips ──► 192kbps MP3, 44,100Hz, stereo
  Video clips ──► 1080×1920, 30fps, H.264

  (This step is what makes the final join seamless.
   Without it, clips from different posts would have
   different resolutions and frame rates, causing
   glitches at every cut.)
        │
        ▼
  ffmpeg joins all clips into one file
  (pure concatenation — no quality loss)
        │
        ▼
  ✓ One MP3 or MP4 — ready to download
```

---

## Mode 3 — Meme Edit

This is the most powerful mode. It lets you take any Instagram Reel and turn it into the classic meme format — white header on top with your caption text, video below.

### The full UI layout

```
┌──────────────────────┬─────────────────────────────────┐
│                      │                                 │
│   URL input          │   MEME CAPTION                  │
│                      │   ┌─────────────────────────┐   │
│  ┌────────────────┐  │   │ Type your caption...    │   │
│  │ instagram.com/ │  │   │ Use Enter for new lines │   │
│  └────────────────┘  │   └─────────────────────────┘   │
│                      │   2 lines · ~314px header       │
│  ┌────────────────┐  │                                 │
│  │                │  │   WATERMARK (optional)          │
│  │   thumbnail    │  │   @yourhandle                   │
│  │   preview      │  │                                 │
│  │   with crop    │  │   FONT STYLE                    │
│  │   handles      │  │   [Impact] [Helvetica] [Georgia]│
│  │                │  │                                 │
│  └────────────────┘  │   TEXT SIZE                     │
│                      │   [slider ◄──────►] 72px        │
│  ↑Top  [   ]px       │                                 │
│  ↓Bot  [   ]px       │   TOP PADDING                   │
│  ←Left [   ]px       │   [slider ◄──────►] 120px       │
│  →Right[   ]px       │                                 │
│  [Reset All]         │   [🎬 Create Meme Reel]         │
│                      │                                 │
│                      │   ── render log ──              │
│                      │   [1/3] Downloading...          │
│                      │   ✓ Download complete           │
│                      │   [2/3] Converting...           │
│                      │   [3/3] Rendering layout...     │
│                      │   DONE                          │
│                      │                                 │
│                      │   [⬇ Download meme_output.mp4]  │
│                      │                                 │
│                      │   Original Caption              │
│                      │   "caption text here..."        │
└──────────────────────┴─────────────────────────────────┘
```

### Step-by-step walkthrough

#### Step 1 — Paste your URL
As soon as you paste a valid Instagram URL, the thumbnail loads automatically in the preview box on the left. You can see the first frame of the video before you do anything.

#### Step 2 — Crop (optional but powerful)
This is the key feature for working with meme videos that already have their own header baked in, or videos with black/colored bars.

**Dragging:** Hover over any edge of the preview image — you'll see a red line. Drag it inward to set how much to crop from that side.

**Typing:** Enter exact pixel values in the four boxes: ↑ Top, ↓ Bottom, ← Left, → Right.

**What the crop does:**
```
Original video (1080×1920):           After crop (example: top=350):
┌──────────────────┐                  ┌──────────────────┐
│  original header │  ← removed       │                  │
│  baked into      │                  │                  │
│  the video       │                  │   clean video    │
├──────────────────┤  ─────────►      │   content only   │
│                  │                  │                  │
│  actual video    │                  │                  │
│  content         │                  └──────────────────┘
│                  │
└──────────────────┘
```

**Three common crop situations:**

1. **No crop needed** — The video is already clean (person talking to camera, etc.). Skip this step entirely.

2. **Crop the top only** — The original Reel has a white meme header baked in with someone else's text. Drag the top handle down to remove it, then add your own caption.

3. **Crop all 4 sides** — The video has black bars on all sides (letterboxed concert footage, TV clips, etc.). Crop each side to extract just the content. The output will show the extracted video at its real size with clean white borders.

#### Step 3 — Type your caption
Type your meme text in the caption box. A few things to know:

- **Press Enter for a new line** — the app respects your line breaks exactly. If you type two lines, you get two lines in the header. No surprises.
- **Auto-wrap** — if a single line is too wide for the chosen font size, it wraps automatically at a word boundary.
- **Live preview** — the counter below the text box updates instantly: `2 lines · ~314px header · ~1606px video`

#### Step 4 — Choose your font

| Font | Style | Best for |
|------|-------|---------|
| **Impact** | ALL CAPS, bold, classic | Traditional memes, viral content |
| **Helvetica** | Mixed case, clean, modern | Clean aesthetic, news-style |
| **Georgia** | Serif, editorial | Quotes, thoughtful content |

#### Step 5 — Adjust text size
The slider goes from 28px (small) to 120px (very large). The live preview counter updates as you drag so you always know the header height before rendering.

#### Step 6 — Set top padding
Top padding adds white space above your text, pushing the text and video down. Range: 0–400px. Default is 120px which gives a comfortable breathing room above the text.

```
top_pad = 0px:          top_pad = 120px:       top_pad = 300px:
┌──────────┐            ┌──────────┐           ┌──────────┐
│YOUR TEXT │            │          │           │          │
│          │            │          │           │          │
│  video   │            │YOUR TEXT │           │          │
│          │            │          │           │          │
└──────────┘            │  video   │           │YOUR TEXT │
                        └──────────┘           │  video   │
                                               └──────────┘
```

#### Step 7 — Optional watermark
Type a handle like `@yourpage` and it'll appear in small text (20px) in the bottom-right corner of the header. Subtle and clean.

#### Step 8 — Create
Click **🎬 Create Meme Reel**. Watch the live log on the right as each step completes:

```
[1/3] Downloading reel...
  ✓ Download complete
[OK] Caption extracted.
[2/3] Converting to H.264...
  Cropping top 350px, bottom 0px from source video...
[3/3] Rendering meme layout...
  ✓ Header image created (1080×314px)
DONE
```

Then download your `meme_output.mp4` and the original post caption appears below.

### What the output looks like

```
Output: 1080×1920 MP4, H.264, plays on any device

┌──────────────────────────┐
│                          │  ← top padding (white space)
│   YOUR CAPTION TEXT      │  ← your text, bold, centered
│   LINE TWO IF NEEDED     │
│                          │  ← small gap (28px)
├──────────────────────────┤  ← header ends, video begins
│                          │
│   original video         │  ← cropped + scaled
│   content here           │     white borders if needed
│                          │
│                          │
│              @watermark  │  ← optional, bottom-right corner
└──────────────────────────┘
  (white padding at bottom if video is shorter than frame)
```

### What happens behind the scenes

```
You paste URL + type caption
        │
        ▼
  yt-dlp downloads the Reel + writes metadata to .info.json
  (thumbnail loads in preview simultaneously)
        │
        ▼
  [OK] Caption + @username extracted from info.json
  (zero extra API calls — uses data already fetched)
        │
        ▼
  ffmpeg converts to H.264 intermediate
        │
        ▼
  [Optional] ffmpeg crops the video
  crop=iw-left-right : ih-top-bottom : left : top
  (one single crop pass handles all 4 sides at once)
        │
        ▼
  Python calculates the layout:
  • Load font at chosen size
  • Measure each word in pixels (actual font metrics)
  • Wrap lines only when they exceed 980px wide
  • Respect explicit newlines as hard breaks
  • header_h = top_pad + (lines × line_height) + 28px gap
  • video_h  = 1920 − header_h
        │
        ▼
  Pillow draws the white header image (1080 × header_h):
  • White canvas
  • Your caption text — centered, bold
  • Emoji rendered as real Twemoji images
  • Optional @watermark in bottom-right corner (20px)
        │
        ▼
  ffmpeg stacks header + video:
  scale video to fit 1080×video_h (preserve aspect ratio)
  pad any remaining space with white
  vstack: header on top, video below
        │
        ▼
  ✓ meme_output.mp4 — 1080×1920, H.264, ready to download
```

---

## Mode 4 — Waveform

### What it does
Takes any audio file and renders a smooth, mirrored frequency-spectrum waveform video. The audio is split into 64 log-spaced frequency bands (like a graphic equaliser). Each band is drawn as a smooth curve that snaps up on the beat and falls gracefully — no jitter, no lag. The output is two files you can drop straight into your video editor.

### How to use it
1. Click the **〜 Waveform** tab at the top
2. Click the drop zone (or drag your audio file onto it) — MP3, WAV, M4A, AAC, OGG, FLAC all work
3. Adjust **Lines** (3 / 5 / 7 / 11 parallel curves), **Spread** (how far the lines fan at peaks), and **Strip height**
4. Click **〜 Generate Waveform**
5. Watch the live log — it shows analysis and render progress in real time
6. Download the **MP4** (for InShot / CapCut) or the **WebM** (for Premiere / DaVinci / Canva)

### Using the MP4 in InShot (black background → transparent)
The black-background MP4 uses a blend-mode trick to fake transparency:

1. Open your main video in InShot
2. Tap **PiP** → import `waveform_black.mp4`
3. Resize and position it over your video
4. Tap the PiP layer → tap **Blend**
5. Select **Screen** (black disappears, white stays visible)

**Screen** is best for most backgrounds. **Lighten** works better if your background is very bright.

### Using the WebM in desktop editors
The WebM has a real alpha channel — import it directly as an overlay track in Premiere Pro, DaVinci Resolve, or Canva. No blend mode needed.

### What happens behind the scenes

```
You upload an audio file
        │
        ▼
  librosa loads audio at 44,100 Hz
        │
        ▼
  librosa.stft() computes one FFT frame per video frame
  (hop_length = sr / fps → exact 1:1 alignment)
        │
        ▼
  64 log-spaced frequency bands: 40 Hz → 14,000 Hz
  Each band = mean magnitude of its FFT bins
        │
        ▼
  Asymmetric temporal smoothing per band:
  RISE: snaps up fast (alpha = 0.80) → tight on the beat
  FALL: decays slowly (alpha = 0.12) → graceful trail-off
        │
        ▼
  For each frame:
  Cubic spline through 64 band values → smooth W-pixel curve
  Mirrored above and below centre line
  N parallel lines fan out proportional to band height (spread)
  3× supersampling + LANCZOS downscale for anti-aliased lines
  Gaussian glow layer composited on top
        │
        ├── ffmpeg → black-bg MP4 (libx264, yuv420p, Screen blend)
        └── ffmpeg → transparent WebM (libvpx-vp9, yuva420p)
        │
        ▼
  ✓ Both files ready to download
```

### Output specs

| File | Codec | Use in |
|------|-------|--------|
| `waveform_black.mp4` | H.264, black background | InShot, CapCut — set blend to Screen |
| `waveform_transparent.webm` | VP9 + alpha channel | Premiere, DaVinci Resolve, Canva |

Both are 1080px wide. Height matches the Strip height slider (default 160px).

### Render time
Approximately 1–2 minutes for a 30-second audio file on an M-series Mac.

---

## Live progress — always

Every mode streams live logs to your browser as things happen. You see each step as it completes. No spinner that might be frozen.

```
[1/3] Downloading reel...
  ✓ Download complete
[OK] Caption extracted.
[2/3] Converting to H.264...
  Cropping top 350px from source video...
[3/3] Rendering meme layout...
  ✓ Header image created (1080×448px)
DONE
```

---

## Output files

| File | Mode | What it contains |
|------|------|-----------------|
| `single_output.mp3` | Single Download (audio) | High-quality MP3 of the Reel |
| `single_output.mp4` | Single Download (video) | H.264 MP4, QuickTime-compatible |
| `output.mp3` | Multi Stitch (audio) | All clips merged into one MP3 |
| `output.mp4` | Multi Stitch (video) | All clips merged into one MP4 |
| `meme_output.mp4` | Meme Edit | White header + video, 1080×1920 |
| `single_transcript.txt` | Single Download (if enabled) | Full text transcript |
| `waveform_black.mp4` | Waveform | Frequency spectrum, black background (Screen blend) |
| `waveform_transparent.webm` | Waveform | Frequency spectrum, VP9 alpha channel |

⚠️ All files are saved to the project folder and **overwritten on each new run**. Download before running again.

---

## Tool breakdown

| Tool | What it actually does |
|------|-----------------------|
| **yt-dlp** | Downloads the Reel video/audio from Instagram. Also fetches the thumbnail and post metadata — caption, username — all from the same request, no extra calls. |
| **ffmpeg** | The video engine. Does H.264 encoding, audio normalization, clip stitching, cropping all 4 sides, stacking the meme header, and encoding the waveform outputs (MP4 + WebM). |
| **Pillow** | Python's image library. Draws the meme header canvas, places text, and renders every waveform frame (supersampled lines + glow). |
| **pilmoji** | Extends Pillow to render emoji as real Twemoji images (colorful Twitter-style) instead of broken boxes or empty squares. |
| **librosa** | Audio analysis library. Used by Waveform mode to load audio and compute the STFT (Short-Time Fourier Transform) — one FFT frame per video frame, exactly aligned. |
| **scipy** | Scientific computing. Used by Waveform mode for per-band temporal smoothing and cubic spline interpolation between frequency bands. |
| **numpy** | Numerical computing. Powers all the array operations in the waveform pipeline — FFT magnitudes, band aggregation, envelope smoothing. |
| **OpenAI Whisper** | Cloud transcription service. Only used if you enable Transcribe in Single Download mode. Requires your own API key. |
| **Flask** | The local web server. Powers the browser UI and streams progress updates in real time via Server-Sent Events. |

---

## Project structure

```
InstaStitch/
├── app.py                  # Flask server — all pipelines + SSE streaming
├── waveform_generator.py   # Waveform engine — STFT, band envelopes, frame renderer
├── templates/
│   └── index.html          # Single-page UI with 4 tabs
├── .env                    # Your OPENAI_API_KEY (not committed to git)
├── venv/                   # Python virtual environment (not committed to git)
└── .claude/
    └── launch.json         # Dev server config
```

---

## Requirements

- macOS (or any system with Python 3.9+)
- `ffmpeg` — the video processing engine
- `yt-dlp` — the downloader
- `flask`, `Pillow`, `pilmoji` — Python packages for the core app
- `librosa`, `scipy`, `numpy` — Python packages for the Waveform feature
- `OPENAI_API_KEY` in a `.env` file — only needed for transcription

---

## Troubleshooting

**Downloads stop working?**
Instagram occasionally changes how Reels are served. Update yt-dlp:
```bash
brew upgrade yt-dlp
```

**Video won't play on my iPhone / QuickTime?**
The app already re-encodes everything to H.264, which is universally compatible. If it still won't play, make sure the download completed fully (file size should be several MB, not a few KB).

**Emoji in my caption shows as a box?**
The `pilmoji` library needs to fetch Twemoji assets from the internet on first use. Make sure you have an internet connection when creating your first meme with emoji.

**Port 8080 already in use?**
Another process is using that port. Either stop it, or find the process:
```bash
lsof -i :8080
```

---

## Notes

- **Personal use only** — this tool is for your own local use
- Files are overwritten each run — save your output before running again
- The meme header height auto-adjusts based on your text, font size, and top padding
- Text wrapping is pixel-accurate — it measures actual font widths, not character counts
- Explicit line breaks in your caption are always respected exactly as typed
