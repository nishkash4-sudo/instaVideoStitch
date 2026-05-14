import os
import glob
import json
import base64
import mimetypes
import shutil
import subprocess
import urllib.error
import urllib.request
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import AppleEmojiSource
from flask import Flask, render_template, request, Response, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_AUDIO = os.path.join(BASE_DIR, "output.mp3")
OUTPUT_VIDEO = os.path.join(BASE_DIR, "output.mp4")
SINGLE_AUDIO = os.path.join(BASE_DIR, "single_output.mp3")
SINGLE_VIDEO = os.path.join(BASE_DIR, "single_output.mp4")
TRANSCRIPT_AUDIO = os.path.join(BASE_DIR, "transcript_input.mp3")
TRANSCRIPT_TEXT = os.path.join(BASE_DIR, "single_transcript.txt")
MEME_OUTPUT = os.path.join(BASE_DIR, "meme_output.mp4")
MEME_THUMB_BASE = os.path.join(BASE_DIR, "meme_preview_thumb")
ENV_FILE = os.path.join(BASE_DIR, ".env")

MEME_FONTS = {
    "impact":    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "helvetica": "/System/Library/Fonts/Helvetica.ttc",
    "georgia":   "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
}
# Filter to only fonts that exist on this system
MEME_FONTS = {k: v for k, v in MEME_FONTS.items() if os.path.exists(v)}
MEME_FONT = MEME_FONTS.get("impact") or next(iter(MEME_FONTS.values()), None)


def load_env_file():
    if not os.path.exists(ENV_FILE):
        return
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_env_file()



def check_dependency(cmd):
    return shutil.which(cmd) is not None


def run_cmd(args):
    """Run a subprocess command and return (returncode, stdout, stderr)."""
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def sse(msg):
    """Format a message as an SSE data line."""
    return f"data: {msg}\n\n"


def encode_text_event(prefix, text):
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return sse(f"{prefix}:{encoded}")


def _read_and_delete_info_json(output_path, is_merge):
    """Read description from yt-dlp's --write-info-json file, then delete it.

    yt-dlp path rules (confirmed by testing):
      merge output  (bestvideo+bestaudio): strips .mp4 ext  → meme_raw.info.json
      audio extract (-x --audio-format mp3): appends suffix → single_output.mp3.info.json
    We check both patterns as a fallback so a yt-dlp version change won't silently break it.
    """
    stem = os.path.splitext(output_path)[0]
    candidate = (stem if is_merge else output_path) + ".info.json"
    fallback   = (output_path if is_merge else stem) + ".info.json"
    for p in (candidate, fallback):
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    meta = json.load(f)
                caption  = meta.get("description") or meta.get("title") or ""
                username = meta.get("channel") or meta.get("uploader_id") or meta.get("uploader") or ""
                return caption, username
            except Exception:
                pass
            finally:
                try:
                    os.remove(p)
                except Exception:
                    pass
    return "", ""


