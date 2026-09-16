from __future__ import annotations

from pathlib import Path

from config import RenderConfig
from manifest_audio import ManifestAudioPlanner
from models import Manifest, MusicCue, MusicState, NarrationClip, ProjectConfig, Shot, SoundEffectCue, StoryFunction, VisualLevel, VisualType


def test_manifest_audio_planner_mixes_voice_and_timed_music_cues(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    music = tmp_path / "mystery.mp3"
    voice.write_bytes(b"fake")
    music.write_bytes(b"fake")
    manifest = Manifest(
        project=ProjectConfig(title="Test", voice=voice, output=tmp_path / "out.mp4"),
        assets={},
        shots=[],
        music_cues=[MusicCue(state=MusicState.MYSTERY, track=music, start=2, end=7, volume=0.11)],
    )

    command = ManifestAudioPlanner(RenderConfig()).build_audio_mix_command(manifest, 10, tmp_path / "mix.m4a")
    filter_complex = command[command.index("-filter_complex") + 1]

    assert str(voice) in command
    assert str(music) in command
    assert "atrim=0:5" in filter_complex
    assert "adelay=2000:all=1" in filter_complex
    assert "sidechaincompress" in filter_complex


def test_manifest_audio_planner_ignores_silence_music_cues(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    manifest = Manifest(
        project=ProjectConfig(title="Test", voice=voice, output=tmp_path / "out.mp4"),
        assets={},
        shots=[],
        music_cues=[MusicCue(state=MusicState.SILENCE, start=2, end=7, volume=0)],
    )

    command = ManifestAudioPlanner(RenderConfig()).build_audio_mix_command(manifest, 10, tmp_path / "mix.m4a")

    assert command.count("-i") == 1


def test_manifest_audio_planner_mixes_voice_and_sfx_without_duck_split(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    sfx = tmp_path / "camera.mp3"
    voice.write_bytes(b"fake")
    sfx.write_bytes(b"fake")
    manifest = Manifest(
        project=ProjectConfig(title="Test", voice=voice, output=tmp_path / "out.mp4"),
        assets={},
        shots=[
            Shot(
                shot_id="SHOT_001",
                asset_id="ASSET_001",
                duration=5,
                story_function=StoryFunction.HOOK,
                visual_type=VisualType.RECONSTRUCTION,
                visual_level=VisualLevel.GRAPHIC,
                importance=10,
                sfx=[SoundEffectCue(name="camera", file=sfx, at=1.25, volume=0.7)],
            )
        ],
    )

    command = ManifestAudioPlanner(RenderConfig()).build_audio_mix_command(manifest, 10, tmp_path / "mix.m4a")
    filter_complex = command[command.index("-filter_complex") + 1]

    assert "asplit=2" not in filter_complex
    assert "volume=1.0[voice_mix]" in filter_complex
    assert "volume=0.7,adelay=1250:all=1" in filter_complex
    assert "amix=inputs=2" in filter_complex


def test_manifest_audio_planner_trims_and_delays_editable_narration(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    manifest = Manifest(
        project=ProjectConfig(
            title="Test",
            voice=voice,
            output=tmp_path / "out.mp4",
            narration_clip=NarrationClip(
                file=voice,
                timeline_start=1.5,
                source_in=2.25,
                source_out=8.75,
                volume=0.8,
            ),
        ),
        assets={},
        shots=[],
    )

    command = ManifestAudioPlanner(RenderConfig()).build_audio_mix_command(manifest, 12, tmp_path / "mix.m4a")
    filter_complex = command[command.index("-filter_complex") + 1]

    assert "atrim=start=2.25:end=8.75" in filter_complex
    assert "asetpts=PTS-STARTPTS" in filter_complex
    assert "adelay=1500:all=1" in filter_complex
    assert "volume=0.8[voice_mix]" in filter_complex


def test_manifest_audio_planner_keeps_legacy_voice_filter_unchanged(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    voice.write_bytes(b"fake")
    manifest = Manifest(
        project=ProjectConfig(title="Test", voice=voice, voice_volume=0.7, output=tmp_path / "out.mp4"),
        assets={},
        shots=[],
    )

    command = ManifestAudioPlanner(RenderConfig()).build_audio_mix_command(manifest, 10, tmp_path / "mix.m4a")
    filter_complex = command[command.index("-filter_complex") + 1]

    assert "volume=0.7[voice_mix]" in filter_complex
    assert "atrim=" not in filter_complex
    assert "adelay=" not in filter_complex
