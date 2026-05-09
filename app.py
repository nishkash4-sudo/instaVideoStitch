import os
import glob
import json
import base64
import mimetypes
import shutil
import subprocess
import urllib.error
import urllib.request
from flask import Flask, render_template, request, Response, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_AUDIO = os.path.join(BASE_DIR, "output.mp3")
OUTPUT_VIDEO = os.path.join(BASE_DIR, "output.mp4")
SINGLE_AUDIO = os.path.join(BASE_DIR, "single_output.mp3")
SINGLE_VIDEO = os.path.join(BASE_DIR, "single_output.mp4")
TRANSCRIPT_AUDIO = os.path.join(BASE_DIR, "transcript_input.mp3")
TRANSCRIPT_TEXT = os.path.join(BASE_DIR, "single_transcript.txt")
ENV_FILE = os.path.join(BASE_DIR, ".env")


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

    total_steps = 3 if is_audio and transcribe else 2
    if not is_audio:
        total_steps = 4 if transcribe else 3

    # ── STEP 1: EXTRACT METADATA (caption) ───────────────────────────────────
    yield sse(f"[1/{total_steps}] Fetching post metadata...")
    code, stdout, stderr = run_cmd(["yt-dlp", "--dump-json", "--no-download", url])
    caption = ""
    if code == 0 and stdout.strip():
        try:
            meta = json.loads(stdout.strip().splitlines()[-1])
            caption = meta.get("description") or meta.get("title") or ""
        except Exception:
            caption = ""
    if caption:
        yield sse("[OK] Caption extracted.")
        yield encode_text_event("CAPTION", caption)
    else:
        yield sse("[WARN] Could not extract caption.")

    # ── STEP 2: DOWNLOAD ─────────────────────────────────────────────────────
    raw_output = os.path.join(BASE_DIR, "single_raw.mp4")

    if is_audio:
        yield sse(f"[2/{total_steps}] Downloading reel at best audio quality...")
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3", "--audio-quality", "0",
            "-o", output, url,
        ]
    else:
        yield sse(f"[2/{total_steps}] Downloading reel at best available quality...")
        if os.path.exists(raw_output):
            os.remove(raw_output)
        cmd = [
            "yt-dlp",
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", raw_output, url,
        ]

    code, _, stderr = run_cmd(cmd)
    dl_path = output if is_audio else raw_output
    if code != 0 or not os.path.exists(dl_path):
        yield sse(f"[ERROR] Download failed. {stderr.strip()[-200:]}")
        return

    if not is_audio:
        yield sse(f"[3/{total_steps}] Converting to QuickTime-compatible H.264...")
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
        step = 3 if is_audio else 4
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


if __name__ == "__main__":
    app.run(debug=False, threaded=True, port=8080)
