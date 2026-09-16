"""Import keyed timeline manifests into the editor's V2 scene format."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from utils import probe_media_duration


def build_editor_manifest(
    source: dict[str, Any],
    previous: dict[str, Any] | None,
    project_name: str,
    subtitle_file: str = "",
    timeline_end: float | None = None,
) -> dict[str, Any]:
    """Convert a keyed ``SCENE_N`` manifest while retaining timeline-level edits."""

    scenes = [_scene_from_source(scene_id, payload) for scene_id, payload in _ordered_scenes(source)]
    if not scenes:
        raise ValueError("The source manifest does not contain any SCENE_N entries.")
    _cover_full_timeline(scenes, timeline_end)

    previous = previous or {}
    manifest: dict[str, Any] = {
        "manifest_version": "2.6",
        "project_title": previous.get("project_title", project_name),
        "voice": previous.get("voice") or "narration.mp3",
        "voice_volume": previous.get("voice_volume", 1.0),
        "duck_amount": previous.get("duck_amount", 0.35),
        "audio_duration_seconds": scenes[-1]["end"],
        "output": previous.get("output", f"output/{project_name}.mp4"),
        "scenes": scenes,
        "subtitle_file": previous.get("subtitle_file") or subtitle_file,
        "subtitle_cues": deepcopy(previous.get("subtitle_cues", [])),
        "text_tracks": deepcopy(previous.get("text_tracks", [])),
        "music_cues": deepcopy(previous.get("music_cues", [])),
        "ambience_cues": deepcopy(previous.get("ambience_cues", [])),
        "track_order": deepcopy(previous.get("track_order", [])),
        "track_settings": deepcopy(previous.get("track_settings", {})),
    }
    _transfer_scene_timeline_edits(previous.get("scenes", []), scenes)
    return manifest


def migrate_project(root: Path, project_name: str) -> tuple[Path, Path | None]:
    """Write a converted editor manifest and return it with its backup, if any."""

    project_root = (root / "projects" / project_name).resolve()
    source_path = project_root / "manifest.json"
    editor_path = project_root / "manifest.editor.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    previous = json.loads(editor_path.read_text(encoding="utf-8")) if editor_path.is_file() else None
    subtitles = sorted((project_root / "project" / "subtitles").glob("*.srt"))
    subtitle_file = f"project/subtitles/{subtitles[0].name}" if subtitles else ""
    audio_file = project_root / "narration.mp3"
    try:
        timeline_end = probe_media_duration(audio_file) if audio_file.is_file() else None
    except Exception:
        timeline_end = None
    migrated = build_editor_manifest(source, previous, project_name, subtitle_file, timeline_end)

    backup_path = None
    if editor_path.is_file():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = editor_path.with_name(f"manifest.editor.backup-{stamp}.json")
        backup_path.write_text(editor_path.read_text(encoding="utf-8"), encoding="utf-8")
    editor_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return editor_path, backup_path


def _ordered_scenes(source: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    # Master manifests may be wrapped in MASTER_MANIFEST and may store scenes
    # as an ordered list instead of keyed SCENE_N entries.
    if isinstance(source.get("MASTER_MANIFEST"), dict):
        source = source["MASTER_MANIFEST"]
    if isinstance(source.get("scenes"), list):
        return [
            (str(scene.get("scene_id", f"SCENE_{index}")), scene)
            for index, scene in enumerate(source["scenes"], start=1)
            if isinstance(scene, dict)
        ]
    entries = [
        (scene_id, payload)
        for scene_id, payload in source.items()
        if re.fullmatch(r"SCENE_\d+", str(scene_id), re.IGNORECASE) and isinstance(payload, dict)
    ]
    return sorted(entries, key=lambda item: int(item[0].split("_", 1)[1]))


def _scene_from_source(scene_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    start = _timeline_value(payload.get("start_time", payload.get("timecode_start", payload.get("start", 0))))
    end = _timeline_value(payload.get("end_time", payload.get("timecode_end", payload.get("end", payload.get("duration_seconds", 0)))))
    if not any(key in payload for key in ("end_time", "timecode_end", "end")):
        end = start + _timeline_value(payload.get("duration_seconds", payload.get("duration", 0)))
    if end <= start:
        raise ValueError(f"{scene_id} has an invalid duration.")
    number = int(re.search(r"(\d+)$", scene_id).group(1))
    filename = f"project/images/SCENE_{number}.jpg"
    return {
        "scene_id": f"SCENE_{number}",
        "start": start,
        "end": end,
        "duration": round(end - start, 3),
        "file": filename,
        "flow_file": filename,
        "motion": "static",
        "motion_speed": 0.5,
        "crop": "wide",
        "focal_point": [0.5, 0.5],
        "transition": "hard_cut",
        "transition_duration": 0.5,
        "beat": payload.get("narration_fragment", payload.get("narration_excerpt", payload.get("narration_line", payload.get("beat", "")))),
        "visual_level": payload.get("visual_level", "GRAPHIC"),
        "focus": payload.get("visual_concept", payload.get("visual_description", "")),
        "keyframes": [],
        "effects": [],
        "sfx": [],
    }


def _cover_full_timeline(scenes: list[dict[str, Any]], timeline_end: float | None) -> None:
    """Keep source scene change points while filling natural narration pauses."""

    source_starts = [scene["start"] for scene in scenes]
    end = round(timeline_end if timeline_end is not None else scenes[-1]["end"], 3)
    if end < source_starts[-1]:
        raise ValueError("The narration ends before the last source scene begins.")
    for index, scene in enumerate(scenes):
        scene_start = 0.0 if index == 0 else source_starts[index]
        scene_end = source_starts[index + 1] if index + 1 < len(scenes) else end
        if scene_end <= scene_start:
            raise ValueError(f"{scene['scene_id']} has an invalid covered duration.")
        scene["start"] = round(scene_start, 3)
        scene["end"] = round(scene_end, 3)
        scene["duration"] = round(scene_end - scene_start, 3)


def _timestamp_seconds(value: Any) -> float:
    try:
        hours, minutes, seconds = str(value).replace(",", ".").split(":")
        return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 3)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid timeline timestamp: {value}") from exc


def _timeline_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return round(float(value), 3)
    text = str(value)
    if text.count(":") == 1:
        minutes, seconds = text.split(":")
        return round(int(minutes) * 60 + float(seconds), 3)
    return _timestamp_seconds(text)


def _transfer_scene_timeline_edits(previous_scenes: list[dict[str, Any]], target_scenes: list[dict[str, Any]]) -> None:
    for source_scene in previous_scenes:
        scene_start = _number(source_scene.get("start"))
        for keyframe in source_scene.get("keyframes", []):
            destination = _scene_at(target_scenes, scene_start + _number(keyframe.get("time")))
            if destination:
                item = deepcopy(keyframe)
                item["time"] = round(scene_start + _number(keyframe.get("time")) - destination["start"], 3)
                destination["keyframes"].append(item)
        for sfx in source_scene.get("sfx", []):
            destination = _scene_at(target_scenes, scene_start + _number(sfx.get("at")))
            if destination:
                item = deepcopy(sfx)
                item["at"] = round(scene_start + _number(sfx.get("at")) - destination["start"], 3)
                destination["sfx"].append(item)
        for effect in source_scene.get("effects", []):
            absolute_start = scene_start + _number(effect.get("start"))
            absolute_end = scene_start + _number(effect.get("end"))
            for part, destination in enumerate(target_scenes, start=1):
                start = max(absolute_start, destination["start"])
                end = min(absolute_end, destination["end"])
                if end <= start:
                    continue
                item = deepcopy(effect)
                item["id"] = f"{effect.get('id', 'effect')}-{part}"
                item["start"] = round(start - destination["start"], 3)
                item["end"] = round(end - destination["start"], 3)
                destination["effects"].append(item)


def _scene_at(scenes: list[dict[str, Any]], time: float) -> dict[str, Any] | None:
    for index, scene in enumerate(scenes):
        if scene["start"] <= time < scene["end"] or (index == len(scenes) - 1 and time == scene["end"]):
            return scene
    return None


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
