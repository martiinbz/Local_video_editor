"""Semantic defaults for V2 shots."""

from __future__ import annotations

from pathlib import Path

from models import MotionType, Shot, SoundEffectCue, StoryFunction, TransitionType, VisualType


class StoryRuleEngine:
    """Apply stable renderer-side defaults from narrative semantics."""

    def __init__(self, sfx_directory: str | Path = "assets/sfx") -> None:
        self.sfx_directory = Path(sfx_directory)

    def apply(self, shot: Shot) -> Shot:
        if shot.story_function is StoryFunction.EMOTIONAL:
            shot.transition = TransitionType.CROSSFADE
            if shot.motion is MotionType.STATIC:
                shot.motion = MotionType.ZOOM_OUT
            return shot

        if shot.story_function is StoryFunction.REVEAL:
            shot.transition = TransitionType.HARD_CUT
            if shot.importance >= 8:
                self._add_first_existing_sfx(shot, ["dark_impact"], volume=0.24)
            return shot

        if shot.story_function is StoryFunction.CONTRADICTION:
            shot.transition = TransitionType.HARD_CUT
            self._add_first_existing_sfx(shot, ["deep_hit"], volume=0.22)
            return shot

        if shot.visual_type is VisualType.DOCUMENT:
            self._add_first_existing_sfx(shot, ["page_turn", "paper_rustle"], volume=0.14)
            return shot

        if shot.visual_type is VisualType.EVIDENCE:
            self._add_first_existing_sfx(shot, ["camera_shutter", "paper_rustle"], volume=0.18)
            return shot

        if shot.story_function in (StoryFunction.CONTEXT, StoryFunction.SETUP) and shot.motion is MotionType.STATIC:
            shot.motion = MotionType.PAN_RIGHT

        return shot

    def _add_first_existing_sfx(self, shot: Shot, names: list[str], volume: float) -> None:
        if shot.sfx:
            return
        for name in names:
            path = self.sfx_directory / f"{name}.mp3"
            if path.exists():
                shot.sfx.append(SoundEffectCue(name=name, file=path, at=min(0.5, max(0.0, shot.duration / 2)), volume=volume))
                return
