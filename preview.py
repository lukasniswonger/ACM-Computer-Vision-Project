"""
Builds a preview video with sound: the annotated video plus the sonification, rendered offline
by SuperCollider so every sound lands exactly on its frame, combined with ffmpeg.
"""
import json
import os
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_SCRIPT = os.path.join(HERE, "supercollider", "render_score.scd")
DEFAULT_SCLANG = "/Applications/SuperCollider.app/Contents/MacOS/sclang"
LOCAL_FFMPEG = os.path.join(HERE, "bin", "ffmpeg")  # optional project-local copy
TAIL_SECONDS = 2.0  # let the last sounds fade out


def _sc_literal(value):
    if isinstance(value, str):
        return json.dumps(value)  # a JSON string is also a valid SuperCollider string
    if isinstance(value, float):
        return f"{value:.5f}"
    return str(value)


def write_score(score, path):
    """Write (video_time, address, args) messages as a SuperCollider array that render_score.scd reads."""
    rows = []
    for t, address, args in score:
        rows.append("  [" + ", ".join(_sc_literal(v) for v in [float(t), address, *args]) + "]")
    with open(path, "w") as f:
        f.write("[\n" + ",\n".join(rows) + "\n]\n")


def render_audio(score_path, wav_path, duration, sclang):
    result = subprocess.run(
        [sclang, RENDER_SCRIPT, score_path, wav_path, str(duration + TAIL_SECONDS)],
        capture_output=True, text=True, timeout=900,
    )
    if not os.path.exists(wav_path):
        raise RuntimeError("SuperCollider did not render the audio:\n" + (result.stdout + result.stderr)[-2000:])


def combine(video_path, wav_path, out_path, ffmpeg):
    """High-quality H.264 + AAC, trimmed to the video's length, playable everywhere."""
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error",
         "-i", video_path, "-i", wav_path,
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
         # The synths are mixed quietly to leave headroom live; bring the preview up to streaming loudness
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000",
         "-c:a", "aac", "-b:a", "256k",
         "-shortest", "-movflags", "+faststart",
         out_path],
        check=True,
    )


def build_preview(score, video_path, output_dir, duration, sclang=None, ffmpeg=None):
    sclang = sclang or DEFAULT_SCLANG
    ffmpeg = ffmpeg or shutil.which("ffmpeg") or (LOCAL_FFMPEG if os.path.exists(LOCAL_FFMPEG) else None)
    if not os.path.exists(sclang):
        raise RuntimeError(f"sclang not found at {sclang} (install SuperCollider or pass --sclang)")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found (install it, put it in bin/, or pass --ffmpeg)")

    score_path = os.path.join(output_dir, "score.scd")
    wav_path = os.path.join(output_dir, "sonification.wav")
    out_path = os.path.join(output_dir, "preview.mp4")

    write_score(score, score_path)
    print(f"Rendering audio ({len(score)} events)...")
    render_audio(score_path, wav_path, duration, sclang)
    print("Combining video and audio...")
    combine(video_path, wav_path, out_path, ffmpeg)
    return out_path
