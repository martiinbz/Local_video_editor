from __future__ import annotations

from pathlib import Path

import pytest

from editor.backend.srt_parser import SrtParseError, parse_srt


def test_parse_srt_accepts_irregular_numbers_and_multiline_text(tmp_path: Path) -> None:
    source = tmp_path / "captions.srt"
    source.write_text(
        "7\n00:00:01,250 --> 00:00:03,500\nPrimera linea\nSegunda linea\n\n"
        "12\n00:00:04.000 --> 00:00:05.100\nFinal\n",
        encoding="utf-8",
    )

    cues = parse_srt(source)

    assert cues == [
        {"id": "subtitle-1", "start": 1.25, "end": 3.5, "text": "Primera linea\nSegunda linea"},
        {"id": "subtitle-2", "start": 4.0, "end": 5.1, "text": "Final"},
    ]


def test_parse_srt_rejects_invalid_time_ranges(tmp_path: Path) -> None:
    source = tmp_path / "broken.srt"
    source.write_text("1\n00:00:03,000 --> 00:00:02,000\nNope\n", encoding="utf-8")

    with pytest.raises(SrtParseError, match="greater"):
        parse_srt(source)
