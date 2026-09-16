from __future__ import annotations

import ffmpeg_builder
from ffmpeg_builder import FFmpegBuilder


def test_run_uses_resolved_ffmpeg_path(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(ffmpeg_builder, "resolve_ffmpeg_executable", lambda: r"C:\tools\ffmpeg.exe")

    def fake_run(command, check):
        captured["command"] = command
        captured["check"] = check

    monkeypatch.setattr(ffmpeg_builder.subprocess, "run", fake_run)

    FFmpegBuilder().run(["ffmpeg", "-y", "input.mp4", "output.mp4"])

    assert captured["command"] == [r"C:\tools\ffmpeg.exe", "-y", "input.mp4", "output.mp4"]
    assert captured["check"] is True
