"""Parser for flat V2.3 manifests produced by Prompt 3."""

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
    NarrationClip,
    ProjectConfig,
    Shot,
    SoundEffectCue,
    StoryFunction,
    TransitionType,
    TextOverlay,
    TextTrack,
    VisualEffect,
    VisualKeyframe,
    VisualLevel,
    VisualType,
)


class ManifestV23Parser:
    """Convert a V2.3 scene-centric manifest into the renderer's internal V2 manifest."""

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
        scenes_raw = payload.get("scenes")
        if not isinstance(scenes_raw, list):
            raise ValidationError("V2.3 manifest must contain a scenes array.")

        assets: dict[str, Asset] = {}
        shots: list[Shot] = []
        for index, scene in enumerate(scenes_raw, start=1):
            asset, shot = self._parse_scene(scene, index)
            assets[asset.asset_id] = asset
            shots.append(shot)

        narration_clip = self._parse_narration_clip(payload.get("narration_clip"))
        voice = narration_clip.file if narration_clip is not None else self._optional_path(payload.get("voice"))
        return Manifest(
            project=ProjectConfig(
                title=str(payload.get("title", "Untitled episode")),
                width=int(payload.get("width", 1920)),
                height=int(payload.get("height", 1080)),
                fps=int(payload.get("fps", 30)),
                voice=voice,
                narration_clip=narration_clip,
                output=Path(str(payload.get("output", "output/documentary.mp4"))),
                voice_volume=float(payload.get("voice_volume", 1.0)),
                duck_amount=float(payload.get("duck_amount", 0.35)),
                duck_fade_duration=float(payload.get("duck_fade_duration", 0.5)),
            ),
            assets=assets,
            shots=shots,
            music_cues=[self._parse_music_cue(item, i) for i, item in enumerate(payload.get("music_cues", []), start=1)],
            ambience_cues=[
                self._parse_ambience_cue(item, i) for i, item in enumerate(payload.get("ambience_cues", []), start=1)
            ],
            subtitle_file=self._optional_path(payload.get("subtitle_file")),
            subtitle_cues=[self._parse_text(item, f"subtitle-{i}") for i, item in enumerate(payload.get("subtitle_cues", []), start=1)],
            text_tracks=[self._parse_text_track(item, i) for i, item in enumerate(payload.get("text_tracks", []), start=1)],
        )

    def _parse_scene(self, payload: Any, index: int) -> tuple[Asset, Shot]:
        if not isinstance(payload, dict):
            raise ValidationError(f"Scene {index} must be a JSON object.")
        scene_id = self._scene_number(payload.get("scene_id", index), index)
        asset_id = f"ASSET_{scene_id:03d}"
        shot_id = f"SHOT_{scene_id:03d}"
        file = self._scene_file(payload, index)
        visual_level = VisualLevel.from_value(str(payload.get("visual_level", VisualLevel.GRAPHIC.value)))
        asset = Asset(
            asset_id=asset_id,
            type=AssetType.IMAGE,
            generation_source=self._generation_source(payload.get("final_source")),
            file=file,
            visual_level=visual_level,
        )
        shot = Shot(
            shot_id=shot_id,
            asset_id=asset_id,
            duration=self._scene_duration(payload, index),
            story_function=StoryFunction.from_value(str(payload.get("story_function", StoryFunction.CONTEXT.value))),
            visual_type=self._visual_type(payload.get("visual_type")),
            visual_level=visual_level,
            importance=int(payload.get("importance", 5)),
            crop=self._crop(payload.get("crop", CropType.WIDE.value)),
            focal_point=self._optional_point(payload.get("focal_point")),
            motion=MotionType.from_value(str(payload.get("motion", MotionType.STATIC.value))),
            transition=TransitionType.from_value(str(payload.get("transition", TransitionType.HARD_CUT.value))),
            transition_duration=self._optional_float(payload.get("transition_duration")),
            motion_speed=self._optional_float(payload.get("motion_speed")),
            sfx=[self._parse_sfx(item, index, i) for i, item in enumerate(payload.get("sfx", []), start=1)],
            keyframes=[self._parse_keyframe(item, index, i) for i, item in enumerate(payload.get("keyframes", []), start=1)],
            effects=[self._parse_effect(item, index, i) for i, item in enumerate(payload.get("effects", []), start=1)],
        )
        return asset, shot

    @staticmethod
    def _scene_file(payload: dict[str, Any], index: int) -> Path:
        raw = payload.get("file") or payload.get("flow_file")
        if raw in (None, ""):
            raise ValidationError(f"Scene {index} is missing file.")
        return Path(str(raw))

    @staticmethod
    def _scene_duration(payload: dict[str, Any], index: int) -> float:
        if "duration" in payload:
            return float(payload["duration"])
        if "start" in payload and "end" in payload:
            duration = float(payload["end"]) - float(payload["start"])
            if duration <= 0:
                raise ValidationError(f"Scene {index} end must be greater than start.")
            return duration
        raise ValidationError(f"Scene {index} is missing duration or start/end.")

    @staticmethod
    def _scene_number(raw: Any, index: int) -> int:
        value = str(raw)
        if value.upper().startswith("SCENE_"):
            value = value.split("_", 1)[1]
        try:
            return int(value)
        except ValueError as exc:
            raise ValidationError(f"Scene {index} has invalid scene_id: {raw}") from exc

    @staticmethod
    def _generation_source(raw: Any) -> GenerationSource:
        if str(raw).upper() == "RENDERER":
            return GenerationSource.RENDERER
        return GenerationSource.FLOW

    @staticmethod
    def _visual_type(raw: Any) -> VisualType:
        value = str(raw or VisualType.RECONSTRUCTION.value)
        aliases = {
            "BANK_TRANSFER_SCREEN": VisualType.EVIDENCE.value,
            "ESTABLISHING": VisualType.LOCATION.value,
            "PHONE_LOG": VisualType.EVIDENCE.value,
            "REAL_PHOTO_INSERT": VisualType.RECONSTRUCTION.value,
            "SURVEILLANCE_LAYOUT": VisualType.EVIDENCE.value,
            "THEORY_BOARD": VisualType.ABSTRACT.value,
        }
        value = aliases.get(value, value)
        try:
            return VisualType.from_value(value)
        except ValueError:
            return VisualType.ABSTRACT

    @staticmethod
    def _crop(raw: Any) -> CropType:
        value = str(raw)
        if value == "detail":
            value = CropType.CLOSE.value
        elif value == "vertical":
            value = CropType.WIDE.value
        return CropType.from_value(value)

    @staticmethod
    def _optional_point(raw: Any) -> tuple[float, float] | None:
        if raw in (None, ""):
            return None
        if not isinstance(raw, list) or len(raw) != 2:
            return None
        return float(raw[0]), float(raw[1])

    @staticmethod
    def _parse_music_cue(payload: Any, index: int) -> MusicCue:
        if not isinstance(payload, dict):
            raise ValidationError(f"Music cue {index} must be a JSON object.")
        return MusicCue(
            state=MusicState.from_value(str(payload.get("state", MusicState.NEUTRAL_DARK.value))),
            start=float(payload["start"]),
            end=float(payload["end"]),
            volume=float(payload.get("volume", 0.12)),
            track=Path(str(payload["file"])) if payload.get("file") else None,
        )

    @staticmethod
    def _parse_narration_clip(payload: Any) -> NarrationClip | None:
        if payload in (None, ""):
            return None
        if not isinstance(payload, dict) or not payload.get("file"):
            raise ValidationError("narration_clip must contain a file")
        source_in = float(payload.get("source_in", 0))
        source_out = payload.get("source_out")
        if source_in < 0 or (source_out is not None and float(source_out) <= source_in):
            raise ValidationError("narration_clip source_out must be greater than source_in")
        return NarrationClip(
            file=Path(str(payload["file"])),
            timeline_start=max(0.0, float(payload.get("timeline_start", 0))),
            source_in=source_in,
            source_out=float(source_out) if source_out is not None else None,
            volume=max(0.0, float(payload.get("volume", 1.0))),
        )

    @staticmethod
    def _parse_ambience_cue(payload: Any, index: int) -> AmbienceCue:
        if not isinstance(payload, dict):
            raise ValidationError(f"Ambience cue {index} must be a JSON object.")
        return AmbienceCue(
            name=str(payload.get("state") or payload.get("name") or f"ambience_{index}").lower(),
            file=Path(str(payload["file"])),
            start=float(payload["start"]),
            end=float(payload["end"]),
            volume=float(payload.get("volume", 0.04)),
        )

    @staticmethod
    def _parse_sfx(payload: Any, scene_index: int, cue_index: int) -> SoundEffectCue:
        if not isinstance(payload, dict):
            raise ValidationError(f"Scene {scene_index} sfx {cue_index} must be a JSON object.")
        return SoundEffectCue(
            name=str(payload["name"]),
            file=Path(str(payload["file"])),
            at=float(payload["at"]),
            volume=float(payload.get("volume", 0.9)),
        )

    @staticmethod
    def _parse_keyframe(payload: Any, scene_index: int, keyframe_index: int) -> VisualKeyframe:
        if not isinstance(payload, dict):
            raise ValidationError(f"Scene {scene_index} keyframe {keyframe_index} must be an object")
        return VisualKeyframe(
            time=max(0.0, float(payload.get("time", 0))),
            scale=max(1.0, float(payload.get("scale", 1))),
            x=min(1.0, max(0.0, float(payload.get("x", 0.5)))),
            y=min(1.0, max(0.0, float(payload.get("y", 0.5)))),
            rotation=float(payload.get("rotation", 0)),
        )

    @staticmethod
    def _parse_effect(payload: Any, scene_index: int, effect_index: int) -> VisualEffect:
        if not isinstance(payload, dict):
            raise ValidationError(f"Scene {scene_index} effect {effect_index} must be an object")
        start, end = float(payload.get("start", 0)), float(payload.get("end", 0))
        if end <= start:
            raise ValidationError(f"Scene {scene_index} effect {effect_index} end must be greater than start")
        return VisualEffect(
            id=str(payload.get("id", f"effect-{scene_index}-{effect_index}")),
            type=str(payload.get("type", "brightness")), start=start, end=end,
            intensity=min(1.0, max(0.0, float(payload.get("intensity", 0.5)))),
            enabled=bool(payload.get("enabled", True)), params=dict(payload.get("params") or {}),
        )

    @classmethod
    def _parse_text(cls, payload: Any, fallback_id: str) -> TextOverlay:
        if not isinstance(payload, dict):
            raise ValidationError("Text overlay must be an object")
        start, end = float(payload.get("start", 0)), float(payload.get("end", 0))
        if end <= start:
            raise ValidationError("Text overlay end must be greater than start")
        return TextOverlay(
            id=str(payload.get("id", fallback_id)), text=str(payload.get("text", "")), start=start, end=end,
            font=cls._optional_path(payload.get("font")), font_size=int(payload.get("font_size", 48)),
            color=str(payload.get("color", "#ffffff")), opacity=float(payload.get("opacity", 1)),
            bold=bool(payload.get("bold", False)), italic=bool(payload.get("italic", False)),
            underline=bool(payload.get("underline", False)), align=str(payload.get("align", "center")),
            x=float(payload.get("x", 0.5)), y=float(payload.get("y", 0.85)),
            outline=float(payload.get("outline", 2)), shadow=float(payload.get("shadow", 0)),
            animation_in=str(payload.get("animation_in", "none")), animation_out=str(payload.get("animation_out", "none")),
            transition_duration=float(payload.get("transition_duration", 0.3)),
        )

    @classmethod
    def _parse_text_track(cls, payload: Any, index: int) -> TextTrack:
        if not isinstance(payload, dict):
            raise ValidationError(f"Text track {index} must be an object")
        return TextTrack(
            id=str(payload.get("id", f"text-track-{index}")), name=str(payload.get("name", f"Texto {index}")),
            overlays=[cls._parse_text(item, f"text-{index}-{i}") for i, item in enumerate(payload.get("overlays", []), start=1)],
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
