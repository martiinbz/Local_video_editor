"""Transition filter generation."""

from __future__ import annotations

from config import RenderConfig
from models import Scene, Shot, TransitionType
from utils import seconds


class TransitionFilterFactory:
    """Build per-segment FFmpeg transition filters."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()

    def build_video_filter(self, scene: Scene) -> str:
        """Return fade filters for a scene segment."""

        if scene.transition is TransitionType.HARD_CUT or scene.duration is None:
            return ""

        duration = scene.duration
        transition_duration = min(scene.transition_duration or self.config.transition_duration, duration / 2)

        if scene.transition is TransitionType.DIP_TO_BLACK:
            out_start = max(0.0, duration - transition_duration)
            return f"fade=t=out:st={seconds(out_start)}:d={seconds(transition_duration)}:color=black"

        if scene.transition in (TransitionType.FADE, TransitionType.CROSSFADE):
            out_start = max(0.0, duration - transition_duration)
            return (
                f"fade=t=in:st=0:d={seconds(transition_duration)},"
                f"fade=t=out:st={seconds(out_start)}:d={seconds(transition_duration)}"
            )

        return ""

    def build_shot_video_filter(self, shot: Shot) -> str:
        """Return fade filters for a V2 shot segment."""

        if shot.transition is TransitionType.HARD_CUT:
            return ""

        duration = shot.duration
        transition_duration = min(shot.transition_duration or self.config.transition_duration, duration / 2)

        if shot.transition is TransitionType.DIP_TO_BLACK:
            out_start = max(0.0, duration - transition_duration)
            return f"fade=t=out:st={seconds(out_start)}:d={seconds(transition_duration)}:color=black"

        if shot.transition in (TransitionType.FADE, TransitionType.CROSSFADE):
            out_start = max(0.0, duration - transition_duration)
            return (
                f"fade=t=in:st=0:d={seconds(transition_duration)},"
                f"fade=t=out:st={seconds(out_start)}:d={seconds(transition_duration)}"
            )

        return ""