def transcription_enabled():
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def transcribe_audio_file(path):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return "", "OPENAI_API_KEY is missing. Add it to .env to enable transcription."

    model = os.environ.get("TRANSCRIBE_MODEL", "gpt-4o-transcribe").strip() or "gpt-4o-transcribe"
    prompt = (
        "Transcribe Indian creator audio as Roman Hinglish, not Hindi script. "
        "Use Latin alphabet only. Never use Devanagari. Do not translate to formal English. "
        "Preserve Hindi words in Roman spelling and preserve English words as English. "
        "Examples: 'भाई मैंने क्लोड से' should be 'Bhai maine Claude se'. "
        "'इंस्टाल दिस स्किल' should be 'install this skill'. "
        "'कमेंट कर दो इंस्टा' should be 'comment kar do Insta'. "
        "Keep platform names, creator names, brand names, slang, and creator terminology as spoken."
    )

    boundary = "----InstaStitchTranscriptionBoundary"
    mime_type = mimetypes.guess_type(path)[0] or "audio/mpeg"
    fields = {
        "model": model,
        "prompt": prompt,
        "language": "en",
        "response_format": "json",
        "temperature": "0",
    }

    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    with open(path, "rb") as f:
        audio_bytes = f.read()

    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
    )
    body.extend(audio_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[-300:]
        return "", f"OpenAI transcription failed. {detail}"
    except Exception as e:
        return "", f"OpenAI transcription failed. {e}"

    text = (payload.get("text") or "").strip()
    if not text:
        return "", "OpenAI returned an empty transcript."
    return text, ""


def wrap_text_pixels(text, font, max_width=980):
    """Split text into lines respecting explicit newlines, wrapping only when a line
    exceeds max_width pixels at the given font size."""
    lines = []
    for paragraph in text.split('\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append('')
            continue
        words = paragraph.split()
        current = ''
        for word in words:
            test = (current + ' ' + word) if current else word
            try:
                w = font.getlength(test)
            except Exception:
                w = len(test) * 0.6 * 72  # fallback estimate
            if current and w > max_width:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
    return lines if lines else ['']


def meme_edit(url, meme_text, watermark="", font_key="impact", crop_top=0, crop_bottom=0, crop_left=0, crop_right=0, top_pad=120, font_size=72):
    """Download a reel and apply meme format: white canvas header + bold text + video below."""
    for dep in ("yt-dlp", "ffmpeg"):
        if not check_dependency(dep):
            yield sse(f"[ERROR] '{dep}' not found on PATH.")
            return

    chosen_font_path = MEME_FONTS.get(font_key) or MEME_FONT
    if not chosen_font_path:
        yield sse("[ERROR] No usable font found on this system for text rendering.")
        return

    url = url.strip()
    meme_text = meme_text.strip()
    if not url or not meme_text:
        yield sse("[ERROR] URL and meme text are both required.")
        return

    raw_path  = os.path.join(BASE_DIR, "meme_raw.mp4")
    conv_path = os.path.join(BASE_DIR, "meme_conv.mp4")
    for p in (raw_path, conv_path, MEME_OUTPUT):
        if os.path.exists(p):
            os.remove(p)

    # ── STEP 1: DOWNLOAD + CAPTION ───────────────────────────────────────────
    yield sse("[1/3] Downloading reel...")
    code, _, stderr = run_cmd([
        "yt-dlp",
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--write-info-json",               # writes meme_raw.info.json (no extra API calls)
        "-o", raw_path, url,
    ])
    if code != 0 or not os.path.exists(raw_path):
        yield sse(f"[ERROR] Download failed. {stderr.strip()[-200:]}")
        return
    yield sse("[OK] Download complete.")

    caption, username = _read_and_delete_info_json(raw_path, is_merge=True)
    if caption:
        yield sse("[OK] Caption extracted.")
        encoded = base64.b64encode(caption.encode("utf-8")).decode("ascii")
        yield sse(f"CAPTION:{encoded}")
    if username:
        yield encode_text_event("USERNAME", username)

    # ── STEP 3: CONVERT TO H.264 ──────────────────────────────────────────────
    yield sse("[2/3] Converting to H.264...")
    code, _, stderr = run_cmd([
        "ffmpeg", "-y", "-i", raw_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        conv_path,
    ])
    if os.path.exists(raw_path):
        os.remove(raw_path)
    if code != 0 or not os.path.exists(conv_path):
        yield sse(f"[ERROR] Conversion failed. {stderr.strip()[-200:]}")
        return
    yield sse("[OK] Conversion complete.")

    # ── OPTIONAL CROP (all 4 sides, single ffmpeg call) ──────────────────────
    if crop_top > 0 or crop_bottom > 0 or crop_left > 0 or crop_right > 0:
        cropped_path = os.path.join(BASE_DIR, "meme_cropped.mp4")
        parts = []
        if crop_top    > 0: parts.append(f"top {crop_top}px")
        if crop_bottom > 0: parts.append(f"bottom {crop_bottom}px")
        if crop_left   > 0: parts.append(f"left {crop_left}px")
        if crop_right  > 0: parts.append(f"right {crop_right}px")
        yield sse(f"  Cropping {', '.join(parts)} from source video...")
        new_w = f"iw-{crop_left}-{crop_right}"
        new_h = f"ih-{crop_top}-{crop_bottom}"
        code, _, stderr = run_cmd([
            "ffmpeg", "-y", "-i", conv_path,
            "-vf", f"crop={new_w}:{new_h}:{crop_left}:{crop_top}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy",
            cropped_path,
        ])
        if os.path.exists(conv_path):
            os.remove(conv_path)
        if code != 0 or not os.path.exists(cropped_path):
            yield sse(f"[ERROR] Crop failed. {stderr.strip()[-200:]}")
            return
        conv_path = cropped_path   # rest of pipeline uses the cropped file

    # ── STEP 4: BUILD MEME LAYOUT ─────────────────────────────────────────────
    yield sse("[3/3] Rendering meme layout...")

    # Load font first — needed for pixel-accurate text wrapping
    try:
        pil_font = ImageFont.truetype(chosen_font_path, font_size)
    except Exception:
        pil_font = ImageFont.load_default()

    display_text = meme_text.upper() if font_key == "impact" else meme_text
    lines      = wrap_text_pixels(display_text, pil_font, max_width=980)
    line_h     = font_size + 28
    bottom_gap = 28                               # small gap between text and video
    header_h   = top_pad + len(lines) * line_h + bottom_gap
    video_h    = 1920 - header_h
    header_png = os.path.join(BASE_DIR, "meme_header.png")

    # --- Draw header image (Pilmoji handles emoji rendering) ---
    try:
        img = Image.new("RGB", (1080, header_h), color=(255, 255, 255))

        # pil_font already loaded above; anchor text block to bottom of header
        text_block_h = len(lines) * line_h
        y_start = header_h - bottom_gap - text_block_h

        with Pilmoji(img, source=AppleEmojiSource) as pilmoji_draw:
            for idx, line in enumerate(lines):
                bbox = pilmoji_draw.getsize(line, font=pil_font)
                text_w = bbox[0]
                x = (1080 - text_w) // 2
                y = y_start + idx * line_h
                pilmoji_draw.text((x, y), line, font=pil_font, fill=(0, 0, 0))

        # Optional watermark (bottom-right, smaller, dark grey)
        if watermark.strip():
            draw = ImageDraw.Draw(img)
            try:
                wm_font = ImageFont.truetype(chosen_font_path, 20)
            except Exception:
                wm_font = ImageFont.load_default()
            wm_text = watermark.strip()
            wbbox = draw.textbbox((0, 0), wm_text, font=wm_font)
            wx = 1080 - (wbbox[2] - wbbox[0]) - 80
            wy = header_h - (wbbox[3] - wbbox[1]) - 10
            draw.text((wx + 2, wy + 2), wm_text, font=wm_font, fill=(200, 200, 200))
            draw.text((wx, wy), wm_text, font=wm_font, fill=(80, 80, 80))

        img.save(header_png)
    except Exception as e:
        if os.path.exists(conv_path):
            os.remove(conv_path)
        yield sse(f"[ERROR] Header image generation failed. {e}")
        return

    # --- ffmpeg: stack header PNG + video ---
    # decrease: scale DOWN if needed (never up) to fit 1080×video_h, preserve AR.
    # pad:white: fill any remaining space with white — invisible on white-bg videos,
    # clean white borders for letterboxed/cropped content (concert footage etc).
    filt = (
        f"[1:v]scale=920:{video_h}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad=1080:{video_h}:(ow-iw)/2:0:white[vid];"  # always ≥80px side borders
        f"[0:v][vid]vstack[out]"
    )

    code, _, stderr = run_cmd([
        "ffmpeg", "-y",
        "-loop", "1", "-i", header_png,   # input 0: header image (looped)
        "-i", conv_path,                   # input 1: video
        "-filter_complex", filt,
        "-map", "[out]",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        MEME_OUTPUT,
    ])

    for p in (conv_path, header_png, os.path.join(BASE_DIR, "meme_cropped.mp4")):
        if os.path.exists(p):
            os.remove(p)

    if code != 0 or not os.path.exists(MEME_OUTPUT):
        yield sse(f"[ERROR] Meme render failed. {stderr.strip()[-400:]}")
        return

    yield sse("[OK] Meme reel ready!")
    yield sse("DONE:meme_mp4")


def pipeline(urls, mode="audio"):
    """mode: 'audio' → MP3, 'video' → MP4"""
    is_audio = (mode == "audio")
    ext       = "mp3" if is_audio else "mp4"
    output    = OUTPUT_AUDIO if is_audio else OUTPUT_VIDEO

    # --- dependency check ---
    for dep in ("yt-dlp", "ffmpeg"):
        if not check_dependency(dep):
            yield sse(f"[ERROR] '{dep}' not found on PATH. Install it and retry.")
            return

    urls = [u.strip() for u in urls if u and u.strip()][:30]
    if not urls:
        yield sse("[ERROR] No URLs provided.")
        return

    # Clean leftover files from previous run
    for pattern in (f"clip_*.{ext}", f"norm_*.{ext}"):
        for f in glob.glob(os.path.join(BASE_DIR, pattern)):
            os.remove(f)
    filelist = os.path.join(BASE_DIR, "filelist.txt")
    if os.path.exists(filelist):
        os.remove(filelist)
    if os.path.exists(output):
        os.remove(output)

    # ── STEP 1: DOWNLOAD ──────────────────────────────────────────────────────
    yield sse(f"[1/3] Downloading {len(urls)} reel(s) ({'audio only' if is_audio else 'video'})...")
    downloaded = []
    for i, url in enumerate(urls, start=1):
        out_path = os.path.join(BASE_DIR, f"clip_{i}.{ext}")
        yield sse(f"  Downloading clip {i}/{len(urls)}: {url}")

        if is_audio:
            cmd = [
                "yt-dlp",
                "-x", "--audio-format", "mp3", "--audio-quality", "0",
                "-o", out_path, url,
            ]
        else:
            cmd = [
                "yt-dlp",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "-o", out_path, url,
            ]

        code, _, stderr = run_cmd(cmd)
        if code != 0 or not os.path.exists(out_path):
            yield sse(f"  [WARN] Failed to download clip {i} — skipping. ({stderr.strip()[:120]})")
        else:
            yield sse(f"  [OK] Clip {i} downloaded.")
            downloaded.append((i, out_path))

    if not downloaded:
        yield sse("[ERROR] No clips were downloaded successfully.")
        return

    # ── STEP 2: NORMALIZE ────────────────────────────────────────────────────
    if is_audio:
        yield sse(f"[2/3] Normalizing {len(downloaded)} clip(s) to 192kbps / 44.1kHz / stereo...")
    else:
        yield sse(f"[2/3] Normalizing {len(downloaded)} clip(s) to 1080×1920 / 30fps / H.264+AAC...")

    normalized = []
    for i, clip_path in downloaded:
        norm_path = os.path.join(BASE_DIR, f"norm_{i}.{ext}")
        yield sse(f"  Normalizing clip {i}...")

        if is_audio:
            cmd = [
                "ffmpeg", "-y", "-i", clip_path,
                "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                norm_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", clip_path,
                "-vf", (
                    "scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                    "fps=30"
                ),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                norm_path,
            ]

        code, _, stderr = run_cmd(cmd)
        if code != 0 or not os.path.exists(norm_path):
            yield sse(f"  [WARN] Failed to normalize clip {i} — skipping. ({stderr.strip()[-120:]})")
        else:
            yield sse(f"  [OK] Clip {i} normalized.")
            normalized.append(norm_path)

    if len(normalized) < 2:
        yield sse("[ERROR] Need at least 2 successfully normalized clips to merge.")
        _cleanup(downloaded, normalized, filelist, ext)
        return

    # ── STEP 3: CONCAT ───────────────────────────────────────────────────────
    out_name = f"output.{ext}"
    yield sse(f"[3/3] Merging {len(normalized)} clip(s) into {out_name}...")
    with open(filelist, "w") as f:
        for p in normalized:
            f.write(f"file '{p}'\n")

    code, _, stderr = run_cmd([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", filelist,
        "-c", "copy",
        output,
    ])
    if code != 0 or not os.path.exists(output):
        yield sse(f"[ERROR] ffmpeg concat failed. {stderr.strip()[-200:]}")
        _cleanup(downloaded, normalized, filelist, ext)
        return

    yield sse("[OK] Merge complete!")
    _cleanup(downloaded, normalized, filelist, ext)
    yield sse("[OK] Intermediate files cleaned up.")
    yield sse(f"DONE:{ext}")   # signal to frontend with the file type


def _cleanup(downloaded, normalized, filelist, ext):
    for _, p in downloaded:
        if os.path.exists(p):
            os.remove(p)
    for p in normalized:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(filelist):
        os.remove(filelist)


@app.route("/")
def index():
    return render_template("index.html", transcription_enabled=transcription_enabled())


@app.route("/stitch", methods=["POST"])
def stitch():
    data = request.get_json(force=True)
    urls = data.get("urls", [])
    mode = data.get("mode", "audio")   # "audio" or "video"
    if mode not in ("audio", "video"):
        mode = "audio"

    def generate():
        yield from pipeline(urls, mode)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/download/<filetype>")
def download(filetype):
    if filetype == "mp3":
        path, name = OUTPUT_AUDIO, "output.mp3"
    elif filetype == "mp4":
        path, name = OUTPUT_VIDEO, "output.mp4"
    elif filetype == "single_mp3":
        path, name = SINGLE_AUDIO, "single_output.mp3"
    elif filetype == "single_mp4":
        path, name = SINGLE_VIDEO, "single_output.mp4"
    elif filetype == "transcript_txt":
        path, name = TRANSCRIPT_TEXT, "single_transcript.txt"
    elif filetype == "meme_mp4":
        path, name = MEME_OUTPUT, "meme_output.mp4"
    else:
        return "Invalid file type", 400

    if not os.path.exists(path):
        return f"{name} not found", 404
    return send_file(path, as_attachment=True, download_name=name)


def single_download(url, mode="audio", transcribe=False):
    """Download one reel at maximum quality + extract caption/transcript."""
    is_audio = (mode == "audio")
    ext = "mp3" if is_audio else "mp4"
    output = SINGLE_AUDIO if is_audio else SINGLE_VIDEO

    for dep in ("yt-dlp", "ffmpeg"):
        if not check_dependency(dep):
            yield sse(f"[ERROR] '{dep}' not found on PATH. Install it and retry.")
            return

    url = url.strip()
    if not url:
        yield sse("[ERROR] No URL provided.")
        return

    # Clean previous single output
    for path in (output, TRANSCRIPT_AUDIO, TRANSCRIPT_TEXT):
        if os.path.exists(path):
            os.remove(path)

    # step counts: audio=[1 download, +1 if transcribe], video=[1 download, 1 convert, +1 if transcribe]
    total_steps = (2 if transcribe else 1) if is_audio else (3 if transcribe else 2)

    # ── STEP 1: DOWNLOAD + CAPTION ───────────────────────────────────────────
    raw_output = os.path.join(BASE_DIR, "single_raw.mp4")

    if is_audio:
        yield sse(f"[1/{total_steps}] Downloading reel at best audio quality...")
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "--no-playlist",
            "--write-info-json",           # writes single_output.mp3.info.json
            "-o", output, url,
        ]
    else:
        yield sse(f"[1/{total_steps}] Downloading reel at best available quality...")
        if os.path.exists(raw_output):
            os.remove(raw_output)
        cmd = [
            "yt-dlp",
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "--write-info-json",           # writes single_raw.info.json
            "-o", raw_output, url,
        ]

    code, _, stderr = run_cmd(cmd)
    dl_path = output if is_audio else raw_output
    if code != 0 or not os.path.exists(dl_path):
        yield sse(f"[ERROR] Download failed. {stderr.strip()[-200:]}")
        return

    caption, username = _read_and_delete_info_json(
        output if is_audio else raw_output,
        is_merge=not is_audio,
    )
    if caption:
        yield sse("[OK] Caption extracted.")
        yield encode_text_event("CAPTION", caption)
        if username:
            yield encode_text_event("USERNAME", username)
    else:
        yield sse("[OK] Download complete.")

    if not is_audio:
        yield sse(f"[2/{total_steps}] Converting to QuickTime-compatible H.264...")
        code, _, stderr = run_cmd([
            "ffmpeg", "-y", "-i", raw_output,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output,
        ])
        if os.path.exists(raw_output):
            os.remove(raw_output)
        if code != 0 or not os.path.exists(output):
            yield sse(f"[ERROR] Conversion failed. {stderr.strip()[-200:]}")
            return
        yield sse("[OK] Done — QuickTime compatible MP4 ready!")
    else:
        yield sse("[OK] Download complete!")

    if transcribe:
        step = 2 if is_audio else 3
        yield sse(f"[{step}/{total_steps}] Preparing Hinglish-aware transcript audio...")
        code, _, stderr = run_cmd([
            "ffmpeg", "-y", "-i", output,
            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k",
            TRANSCRIPT_AUDIO,
        ])
        if code != 0 or not os.path.exists(TRANSCRIPT_AUDIO):
            yield sse(f"[WARN] Could not prepare audio for transcription. {stderr.strip()[-180:]}")
        else:
            yield sse("  Transcribing with Hinglish preservation...")
            transcript, err = transcribe_audio_file(TRANSCRIPT_AUDIO)
            if os.path.exists(TRANSCRIPT_AUDIO):
                os.remove(TRANSCRIPT_AUDIO)
            if err:
                yield sse(f"[WARN] {err}")
            else:
                with open(TRANSCRIPT_TEXT, "w", encoding="utf-8") as f:
                    f.write(transcript)
                yield sse("[OK] Transcript ready.")
                yield encode_text_event("TRANSCRIPT", transcript)

    yield sse(f"DONE:{ext}")


@app.route("/single", methods=["POST"])
def single():
    data = request.get_json(force=True)
    url = data.get("url", "")
    mode = data.get("mode", "audio")
    transcribe = bool(data.get("transcribe", False))
    if mode not in ("audio", "video"):
        mode = "audio"

    def generate():
        yield from single_download(url, mode, transcribe)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/preview", methods=["POST"])
def preview():
    """Fetch just the thumbnail for a Reel URL (no video download). Returns image or 204."""
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    if not url:
        return "", 204

    # Clean up any previous thumbnail
    for ext in ("jpg", "jpeg", "webp", "png"):
        p = f"{MEME_THUMB_BASE}.{ext}"
        if os.path.exists(p):
            os.remove(p)

    run_cmd([
        "yt-dlp", "--write-thumbnail", "--no-download",
        "-o", MEME_THUMB_BASE, url,
    ])

    for ext in ("jpg", "jpeg", "webp", "png"):
        p = f"{MEME_THUMB_BASE}.{ext}"
        if os.path.exists(p):
            mime = "image/webp" if ext == "webp" else "image/jpeg"
            return send_file(p, mimetype=mime)

    return "", 204  # thumbnail unavailable — not an error


@app.route("/meme", methods=["POST"])
def meme():
    data = request.get_json(force=True)
    url        = data.get("url", "")
    meme_text  = data.get("meme_text", "")
    watermark  = data.get("watermark", "")
    font_key   = data.get("font", "impact")
    crop_top    = max(0, int(data.get("crop_top",    0) or 0))
    crop_bottom = max(0, int(data.get("crop_bottom", 0) or 0))
    crop_left   = max(0, int(data.get("crop_left",   0) or 0))
    crop_right  = max(0, int(data.get("crop_right",  0) or 0))
    top_pad      = max(0, min(int(data.get("top_pad", 120) if data.get("top_pad") is not None else 120), 400))
    font_size    = max(28, min(int(data.get("font_size", 72) or 72), 120))

    def generate():
        yield from meme_edit(url, meme_text, watermark, font_key, crop_top, crop_bottom, crop_left, crop_right, top_pad, font_size)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    app.run(debug=False, threaded=True, port=8080)
