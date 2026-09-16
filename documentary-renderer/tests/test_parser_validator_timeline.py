from __future__ import annotations

import json
from pathlib import Path

import pytest

from exceptions import ValidationError
from models import MotionType, SceneType, TransitionType
from parser import StoryboardParser
from timeline import TimelineBuilder
from validator import StoryboardValidator


def write_storyboard(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "storyboard.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def base_payload(tmp_path: Path) -> dict:
    image = tmp_path / "image.png"
    voice = tmp_path / "voice.mp3"
    image.write_bytes(b"fake-image")
    voice.write_bytes(b"fake-audio")
    return {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "voice": str(voice),
        "output": str(tmp_path / "documentary.mp4"),
        "scenes": [
            {
                "type": "image",
                "file": str(image),
                "duration": 5,
                "motion": "zoom_in",
                "transition": "fade",
            }
        ],
    }


def test_parser_loads_storyboard_with_typed_scene_values(tmp_path: Path) -> None:
    path = write_storyboard(tmp_path, base_payload(tmp_path))

    storyboard = StoryboardParser().parse(path)

    assert storyboard.width == 1920
    assert storyboard.height == 1080
    assert storyboard.fps == 30
    assert storyboard.scenes[0].type is SceneType.IMAGE
    assert storyboard.scenes[0].motion is MotionType.ZOOM_IN
    assert storyboard.scenes[0].transition is TransitionType.FADE


def test_validator_rejects_missing_scene_file(tmp_path: Path) -> None:
    payload = base_payload(tmp_path)
    payload["scenes"][0]["file"] = str(tmp_path / "missing.png")
    storyboard = StoryboardParser().parse(write_storyboard(tmp_path, payload))

    with pytest.raises(ValidationError, match="missing.png"):
        StoryboardValidator().validate(storyboard)


def test_validator_rejects_negative_duration(tmp_path: Path) -> None:
    payload = base_payload(tmp_path)
    payload["scenes"][0]["duration"] = -1
    storyboard = StoryboardParser().parse(write_storyboard(tmp_path, payload))

    with pytest.raises(ValidationError, match="duration"):
        StoryboardValidator().validate(storyboard)


def test_timeline_calculates_scene_timestamps(tmp_path: Path) -> None:
    second = tmp_path / "second.png"
    second.write_bytes(b"fake-image")
    payload = base_payload(tmp_path)
    payload["scenes"].append(
        {
            "type": "image",
            "file": str(second),
            "duration": 2.5,
            "motion": "static",
            "transition": "hard_cut",
        }
    )
    storyboard = StoryboardParser().parse(write_storyboard(tmp_path, payload))
    StoryboardValidator().validate(storyboard)

    timeline = TimelineBuilder().build(storyboard)

    assert timeline.total_duration == 7.5
    assert timeline.scenes[0].start_time == 0
    assert timeline.scenes[0].end_time == 5
    assert timeline.scenes[1].start_time == 5
    assert timeline.scenes[1].end_time == 7.5
