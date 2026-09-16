from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from editor.backend.manifest_adapter import (
    ManifestValidationError,
    editor_project_from_manifest,
    manifest_from_editor_project,
)


def sample_manifest() -> dict:
    return {
        "manifest_version": "2.6",
        "project_title": "Test project",
        "voice": "project/narration.mp3",
        "audio_duration_seconds": 8.5,
        "custom_top_level": {"keep": True},
        "music_cues": [{"file": "assets/music/background.mp3", "start": 0, "end": 8.5}],
        "ambience_cues": [{"file": "assets/ambience/room.mp3", "start": 1, "end": 4}],
        "scenes": [
            {
                "scene_id": "SCENE_1",
                "start": 0,
                "end": 3.25,
                "file": "project/images/SCENE_1.jpg",
                "beat": "Opening",
                "unknown_scene_field": "preserve me",
                "sfx": [{"file": "assets/sfx/hit.mp3", "at": 1.2}],
            },
            {
                "scene_id": "SCENE_2",
                "duration": 2.75,
                "flow_file": "project/images/SCENE_2.jpg",
                "motion": "zoom_in",
            },
        ],
    }


def test_normalizes_timeline_tracks_and_defaults() -> None:
    project = editor_project_from_manifest(sample_manifest())

    assert project["duration"] == 6.0
    assert project["visualTrack"][0]["duration"] == 3.25
    assert project["visualTrack"][1]["start"] == 3.25
    assert project["visualTrack"][1]["end"] == 6.0
    assert project["visualTrack"][0]["motion"] == "static"
    assert project["visualTrack"][0]["transition"] == "hard_cut"
    assert project["visualTrack"][0]["crop"] == "wide"
    assert project["narrationTrack"]["file"] == "project/narration.mp3"
    assert project["musicTrack"][0]["end"] == 8.5
    assert project["ambienceTrack"][0]["start"] == 1
    assert project["sfxTrack"][0]["sceneId"] == "SCENE_1"


def test_round_trips_project_dimensions_for_vertical_shorts() -> None:
    manifest = sample_manifest() | {"width": 1080, "height": 1920}

    project = editor_project_from_manifest(manifest)
    exported = manifest_from_editor_project(project)

    assert (project["width"], project["height"]) == (1080, 1920)
    assert (exported["width"], exported["height"]) == (1080, 1920)


def test_export_recalculates_following_times_and_preserves_unknown_fields() -> None:
    original = sample_manifest()
    project = editor_project_from_manifest(deepcopy(original))
    project["visualTrack"][0]["duration"] = 4.0
    project["visualTrack"][0]["motion"] = "pan_left"

    exported = manifest_from_editor_project(project)

    assert exported["custom_top_level"] == {"keep": True}
    assert exported["scenes"][0]["unknown_scene_field"] == "preserve me"
    assert exported["scenes"][0]["start"] == 0
    assert exported["scenes"][0]["end"] == 4.0
    assert exported["scenes"][0]["motion"] == "pan_left"
    assert exported["scenes"][1]["start"] == 4.0
    assert exported["scenes"][1]["end"] == 6.75
    assert exported["audio_duration_seconds"] == 6.75


def test_export_keeps_scene_metadata_when_scenes_are_reordered_or_added() -> None:
    project = editor_project_from_manifest(sample_manifest())
    first, second = project["visualTrack"]
    project["visualTrack"] = [
        {**second, "duration": 2.75},
        {
            "id": "SCENE_3", "sceneId": "SCENE_3", "duration": 5,
            "file": "assets/images/new-evidence.jpg", "flowFile": "assets/images/new-evidence.jpg",
            "motion": "static", "motionSpeed": 0.5, "crop": "wide", "focalPoint": [0.5, 0.5],
            "transition": "hard_cut", "transitionDuration": 0.5, "keyframes": [], "effects": [],
        },
        {**first, "duration": 3.25},
    ]

    exported = manifest_from_editor_project(project)

    assert [scene["scene_id"] for scene in exported["scenes"]] == ["SCENE_2", "SCENE_3", "SCENE_1"]
    assert exported["scenes"][0]["motion"] == "zoom_in"
    assert exported["scenes"][2]["unknown_scene_field"] == "preserve me"
    assert exported["scenes"][1]["file"] == "assets/images/new-evidence.jpg"
    assert [(scene["start"], scene["end"]) for scene in exported["scenes"]] == [(0.0, 2.75), (2.75, 7.75), (7.75, 11.0)]


def test_rejects_invalid_scene_duration() -> None:
    project = editor_project_from_manifest(sample_manifest())
    project["visualTrack"][0]["duration"] = 0

    with pytest.raises(ManifestValidationError, match="duration"):
        manifest_from_editor_project(project)


def test_rejects_manifest_without_scenes() -> None:
    with pytest.raises(ManifestValidationError, match="scenes"):
        editor_project_from_manifest({"manifest_version": "2.6"})


def test_accepts_master_manifest_duration_seconds() -> None:
    project = editor_project_from_manifest({
        "manifest_version": "2.0",
        "scenes": [{
            "scene_id": "SCENE_001",
            "duration_seconds": 8.99,
            "file": "project/images/SCENE_001.jpg",
        }],
    })

    assert project["visualTrack"][0]["duration"] == 8.99
    assert project["duration"] == 8.99


def test_episode_6_manifest_uses_numeric_scene_timing_and_local_assets() -> None:
    manifest_path = Path(__file__).parents[1] / "projects" / "6.cryptospain" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    project = editor_project_from_manifest(manifest)

    assert len(project["visualTrack"]) == 151
    assert project["visualTrack"][0]["duration"] == 4.39
    assert project["visualTrack"][0]["file"] == "images/SCENE_1.jpg"
    assert project["narrationTrack"]["file"] == "narration.mp3"


