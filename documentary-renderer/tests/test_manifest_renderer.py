from __future__ import annotations

import json
from pathlib import Path

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


def test_renderer_renders_manifest_shots_instead_of_scenes(tmp_path: Path) -> None:
    image = tmp_path / "ASSET_001.jpeg"
    voice = tmp_path / "narration.mp3"
    image.write_bytes(b"fake-image")
    voice.write_bytes(b"fake-audio")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "project": {
                    "title": "Test",
                    "voice": str(voice),
                    "output": str(tmp_path / "out.mp4"),
                },
                "assets": [
                    {
                        "asset_id": "ASSET_001",
                        "type": "image",
                        "generation_source": "flow",
                        "file": str(image),
                        "visual_level": "CINEMATIC",
                    }
                ],
                "shots": [
                    {
                        "shot_id": "SHOT_001",
                        "asset_id": "ASSET_001",
                        "duration": 3,
                        "story_function": "HOOK",
                        "visual_type": "RECONSTRUCTION",
                        "visual_level": "CINEMATIC",
                        "importance": 8,
                    },
                    {
                        "shot_id": "SHOT_002",
                        "asset_id": "ASSET_001",
                        "duration": 2,
                        "story_function": "CONTEXT",
                        "visual_type": "LOCATION",
                        "visual_level": "GRAPHIC",
                        "importance": 4,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    ffmpeg = RecordingFFmpeg()

    output = DocumentaryRenderer(ffmpeg=ffmpeg).render_manifest(manifest_path)

    assert output == tmp_path / "out.mp4"
    assert [command[1] for command in ffmpeg.commands[:3]] == ["shot", "shot", "concat"]
    assert ffmpeg.commands[-1][1] == "mux"
    assert ffmpeg.commands[0][2] == "SHOT_001"
    assert ffmpeg.commands[1][2] == "SHOT_002"
