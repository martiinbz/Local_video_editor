from __future__ import annotations

import json
from pathlib import Path

import pytest

from exceptions import ValidationError
from manifest_parser import ManifestParser
from manifest_timeline import ManifestTimelineBuilder
from manifest_validator import ManifestValidator
from models import CropType, MotionType, StoryFunction, VisualLevel, VisualType


def write_manifest(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def base_manifest(tmp_path: Path) -> dict:
    image = tmp_path / "ASSET_001.jpeg"
    voice = tmp_path / "narration.mp3"
    image.write_bytes(b"fake-image")
    voice.write_bytes(b"fake-audio")
    return {
        "project": {
            "title": "Test episode",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "voice": str(voice),
            "output": str(tmp_path / "documentary.mp4"),
            "accent_color": "#A33A2A",
        },
        "assets": [
            {
                "asset_id": "ASSET_001",
                "type": "image",
                "generation_source": "flow",
                "file": str(image),
                "visual_level": "CINEMATIC",
                "focal_points": {"telephone": [0.67, 0.42]},
            }
        ],
        "shots": [
            {
                "shot_id": "SHOT_001",
                "asset_id": "ASSET_001",
                "duration": 3.1,
                "story_function": "CONTRADICTION",
                "visual_type": "EVIDENCE",
                "visual_level": "CINEMATIC",
                "importance": 8,
                "crop": "focal",
                "focal_point": [0.67, 0.42],
                "motion": "focal_zoom",
                "transition": "hard_cut",
            }
        ],
        "music_cues": [{"state": "MYSTERY", "start": 0, "end": 3.1, "volume": 0.12}],
        "ambience_cues": [],
    }


def test_manifest_parser_loads_assets_and_shots_with_typed_values(tmp_path: Path) -> None:
    manifest = ManifestParser().parse(write_manifest(tmp_path, base_manifest(tmp_path)))

    assert manifest.project.title == "Test episode"
    assert manifest.assets["ASSET_001"].visual_level is VisualLevel.CINEMATIC
    assert manifest.shots[0].story_function is StoryFunction.CONTRADICTION
    assert manifest.shots[0].visual_type is VisualType.EVIDENCE
    assert manifest.shots[0].crop is CropType.FOCAL
    assert manifest.shots[0].motion is MotionType.FOCAL_ZOOM


def test_manifest_validator_rejects_missing_asset_reference(tmp_path: Path) -> None:
    payload = base_manifest(tmp_path)
    payload["shots"][0]["asset_id"] = "ASSET_MISSING"
    manifest = ManifestParser().parse(write_manifest(tmp_path, payload))

    with pytest.raises(ValidationError, match="ASSET_MISSING"):
        ManifestValidator().validate(manifest)


def test_manifest_validator_rejects_out_of_range_focal_point(tmp_path: Path) -> None:
    payload = base_manifest(tmp_path)
    payload["shots"][0]["focal_point"] = [1.5, 0.42]
    manifest = ManifestParser().parse(write_manifest(tmp_path, payload))

    with pytest.raises(ValidationError, match="focal_point"):
        ManifestValidator().validate(manifest)


def test_manifest_timeline_calculates_shot_timestamps(tmp_path: Path) -> None:
    payload = base_manifest(tmp_path)
    payload["shots"].append(
        {
            "shot_id": "SHOT_002",
            "asset_id": "ASSET_001",
            "duration": 2.4,
            "story_function": "CONTEXT",
            "visual_type": "LOCATION",
            "visual_level": "GRAPHIC",
            "importance": 4,
            "crop": "wide",
            "motion": "pan_right",
            "transition": "fade",
        }
    )
    manifest = ManifestParser().parse(write_manifest(tmp_path, payload))
    ManifestValidator().validate(manifest)

    timeline = ManifestTimelineBuilder().build(manifest)

    assert timeline.total_duration == 5.5
    assert timeline.shots[0].start_time == 0
    assert timeline.shots[0].end_time == 3.1
    assert timeline.shots[1].start_time == 3.1
    assert timeline.shots[1].end_time == 5.5
