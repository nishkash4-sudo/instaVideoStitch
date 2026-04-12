import os
import glob
import shutil
import subprocess
from flask import Flask, render_template, request, Response, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "output.mp4")


def check_dependency(cmd):
    return shutil.which(cmd) is not None


def run_cmd(args):
    """Run a subprocess command and return (returncode, stdout, stderr)."""
    result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def sse(msg):
    """Format a message as an SSE data line."""
    return f"data: {msg}\n\n"


def pipeline(urls):
    # --- dependency check ---
    for dep in ("yt-dlp", "ffmpeg"):
        if not check_dependency(dep):
            yield sse(f"[ERROR] '{dep}' not found on PATH. Install it and retry.")
            return

    urls = [u.strip() for u in urls if u and u.strip()][:10]
    if not urls:
        yield sse("[ERROR] No URLs provided.")
        return

    # Clean any leftover files from a previous run
    for f in glob.glob(os.path.join(BASE_DIR, "clip_*.mp4")):
        os.remove(f)
    for f in glob.glob(os.path.join(BASE_DIR, "norm_*.mp4")):
        os.remove(f)
    filelist = os.path.join(BASE_DIR, "filelist.txt")
    if os.path.exists(filelist):
        os.remove(filelist)
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    # --- download ---
    yield sse(f"[1/3] Downloading {len(urls)} reel(s)...")
    downloaded = []
    for i, url in enumerate(urls, start=1):
        out_path = os.path.join(BASE_DIR, f"clip_{i}.mp4")
        yield sse(f"  Downloading clip {i}/{len(urls)}: {url}")
        code, _, stderr = run_cmd([
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", out_path,
            url,
        ])
        if code != 0 or not os.path.exists(out_path):
            yield sse(f"  [WARN] Failed to download clip {i} — skipping. ({stderr.strip()[:120]})")
        else:
            yield sse(f"  [OK] Clip {i} downloaded.")
            downloaded.append((i, out_path))

    if not downloaded:
        yield sse("[ERROR] No clips were downloaded successfully.")
        return

    # --- normalize ---
    yield sse(f"[2/3] Normalizing {len(downloaded)} clip(s) to 1080x1920 / 30fps / H.264+AAC...")
    normalized = []
    for i, clip_path in downloaded:
        norm_path = os.path.join(BASE_DIR, f"norm_{i}.mp4")
        yield sse(f"  Normalizing clip {i}...")
        code, _, stderr = run_cmd([
            "ffmpeg", "-y",
            "-i", clip_path,
            "-vf", (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                "fps=30"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            norm_path,
        ])
        if code != 0 or not os.path.exists(norm_path):
            yield sse(f"  [WARN] Failed to normalize clip {i} — skipping. ({stderr.strip()[-120:]})")
        else:
            yield sse(f"  [OK] Clip {i} normalized.")
            normalized.append(norm_path)

    if len(normalized) < 2:
        yield sse("[ERROR] Need at least 2 successfully normalized clips to merge.")
        _cleanup(downloaded, normalized, filelist)
        return

    # --- concat ---
    yield sse(f"[3/3] Merging {len(normalized)} clip(s) into output.mp4...")
    with open(filelist, "w") as f:
        for p in normalized:
            f.write(f"file '{p}'\n")

    code, _, stderr = run_cmd([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", filelist,
        "-c", "copy",
        OUTPUT_FILE,
    ])
    if code != 0 or not os.path.exists(OUTPUT_FILE):
        yield sse(f"[ERROR] ffmpeg concat failed. {stderr.strip()[-200:]}")
        _cleanup(downloaded, normalized, filelist)
        return

    yield sse("[OK] Merge complete!")

    # --- cleanup ---
    _cleanup(downloaded, normalized, filelist)
    yield sse("[OK] Intermediate files cleaned up.")
    yield sse("DONE")


def _cleanup(downloaded, normalized, filelist):
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

    def generate():
        yield from pipeline(urls)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/download")
def download():
    if not os.path.exists(OUTPUT_FILE):
        return "output.mp4 not found", 404
    return send_file(OUTPUT_FILE, as_attachment=True, download_name="output.mp4")


if __name__ == "__main__":
    app.run(debug=False, threaded=True, port=8080)
