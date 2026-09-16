from __future__ import annotations

import json
from pathlib import Path

from renderer import DocumentaryRenderer


class RecordingFFmpeg:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def build_image_shot_command(self, shot, asset, output: Path, config) -> list[str]:
        return ["ffmpeg", "shot", str(asset.file), str(output)]

    def build_concat_command(self, concat_file: Path, output: Path, config) -> list[str]:
        return ["ffmpeg", "concat", str(concat_file), str(output)]

    def build_mux_command(self, video: Path, audio: Path | None, output: Path, config) -> list[str]:
        return ["ffmpeg", "mux", str(output)]

    def run(self, command: list[str]) -> None:
        self.commands.append(command)


def test_renderer_resolves_selected_project_paths_and_shared_assets(tmp_path: Path) -> None:
    renderer_root = tmp_path / "renderer"
    project_dir = renderer_root / "projects" / "case-a"
    image = project_dir / "images" / "SCENE_1.jpg"
    music = renderer_root / "assets" / "music" / "mystery_01.mp3"
    image.parent.mkdir(parents=True)
    music.parent.mkdir(parents=True)
    image.write_bytes(b"fake")
    music.write_bytes(b"fake")
    manifest_path = project_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "2.3",
                "output": "output/documentary.mp4",
                "music_cues": [{"file": "assets/music/mystery_01.mp3", "start": 0, "end": 3, "state": "MYSTERY"}],
                "scenes": [
                    {
                        "scene_id": 1,
                        "type": "image",
                        "final_source": "FLOW",
                        "file": "project/images/SCENE_1.jpg",
                        "story_function": "HOOK",
                        "visual_type": "RECONSTRUCTION",
                        "visual_level": "GRAPHIC",
                        "importance": 8,
                        "duration": 3,
                        "motion": "static",
                        "transition": "hard_cut",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ffmpeg = RecordingFFmpeg()

    output = DocumentaryRenderer(ffmpeg=ffmpeg, renderer_root=renderer_root).render_manifest(manifest_path, ignore_qc=True)

    assert output == project_dir / "output" / "documentary.mp4"
    assert ffmpeg.commands[0][2] == str(image)
