"""Small strict-enough SRT parser for the local editor."""

from __future__ import annotations

import re
from pathlib import Path


class SrtParseError(ValueError):
    """Raised when an SRT cue cannot be normalized."""


_TIMING = re.compile(
    r"^(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})(?:\s+.*)?$"
)


def _seconds(parts: tuple[str, str, str, str]) -> float:
    hours, minutes, seconds, millis = (int(value) for value in parts)
    if minutes > 59 or seconds > 59:
        raise SrtParseError("SRT timestamp contains an invalid minute or second")
    return round(hours * 3600 + minutes * 60 + seconds + millis / 1000, 3)


def parse_srt(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    blocks = re.split(r"\n\s*\n", text.strip()) if text.strip() else []
    cues: list[dict[str, object]] = []
    for block_index, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.split("\n")]
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), -1)
        if timing_index < 0:
            raise SrtParseError(f"SRT cue {block_index} is missing a timing line")
        match = _TIMING.match(lines[timing_index].strip())
        if not match:
            raise SrtParseError(f"SRT cue {block_index} has an invalid timestamp")
        start = _seconds(match.groups()[:4])
        end = _seconds(match.groups()[4:])
        if end <= start:
            raise SrtParseError(f"SRT cue {block_index} end must be greater than start")
        caption = "\n".join(lines[timing_index + 1 :]).strip()
        if not caption:
            raise SrtParseError(f"SRT cue {block_index} has no text")
        cues.append({"id": f"subtitle-{len(cues) + 1}", "start": start, "end": end, "text": caption})
    return cues
