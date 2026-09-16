from __future__ import annotations

import json
from pathlib import Path

import pytest

from exceptions import ValidationError
from renderer import DocumentaryRenderer


class RecordingFFmpeg:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def build_image_shot_command(self, shot, asset, output: Path, config) -> list[str]:
        return ["ffmpeg", "shot", shot.shot_id, str(asset.file), str(output)]

    def build_concat_command(self, concat_file: Path, output: Path, config) -> list[str]:
        return ["ffmpeg", "concat", str(concat_file), str(output)]

    def build_mux_command(self, video: Path, audio: Path | None, output: Path, config) -> list[str]:
        return ["ffmpeg", "mux", str(video), str(audio), str(output)]

    def run(self, command: list[str]) -> None:
        self.commands.append(command)


def test_renderer_accepts_v23_manifest_version(tmp_path: Path) -> None:
    image = tmp_path / "SCENE_1.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "2.3",
                "output": str(tmp_path / "out.mp4"),
                "scenes": [
                    {
                        "scene_id": 1,
                        "type": "image",
                        "final_source": "FLOW",
                        "file": str(image),
                        "story_function": "HOOK",
                        "visual_type": "RECONSTRUCTION",
                        "visual_level": "GRAPHIC",
                        "importance": 10,
                        "duration": 4.2,
                        "motion": "static",
                        "transition": "hard_cut",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ffmpeg = RecordingFFmpeg()

    output = DocumentaryRenderer(ffmpeg=ffmpeg).render_manifest(path)

    assert output == tmp_path / "out.mp4"
    assert ffmpeg.commands[0][1] == "shot"
    assert ffmpeg.commands[0][2] == "SHOT_001"


def test_renderer_accepts_flat_scene_manifest_by_shape(tmp_path: Path) -> None:
    image = tmp_path / "SCENE_1.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "2.6",
                "output": str(tmp_path / "out.mp4"),
                "scenes": [
                    {
                        "scene_id": 1,
                        "type": "image",
                        "final_source": "FLOW",
                        "file": str(image),
                        "story_function": "HOOK",
                        "visual_type": "RECONSTRUCTION",
                        "visual_level": "GRAPHIC",
                        "importance": 10,
                        "start": 0,
                        "end": 4.2,
                        "motion": "static",
                        "transition": "hard_cut",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ffmpeg = RecordingFFmpeg()

    output = DocumentaryRenderer(ffmpeg=ffmpeg).render_manifest(path)

    assert output == tmp_path / "out.mp4"
    assert ffmpeg.commands[0][2] == "SHOT_001"


def test_renderer_can_ignore_qc_errors(tmp_path: Path) -> None:
    image = tmp_path / "SCENE_1.jpg"
    image.write_bytes(b"fake")
    scenes = []
    for index in range(1, 8):
        scenes.append(
            {
                "scene_id": index,
                "type": "image",
                "final_source": "FLOW",
                "file": str(image),
                "story_function": "HOOK",
                "visual_type": "RECONSTRUCTION",
                "visual_level": "HERO" if index <= 2 else "GRAPHIC",
                "importance": 10,
                "duration": 4.2,
                "motion": "static",
                "transition": "hard_cut",
            }
        )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"manifest_version": "2.6", "output": str(tmp_path / "out.mp4"), "scenes": scenes}), encoding="utf-8")

    ffmpeg = RecordingFFmpeg()

    output = DocumentaryRenderer(ffmpeg=ffmpeg).render_manifest(path, ignore_qc=True)

    assert output == tmp_path / "out.mp4"
    assert ffmpeg.commands[0][1] == "shot"


def test_renderer_allows_high_hero_usage_by_default(tmp_path: Path) -> None:
    image = tmp_path / "SCENE_1.jpg"
    image.write_bytes(b"fake")
    scenes = []
    for index in range(1, 8):
        scenes.append(
            {
                "scene_id": index,
                "type": "image",
                "final_source": "FLOW",
                "file": str(image),
                "story_function": "HOOK",
                "visual_type": "RECONSTRUCTION",
                "visual_level": "HERO" if index <= 2 else "GRAPHIC",
                "importance": 10,
                "duration": 4.2,
                "motion": "static",
                "transition": "hard_cut",
            }
        )
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"manifest_version": "2.6", "output": str(tmp_path / "out.mp4"), "scenes": scenes}), encoding="utf-8")

    output = DocumentaryRenderer(ffmpeg=RecordingFFmpeg()).render_manifest(path)

    assert output == tmp_path / "out.mp4"
    assert "HERO usage" not in (tmp_path / "qc_report.txt").read_text(encoding="utf-8")
