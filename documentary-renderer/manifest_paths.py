"""Path normalization for project-local media and shared renderer assets."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from models import AmbienceCue, Manifest, MusicCue, NarrationClip, SoundEffectCue


def normalize_manifest_paths(manifest: Manifest, project_dir: str | Path, renderer_root: str | Path) -> Manifest:
    """Resolve V2 manifest paths against a selected project and shared assets.

    Rules:
    - `assets/...` paths are shared and resolve from the renderer root.
    - `project/...` paths are legacy project-local paths; strip `project/` and resolve from project_dir.
    - other relative paths resolve from project_dir.
    - `output/...` is project-local, so rendered MP4/QC sit inside the selected project.
    """

    project_dir = Path(project_dir)
    renderer_root = Path(renderer_root)

    manifest.project = replace(
        manifest.project,
        voice=_resolve_optional(manifest.project.voice, project_dir, renderer_root),
        transcript=_resolve_optional(manifest.project.transcript, project_dir, renderer_root),
        output=_resolve_project_path(manifest.project.output, project_dir),
        narration_clip=_resolve_narration_clip(manifest.project.narration_clip, project_dir, renderer_root),
    )

    if manifest.subtitle_file is not None:
        manifest.subtitle_file = _resolve_path(manifest.subtitle_file, project_dir, renderer_root)

    for asset in manifest.assets.values():
        if asset.file is not None:
            asset.file = _resolve_path(asset.file, project_dir, renderer_root)

    for shot in manifest.shots:
        shot.sfx = [
            SoundEffectCue(name=cue.name, file=_resolve_path(cue.file, project_dir, renderer_root), at=cue.at, volume=cue.volume)
            for cue in shot.sfx
        ]

    manifest.music_cues = [
        MusicCue(
            state=cue.state,
            start=cue.start,
            end=cue.end,
            volume=cue.volume,
            track=_resolve_optional(cue.track, project_dir, renderer_root),
        )
        for cue in manifest.music_cues
    ]
    manifest.ambience_cues = [
        AmbienceCue(
            name=cue.name,
            file=_resolve_path(cue.file, project_dir, renderer_root),
            start=cue.start,
            end=cue.end,
            volume=cue.volume,
        )
        for cue in manifest.ambience_cues
    ]
    return manifest


def _resolve_narration_clip(
    clip: NarrationClip | None,
    project_dir: Path,
    renderer_root: Path,
) -> NarrationClip | None:
    if clip is None:
        return None
    return replace(clip, file=_resolve_path(clip.file, project_dir, renderer_root))


def _resolve_optional(path: Path | None, project_dir: Path, renderer_root: Path) -> Path | None:
    if path is None:
        return None
    return _resolve_path(path, project_dir, renderer_root)


def _resolve_path(path: Path, project_dir: Path, renderer_root: Path) -> Path:
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0].lower() == "assets":
        return renderer_root.joinpath(*parts)
    return _resolve_project_path(path, project_dir)


def _resolve_project_path(path: Path, project_dir: Path) -> Path:
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0].lower() == "project":
        return project_dir.joinpath(*parts[1:])
    return project_dir / path
