from __future__ import annotations

from pathlib import Path

from config import RenderConfig
from ffmpeg_builder import FFmpegBuilder
from models import (
    Asset,
    AssetType,
    CropType,
    GenerationSource,
    MotionType,
    Shot,
    StoryFunction,
    TransitionType,
    VisualLevel,
    VisualType,
)
from motion import MotionFilterFactory


def asset(path: Path = Path("ASSET_001.jpeg")) -> Asset:
    return Asset(
        asset_id="ASSET_001",
        type=AssetType.IMAGE,
        generation_source=GenerationSource.FLOW,
        file=path,
        visual_level=VisualLevel.CINEMATIC,
        focal_points={"telephone": (0.67, 0.42)},
    )


def shot() -> Shot:
    return Shot(
        shot_id="SHOT_001",
        asset_id="ASSET_001",
        duration=3.1,
        story_function=StoryFunction.CONTRADICTION,
        visual_type=VisualType.EVIDENCE,
        visual_level=VisualLevel.CINEMATIC,
        importance=8,
        crop=CropType.FOCAL,
        focal_point=(0.67, 0.42),
        motion=MotionType.FOCAL_ZOOM,
        transition=TransitionType.HARD_CUT,
    )


def test_motion_filter_builds_focal_zoom_for_manifest_shot() -> None:
    filter_text = MotionFilterFactory().build_for_shot(shot(), RenderConfig())

    assert "zoompan" in filter_text
    assert "min(1+on*0.0015,1.35)" in filter_text
    assert "0.67" in filter_text
    assert "0.42" in filter_text


def test_motion_filter_builds_static_medium_crop_for_manifest_shot() -> None:
    medium_shot = shot()
    medium_shot.motion = MotionType.STATIC
    medium_shot.crop = CropType.MEDIUM
    medium_shot.focal_point = None

    filter_text = MotionFilterFactory().build_for_shot(medium_shot, RenderConfig())

    assert "crop=iw*0.85:ih*0.85" in filter_text
    assert "scale=1920:1080" in filter_text


def test_ffmpeg_builder_builds_image_shot_command_from_asset(tmp_path: Path) -> None:
    image = tmp_path / "ASSET_001.jpeg"
    output = tmp_path / "shot.mp4"
    command = FFmpegBuilder().build_image_shot_command(shot(), asset(image), output, RenderConfig())

    assert command[:2] == ["ffmpeg", "-y"]
    assert str(image) in command
    assert "-t" in command
    assert "3.1" in command
    assert str(output) == command[-1]


def test_keyframes_and_effects_generate_timed_video_filters() -> None:
    animated = shot()
    from models import VisualEffect, VisualKeyframe
    animated.keyframes = [
        VisualKeyframe(time=0, scale=1, x=0.5, y=0.5),
        VisualKeyframe(time=3.1, scale=1.2, x=0.6, y=0.4, rotation=2),
    ]
    animated.effects = [VisualEffect(id="fx-1", type="blur", start=0.5, end=2, intensity=0.5)]

    filter_text = MotionFilterFactory().build_for_shot(animated, RenderConfig())

    assert "zoompan" in filter_text
    assert "if(between(on" in filter_text
    assert "boxblur" in filter_text
    assert "enable='between(t,0.5,2)'" in filter_text


def test_text_overlay_command_uses_font_and_timing(tmp_path: Path) -> None:
    from models import TextOverlay
    overlays = [TextOverlay(id="text-1", text="Hola: mundo", start=1, end=3, font=tmp_path / "Title.ttf", font_size=72, color="#ffffff")]

    command = FFmpegBuilder().build_text_overlay_command(tmp_path / "video.mp4", overlays, tmp_path / "styled.mp4", RenderConfig())
    filter_text = command[command.index("-vf") + 1]

    assert "drawtext=" in filter_text
    assert "fontfile=" in filter_text
    assert "enable='between(t,1,3)'" in filter_text
    assert "Hola\\: mundo" in filter_text


def test_text_overlay_command_animates_slide_positions(tmp_path: Path) -> None:
    from models import TextOverlay
    overlay = TextOverlay(
        id="title", text="Title", start=1, end=4, x=0.5, y=0.5,
        animation_in="slide_left", animation_out="slide_down", transition_duration=0.5,
    )

    command = FFmpegBuilder().build_text_overlay_command(
        tmp_path / "input.mp4", [overlay], tmp_path / "output.mp4", RenderConfig(),
    )
    filter_text = command[command.index("-vf") + 1]

    assert "if(lt(t,1.5)" in filter_text
    assert "if(gt(t,3.5)" in filter_text
    assert "text_w" in filter_text
    assert "text_h" in filter_text


def test_text_overlay_command_uses_a_fallback_font_when_none_is_selected(tmp_path: Path, monkeypatch) -> None:
    from models import TextOverlay
    monkeypatch.setattr(FFmpegBuilder, "_default_font_path", staticmethod(lambda: Path("fallback.ttf")))

    command = FFmpegBuilder().build_text_overlay_command(
        tmp_path / "input.mp4", [TextOverlay(id="caption", text="Hola", start=0, end=1)],
        tmp_path / "output.mp4", RenderConfig(),
    )

    assert "fontfile='fallback.ttf'" in command[command.index("-vf") + 1]
