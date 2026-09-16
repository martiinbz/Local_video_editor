"""V2 manifest validation."""

from __future__ import annotations

from pathlib import Path

from exceptions import ValidationError
from models import CropType, GenerationSource, Manifest


class ManifestValidator:
    """Validate V2 manifests before rendering."""

    def validate(self, manifest: Manifest) -> None:
        self._positive_int(manifest.project.width, "width")
        self._positive_int(manifest.project.height, "height")
        self._positive_int(manifest.project.fps, "fps")
        self._optional_existing_file(manifest.project.voice, "voice")
        self._optional_existing_file(manifest.project.transcript, "transcript")
        self._range(manifest.project.duck_amount, "duck_amount", 0, 1)
        self._positive_float(manifest.project.duck_fade_duration, "duck_fade_duration")

        if not manifest.assets:
            raise ValidationError("Manifest must contain at least one asset.")
        if not manifest.shots:
            raise ValidationError("Manifest must contain at least one shot.")

        for asset in manifest.assets.values():
            if asset.file is None:
                if asset.generation_source is not GenerationSource.RENDERER or asset.overlay is None:
                    raise ValidationError(f"Asset {asset.asset_id} requires file unless it has a renderer overlay.")
            else:
                self._existing_file(asset.file, f"Asset {asset.asset_id} file")
            for name, point in asset.focal_points.items():
                self._focal_point(point, f"Asset {asset.asset_id} focal_points.{name}")

        for shot in manifest.shots:
            if shot.asset_id not in manifest.assets:
                raise ValidationError(f"Shot {shot.shot_id} references missing asset: {shot.asset_id}")
            self._positive_float(shot.duration, f"Shot {shot.shot_id} duration")
            self._range(shot.importance, f"Shot {shot.shot_id} importance", 1, 10)
            if shot.crop is CropType.FOCAL and shot.focal_point is None:
                raise ValidationError(f"Shot {shot.shot_id} focal crop requires focal_point.")
            if shot.focal_point is not None:
                self._focal_point(shot.focal_point, f"Shot {shot.shot_id} focal_point")
            if shot.transition_duration is not None:
                self._positive_float(shot.transition_duration, f"Shot {shot.shot_id} transition_duration")
            if shot.motion_speed is not None:
                self._positive_float(shot.motion_speed, f"Shot {shot.shot_id} motion_speed")
            for cue_index, cue in enumerate(shot.sfx, start=1):
                self._existing_file(cue.file, f"Shot {shot.shot_id} sfx {cue_index} file")
                if cue.at < 0 or cue.at >= shot.duration:
                    raise ValidationError(f"Shot {shot.shot_id} sfx {cue_index} at must be within shot duration.")
                self._volume(cue.volume, f"Shot {shot.shot_id} sfx {cue_index} volume")

        for index, cue in enumerate(manifest.music_cues, start=1):
            self._cue_range(cue.start, cue.end, f"Music cue {index}")
            self._volume(cue.volume, f"Music cue {index} volume")
            self._optional_existing_file(cue.track, f"Music cue {index} track")

        for index, cue in enumerate(manifest.ambience_cues, start=1):
            self._cue_range(cue.start, cue.end, f"Ambience cue {index}")
            self._volume(cue.volume, f"Ambience cue {index} volume")
            self._existing_file(cue.file, f"Ambience cue {index} file")

    @staticmethod
    def _existing_file(path: Path, label: str) -> None:
        if not path.exists():
            raise ValidationError(f"{label} does not exist: {path}")

    @classmethod
    def _optional_existing_file(cls, path: Path | None, label: str) -> None:
        if path is not None:
            cls._existing_file(path, label)

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

    @classmethod
    def _focal_point(cls, point: tuple[float, float], label: str) -> None:
        cls._range(point[0], label, 0, 1)
        cls._range(point[1], label, 0, 1)

    @staticmethod
    def _cue_range(start: float, end: float, label: str) -> None:
        if start < 0:
            raise ValidationError(f"{label} start cannot be negative.")
        if end <= start:
            raise ValidationError(f"{label} end must be greater than start.")
