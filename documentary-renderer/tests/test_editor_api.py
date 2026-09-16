from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from editor.backend.app import create_app
from editor.backend.render_manager import RenderManager


def create_fixture(root: Path) -> None:
    (root / "project" / "images").mkdir(parents=True)
    (root / "project" / "images" / "scene.jpg").write_bytes(b"jpeg")
    (root / "project" / "manifest.json").write_text(
        json.dumps(
            {
                "manifest_version": "2.6",
                "scenes": [
                    {
                        "scene_id": "SCENE_1",
                        "start": 0,
                        "end": 2,
                        "file": "project/images/scene.jpg",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_project_save_and_media_endpoints(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    client = TestClient(create_app(tmp_path))

    project_response = client.get("/api/project")
    assert project_response.status_code == 200
    project = project_response.json()
    assert project["visualTrack"][0]["duration"] == 2

    project["visualTrack"][0]["duration"] = 3
    save_response = client.post("/api/project/save", json=project)
    assert save_response.status_code == 200
    assert save_response.json()["path"] == "project/manifest.editor.json"

    media_response = client.get("/api/media", params={"path": "project/images/scene.jpg"})
    assert media_response.status_code == 200
    assert media_response.content == b"jpeg"
    assert "no-store" in media_response.headers["cache-control"]


def test_media_endpoint_rejects_traversal(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    client = TestClient(create_app(tmp_path))

    response = client.get("/api/media", params={"path": "../secret.txt"})

    assert response.status_code == 400


def test_media_endpoint_uses_the_requested_project_not_the_active_project(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    for project_id, contents in (("first", b"first-image"), ("second", b"second-image")):
        image_dir = tmp_path / "projects" / project_id / "project" / "images"
        image_dir.mkdir(parents=True)
        (image_dir / "scene.jpg").write_bytes(contents)
        (image_dir.parent / "manifest.json").write_text(json.dumps({
            "manifest_version": "2.6",
            "scenes": [{"scene_id": "SCENE_1", "start": 0, "end": 1, "file": "project/images/scene.jpg"}],
        }), encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    client.get("/api/project", params={"project": "second"})
    first = client.get("/api/media", params={"path": "project/images/scene.jpg", "project": "first"})
    second = client.get("/api/media", params={"path": "project/images/scene.jpg", "project": "second"})

    assert first.content == b"first-image"
    assert second.content == b"second-image"


def test_waveform_endpoint_validates_path_and_point_range(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    (tmp_path / "project" / "narration.mp3").write_bytes(b"audio")

    class FakeAudioAnalysis:
        def waveform(self, path: Path, points: int) -> dict:
            return {"duration": 2.0, "points": points, "peaks": [[-0.5, 0.5]] * points}

    client = TestClient(create_app(tmp_path, audio_analysis=FakeAudioAnalysis()))

    response = client.get("/api/audio/waveform", params={"path": "project/narration.mp3", "points": 256})
    image = client.get("/api/audio/waveform", params={"path": "project/images/scene.jpg", "points": 256})
    traversal = client.get("/api/audio/waveform", params={"path": "../voice.mp3", "points": 256})
    invalid_points = client.get("/api/audio/waveform", params={"path": "project/images/scene.jpg", "points": 12})

    assert response.status_code == 200
    assert len(response.json()["peaks"]) == 256
    assert image.status_code == 400
    assert traversal.status_code == 400
    assert invalid_points.status_code == 422


def test_subtitle_and_font_endpoints_are_safe(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    (tmp_path / "project" / "subtitles").mkdir()
    (tmp_path / "assets" / "fonts").mkdir(parents=True)
    (tmp_path / "project" / "subtitles" / "episode.srt").write_text(
        "1\n00:00:00,500 --> 00:00:02,000\nHola\n", encoding="utf-8"
    )
    (tmp_path / "assets" / "fonts" / "Editorial.ttf").write_bytes(b"font")
    client = TestClient(create_app(tmp_path))

    assert client.get("/api/project/subtitles").json() == [
        {"path": "project/subtitles/episode.srt", "name": "episode.srt"}
    ]
    parsed = client.get("/api/subtitles", params={"path": "project/subtitles/episode.srt"})
    assert parsed.json()["cues"][0]["text"] == "Hola"
    assert client.get("/api/fonts").json()[0]["family"] == "Editorial"
    assert client.get("/api/fonts/file", params={"path": "assets/fonts/Editorial.ttf"}).status_code == 200
    assert client.get("/api/subtitles", params={"path": "../outside.srt"}).status_code == 400
    assert client.get("/api/fonts/file", params={"path": "project/images/scene.jpg"}).status_code == 400


def test_save_rejects_font_references_outside_assets(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    client = TestClient(create_app(tmp_path))
    project = client.get("/api/project").json()
    project["textTracks"] = [{
        "id": "track-1", "name": "Texto 1", "overlays": [{
            "id": "text-1", "text": "No", "start": 0, "end": 1,
            "font": "../private.ttf",
        }],
    }]

    response = client.post("/api/project/save", json=project)

    assert response.status_code == 422
    assert "font" in response.json()["detail"].lower()


def test_save_allows_missing_shared_font_as_renderer_fallback(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    (tmp_path / "assets" / "fonts").mkdir(parents=True)
    client = TestClient(create_app(tmp_path))
    project = client.get("/api/project").json()
    project["textTracks"] = [{
        "id": "track-1", "name": "Texto 1", "overlays": [{
            "id": "text-1", "text": "Fallback", "start": 0, "end": 1,
            "font": "assets/fonts/old-web-font.woff",
        }],
    }]

    response = client.post("/api/project/save", json=project)

    assert response.status_code == 200


def test_render_endpoint_saves_project_then_starts_render(tmp_path: Path) -> None:
    create_fixture(tmp_path)
    calls: list[Path] = []

    class FakeRenderManager:
        def start(self, manifest_path: Path) -> bool:
            calls.append(manifest_path)
            return True

        def status(self) -> dict:
            return {"state": "rendering", "logs": []}

    client = TestClient(create_app(tmp_path, render_manager=FakeRenderManager()))
    project = client.get("/api/project").json()

    response = client.post("/api/project/render", json=project)

    assert response.status_code == 202
    assert calls == [tmp_path / "project" / "manifest.editor.json"]


def test_render_manager_captures_process_log_and_success(tmp_path: Path) -> None:
    script = tmp_path / "render.py"
    manifest = tmp_path / "manifest.json"
    script.write_text("import sys\nprint('render complete ' + ' '.join(sys.argv[1:]))", encoding="utf-8")
    manifest.write_text("{}", encoding="utf-8")
    manager = RenderManager(tmp_path)

    assert manager.start(manifest) is True
    for _ in range(100):
        status = manager.status()
        if status["state"] != "rendering":
            break
        time.sleep(0.01)

    assert status["state"] == "success"
    assert any("render complete" in line for line in status["logs"])
    assert any("--ignore-qc" in line for line in status["logs"])


def test_render_manager_uses_renderer_root_for_named_project(tmp_path: Path) -> None:
    renderer_root = tmp_path / "renderer"
    project_root = renderer_root / "projects" / "episode-01"
    renderer_root.mkdir(parents=True)
    project_root.mkdir(parents=True)
    (renderer_root / "render.py").write_text("print('root render complete')", encoding="utf-8")
    manifest = project_root / "manifest.editor.json"
    manifest.write_text("{}", encoding="utf-8")

    manager = RenderManager(project_root, renderer_root=renderer_root)

    assert manager.start(manifest) is True
    for _ in range(100):
        status = manager.status()
        if status["state"] != "rendering":
            break
        time.sleep(0.01)

    assert status["state"] == "success"
    assert any("root render complete" in line for line in status["logs"])
