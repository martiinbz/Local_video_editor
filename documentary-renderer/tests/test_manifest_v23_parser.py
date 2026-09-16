from __future__ import annotations

import json
from pathlib import Path

from manifest_v23_parser import ManifestV23Parser
from models import CropType, GenerationSource, MotionType, MusicState, StoryFunction, VisualType


def test_manifest_v23_parser_converts_scenes_to_assets_and_shots(tmp_path: Path) -> None:
    image = tmp_path / "SCENE_1.jpg"
    voice = tmp_path / "narration.mp3"
    music = tmp_path / "music.mp3"
    ambience = tmp_path / "office.mp3"
    sfx = tmp_path / "deep_hit.mp3"
    for file in (image, voice, music, ambience, sfx):
        file.write_bytes(b"fake")
    payload = {
        "manifest_version": "2.3",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "voice": str(voice),
        "output": str(tmp_path / "out.mp4"),
        "music_cues": [{"file": str(music), "start": 0, "end": 4.2, "volume": 0.055, "state": "MYSTERY"}],
        "ambience_cues": [{"file": str(ambience), "start": 0, "end": 4.2, "volume": 0.035, "state": "OFFICE"}],
        "scenes": [
            {
                "scene_id": 1,
                "scene_generation_name": "SCENE_1",
                "type": "image",
                "final_source": "FLOW",
                "file": str(image),
                "story_function": "HOOK",
                "visual_type": "RECONSTRUCTION",
                "visual_level": "HERO",
                "importance": 10,
                "duration": 4.2,
                "motion": "focal_zoom",
                "motion_speed": 0.7,
                "focal_point": [0.62, 0.46],
                "transition": "hard_cut",
                "transition_duration": 0.3,
                "sfx": [{"name": "deep_hit", "file": str(sfx), "at": 0.18, "volume": 0.32}],
            }
        ],
    }
    path = tmp_path / "manifest_v2_3.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = ManifestV23Parser().parse(path)

    assert manifest.project.voice == voice
    assert len(manifest.assets) == 1
    assert manifest.assets["ASSET_001"].generation_source is GenerationSource.FLOW
    assert manifest.shots[0].shot_id == "SHOT_001"
    assert manifest.shots[0].story_function is StoryFunction.HOOK
    assert manifest.shots[0].visual_type is VisualType.RECONSTRUCTION
    assert manifest.shots[0].motion is MotionType.FOCAL_ZOOM
    assert manifest.music_cues[0].state is MusicState.MYSTERY
    assert manifest.music_cues[0].track == music
    assert manifest.ambience_cues[0].file == ambience
    assert manifest.shots[0].sfx[0].file == sfx


def test_manifest_v23_parser_maps_legacy_vertical_crop_to_wide() -> None:
    assert ManifestV23Parser._crop("vertical") is CropType.WIDE


def test_manifest_v23_parser_maps_real_photo_insert_to_reconstruction(tmp_path: Path) -> None:
    image = tmp_path / "real.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest_v2_3.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "2.3",
                "output": str(tmp_path / "out.mp4"),
                "scenes": [
                    {
                        "scene_id": 4,
                        "scene_generation_name": "SCENE_4",
                        "type": "image",
                        "final_source": "REAL_IMAGE",
                        "file": str(image),
                        "story_function": "EVIDENCE",
                        "visual_type": "REAL_PHOTO_INSERT",
                        "visual_level": "CINEMATIC",
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

    manifest = ManifestV23Parser().parse(path)

    assert manifest.assets["ASSET_004"].generation_source is GenerationSource.FLOW
    assert manifest.shots[0].visual_type is VisualType.RECONSTRUCTION


def test_manifest_v23_parser_maps_phone_log_to_evidence(tmp_path: Path) -> None:
    image = tmp_path / "phone.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest_v2_6.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "2.6",
                "output": str(tmp_path / "out.mp4"),
                "scenes": [
                    {
                        "scene_id": "SCENE_12",
                        "file": str(image),
                        "visual_type": "PHONE_LOG",
                        "visual_level": "GRAPHIC",
                        "duration": 3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = ManifestV23Parser().parse(path)

    assert manifest.shots[0].visual_type is VisualType.EVIDENCE


def test_manifest_v23_parser_maps_v26_editorial_visual_types(tmp_path: Path) -> None:
    image = tmp_path / "scene.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest_v2_6.json"
    scenes = []
    for index, visual_type in enumerate(
        ["BANK_TRANSFER_SCREEN", "ESTABLISHING", "SURVEILLANCE_LAYOUT", "THEORY_BOARD"],
        start=1,
    ):
        scenes.append(
            {
                "scene_id": f"SCENE_{index}",
                "file": str(image),
                "visual_type": visual_type,
                "visual_level": "GRAPHIC",
                "duration": 3,
            }
        )
    path.write_text(json.dumps({"manifest_version": "2.6", "scenes": scenes}), encoding="utf-8")

    manifest = ManifestV23Parser().parse(path)

    assert [shot.visual_type for shot in manifest.shots] == [
        VisualType.EVIDENCE,
        VisualType.LOCATION,
        VisualType.EVIDENCE,
        VisualType.ABSTRACT,
    ]


def test_manifest_v23_parser_accepts_unknown_editorial_visual_type(tmp_path: Path) -> None:
    image = tmp_path / "scene.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"scenes": [{
            "scene_id": "SCENE_1", "file": str(image), "duration": 3,
            "visual_type": "HERO_DEVICE", "visual_level": "HERO",
        }]}),
        encoding="utf-8",
    )

    manifest = ManifestV23Parser().parse(path)

    assert manifest.shots[0].visual_type is VisualType.ABSTRACT


