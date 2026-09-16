from __future__ import annotations

from pathlib import Path

from models import (
    CropType,
    MotionType,
    Shot,
    StoryFunction,
    TransitionType,
    VisualLevel,
    VisualType,
)
from story_rules import StoryRuleEngine


def make_shot(story_function: StoryFunction, visual_type: VisualType, importance: int = 5) -> Shot:
    return Shot(
        shot_id="SHOT_001",
        asset_id="ASSET_001",
        duration=4,
        story_function=story_function,
        visual_type=visual_type,
        visual_level=VisualLevel.CINEMATIC,
        importance=importance,
        crop=CropType.WIDE,
    )


def test_story_rules_add_reveal_impact_when_importance_is_high(tmp_path: Path) -> None:
    sfx = tmp_path / "dark_impact.mp3"
    sfx.write_bytes(b"fake")
    shot = make_shot(StoryFunction.REVEAL, VisualType.REVEAL, importance=9)

    StoryRuleEngine(sfx_directory=tmp_path).apply(shot)

    assert shot.transition is TransitionType.HARD_CUT
    assert shot.sfx[0].name == "dark_impact"
    assert shot.sfx[0].file == sfx


def test_story_rules_make_emotional_shots_slow_and_soft(tmp_path: Path) -> None:
    shot = make_shot(StoryFunction.EMOTIONAL, VisualType.CHARACTER)

    StoryRuleEngine(sfx_directory=tmp_path).apply(shot)

    assert shot.transition is TransitionType.CROSSFADE
    assert shot.motion is MotionType.ZOOM_OUT
    assert shot.sfx == []


def test_story_rules_use_document_sfx_when_available(tmp_path: Path) -> None:
    sfx = tmp_path / "page_turn.mp3"
    sfx.write_bytes(b"fake")
    shot = make_shot(StoryFunction.EVIDENCE, VisualType.DOCUMENT)

    StoryRuleEngine(sfx_directory=tmp_path).apply(shot)

    assert shot.sfx[0].name == "page_turn"
