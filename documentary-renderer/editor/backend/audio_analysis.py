"""FFmpeg-backed audio metadata and cached waveform extraction."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from array import array
from pathlib import Path
from typing import Any


class AudioAnalysisError(RuntimeError):
    """Raised when ffprobe or FFmpeg cannot analyze an audio file."""


class AudioAnalysisService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def metadata(self, path: Path) -> dict[str, Any]:
        command = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise AudioAnalysisError(result.stderr.strip() or f"Could not inspect {path.name}")
        try:
            duration = float(json.loads(result.stdout)["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AudioAnalysisError(f"Audio duration unavailable for {path.name}") from exc
        return {"duration": round(duration, 6)}

    def waveform(self, path: Path, points: int = 4096) -> dict[str, Any]:
        cache_path = self._cache_path(path, points)
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        metadata = self.metadata(path)
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise AudioAnalysisError(result.stderr.decode("utf-8", errors="replace").strip() or "Waveform extraction failed")
        samples = array("f")
        samples.frombytes(result.stdout)
        if sys.byteorder != "little":
            samples.byteswap()
        peak = max((abs(value) for value in samples), default=1.0) or 1.0
        pairs: list[list[float]] = []
        sample_count = len(samples)
        for index in range(points):
            start = index * sample_count // points
            end = max(start + 1, (index + 1) * sample_count // points)
            bucket = samples[start:min(end, sample_count)] if sample_count else [0.0]
            pairs.append([round(min(bucket) / peak, 4), round(max(bucket) / peak, 4)])
        payload = {"duration": metadata["duration"], "points": points, "peaks": pairs}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        return payload

    def _cache_path(self, path: Path, points: int) -> Path:
        stat = path.stat()
        signature = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{points}"
        digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"
