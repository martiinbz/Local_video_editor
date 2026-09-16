"""Small filesystem and media helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from constants import FFPROBE_EXECUTABLE
from exceptions import FFmpegError
from ffmpeg_runtime import resolve_ffprobe_executable


def ensure_parent_dir(path: Path) -> None:
    """Create the parent directory for a path if needed."""

    path.parent.mkdir(parents=True, exist_ok=True)


def as_posix_for_ffmpeg(path: Path) -> str:
    """Return a path string that FFmpeg concat files can read reliably."""

    return path.resolve().as_posix().replace("'", "'\\''")


def probe_media_duration(path: Path) -> float:
    """Return media duration in seconds using ffprobe."""

    command = [
        resolve_ffprobe_executable() if FFPROBE_EXECUTABLE == "ffprobe" else FFPROBE_EXECUTABLE,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise FFmpegError("ffprobe executable was not found on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise FFmpegError(f"ffprobe failed for {path}: {exc.stderr.strip()}") from exc

    try:
        payload = json.loads(completed.stdout)
        return float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise FFmpegError(f"Could not read duration for {path}.") from exc


def seconds(value: float) -> str:
    """Format a duration for FFmpeg without unnecessary noise."""

    rounded = round(float(value), 6)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.6f}".rstrip("0").rstrip(".")
