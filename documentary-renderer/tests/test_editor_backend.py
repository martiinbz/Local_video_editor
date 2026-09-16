from __future__ import annotations

import json
from pathlib import Path

import pytest

from editor.backend.project_service import ProjectService, UnsafeMediaPathError


def write_project(root: Path) -> None:
    (root / "project" / "images").mkdir(parents=True)
    (root / "assets" / "music").mkdir(parents=True)
    (root / "assets" / "sfx").mkdir(parents=True)
    (root / "project" / "images" / "scene.jpg").write_bytes(b"image")
    (root / "project" / "narration.mp3").write_bytes(b"voice")
    (root / "assets" / "music" / "score.mp3").write_bytes(b"music")
    (root / "assets" / "sfx" / "hit.wav").write_bytes(b"sfx")
    (root / "private.txt").write_text("not media", encoding="utf-8")
    manifest = {
        "manifest_version": "2.6",
        "voice": "project/narration.mp3",
        "scenes": [
            {
                "scene_id": "SCENE_1",
                "start": 0,
                "end": 2,
                "file": "project/images/scene.jpg",
            }
        ],
    }
    (root / "project" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_load_project_includes_local_media_library(tmp_path: Path) -> None:
    write_project(tmp_path)
    service = ProjectService(tmp_path)

    project = service.load()

    assert project["visualTrack"][0]["sceneId"] == "SCENE_1"
    assert project["files"]["images"] == ["project/images/scene.jpg"]
    assert project["files"]["music"] == ["assets/music/score.mp3"]
    assert project["files"]["sfx"] == ["assets/sfx/hit.wav"]


def test_load_project_includes_audio_library_metadata_and_ambience(tmp_path: Path) -> None:
    write_project(tmp_path)
    (tmp_path / "assets" / "ambience").mkdir(parents=True)
    (tmp_path / "assets" / "ambience" / "room.wav").write_bytes(b"ambience")

    class FakeAnalyzer:
        def metadata(self, path: Path) -> dict:
            return {"duration": 12.5 if path.name == "score.mp3" else 1.25}

    project = ProjectService(tmp_path, audio_analysis=FakeAnalyzer()).load()

    assert project["audioLibrary"]["music"][0] == {
        "path": "assets/music/score.mp3", "name": "score.mp3", "duration": 12.5, "type": "music"
    }
    assert project["audioLibrary"]["ambience"][0]["path"] == "assets/ambience/room.wav"
    assert project["audioLibrary"]["sfx"][0]["duration"] == 1.25
    assert project["narrationTrack"]["sourceDuration"] == 1.25


def test_named_project_uses_shared_root_assets(tmp_path: Path) -> None:
    (tmp_path / "projects" / "episodio-02").mkdir(parents=True)
    (tmp_path / "projects" / "episodio-02" / "manifest.json").write_text(
        json.dumps({
            "manifest_version": "2.6",
            "scenes": [{"scene_id": "SCENE_1", "start": 0, "end": 1, "file": "project/images/scene.jpg"}],
        }), encoding="utf-8"
    )
    (tmp_path / "projects" / "episodio-02" / "project" / "images").mkdir(parents=True)
    (tmp_path / "projects" / "episodio-02" / "project" / "images" / "scene.jpg").write_bytes(b"image")
    (tmp_path / "assets" / "music").mkdir(parents=True)
    (tmp_path / "assets" / "music" / "shared.mp3").write_bytes(b"music")
    (tmp_path / "projects" / "episodio-02" / "assets" / "music").mkdir(parents=True)
    (tmp_path / "projects" / "episodio-02" / "assets" / "music" / "local.mp3").write_bytes(b"music")

    project = ProjectService(tmp_path, project_name="episodio-02").load()

    assert project["files"]["music"] == ["assets/music/shared.mp3"]


def test_episode_6_autosave_uses_an_allowed_project_subtitle() -> None:
    root = Path(__file__).parents[1]
    service = ProjectService(root, project_name="6.cryptospain")

    project = service.load()

    assert project["subtitleFile"] == "project/subtitles/srt.srt"
    assert service.save(project).is_file()


def test_master_manifest_uses_legacy_images_and_root_narration(tmp_path: Path) -> None:
    project_root = tmp_path / "projects" / "ep3"
    (project_root / "images").mkdir(parents=True)
    (project_root / "images" / "SCENE_1.jpg").write_bytes(b"image")
    (project_root / "narration.mp3").write_bytes(b"voice")
    (project_root / "manifest.json").write_text(json.dumps({
        "manifest_type": "MASTER_MANIFEST",
        "project": {"duration_seconds": 8.99},
        "scenes": [{
            "scene_id": "SCENE_001", "duration_seconds": 8.99,
            "file": "project/real/SCENE_001_REAL.jpg",
            "flow_file": "project/images/SCENE_001.jpg",
        }],
    }), encoding="utf-8")

    service = ProjectService(tmp_path, project_name="ep3")
    project = service.load()

    assert project["narrationTrack"]["file"] == "narration.mp3"
    assert project["visualTrack"][0]["file"] == "project/images/SCENE_001.jpg"
    assert service.resolve_media(project["visualTrack"][0]["file"]) == project_root / "images" / "SCENE_1.jpg"


def test_save_writes_editor_copy_without_overwriting_source(tmp_path: Path) -> None:
    write_project(tmp_path)
    service = ProjectService(tmp_path)
    project = service.load()
    project["visualTrack"][0]["duration"] = 3.5

    destination = service.save(project)

    original = json.loads((tmp_path / "project" / "manifest.json").read_text(encoding="utf-8"))
    edited = json.loads(destination.read_text(encoding="utf-8"))
    assert destination == tmp_path / "project" / "manifest.editor.json"
    assert original["scenes"][0]["end"] == 2
    assert edited["scenes"][0]["end"] == 3.5


def test_resolve_media_allows_only_existing_files_in_project_root(tmp_path: Path) -> None:
    write_project(tmp_path)
    service = ProjectService(tmp_path)

    assert service.resolve_media("project/images/scene.jpg") == tmp_path / "project" / "images" / "scene.jpg"

    with pytest.raises(UnsafeMediaPathError):
        service.resolve_media("../secret.txt")
    with pytest.raises(UnsafeMediaPathError):
        service.resolve_media("project/images/missing.jpg")
    with pytest.raises(UnsafeMediaPathError):
        service.resolve_media("private.txt")