def test_short_6s_manifests_cover_their_narration_with_local_scene_images() -> None:
    root = Path(__file__).parents[1]
    for short_name in ("6S1", "6S2"):
        project_root = root / "projects" / short_name
        manifest_paths = [project_root / "manifest.json"]
        editor_manifest = project_root / "manifest.editor.json"
        if editor_manifest.is_file():
            manifest_paths.append(editor_manifest)

        for manifest_path in manifest_paths:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            project = editor_project_from_manifest(manifest)

            assert len(project["visualTrack"]) == 6
            assert project["narrationTrack"]["file"] == "narration.mp3"
            assert project["duration"] == manifest["audio_duration_seconds"]
            assert all(scene["duration"] > 0 for scene in project["visualTrack"])
            assert all((project_root / scene["file"]).is_file() for scene in project["visualTrack"])


def test_normalizes_and_exports_editable_narration_without_changing_scenes() -> None:
    manifest = sample_manifest()
    manifest["voice_volume"] = 0.9
    manifest["narration_clip"] = {
        "file": "project/narration.mp3",
        "timeline_start": 1.5,
        "source_in": 2.0,
        "source_out": 7.0,
        "volume": 0.8,
        "custom": "keep",
    }
    project = editor_project_from_manifest(manifest)
    original_scene_times = [(scene["start"], scene["end"]) for scene in project["visualTrack"]]

    assert project["narrationTrack"] == {
        "id": "narration", "type": "narration", "file": "project/narration.mp3",
        "start": 1.5, "sourceIn": 2.0, "sourceOut": 7.0, "duration": 5.0, "end": 6.5, "volume": 0.8,
    }

    project["narrationTrack"].update({"start": 3.0, "sourceIn": 2.5, "sourceOut": 6.0, "volume": 0.7})
    exported = manifest_from_editor_project(project)

    assert exported["narration_clip"] == {
        "file": "project/narration.mp3", "timeline_start": 3.0, "source_in": 2.5,
        "source_out": 6.0, "volume": 0.7, "custom": "keep",
    }
    assert exported["voice"] == "project/narration.mp3"
    assert exported["voice_volume"] == 0.7
    assert [(scene["start"], scene["end"]) for scene in exported["scenes"]] == original_scene_times


def test_legacy_voice_becomes_editable_narration_defaults() -> None:
    project = editor_project_from_manifest(sample_manifest())

    assert project["narrationTrack"]["start"] == 0
    assert project["narrationTrack"]["sourceIn"] == 0
    assert project["narrationTrack"]["sourceOut"] == 8.5
    assert project["narrationTrack"]["volume"] == 1.0


def test_moved_sfx_is_serialized_relative_to_destination_scene() -> None:
    manifest = sample_manifest()
    project = editor_project_from_manifest(manifest)
    cue = project["sfxTrack"][0]
    cue.update({"start": 4.0, "volume": 0.55})

    exported = manifest_from_editor_project(project)

    assert exported["scenes"][0]["sfx"] == []
    assert exported["scenes"][1]["sfx"][0]["at"] == 0.75
    assert exported["scenes"][1]["sfx"][0]["volume"] == 0.55
    assert exported["scenes"][1]["sfx"][0]["file"] == "assets/sfx/hit.mp3"


def test_sfx_without_explicit_volume_defaults_to_ninety_two_percent() -> None:
    project = editor_project_from_manifest(sample_manifest())

    exported = manifest_from_editor_project(project)

    assert exported["scenes"][0]["sfx"][0]["volume"] == 0.92


def test_invalid_editor_crop_is_saved_as_wide() -> None:
    project = editor_project_from_manifest(sample_manifest())
    project["visualTrack"][0]["crop"] = "vertical"

    exported = manifest_from_editor_project(project)

    assert exported["scenes"][0]["crop"] == "wide"


def test_visual_and_text_editor_data_round_trips_losslessly() -> None:
    manifest = sample_manifest()
    manifest["scenes"][0]["keyframes"] = [
        {"time": 0, "scale": 1, "x": 0.5, "y": 0.5, "rotation": 0},
        {"time": 2, "scale": 1.2, "x": 0.6, "y": 0.4, "rotation": 2},
    ]
    manifest["scenes"][0]["effects"] = [
        {"id": "fx-1", "type": "blur", "start": 0.5, "end": 2, "intensity": 0.4, "enabled": True}
    ]
    manifest["subtitle_file"] = "project/subtitles/es.srt"
    manifest["subtitle_cues"] = [{"id": "sub-1", "start": 1, "end": 2, "text": "Hola", "custom": 9}]
    manifest["text_tracks"] = [{
        "id": "text-track-1", "name": "Texto 1", "overlays": [{
            "id": "text-1", "text": "Titulo", "start": 0, "end": 3,
            "font": "assets/fonts/Title.ttf", "font_size": 72, "color": "#ffffff",
        }],
    }]

    project = editor_project_from_manifest(manifest)
    exported = manifest_from_editor_project(project)

    assert project["visualTrack"][0]["keyframes"][1]["scale"] == 1.2
    assert project["visualTrack"][0]["effects"][0]["type"] == "blur"
    assert project["subtitleTrack"][0]["text"] == "Hola"
    assert project["textTracks"][0]["overlays"][0]["text"] == "Titulo"
    assert exported["scenes"][0]["keyframes"] == manifest["scenes"][0]["keyframes"]
    assert exported["scenes"][0]["effects"] == manifest["scenes"][0]["effects"]
    assert exported["subtitle_cues"][0]["custom"] == 9
    assert exported["text_tracks"] == manifest["text_tracks"]
