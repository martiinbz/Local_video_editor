"""Automatic V2 manifest quality checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from models import Manifest, MotionType


@dataclass(frozen=True, slots=True)
class QCReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def text(self) -> str:
        lines = ["QC REPORT"]
        if not self.errors and not self.warnings:
            lines.append("OK: no issues found.")
        for error in self.errors:
            lines.append(f"ERROR: {error}")
        for warning in self.warnings:
            lines.append(f"WARNING: {warning}")
        return "\n".join(lines) + "\n"


class QualityControl:
    """Run non-destructive checks before expensive rendering."""

    def check(self, manifest: Manifest) -> QCReport:
        errors: list[str] = []
        warnings: list[str] = []

        if not manifest.assets:
            errors.append("Manifest has no assets.")
        if not manifest.shots:
            errors.append("Manifest has no shots.")

        consecutive_zoom_in = 0
        for shot in manifest.shots:
            if shot.duration < 1.8:
                errors.append(f"{shot.shot_id} duration is below 1.8s.")
            if shot.duration > 10:
                warnings.append(f"{shot.shot_id} duration is above 10s.")
            if shot.motion is MotionType.ZOOM_IN:
                consecutive_zoom_in += 1
                if consecutive_zoom_in > 3:
                    warnings.append("More than 3 zoom_in shots in a row.")
                    break
            else:
                consecutive_zoom_in = 0

        dark_impact_times: list[float] = []
        cursor = 0.0
        for shot in manifest.shots:
            for cue in shot.sfx:
                absolute_at = cursor + cue.at
                if dark_impact_times and absolute_at - dark_impact_times[-1] < 30 and cue.name == "dark_impact":
                    warnings.append("Two dark_impact SFX occur less than 30s apart.")
                if cue.name == "dark_impact":
                    dark_impact_times.append(absolute_at)
            cursor += shot.duration

        return QCReport(errors=errors, warnings=warnings)

    @staticmethod
    def write_report(report: QCReport, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.text(), encoding="utf-8")
        return path
