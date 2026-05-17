#!/usr/bin/env python3
"""
waveform_generator.py — Smooth frequency-spectrum waveform

Splits audio into log-spaced frequency bands (like an equalizer), renders
each band as a smooth mirrored bar that rises fast and falls slowly.
The multi-line spread effect fans lines at peaks for a premium look.

Usage:
  python waveform_generator.py audio.mp3
  python waveform_generator.py audio.mp3 --lines 5 --spread 0.15 --height 160 --fps 30
"""

import os, sys, shutil, tempfile, subprocess, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import librosa
import scipy.ndimage
from scipy.interpolate import CubicSpline


# ── Defaults ──────────────────────────────────────────────────────────────────
STRIP_W      = 1080
STRIP_H      = 160
SCALE        = 3
N_LINES      = 5
SPREAD       = 0.15
MAX_AMP_FRAC = 0.44     # divided by spread_factor at render time → no clipping
LINE_W       = 1
GLOW_RADIUS  = 5
GLOW_ALPHA   = 0.6
FPS          = 30
FADE_S       = 0.45

# Frequency bands
N_BARS   = 64           # number of log-spaced frequency bands
FMIN     = 40.0         # Hz — lowest band (deep bass)
FMAX     = 14000.0      # Hz — highest band

# Per-band temporal smoothing (asymmetric: snappy rise, graceful fall)
RISE_ALPHA = 0.80       # 0–1: fraction of new value to take when rising
FALL_ALPHA = 0.12       # fraction when falling — lower = slower fall


# ── Audio loading ─────────────────────────────────────────────────────────────
def load_audio(path, sr=44100):
    y, sr_out = librosa.load(path, sr=sr, mono=True)
    return y, sr_out


# ── Pre-compute per-frame per-band magnitudes ─────────────────────────────────
def build_band_envelopes(y, sr, fps):
    """
    Returns smoothed_bands: ndarray (N_BARS, n_frames), values in [0, 1].

    Steps:
      1. STFT with hop = sr//fps → one column per video frame
      2. Map FFT bins → N_BARS log-spaced frequency bands (mean magnitude)
      3. Asymmetric temporal smoothing per band: fast rise, slow fall
      4. Global normalise to [0, 1]
    """
    hop     = sr // fps
    n_fft   = 2048
    stft    = librosa.stft(y, n_fft=n_fft, hop_length=hop, center=True)
    mag     = np.abs(stft)                        # (1+n_fft//2, n_stft)
    freqs   = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    n_stft  = mag.shape[1]
    n_frames = int(len(y) / sr * fps)

    # Log-spaced band edges
    edges = np.logspace(np.log10(FMIN), np.log10(FMAX), N_BARS + 1)

    # Aggregate FFT bins into bands
    raw_bands = np.zeros((N_BARS, n_stft))
    for b in range(N_BARS):
        mask = (freqs >= edges[b]) & (freqs < edges[b + 1])
        if mask.any():
            raw_bands[b] = np.mean(mag[mask, :], axis=0)

    # Asymmetric temporal smoothing: fast rise, slow fall
    smoothed = np.zeros((N_BARS, n_frames))
    state    = np.zeros(N_BARS)
    for f in range(n_frames):
        col  = min(f, n_stft - 1)
        raw  = raw_bands[:, col]
        alpha = np.where(raw > state, RISE_ALPHA, FALL_ALPHA)
        state = alpha * raw + (1.0 - alpha) * state
        smoothed[:, f] = state.copy()

    # Fade in/out
    fade_f   = max(1, int(fps * FADE_S))
    ramp_in  = np.linspace(0.0, 1.0, fade_f)
    ramp_out = np.linspace(1.0, 0.0, fade_f)
    smoothed[:, :fade_f]              *= ramp_in
    smoothed[:, n_frames - fade_f:]   *= ramp_out[:n_frames - (n_frames - fade_f)]

    # Global normalise
    peak = np.max(smoothed) + 1e-9
    return smoothed / peak