def test_manifest_v23_parser_derives_duration_from_start_and_end(tmp_path: Path) -> None:
    image = tmp_path / "SCENE_1.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest_v2_6.json"
    path.write_text(
        json.dumps(
            {
                "manifest_version": "2.6",
                "output": str(tmp_path / "out.mp4"),
                "scenes": [
                    {
                        "scene_id": "SCENE_1",
                        "type": "image",
                        "final_source": "FLOW",
                        "file": str(image),
                        "story_function": "HOOK",
                        "visual_type": "RECONSTRUCTION",
                        "visual_level": "GRAPHIC",
                        "importance": 10,
                        "start": 5.011,
                        "end": 10.022,
                        "motion": "static",
                        "transition": "hard_cut",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = ManifestV23Parser().parse(path)

    assert manifest.shots[0].duration == 5.011
    assert manifest.shots[0].shot_id == "SHOT_001"


def test_manifest_v23_parser_reads_editable_narration_clip(tmp_path: Path) -> None:
    image = tmp_path / "scene.jpg"
    voice = tmp_path / "voice.mp3"
    image.write_bytes(b"fake")
    voice.write_bytes(b"fake")
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "voice": str(voice),
                "narration_clip": {
                    "file": str(voice),
                    "timeline_start": 1.5,
                    "source_in": 2.25,
                    "source_out": 8.75,
                    "volume": 0.8,
                },
                "scenes": [{"scene_id": "SCENE_1", "file": str(image), "duration": 10}],
            }
        ),
        encoding="utf-8",
    )

    manifest = ManifestV23Parser().parse(path)

    assert manifest.project.voice == voice
    assert manifest.project.narration_clip is not None
    assert manifest.project.narration_clip.timeline_start == 1.5
    assert manifest.project.narration_clip.source_in == 2.25
    assert manifest.project.narration_clip.source_out == 8.75
    assert manifest.project.narration_clip.volume == 0.8


def test_manifest_v23_parser_reads_keyframes_effects_and_text(tmp_path: Path) -> None:
    image = tmp_path / "scene.jpg"
    image.write_bytes(b"fake")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "scenes": [{
            "scene_id": "SCENE_1", "file": str(image), "duration": 5,
            "keyframes": [{"time": 0, "scale": 1, "x": 0.5, "y": 0.5}, {"time": 5, "scale": 1.2, "x": 0.6, "y": 0.4}],
            "effects": [{"id": "fx-1", "type": "blur", "start": 1, "end": 3, "intensity": 0.5}],
        }],
        "subtitle_file": "project/subtitles/es.srt",
        "subtitle_cues": [{"id": "sub-1", "text": "Hola", "start": 1, "end": 2}],
        "text_tracks": [{"id": "track-1", "name": "Titulos", "overlays": [{"id": "txt-1", "text": "Caso", "start": 0, "end": 4, "font_size": 64}]}],
    }), encoding="utf-8")

    manifest = ManifestV23Parser().parse(path)

    assert manifest.shots[0].keyframes[1].scale == 1.2
    assert manifest.shots[0].effects[0].type == "blur"
    assert manifest.subtitle_cues[0].text == "Hola"
    assert manifest.text_tracks[0].overlays[0].font_size == 64
