from __future__ import annotations

from editor.backend.master_manifest_import import build_editor_manifest


def test_build_editor_manifest_converts_keyed_scenes_and_preserves_timeline_edits() -> None:
    source = {
        "SCENE_1": {
            "start_time": "00:00:00,000", "end_time": "00:00:02,000",
            "narration_fragment": "Primera escena", "visual_concept": "Concepto 1", "visual_level": "HERO",
        },
        "SCENE_2": {
            "start_time": "00:00:02,000", "end_time": "00:00:05,000",
            "narration_fragment": "Segunda escena", "visual_concept": "Concepto 2", "visual_level": "GRAPHIC",
        },
    }
    previous = {
        "manifest_version": "2.6",
        "scenes": [{
            "scene_id": "OLD_1", "start": 0, "end": 5,
            "keyframes": [{"id": "key-1", "time": 3, "scale": 1.2, "x": 0.5, "y": 0.5}],
            "effects": [{"id": "fx-1", "type": "blur", "start": 1, "end": 4, "intensity": 0.4, "enabled": True}],
            "sfx": [{"name": "hit", "file": "assets/sfx/hit.mp3", "at": 3, "volume": 0.8}],
        }],
        "subtitle_cues": [{"id": "sub-1", "start": 1, "end": 2, "text": "Hola"}],
        "text_tracks": [{"id": "text-1", "overlays": [{"id": "title", "start": 2, "end": 3, "text": "Titulo"}]}],
        "music_cues": [{"id": "music-1", "start": 0, "end": 5, "file": "assets/music/score.mp3"}],
    }

    migrated = build_editor_manifest(source, previous, "ep3", "project/subtitles/es.srt")

    assert [scene["scene_id"] for scene in migrated["scenes"]] == ["SCENE_1", "SCENE_2"]
    assert migrated["scenes"][0]["file"] == "project/images/SCENE_1.jpg"
    assert migrated["scenes"][1]["duration"] == 3.0
    assert migrated["voice"] == "narration.mp3"
    assert migrated["subtitle_cues"] == previous["subtitle_cues"]
    assert migrated["text_tracks"] == previous["text_tracks"]
    assert migrated["music_cues"] == previous["music_cues"]
    assert migrated["scenes"][1]["keyframes"][0]["time"] == 1.0
    assert migrated["scenes"][0]["effects"][0]["end"] == 2.0
    assert migrated["scenes"][1]["effects"][0]["start"] == 0.0
    assert migrated["scenes"][1]["sfx"][0]["at"] == 1.0


def test_build_editor_manifest_keeps_source_scene_starts_and_covers_audio_gaps() -> None:
    source = {
        "SCENE_1": {"start_time": "00:00:00,390", "end_time": "00:00:02,000"},
        "SCENE_2": {"start_time": "00:00:03,000", "end_time": "00:00:04,000"},
    }

    migrated = build_editor_manifest(source, None, "ep3", timeline_end=5.0)

    assert [(scene["start"], scene["end"]) for scene in migrated["scenes"]] == [(0.0, 3.0), (3.0, 5.0)]
    assert migrated["audio_duration_seconds"] == 5.0