# ── Frame renderer ────────────────────────────────────────────────────────────
def render_frame(bar_heights, n_lines, spread, max_amp_frac,
                 strip_w, strip_h, scale, line_w, glow_radius, glow_alpha):
    """
    bar_heights : 1-D array (N_BARS,), values in [0, 1]
    Renders a smooth mirrored frequency spectrum with multi-line spread.
    """
    W  = strip_w * scale
    H  = strip_h * scale
    cy = H // 2

    # Spread-aware amplitude cap so outer lines never clip
    spread_factor = 1.0 + (n_lines // 2) * spread
    max_amp = int(strip_h * max_amp_frac / spread_factor) * scale

    # Cubic spline: N_BARS control points → W pixel-wide smooth envelope
    x_src    = np.linspace(0.0, 1.0, len(bar_heights))
    x_dst    = np.linspace(0.0, 1.0, W)
    cs       = CubicSpline(x_src, bar_heights * max_amp, bc_type='not-a-knot')
    envelope = np.clip(cs(x_dst), 0.0, max_amp)   # always ≥ 0

    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lw   = max(1, line_w * scale)

    for i in range(n_lines):
        offset = float(i - n_lines // 2)   # e.g. -2,-1,0,1,2 for 5 lines
        spread_px = offset * envelope * spread

        # Upper half (above center)
        ys_up = cy - (envelope + spread_px)
        ys_up = np.clip(ys_up, 1, cy - 1).astype(np.float32)
        draw.line(list(zip(range(W), ys_up.tolist())),
                  fill=(255, 255, 255, 220), width=lw)

        # Lower half (mirrored below center)
        ys_dn = cy + (envelope + spread_px)
        ys_dn = np.clip(ys_dn, cy + 1, H - 2).astype(np.float32)
        draw.line(list(zip(range(W), ys_dn.tolist())),
                  fill=(255, 255, 255, 220), width=lw)

    small = img.resize((strip_w, strip_h), Image.LANCZOS)

    if glow_radius > 0 and glow_alpha > 0:
        glow  = small.filter(ImageFilter.GaussianBlur(radius=glow_radius))
        g_arr = np.array(glow, dtype=np.float32)
        g_arr[:, :, 3] *= glow_alpha
        glow   = Image.fromarray(g_arr.astype(np.uint8), "RGBA")
        result = Image.alpha_composite(glow, small)
    else:
        result = small

    return result


# ── Main generation ───────────────────────────────────────────────────────────
def generate(audio_path, out_black_mp4, out_webm,
             n_lines=N_LINES, spread=SPREAD, strip_h=STRIP_H,
             fps=FPS, glow_radius=GLOW_RADIUS, glow_alpha=GLOW_ALPHA,
             progress_cb=None):

    strip_w = STRIP_W

    if progress_cb: progress_cb("Loading audio…")
    y, sr    = load_audio(audio_path)
    duration = len(y) / sr
    n_frames = int(duration * fps)
    if progress_cb: progress_cb(f"  {duration:.1f}s  →  {n_frames} frames at {fps}fps")

    if progress_cb: progress_cb("Analysing frequency content…")
    bands = build_band_envelopes(y, sr, fps)   # (N_BARS, n_frames)

    tmpdir = tempfile.mkdtemp(prefix="waveform_")
    try:
        milestones = {int(n_frames * p) for p in (0.25, 0.5, 0.75, 1.0)}
        if progress_cb: progress_cb(f"[1/3] Rendering {n_frames} frames…")

        for f in range(n_frames):
            frame_img = render_frame(
                bands[:, f], n_lines, spread, MAX_AMP_FRAC,
                strip_w, strip_h, SCALE, LINE_W, glow_radius, glow_alpha,
            )
            frame_img.save(os.path.join(tmpdir, f"f{f:06d}.png"))
            if progress_cb and f in milestones:
                pct = int(f / n_frames * 100)
                progress_cb(f"  {pct}% complete ({f}/{n_frames} frames)")

        seq = os.path.join(tmpdir, "f%06d.png")

        if progress_cb: progress_cb("[2/3] Encoding MP4 (black background)…")
        r = subprocess.run([
            "ffmpeg", "-y",
            "-framerate", str(fps), "-i", seq,
            "-vf", "format=rgba,colorchannelmixer=rr=1:gg=1:bb=1:aa=1,"
                   "format=rgb24,pad=iw:ih:0:0:black",
            "-c:v", "libx264", "-crf", "15", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            out_black_mp4,
        ], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("MP4 encode failed:\n" + r.stderr[-400:])

        if progress_cb: progress_cb("[3/3] Encoding WebM (transparent)…")
        r = subprocess.run([
            "ffmpeg", "-y",
            "-framerate", str(fps), "-i", seq,
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-b:v", "0", "-crf", "18", "-auto-alt-ref", "0",
            out_webm,
        ], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("WebM encode failed:\n" + r.stderr[-400:])

        if progress_cb: progress_cb("Done!")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Smooth frequency-spectrum waveform")
    p.add_argument("audio")
    p.add_argument("--lines",  type=int,   default=N_LINES)
    p.add_argument("--spread", type=float, default=SPREAD)
    p.add_argument("--height", type=int,   default=STRIP_H)
    p.add_argument("--fps",    type=int,   default=FPS)
    p.add_argument("--out",    default=None)
    args = p.parse_args()

    if not os.path.isfile(args.audio):
        sys.exit(f"File not found: {args.audio}")

    base  = args.out or os.path.splitext(args.audio)[0]
    black = base + "_waveform_black.mp4"
    webm  = base + "_waveform_transparent.webm"

    generate(args.audio, black, webm,
             n_lines=args.lines, spread=args.spread,
             strip_h=args.height, fps=args.fps,
             progress_cb=print)
    print(f"\n  Black-bg MP4 : {black}")
    print(f"  Transparent  : {webm}")


if __name__ == "__main__":
    main()
