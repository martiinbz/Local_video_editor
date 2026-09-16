"""Locate the FFmpeg tools used by the renderer."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_ffmpeg_executable() -> str:
    """Return an executable path for FFmpeg, or raise a clear error."""

    return _resolve_tool("ffmpeg", "FFMPEG_PATH")


def resolve_ffprobe_executable() -> str:
    """Return an executable path for FFprobe, or raise a clear error."""

    return _resolve_tool("ffprobe", "FFPROBE_PATH")


def _resolve_tool(name: str, environment_variable: str) -> str:
    explicit_path = os.environ.get(environment_variable)
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.is_file():
            return str(path.resolve())
        raise FileNotFoundError(
            f"{environment_variable} points to a file that does not exist: {explicit_path}"
        )

    path_from_environment = shutil.which(name)
    if path_from_environment:
        return str(Path(path_from_environment).resolve())

    renderer_root = Path(__file__).resolve().parent
    local_candidates = (
        renderer_root / "tools" / f"{name}.exe",
        renderer_root / "bin" / f"{name}.exe",
        renderer_root / "tools" / name,
        renderer_root / "bin" / name,
    )
    for candidate in local_candidates:
        if candidate.is_file():
            return str(candidate.resolve())

    raise FileNotFoundError(
        f"{name} was not found. Install FFmpeg or set {environment_variable} "
        f"to the full path of {name}.exe."
    )
