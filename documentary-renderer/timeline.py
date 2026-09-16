"""Timeline calculation."""

from __future__ import annotations

from models import Scene, Storyboard, Timeline, TimelineScene
from utils import probe_media_duration


class TimelineBuilder:
    """Calculate scene timestamps automatically."""

    def build(self, storyboard: Storyboard) -> Timeline:
        """Return a timeline with start/end timestamps for every scene."""

        timeline_scenes: list[TimelineScene] = []
        cursor = 0.0

        for index, scene in enumerate(storyboard.scenes):
            duration = self._duration(scene)
            start = cursor
            end = start + duration
            scene.duration = duration
            timeline_scenes.append(
                TimelineScene(
                    index=index,
                    source=scene,
                    start_time=start,
                    end_time=end,
                    duration=duration,
                    transition=scene.transition,
                    motion=scene.motion,
                )
            )
            cursor = end

        return Timeline(scenes=timeline_scenes, total_duration=cursor)

    @staticmethod
    def _duration(scene: Scene) -> float:
        if scene.duration is not None:
            return float(scene.duration)
        if scene.start_time is not None and scene.end_time is not None:
            return float(scene.end_time - scene.start_time)
        source_duration = probe_media_duration(scene.file)
        if scene.start_time is not None:
            return source_duration - scene.start_time
        return source_duration
