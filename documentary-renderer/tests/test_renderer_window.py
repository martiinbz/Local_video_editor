from __future__ import annotations

import json
from pathlib import Path

from renderer import DocumentaryRenderer


def test_window_advances_narration_source_to_requested_timeline_time(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "output": "output/full.mp4",
        "audio_duration_seconds": 300,
        "narration_clip": {
            "file": "narration.mp3", "timeline_start": 0,
            "source_in": 10, "source_out": 310, "volume": 1,
        },
        "scenes": [{"scene_id": "SCENE_1", "duration": 300}],
    }), encoding="utf-8")
    captured = {}
    renderer = DocumentaryRenderer()

    def capture(path, ignore_qc=False):
        captured.update(json.loads(Path(path).read_text(encoding="utf-8")))
        return tmp_path / "preview.mp4"

    monkeypatch.setattr(renderer, "render_manifest", capture)
    renderer.render_manifest_window(manifest, tmp_path / "preview.mp4", start=120, duration=12)

    assert captured["narration_clip"] == {
        "file": "narration.mp3", "timeline_start": 0,
        "source_in": 130, "source_out": 142, "volume": 1,
    }
