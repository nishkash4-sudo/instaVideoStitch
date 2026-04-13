import os
import glob
import shutil
import subprocess
from flask import Flask, render_template, request, Response, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_AUDIO = os.path.join(BASE_DIR, "output.mp3")
OUTPUT_VIDEO = os.path.join(BASE_DIR, "output.mp4")


def check_dependency(cmd):
    return shutil.which(cmd) is not None


def run_cmd(args):
    """Run a subprocess command and return (returncode, stdout, stderr)."""
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def sse(msg):
    """Format a message as an SSE data line."""
    return f"data: {msg}\n\n"


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
    return render_template("index.html")


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
    else:
        return "Invalid file type", 400

    if not os.path.exists(path):
        return f"{name} not found", 404
    return send_file(path, as_attachment=True, download_name=name)


if __name__ == "__main__":
    app.run(debug=False, threaded=True, port=8080)
