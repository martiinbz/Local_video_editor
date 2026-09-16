"""Storyboard validation."""

from __future__ import annotations

from pathlib import Path

from exceptions import ValidationError
from models import Scene, SceneType, Storyboard, TransitionType


class StoryboardValidator:
    """Validate storyboards before rendering."""

    def validate(self, storyboard: Storyboard) -> None:
        """Raise ValidationError if the storyboard is not renderable."""

        self._positive_int(storyboard.width, "width")
        self._positive_int(storyboard.height, "height")
        self._positive_int(storyboard.fps, "fps")
        self._volume(storyboard.music_volume, "music_volume")
        self._volume(storyboard.voice_volume, "voice_volume")
        self._range(storyboard.duck_amount, "duck_amount", 0, 1)
        self._positive_float(storyboard.duck_fade_duration, "duck_fade_duration")

        if not storyboard.scenes:
            raise ValidationError("Storyboard must contain at least one scene.")

        self._optional_existing_file(storyboard.voice, "voice")
        self._optional_existing_file(storyboard.music, "music")

        for index, scene in enumerate(storyboard.scenes, start=1):
            self._scene(scene, index)

    def _scene(self, scene: Scene, index: int) -> None:
        if not scene.file.exists():
            raise ValidationError(f"Scene {index} file does not exist: {scene.file}")
        if scene.duration is not None:
            self._positive_float(scene.duration, f"Scene {index} duration")
        if scene.type is SceneType.IMAGE and scene.duration is None:
            raise ValidationError(f"Scene {index} image scenes require duration.")
        if scene.type is SceneType.IMAGE and (scene.start_time is not None or scene.end_time is not None):
            raise ValidationError(f"Scene {index} image scenes cannot use start_time or end_time.")
        if scene.start_time is not None and scene.start_time < 0:
            raise ValidationError(f"Scene {index} start_time cannot be negative.")
        if scene.end_time is not None and scene.end_time < 0:
            raise ValidationError(f"Scene {index} end_time cannot be negative.")
        if scene.start_time is not None and scene.end_time is not None and scene.end_time <= scene.start_time:
            raise ValidationError(f"Scene {index} end_time must be greater than start_time.")
        if scene.transition_duration is not None:
            self._positive_float(scene.transition_duration, f"Scene {index} transition_duration")
        if scene.motion_speed is not None:
            self._positive_float(scene.motion_speed, f"Scene {index} motion_speed")
        if scene.transition is TransitionType.HARD_CUT and scene.transition_duration is not None:
            self._positive_float(scene.transition_duration, f"Scene {index} transition_duration")
        scene_duration = scene.duration
        if scene_duration is not None:
            for cue_index, cue in enumerate(scene.sfx, start=1):
                if not cue.file.exists():
                    raise ValidationError(f"Scene {index} sfx {cue_index} file does not exist: {cue.file}")
                if cue.at < 0 or cue.at >= scene_duration:
                    raise ValidationError(f"Scene {index} sfx {cue_index} at must be within scene duration.")
                self._volume(cue.volume, f"Scene {index} sfx {cue_index} volume")

    @staticmethod
    def _optional_existing_file(path: Path | None, label: str) -> None:
        if path is not None and not path.exists():
            raise ValidationError(f"{label} file does not exist: {path}")

    @staticmethod
    def _positive_int(value: int, label: str) -> None:
        if value <= 0:
            raise ValidationError(f"{label} must be positive.")

    @staticmethod
    def _positive_float(value: float, label: str) -> None:
        if value <= 0:
            raise ValidationError(f"{label} must be positive.")

    @staticmethod
    def _volume(value: float, label: str) -> None:
        if value < 0:
            raise ValidationError(f"{label} cannot be negative.")

    @staticmethod
    def _range(value: float, label: str, minimum: float, maximum: float) -> None:
        if value < minimum or value > maximum:
            raise ValidationError(f"{label} must be between {minimum} and {maximum}.")
