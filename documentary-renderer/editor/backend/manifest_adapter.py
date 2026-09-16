"""Lossless conversion between a flat V2.6 manifest and editor state."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


class ManifestValidationError(ValueError):
    """Raised when editor data cannot be converted to a render manifest."""


DEFAULT_SCENE = {
    "motion": "static",
    "motion_speed": 0.5,
    "crop": "wide",
    "focal_point": [0.5, 0.5],
    "transition": "hard_cut",
    "transition_duration": 0.5,
}


def _number(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _scene_duration(scene: dict[str, Any]) -> float:
    if scene.get("duration") is not None:
        return round(_number(scene["duration"]), 3)
    if scene.get("duration_seconds") is not None:
        return round(_number(scene["duration_seconds"]), 3)
    return round(_number(scene.get("end")) - _number(scene.get("start")), 3)


def editor_project_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Build browser-friendly tracks while retaining the source manifest."""

    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ManifestValidationError("Manifest must contain a non-empty scenes list")

    visual_track: list[dict[str, Any]] = []
    sfx_track: list[dict[str, Any]] = []
    cursor = 0.0
    for index, source in enumerate(scenes):
        duration = _scene_duration(source)
        if duration <= 0:
            raise ManifestValidationError(f"Scene {index + 1} has an invalid duration")
        start = round(cursor, 3)
        end = round(start + duration, 3)
        scene_id = str(source.get("scene_id", f"SCENE_{index + 1}"))
        scene = {
            "id": scene_id,
            "sceneId": scene_id,
            "index": index,
            "start": start,
            "end": end,
            "duration": duration,
            "file": source.get("file") or source.get("flow_file") or "",
            "flowFile": source.get("flow_file") or source.get("file") or "",
            "motion": source.get("motion", DEFAULT_SCENE["motion"]),
            "motionSpeed": _number(source.get("motion_speed"), DEFAULT_SCENE["motion_speed"]),
            "crop": source.get("crop", DEFAULT_SCENE["crop"]),
            "focalPoint": source.get("focal_point", DEFAULT_SCENE["focal_point"]),
            "transition": source.get("transition", DEFAULT_SCENE["transition"]),
            "transitionDuration": _number(
                source.get("transition_duration"), DEFAULT_SCENE["transition_duration"]
            ),
            "beat": source.get("beat", ""),
            "visualType": source.get("visual_type", ""),
            "visualLevel": source.get("visual_level", ""),
            "focus": source.get("focus", ""),
            "keyframes": deepcopy(source.get("keyframes", [])),
            "effects": deepcopy(source.get("effects", [])),
        }
        visual_track.append(scene)
        for cue_index, cue in enumerate(source.get("sfx", [])):
            item = deepcopy(cue)
            item.update(
                {
                    "id": f"{scene_id}-sfx-{cue_index}",
                    "sceneId": scene_id,
                    "start": round(start + _number(cue.get("at")), 3),
                }
            )
            sfx_track.append(item)
        cursor = end

    narration_source = deepcopy(manifest.get("narration_clip") or {})
    narration_file = narration_source.get("file") or manifest.get("voice", "")
    narration_start = _number(narration_source.get("timeline_start"), 0)
    narration_in = _number(narration_source.get("source_in"), 0)
    narration_out = _number(
        narration_source.get("source_out"), _number(manifest.get("audio_duration_seconds"), cursor)
    )
    narration_duration = max(0.0, narration_out - narration_in)
    music_track = []
    for index, cue in enumerate(manifest.get("music_cues", [])):
        item = deepcopy(cue)
        item.setdefault("id", f"music-{index}")
        item.setdefault("type", "music")
        item.setdefault("loop", True)
        music_track.append(item)
    ambience_track = []
    for index, cue in enumerate(manifest.get("ambience_cues", [])):
        item = deepcopy(cue)
        item.setdefault("id", f"ambience-{index}")
        item.setdefault("type", "ambience")
        item.setdefault("loop", True)
        ambience_track.append(item)

    return {
        "title": manifest.get("project_title", "Untitled project"),
        "manifestVersion": manifest.get("manifest_version", "2.6"),
        "width": int(manifest.get("width", 1920)),
        "height": int(manifest.get("height", 1080)),
        "duration": round(cursor, 3),
        "visualTrack": visual_track,
        "narrationTrack": {
            "id": "narration",
            "type": "narration",
            "file": narration_file,
            "start": narration_start,
            "sourceIn": narration_in,
            "sourceOut": narration_out,
            "duration": round(narration_duration, 3),
            "end": round(narration_start + narration_duration, 3),
            "volume": _number(narration_source.get("volume"), _number(manifest.get("voice_volume"), 1.0)),
        },
        "musicTrack": music_track,
        "ambienceTrack": ambience_track,
        "sfxTrack": sfx_track,
        "subtitleFile": manifest.get("subtitle_file", ""),
        "subtitleTrack": deepcopy(manifest.get("subtitle_cues", [])),
        "textTracks": deepcopy(manifest.get("text_tracks", [])),
        "trackOrder": deepcopy(manifest.get("track_order", [])),
        "trackSettings": deepcopy(manifest.get("track_settings", {})),
        "sourceManifest": deepcopy(manifest),
    }


