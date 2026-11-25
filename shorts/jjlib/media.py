"""ffmpeg probing and Shorts rendering.

Renders in two stages so that arbitrary phone footage concatenates cleanly:

  1. Every source (video or still) becomes a normalised segment — 1080x1920,
     30fps, yuv420p, AAC stereo — with the persistent title overlay burned in.
  2. Segments plus the end card are joined with the concat demuxer, which is
     lossless and fast precisely because stage 1 made the parameters identical.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

W, H, FPS = 1080, 1920, 30
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".hevc", ".3gp"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp"}

# Shared encoder settings. Every segment must agree for concat to work.
VCODEC = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
          "-profile:v", "high", "-level", "4.1", "-r", str(FPS), "-g", str(FPS * 2)]
ACODEC = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


class FFmpegMissing(RuntimeError):
    pass


def require_ffmpeg() -> None:
    missing = [b for b in ("ffmpeg", "ffprobe") if not shutil.which(b)]
    if missing:
        raise FFmpegMissing(
            f"{' and '.join(missing)} not found on PATH.\n"
            "  macOS:  brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: winget install Gyan.FFmpeg"
        )


@dataclass
class Probe:
    path: Path
    is_video: bool
    duration: float
    has_audio: bool
    width: int
    height: int

    @property
    def is_portrait(self) -> bool:
        return self.height >= self.width


def probe(path: Path) -> Probe:
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        out = _run_json(["-select_streams", "v:0", "-show_streams", str(path)])
        st = (out.get("streams") or [{}])[0]
        return Probe(path, False, 0.0, False, int(st.get("width", 0)), int(st.get("height", 0)))

    out = _run_json(["-show_streams", "-show_format", str(path)])
    streams = out.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"{path.name}: no video stream")
    duration = float(out.get("format", {}).get("duration") or video.get("duration") or 0)
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    # A rotation side-data tag means the stored frame is transposed relative to
    # how it should display; ffmpeg auto-rotates on decode, so swap here to match.
    if _rotation(video) in (90, 270):
        width, height = height, width
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return Probe(path, True, duration, has_audio, width, height)


def _rotation(stream: dict) -> int:
    tag = (stream.get("tags") or {}).get("rotate")
    if tag:
        return abs(int(float(tag))) % 360
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            return abs(int(float(side["rotation"]))) % 360
    return 0


def _run_json(args: list[str]) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "ffprobe failed")
    return json.loads(proc.stdout or "{}")


def _run(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr.strip()[-3000:]}")


def _fit_filter(label_in: str, label_out: str) -> str:
    """Fit the source inside the frame over a blurred, darkened copy of itself.

    Portrait footage fills the frame and the backdrop never shows; square and
    landscape footage gets a backdrop instead of black bars.
    """
    return (
        f"[{label_in}]split=2[bgsrc][fgsrc];"
        f"[bgsrc]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},gblur=sigma=32,eq=brightness=-0.10:saturation=1.15[bg];"
        f"[fgsrc]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[{label_out}]"
    )


def render_video_segment(
    src: Path, overlay_png: Path, dest: Path, max_seconds: float, mute: bool
) -> None:
    p = probe(src)
    args = ["-i", str(src), "-i", str(overlay_png)]
    chain = [
        "[0:v]" + f"trim=0:{max_seconds},setpts=PTS-STARTPTS[t]",
        _fit_filter("t", "base"),
        f"[base][1:v]overlay=0:0:format=auto,format=yuv420p,fps={FPS}[v]",
    ]
    maps = ["-map", "[v]"]

    tail: list[str] = []
    if p.has_audio and not mute:
        chain.append(
            f"[0:a]atrim=0:{max_seconds},asetpts=PTS-STARTPTS,"
            "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]"
        )
        maps += ["-map", "[a]"]
    else:
        # The silent track is generated at full target length because we do not
        # know the source duration inside the filter graph. -shortest then ends
        # the output with the video, so a 5s clip does not become 20s of frozen
        # frame with silence running underneath it.
        args += ["-f", "lavfi", "-t", str(max_seconds), "-i",
                 "anullsrc=channel_layout=stereo:sample_rate=48000"]
        maps += ["-map", "2:a"]
        tail = ["-shortest"]

    _run([*args, "-filter_complex", ";".join(chain), *maps,
          "-t", str(max_seconds), *VCODEC, *ACODEC, *tail, str(dest)])


def render_still_segment(
    src: Path, overlay_png: Path, dest: Path, seconds: float
) -> None:
    """Ken Burns push on a still.

    The image is fed in as a single frame — not `-loop 1` — because zoompan's
    `d` is frames emitted *per input frame*. Looping the input as well would
    multiply the two and emit thousands of frames. It is also upscaled first,
    since zoompan samples at the input resolution and looks steppy otherwise.
    """
    frames = max(int(seconds * FPS), 1)
    chain = [
        f"[0:v]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
        f"crop={W * 2}:{H * 2},setsar=1,"
        f"zoompan=z='min(zoom+0.00045,1.16)':d={frames}:x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[kb]",
        # overlay's default eof_action=repeat holds the single overlay frame
        # for the whole clip.
        "[kb][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
    ]
    _run([
        "-i", str(src),
        "-i", str(overlay_png),
        "-f", "lavfi", "-t", str(seconds), "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex", ";".join(chain),
        "-map", "[v]", "-map", "2:a", "-t", str(seconds), *VCODEC, *ACODEC, str(dest),
    ])


def render_end_card(png: Path, dest: Path, seconds: float = 2.5) -> None:
    _run([
        "-loop", "1", "-t", str(seconds), "-i", str(png),
        "-f", "lavfi", "-t", str(seconds), "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex",
        f"[0:v]scale={W}:{H},fade=t=in:st=0:d=0.35,format=yuv420p,fps={FPS}[v]",
        "-map", "[v]", "-map", "1:a", "-t", str(seconds), *VCODEC, *ACODEC, str(dest),
    ])


def concat(segments: list[Path], dest: Path, music: Path | None = None) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        for seg in segments:
            fh.write(f"file '{seg.resolve().as_posix()}'\n")
        listfile = Path(fh.name)
    try:
        if music is None:
            _run(["-f", "concat", "-safe", "0", "-i", str(listfile),
                  "-c", "copy", "-movflags", "+faststart", str(dest)])
        else:
            # Duck the music under any original audio rather than replacing it.
            _run([
                "-f", "concat", "-safe", "0", "-i", str(listfile),
                "-stream_loop", "-1", "-i", str(music),
                "-filter_complex",
                "[1:a]volume=0.18[bed];[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", *ACODEC,
                "-movflags", "+faststart", "-shortest", str(dest),
            ])
    finally:
        listfile.unlink(missing_ok=True)


def duration_of(path: Path) -> float:
    return probe(path).duration
