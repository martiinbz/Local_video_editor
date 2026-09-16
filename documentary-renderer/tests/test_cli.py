from __future__ import annotations

from pathlib import Path

import render


def test_cli_uses_manifest_renderer_when_v2_flag_is_set(monkeypatch, tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    called: dict[str, Path] = {}

    class FakeRenderer:
        def __init__(self, logger=None) -> None:
            pass

        def render_manifest(self, path: Path) -> Path:
            called["path"] = path
            return tmp_path / "out.mp4"

    monkeypatch.setattr(render, "DocumentaryRenderer", FakeRenderer)

    result = render.main(["--v2", str(manifest)])

    assert result == 0
    assert called["path"] == manifest