def manifest_from_editor_project(project: dict[str, Any]) -> dict[str, Any]:
    """Apply editable scene fields onto the original manifest without data loss."""

    source = project.get("sourceManifest")
    visual_track = project.get("visualTrack")
    if not isinstance(source, dict) or not isinstance(visual_track, list):
        raise ManifestValidationError("Editor project is missing sourceManifest or visualTrack")
    source_scenes = source.get("scenes")
    if not isinstance(source_scenes, list):
        raise ManifestValidationError("Source manifest must contain a scenes list")

    manifest = deepcopy(source)
    manifest["width"] = int(project.get("width", source.get("width", 1920)))
    manifest["height"] = int(project.get("height", source.get("height", 1080)))
    source_by_id = {
        str(scene.get("scene_id", f"SCENE_{index + 1}")): scene
        for index, scene in enumerate(source_scenes)
    }
    manifest["scenes"] = []
    cursor = 0.0
    editable_fields = {
        "motion": "motion",
        "motionSpeed": "motion_speed",
        "crop": "crop",
        "focalPoint": "focal_point",
        "transition": "transition",
        "transitionDuration": "transition_duration",
    }
    for index, editor_scene in enumerate(visual_track):
        duration = _number(editor_scene.get("duration"))
        if duration <= 0:
            raise ManifestValidationError(f"Scene {index + 1} duration must be greater than zero")
        scene_id = str(editor_scene.get("sceneId") or editor_scene.get("id") or f"SCENE_{index + 1}")
        if any(scene.get("scene_id") == scene_id for scene in manifest["scenes"]):
            raise ManifestValidationError(f"Scene id {scene_id} is duplicated")
        scene = deepcopy(source_by_id.get(scene_id, {"scene_id": scene_id}))
        start = round(cursor, 3)
        end = round(start + duration, 3)
        scene["scene_id"] = scene_id
        scene["start"] = start
        scene["end"] = end
        if "duration" in scene:
            scene["duration"] = round(duration, 3)
        file_value = editor_scene.get("file", "")
        flow_value = editor_scene.get("flowFile", "")
        if file_value:
            scene["file"] = file_value
        if flow_value:
            scene["flow_file"] = flow_value
        for editor_key, manifest_key in editable_fields.items():
            if editor_key in editor_scene:
                value = deepcopy(editor_scene[editor_key])
                if manifest_key == "crop" and value not in {"wide", "medium", "close", "focal"}:
                    value = DEFAULT_SCENE["crop"]
                scene[manifest_key] = value
        scene["keyframes"] = deepcopy(editor_scene.get("keyframes", []))
        scene["effects"] = deepcopy(editor_scene.get("effects", []))
        manifest["scenes"].append(scene)
        cursor = end

    manifest["audio_duration_seconds"] = round(cursor, 3)
    narration = project.get("narrationTrack")
    if isinstance(narration, dict) and narration.get("file"):
        source_in = _number(narration.get("sourceIn"))
        source_out = _number(narration.get("sourceOut"))
        if source_out <= source_in:
            raise ManifestValidationError("Narration sourceOut must be greater than sourceIn")
        narration_manifest = deepcopy(source.get("narration_clip") or {})
        narration_manifest.update(
            {
                "file": narration["file"],
                "timeline_start": round(max(0.0, _number(narration.get("start"))), 3),
                "source_in": round(source_in, 3),
                "source_out": round(source_out, 3),
                "volume": round(max(0.0, _number(narration.get("volume"), 1.0)), 3),
            }
        )
        manifest["narration_clip"] = narration_manifest
        manifest["voice"] = narration["file"]
        manifest["voice_volume"] = narration_manifest["volume"]
    manifest["music_cues"] = [_manifest_audio_cue(cue) for cue in project.get("musicTrack", [])]
    manifest["ambience_cues"] = [_manifest_audio_cue(cue) for cue in project.get("ambienceTrack", [])]
    manifest["subtitle_file"] = project.get("subtitleFile", "")
    manifest["subtitle_cues"] = deepcopy(project.get("subtitleTrack", []))
    manifest["text_tracks"] = deepcopy(project.get("textTracks", []))
    manifest["track_order"] = deepcopy(project.get("trackOrder", []))
    manifest["track_settings"] = deepcopy(project.get("trackSettings", {}))
    for scene in manifest["scenes"]:
        scene["sfx"] = []
    for cue in project.get("sfxTrack", []):
        absolute_start = max(0.0, _number(cue.get("start")))
        destination = len(visual_track) - 1
        for index, scene in enumerate(visual_track):
            if _number(scene.get("start")) <= absolute_start < _number(scene.get("end")):
                destination = index
                break
        relative_at = round(absolute_start - _number(visual_track[destination].get("start")), 3)
        item = {
            key: deepcopy(value)
            for key, value in cue.items()
            if key not in {"id", "sceneId", "start", "type", "duration", "sourceDuration"}
        }
        item["name"] = item.get("name") or Path(str(item.get("file", "sfx"))).stem
        item["at"] = relative_at
        item["volume"] = round(max(0.0, _number(item.get("volume"), 0.92)), 3)
        manifest["scenes"][destination]["sfx"].append(item)
    return manifest


def _manifest_audio_cue(cue: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in cue.items()
        if key not in {"type", "duration", "sourceDuration"}
    }
