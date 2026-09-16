"""V2 master manifest JSON parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exceptions import StoryboardParseError, ValidationError
from models import (
    AmbienceCue,
    Asset,
    AssetType,
    CropType,
    GenerationSource,
    Manifest,
    MotionType,
    MusicCue,
    MusicState,
    OverlaySpec,
    OverlayType,
    ProjectConfig,
    Shot,
    SoundEffectCue,
    StoryFunction,
    TransitionType,
    VisualLevel,
    VisualType,
)


class ManifestParser:
    """Load V2 master manifests into typed models."""

    def parse(self, path: str | Path) -> Manifest:
        manifest_path = Path(path)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise StoryboardParseError(f"Manifest not found: {manifest_path}") from exc
        except json.JSONDecodeError as exc:
            raise StoryboardParseError(f"Invalid JSON in {manifest_path}: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise StoryboardParseError("Manifest root must be a JSON object.")
        return self._parse_payload(payload)

    def _parse_payload(self, payload: dict[str, Any]) -> Manifest:
        project_raw = payload.get("project")
        assets_raw = payload.get("assets")
        shots_raw = payload.get("shots")
        if not isinstance(project_raw, dict):
            raise ValidationError("Manifest must contain a project object.")
        if not isinstance(assets_raw, list):
            raise ValidationError("Manifest must contain an assets array.")
        if not isinstance(shots_raw, list):
            raise ValidationError("Manifest must contain a shots array.")

        assets = [self._parse_asset(item, index) for index, item in enumerate(assets_raw, start=1)]
        return Manifest(
            project=self._parse_project(project_raw),
            assets={asset.asset_id: asset for asset in assets},
            shots=[self._parse_shot(item, index) for index, item in enumerate(shots_raw, start=1)],
            music_cues=[
                self._parse_music_cue(item, index)
                for index, item in enumerate(payload.get("music_cues", []), start=1)
            ],
            ambience_cues=[
                self._parse_ambience_cue(item, index)
                for index, item in enumerate(payload.get("ambience_cues", []), start=1)
            ],
        )

    def _parse_project(self, payload: dict[str, Any]) -> ProjectConfig:
        return ProjectConfig(
            title=str(payload.get("title", "Untitled episode")),
            width=int(payload.get("width", 1920)),
            height=int(payload.get("height", 1080)),
            fps=int(payload.get("fps", 30)),
            voice=self._optional_path(payload.get("voice")),
            transcript=self._optional_path(payload.get("transcript")),
            output=Path(str(payload.get("output", "output/documentary.mp4"))),
            accent_color=str(payload.get("accent_color", "#A33A2A")),
            voice_volume=float(payload.get("voice_volume", 1.0)),
            duck_amount=float(payload.get("duck_amount", 0.35)),
            duck_fade_duration=float(payload.get("duck_fade_duration", 0.5)),
        )

    def _parse_asset(self, payload: Any, index: int) -> Asset:
        if not isinstance(payload, dict):
            raise ValidationError(f"Asset {index} must be a JSON object.")
        for field in ("asset_id", "type", "generation_source", "visual_level"):
            if field not in payload:
                raise ValidationError(f"Asset {index} is missing required field: {field}")
        generation_source = GenerationSource.from_value(str(payload["generation_source"]))
        file = self._optional_path(payload.get("file"))
        overlay = self._parse_overlay(payload.get("overlay"), index)
        return Asset(
            asset_id=str(payload["asset_id"]),
            type=AssetType.from_value(str(payload["type"])),
            generation_source=generation_source,
            file=file,
            visual_level=VisualLevel.from_value(str(payload["visual_level"])),
            overlay=overlay,
            focal_points=self._parse_focal_points(payload.get("focal_points", {}), f"Asset {index}"),
        )

    def _parse_overlay(self, payload: Any, asset_index: int) -> OverlaySpec | None:
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValidationError(f"Asset {asset_index} overlay must be a JSON object.")
        for field in ("type", "data"):
            if field not in payload:
                raise ValidationError(f"Asset {asset_index} overlay is missing required field: {field}")
        if not isinstance(payload["data"], dict):
            raise ValidationError(f"Asset {asset_index} overlay data must be an object.")
        return OverlaySpec(type=OverlayType.from_value(str(payload["type"])), data=dict(payload["data"]))

    def _parse_shot(self, payload: Any, index: int) -> Shot:
        if not isinstance(payload, dict):
            raise ValidationError(f"Shot {index} must be a JSON object.")
        required = ("shot_id", "asset_id", "duration", "story_function", "visual_type", "visual_level", "importance")
        for field in required:
            if field not in payload:
                raise ValidationError(f"Shot {index} is missing required field: {field}")
        return Shot(
            shot_id=str(payload["shot_id"]),
            asset_id=str(payload["asset_id"]),
            duration=float(payload["duration"]),
            story_function=StoryFunction.from_value(str(payload["story_function"])),
            visual_type=VisualType.from_value(str(payload["visual_type"])),
            visual_level=VisualLevel.from_value(str(payload["visual_level"])),
            importance=int(payload["importance"]),
            crop=CropType.from_value(str(payload.get("crop", CropType.WIDE.value))),
            focal_point=self._optional_point(payload.get("focal_point"), f"Shot {index} focal_point"),
            motion=MotionType.from_value(str(payload.get("motion", MotionType.STATIC.value))),
            transition=TransitionType.from_value(str(payload.get("transition", TransitionType.HARD_CUT.value))),
            transition_duration=self._optional_float(payload.get("transition_duration")),
            motion_speed=self._optional_float(payload.get("motion_speed")),
            sfx=[
                self._parse_sfx(item, index, cue_index)
                for cue_index, item in enumerate(payload.get("sfx", []), start=1)
            ],
        )

    def _parse_music_cue(self, payload: Any, index: int) -> MusicCue:
        if not isinstance(payload, dict):
            raise ValidationError(f"Music cue {index} must be a JSON object.")
        for field in ("state", "start", "end"):
            if field not in payload:
                raise ValidationError(f"Music cue {index} is missing required field: {field}")
        return MusicCue(
            state=MusicState.from_value(str(payload["state"])),
            start=float(payload["start"]),
            end=float(payload["end"]),
            volume=float(payload.get("volume", 0.12)),
            track=self._optional_path(payload.get("track")),
        )

    def _parse_ambience_cue(self, payload: Any, index: int) -> AmbienceCue:
        if not isinstance(payload, dict):
            raise ValidationError(f"Ambience cue {index} must be a JSON object.")
        for field in ("name", "file", "start", "end"):
            if field not in payload:
                raise ValidationError(f"Ambience cue {index} is missing required field: {field}")
        return AmbienceCue(
            name=str(payload["name"]),
            file=Path(str(payload["file"])),
            start=float(payload["start"]),
            end=float(payload["end"]),
            volume=float(payload.get("volume", 0.04)),
        )

    @classmethod
    def _parse_focal_points(cls, payload: Any, label: str) -> dict[str, tuple[float, float]]:
        if not isinstance(payload, dict):
            raise ValidationError(f"{label} focal_points must be an object.")
        return {str(name): cls._point(value, f"{label} focal_points.{name}") for name, value in payload.items()}

    @classmethod
    def _optional_point(cls, payload: Any, label: str) -> tuple[float, float] | None:
        if payload is None:
            return None
        return cls._point(payload, label)

    @staticmethod
    def _point(payload: Any, label: str) -> tuple[float, float]:
        if not isinstance(payload, list) or len(payload) != 2:
            raise ValidationError(f"{label} must be [x, y].")
        return float(payload[0]), float(payload[1])

    @staticmethod
    def _parse_sfx(payload: Any, shot_index: int, cue_index: int) -> SoundEffectCue:
        if not isinstance(payload, dict):
            raise ValidationError(f"Shot {shot_index} sfx {cue_index} must be a JSON object.")
        for field in ("name", "file", "at"):
            if field not in payload:
                raise ValidationError(f"Shot {shot_index} sfx {cue_index} is missing required field: {field}")
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
