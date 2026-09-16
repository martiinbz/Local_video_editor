from __future__ import annotations

from pathlib import Path

from audio import AudioPlanner
from config import RenderConfig
from ffmpeg_builder import FFmpegBuilder
from models import MotionType, Scene, SceneType, SoundEffectCue, Storyboard, TextOverlay, TransitionType
from motion import MotionFilterFactory
from transitions import TransitionFilterFactory


def test_motion_filter_uses_zoompan_for_zoom_in() -> None:
    scene = Scene(
        type=SceneType.IMAGE,
        file=Path("image.png"),
        duration=5,
        motion=MotionType.ZOOM_IN,
    )

    filter_text = MotionFilterFactory().build(scene, RenderConfig())

    assert "zoompan" in filter_text
    assert "fps=30" in filter_text
    assert "s=1920x1080" in filter_text


def test_motion_speed_one_uses_default_cinematic_speed() -> None:
    scene = Scene(
        type=SceneType.IMAGE,
        file=Path("image.png"),
        duration=5,
        motion=MotionType.ZOOM_IN,
        motion_speed=1.0,
    )

    filter_text = MotionFilterFactory().build(scene, RenderConfig())

    assert "min(1+on*0.0015,1.25)" in filter_text


def test_transition_filter_builds_fade_in_and_out() -> None:
    scene = Scene(
        type=SceneType.IMAGE,
        file=Path("image.png"),
        duration=5,
        transition=TransitionType.FADE,
        transition_duration=0.5,
    )

    filter_text = TransitionFilterFactory().build_video_filter(scene)

    assert "fade=t=in:st=0:d=0.5" in filter_text
    assert "fade=t=out:st=4.5:d=0.5" in filter_text


def test_image_scene_command_contains_expected_export_flags(tmp_path: Path) -> None:
    scene = Scene(
        type=SceneType.IMAGE,
        file=tmp_path / "image.png",
        duration=5,
        motion=MotionType.STATIC,
    )
    output = tmp_path / "scene.mp4"

    command = FFmpegBuilder().build_image_scene_command(scene, output, RenderConfig())

    assert command[:2] == ["ffmpeg", "-y"]
    assert "-loop" in command
    assert "-t" in command
    assert "5" in command
    assert "-movflags" in command
    assert "+faststart" in command
    assert str(output) == command[-1]


def test_audio_planner_builds_ducked_music_mix(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    music = tmp_path / "music.mp3"
    output = tmp_path / "mix.m4a"
    storyboard = Storyboard(
        voice=voice,
        music=music,
        output=tmp_path / "out.mp4",
        music_volume=0.2,
        voice_volume=1,
        duck_amount=0.35,
        scenes=[
            Scene(
                type=SceneType.IMAGE,
                file=tmp_path / "image.png",
                duration=4,
            )
        ],
    )

    command = AudioPlanner().build_audio_mix_command(storyboard, 4, output)

    assert "-stream_loop" in command
    assert "sidechaincompress" in " ".join(command)
    assert str(output) == command[-1]


def test_audio_planner_splits_voice_before_ducking_and_final_mix(tmp_path: Path) -> None:
    storyboard = Storyboard(
        voice=tmp_path / "voice.mp3",
        music=tmp_path / "music.mp3",
        output=tmp_path / "out.mp4",
        music_volume=0.08,
        voice_volume=1.15,
        duck_amount=0.18,
        scenes=[
            Scene(
                type=SceneType.IMAGE,
                file=tmp_path / "image.png",
                duration=4,
            )
        ],
    )

    command = AudioPlanner().build_audio_mix_command(storyboard, 4, tmp_path / "mix.m4a")
    filter_complex = command[command.index("-filter_complex") + 1]

    assert "asplit=2[voice_for_duck][voice_mix]" in filter_complex
    assert "[music][voice_for_duck]sidechaincompress" in filter_complex
    assert "[ducked][voice_mix]amix" in filter_complex


def test_audio_planner_mixes_scene_sound_effect_at_relative_timestamp(tmp_path: Path) -> None:
    voice = tmp_path / "voice.mp3"
    sfx = tmp_path / "impact.mp3"
    storyboard = Storyboard(
        voice=voice,
        output=tmp_path / "out.mp4",
        scenes=[
            Scene(
                type=SceneType.IMAGE,
                file=tmp_path / "image.png",
                duration=4,
                sfx=[SoundEffectCue(name="deep_hit", file=sfx, at=1.25, volume=0.9)],
            )
        ],
    )

    command = AudioPlanner().build_audio_mix_command(storyboard, 4, tmp_path / "mix.m4a")
    filter_complex = command[command.index("-filter_complex") + 1]

    assert str(sfx) in command
    assert "volume=0.9,adelay=1250:all=1" in filter_complex
    assert "amix=inputs=2" in filter_complex


def test_text_overlay_command_writes_long_filter_to_script_file(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    output = tmp_path / "video_styled.mp4"
    overlays = [
        TextOverlay(id=f"subtitle-{index}", text=f"Subtitle {index}", start=index, end=index + 1)
        for index in range(200)
    ]

    command = FFmpegBuilder().build_text_overlay_command(video, overlays, output, RenderConfig())

    assert "-filter_complex_script" in command
    script_path = Path(command[command.index("-filter_complex_script") + 1])
    assert script_path.is_file()
    assert script_path.read_text(encoding="utf-8").count("drawtext=") == 200
    assert len(" ".join(command)) < 8_000


def test_drawtext_ignores_web_fonts_unsupported_by_ffmpeg(tmp_path: Path) -> None:
    overlay = TextOverlay(
        id="title",
        text="Título",
        start=0,
        end=1,
        font=tmp_path / "ClimbingNevis-Demo.woff",
    )

    filter_text = FFmpegBuilder._drawtext_filter(overlay, RenderConfig())

    assert "ClimbingNevis-Demo.woff" not in filter_text
    assert "fontfile=" in filter_text
