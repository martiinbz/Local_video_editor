"""Storyboard JSON parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exceptions import StoryboardParseError, ValidationError
from models import MotionType, Scene, SceneType, SoundEffectCue, Storyboard, TransitionType


class StoryboardParser:
    """Load JSON storyboards into typed models."""

    def parse(self, path: str | Path) -> Storyboard:
        """Read and parse a storyboard JSON file."""

        storyboard_path = Path(path)
        try:
            payload = json.loads(storyboard_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise StoryboardParseError(f"Storyboard not found: {storyboard_path}") from exc
        except json.JSONDecodeError as exc:
            raise StoryboardParseError(f"Invalid JSON in {storyboard_path}: {exc.msg}") from exc

        if not isinstance(payload, dict):
            raise StoryboardParseError("Storyboard root must be a JSON object.")

        return self._parse_payload(payload)

    def _parse_payload(self, payload: dict[str, Any]) -> Storyboard:
        scenes_raw = payload.get("scenes")
        if not isinstance(scenes_raw, list):
            raise ValidationError("Storyboard must contain a scenes array.")

        return Storyboard(
            width=int(payload.get("width", 1920)),
            height=int(payload.get("height", 1080)),
            fps=int(payload.get("fps", 30)),
            voice=self._optional_path(payload.get("voice")),
            music=self._optional_path(payload.get("music")),
            music_volume=float(payload.get("music_volume", 0.15)),
            voice_volume=float(payload.get("voice_volume", 1.0)),
            duck_amount=float(payload.get("duck_amount", 0.35)),
            duck_fade_duration=float(payload.get("duck_fade_duration", 0.5)),
            output=Path(str(payload.get("output", "output/documentary.mp4"))),
            scenes=[self._parse_scene(item, index) for index, item in enumerate(scenes_raw, start=1)],
        )

    def _parse_scene(self, payload: Any, index: int) -> Scene:
        if not isinstance(payload, dict):
            raise ValidationError(f"Scene {index} must be a JSON object.")
        try:
            scene_type = SceneType.from_value(str(payload["type"]))
            motion = MotionType.from_value(str(payload.get("motion", MotionType.STATIC.value)))
            transition = TransitionType.from_value(str(payload.get("transition", TransitionType.HARD_CUT.value)))
        except KeyError as exc:
            raise ValidationError(f"Scene {index} is missing required field: {exc.args[0]}") from exc
        except ValueError as exc:
            raise ValidationError(f"Scene {index}: {exc}") from exc

        if "file" not in payload:
            raise ValidationError(f"Scene {index} is missing required field: file")

        sfx_raw = payload.get("sfx", [])
        if not isinstance(sfx_raw, list):
            raise ValidationError(f"Scene {index} sfx must be an array.")

        return Scene(
            type=scene_type,
            file=Path(str(payload["file"])),
            duration=self._optional_float(payload.get("duration")),
            motion=motion,
            transition=transition,
            transition_duration=self._optional_float(payload.get("transition_duration")),
            motion_speed=self._optional_float(payload.get("motion_speed")),
            start_time=self._optional_float(payload.get("start_time")),
            end_time=self._optional_float(payload.get("end_time")),
            sfx=[self._parse_sfx(item, index, cue_index) for cue_index, item in enumerate(sfx_raw, start=1)],
        )

    @staticmethod
    def _parse_sfx(payload: Any, scene_index: int, cue_index: int) -> SoundEffectCue:
        if not isinstance(payload, dict):
            raise ValidationError(f"Scene {scene_index} sfx {cue_index} must be a JSON object.")
        for field in ("name", "file", "at"):
            if field not in payload:
                raise ValidationError(f"Scene {scene_index} sfx {cue_index} is missing required field: {field}")
        return SoundEffectCue(
            name=str(payload["name"]),
            file=Path(str(payload["file"])),
            at=float(payload["at"]),
            volume=float(payload.get("volume", 0.9)),
        )

    @staticmethod
    def _optional_path(raw: Any) -> Path | None:
        if raw in (None, ""):
            return None
        return Path(str(raw))

    @staticmethod
    def _optional_float(raw: Any) -> float | None:
        if raw is None:
            return None
        return float(raw)
