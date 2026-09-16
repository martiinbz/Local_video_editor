"""Filesystem operations for the local editor project."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .audio_analysis import AudioAnalysisError, AudioAnalysisService
from .manifest_adapter import ManifestValidationError, editor_project_from_manifest, manifest_from_editor_project


class UnsafeMediaPathError(ValueError):
    """Raised when a requested media path is missing or outside the workspace."""


class ProjectService:
    MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".srt", ".ttf", ".otf", ".woff", ".woff2"}

    AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}

    def __init__(self, root: Path, audio_analysis: Any | None = None, project_name: str | None = None) -> None:
        self.root = root.resolve()
        self.project_name = project_name or "default"
        self.project_root = self.root if not project_name else self.root / "projects" / project_name
        self.source_path = self.project_root / "project" / "manifest.json" if project_name else self.root / "project" / "manifest.json"
        if project_name and not self.source_path.is_file():
            self.source_path = self.project_root / "manifest.json"
        self.editor_path = self.source_path.with_name("manifest.editor.json")
        self.audio_analysis = audio_analysis or AudioAnalysisService(self.root / ".cache" / "editor-waveforms")

    def load(self) -> dict[str, Any]:
        load_path = self.editor_path if self.editor_path.is_file() else self.source_path
        manifest = json.loads(load_path.read_text(encoding="utf-8"))
        is_master_manifest = manifest.get("manifest_type") == "MASTER_MANIFEST"
        if is_master_manifest and not manifest.get("voice") and (self.project_root / "narration.mp3").is_file():
            manifest["voice"] = "narration.mp3"
        project = editor_project_from_manifest(manifest)
        if is_master_manifest:
            for scene in project["visualTrack"]:
                if not self._media_exists(scene["file"]) and self._media_exists(scene["flowFile"]):
                    scene["file"] = scene["flowFile"]
        project_base = self.project_root
        project["projectId"] = self.project_name
        project["files"] = {
            "images": self._list_media(project_base / "project" / "images", {".jpg", ".jpeg", ".png", ".webp"}),
            "music": self._list_media(self.root / "assets" / "music", {".mp3", ".wav", ".m4a", ".aac"}, relative_to=self.root),
            "ambience": self._list_media(self.root / "assets" / "ambience", {".mp3", ".wav", ".m4a", ".aac"}, relative_to=self.root),
            "sfx": self._list_media(self.root / "assets" / "sfx", {".mp3", ".wav", ".m4a", ".aac"}, relative_to=self.root),
        }
        project["audioLibrary"] = {
            kind: [self._audio_item(path, kind) for path in project["files"][kind]]
            for kind in ("music", "ambience", "sfx")
        }
        project["subtitleLibrary"] = self.list_subtitles()
        project["fontLibrary"] = self.list_fonts()
        durations = {
            item["path"]: item["duration"]
            for items in project["audioLibrary"].values()
            for item in items
        }
        narration = project.get("narrationTrack", {})
        if narration.get("file"):
            try:
                narration["sourceDuration"] = float(
                    self.audio_analysis.metadata(self.project_root / narration["file"])["duration"]
                )
            except (AudioAnalysisError, OSError, KeyError, TypeError, ValueError):
                narration["sourceDuration"] = narration.get("sourceOut", 0)
        for track_name, kind in (("musicTrack", "music"), ("ambienceTrack", "ambience"), ("sfxTrack", "sfx")):
            for cue in project.get(track_name, []):
                cue.setdefault("type", kind)
                cue["sourceDuration"] = durations.get(cue.get("file"), 0.0)
                cue.setdefault("duration", max(0.0, float(cue.get("end", cue.get("start", 0))) - float(cue.get("start", 0))))
        return project

    def save(self, project: dict[str, Any]) -> Path:
        self._validate_editor_paths(project)
        manifest = manifest_from_editor_project(project)
        self.editor_path.parent.mkdir(parents=True, exist_ok=True)
        self.editor_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self.editor_path

    def _validate_editor_paths(self, project: dict[str, Any]) -> None:
        try:
            subtitle_file = project.get("subtitleFile")
            if subtitle_file:
                self.resolve_subtitle(str(subtitle_file))
            overlays = [
                overlay
                for track in project.get("textTracks", [])
                for overlay in track.get("overlays", [])
            ]
            overlays.extend(project.get("subtitleTrack", []))
            for overlay in overlays:
                if overlay.get("font"):
                    try:
                        self.resolve_font(str(overlay["font"]))
                    except UnsafeMediaPathError as exc:
                        if not self._is_missing_shared_font(str(overlay["font"]), exc):
                            raise
        except UnsafeMediaPathError as exc:
            raise ManifestValidationError(f"Invalid subtitle or font reference: {exc}") from exc

    def resolve_media(self, requested: str) -> Path:
        requested_path = Path(requested)
        if requested_path.parts and requested_path.parts[0].lower() == "assets":
            candidate = (self.root / requested_path).resolve()
            allowed_root = self.root
            outside_message = "Media path is outside the renderer root"
        else:
            candidate = (self.project_root / requested_path).resolve()
            allowed_root = self.project_root
            outside_message = "Media path is outside the project"
        try:
            candidate.relative_to(allowed_root)
        except ValueError as exc:
            raise UnsafeMediaPathError(outside_message) from exc
        if not candidate.is_file():
            for fallback in self._legacy_project_candidates(requested_path):
                if fallback.is_file():
                    candidate = fallback
                    break
            else:
                raise UnsafeMediaPathError("Media file does not exist")
        if candidate.suffix.lower() not in self.MEDIA_EXTENSIONS:
            raise UnsafeMediaPathError("Requested file is not an allowed media type")
        return candidate

    def _legacy_project_candidates(self, requested_path: Path) -> tuple[Path, ...]:
        """Locate MASTER_MANIFEST media stored beside, not inside, ``project/``."""

        if not requested_path.parts or requested_path.parts[0].lower() != "project":
            return ()
        legacy = self.project_root.joinpath(*requested_path.parts[1:])
        candidates = [legacy]
        match = re.fullmatch(r"(SCENE_)(0*)(\d+)(\.[^.]+)", legacy.name, re.IGNORECASE)
        if match:
            candidates.append(legacy.with_name(f"{match.group(1)}{int(match.group(3))}{match.group(4)}"))
        return tuple(candidates)

    def _media_exists(self, requested: str) -> bool:
        try:
            self.resolve_media(requested)
        except UnsafeMediaPathError:
            return False
        return True

    def _is_missing_shared_font(self, requested: str, error: UnsafeMediaPathError) -> bool:
        """Allow stale shared font references; the renderer will use its fallback font."""

        if str(error) != "Media file does not exist":
            return False
        requested_path = Path(requested)
        if not requested_path.parts or requested_path.parts[0].lower() != "assets":
            return False
        if requested_path.suffix.lower() not in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}:
            return False
        candidate = (self.root / requested_path).resolve()
        allowed = (self.root / "assets" / "fonts").resolve()
        try:
            candidate.relative_to(allowed)
        except ValueError:
            return False
        return True

    def resolve_audio(self, requested: str) -> Path:
        candidate = self.resolve_media(requested)
        if candidate.suffix.lower() not in self.AUDIO_EXTENSIONS:
            raise UnsafeMediaPathError("Requested file is not an allowed audio type")
        return candidate

    def list_subtitles(self) -> list[dict[str, str]]:
        return [
            {"path": path, "name": Path(path).name}
            for path in self._list_media(self.project_root / "project" / "subtitles", {".srt"})
        ]

    def list_fonts(self) -> list[dict[str, str]]:
        return [
            {"path": path, "name": Path(path).name, "family": Path(path).stem}
            for path in self._list_media(self.root / "assets" / "fonts", {".ttf", ".otf", ".woff", ".woff2"}, relative_to=self.root)
        ]

    def resolve_subtitle(self, requested: str) -> Path:
        path = self.resolve_media(requested)
        allowed = (self.project_root / "project" / "subtitles").resolve()
        if path.suffix.lower() != ".srt" or allowed not in path.parents:
            raise UnsafeMediaPathError("Requested file is not a project subtitle")
        return path

    def resolve_font(self, requested: str) -> Path:
        path = self.resolve_media(requested)
        allowed = (self.root / "assets" / "fonts").resolve()
        if path.suffix.lower() not in {".ttf", ".otf", ".woff", ".woff2"} or allowed not in path.parents:
            raise UnsafeMediaPathError("Requested file is not a project font")
        return path

    def _audio_item(self, relative_path: str, kind: str) -> dict[str, Any]:
        path = self.resolve_media(relative_path)
        try:
            duration = float(self.audio_analysis.metadata(path)["duration"])
        except (AudioAnalysisError, OSError, KeyError, TypeError, ValueError):
            duration = 0.0
        return {"path": relative_path, "name": path.name, "duration": duration, "type": kind}

    def _list_media(self, directory: Path, extensions: set[str], relative_to: Path | None = None) -> list[str]:
        if not directory.exists():
            return []
        base = relative_to or self.project_root
        return sorted(
            path.relative_to(base).as_posix()
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in extensions
        )
