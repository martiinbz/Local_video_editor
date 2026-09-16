"""End-to-end documentary rendering orchestration."""

from __future__ import annotations

import logging
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from audio import AudioPlanner
from config import RenderConfig
from constants import CONCAT_LIST_FILE
from ffmpeg_builder import FFmpegBuilder
from generated_assets import GeneratedAssetBuilder
from manifest_parser import ManifestParser
from manifest_paths import normalize_manifest_paths
from manifest_timeline import ManifestTimelineBuilder
from manifest_validator import ManifestValidator
from manifest_v23_parser import ManifestV23Parser
from models import SceneType, Storyboard
from parser import StoryboardParser
from exceptions import ValidationError
from qc import QualityControl
from story_rules import StoryRuleEngine
from timeline import TimelineBuilder
from utils import as_posix_for_ffmpeg, ensure_parent_dir
from validator import StoryboardValidator


class DocumentaryRenderer:
    """Render a complete documentary from a storyboard JSON file."""

    def __init__(
        self,
        parser: StoryboardParser | None = None,
        validator: StoryboardValidator | None = None,
        timeline_builder: TimelineBuilder | None = None,
        ffmpeg: FFmpegBuilder | None = None,
        logger: logging.Logger | None = None,
        renderer_root: str | Path | None = None,
    ) -> None:
        self.parser = parser or StoryboardParser()
        self.validator = validator or StoryboardValidator()
        self.timeline_builder = timeline_builder or TimelineBuilder()
        self.ffmpeg = ffmpeg or FFmpegBuilder()
        self.logger = logger or logging.getLogger("documentary_renderer")
        self.renderer_root = Path(renderer_root) if renderer_root is not None else Path(__file__).resolve().parent

    def render(self, storyboard_path: str | Path) -> Path:
        """Render the storyboard and return the output path."""

        self.logger.info("Loading project...")
        storyboard = self.parser.parse(storyboard_path)

        self.logger.info("Validating storyboard...")
        self.validator.validate(storyboard)

        config = self._config_from_storyboard(storyboard)
        timeline = self.timeline_builder.build(storyboard)
        ensure_parent_dir(storyboard.output)

        with tempfile.TemporaryDirectory(prefix="documentary-renderer-") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)

            self.logger.info("Building FFmpeg pipeline...")
            scene_outputs = self._render_scenes(storyboard, config, temp_dir)
            concat_file = self._write_concat_file(scene_outputs, temp_dir / CONCAT_LIST_FILE)
            video_output = temp_dir / "video.mp4"
            self.ffmpeg.run(self.ffmpeg.build_concat_command(concat_file, video_output, config))

            audio_output = self._render_audio(storyboard, timeline.total_duration, temp_dir, config)

            self.logger.info("Rendering final output...")
            self.ffmpeg.run(self.ffmpeg.build_mux_command(video_output, audio_output, storyboard.output, config))

        self.logger.info("Done.")
        return storyboard.output

    def render_manifest(self, manifest_path: str | Path, ignore_qc: bool = False) -> Path:
        """Render a V2 master manifest and return the output path."""

        self.logger.info("Loading V2 manifest...")
        manifest_path = Path(manifest_path)
        manifest = self._parse_manifest(manifest_path)
        manifest = normalize_manifest_paths(manifest, project_dir=manifest_path.resolve().parent, renderer_root=self.renderer_root)

        self.logger.info("Validating V2 manifest...")
        manifest_base_dir = Path(manifest_path).resolve().parent
        GeneratedAssetBuilder(base_dir=manifest_base_dir).build(manifest)
        rule_engine = StoryRuleEngine()
        for shot in manifest.shots:
            rule_engine.apply(shot)
        ManifestValidator().validate(manifest)
        qc = QualityControl()
        report = qc.check(manifest)
        report_path = manifest.project.output.parent / "qc_report.txt"
        qc.write_report(report, report_path)
        if report.has_errors and not ignore_qc:
            raise ValidationError(f"V2 QC failed. See report: {report_path}")
        if report.has_errors:
            self.logger.warning("Ignoring V2 QC errors. See report: %s", report_path)

        config = self._config_from_manifest(manifest)
        timeline = ManifestTimelineBuilder().build(manifest)
        ensure_parent_dir(manifest.project.output)

        with tempfile.TemporaryDirectory(prefix="documentary-renderer-v2-") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)

            self.logger.info("Building V2 FFmpeg pipeline...")
            shot_outputs = self._render_manifest_shots(timeline, config, temp_dir)
            concat_file = self._write_concat_file(shot_outputs, temp_dir / CONCAT_LIST_FILE)
            video_output = temp_dir / "video.mp4"
            self.ffmpeg.run(self.ffmpeg.build_concat_command(concat_file, video_output, config))

            overlays = [*manifest.subtitle_cues, *(overlay for track in manifest.text_tracks for overlay in track.overlays)]
            if overlays:
                styled_output = temp_dir / "video_styled.mp4"
                self.ffmpeg.run(self.ffmpeg.build_text_overlay_command(video_output, overlays, styled_output, config))
                video_output = styled_output

            audio_output = self._render_manifest_audio(manifest, timeline.total_duration, temp_dir, config)

            self.logger.info("Rendering final V2 output...")
            self.ffmpeg.run(self.ffmpeg.build_mux_command(video_output, audio_output, manifest.project.output, config))

        self.logger.info("Done.")
        return manifest.project.output

    def _render_scenes(self, storyboard: Storyboard, config: RenderConfig, temp_dir: Path) -> list[Path]:
        scene_outputs: list[Path] = []
        total = len(storyboard.scenes)

        for index, scene in enumerate(storyboard.scenes, start=1):
            self.logger.info("Rendering scene %s/%s...", index, total)
            output = temp_dir / f"scene_{index:05d}.mp4"
            if scene.type is SceneType.IMAGE:
                command = self.ffmpeg.build_image_scene_command(scene, output, config)
            else:
                command = self.ffmpeg.build_video_scene_command(scene, output, config)
            self.ffmpeg.run(command)
            scene_outputs.append(output)

        return scene_outputs

    def _render_manifest_shots(self, timeline, config: RenderConfig, temp_dir: Path) -> list[Path]:
        shot_outputs: list[Path] = []
        total = len(timeline.shots)
        for index, timeline_shot in enumerate(timeline.shots, start=1):
            self.logger.info("Rendering shot %s/%s...", index, total)
            output = temp_dir / f"shot_{index:05d}.mp4"
            command = self.ffmpeg.build_image_shot_command(
                timeline_shot.source,
                timeline_shot.asset,
                output,
                config,
            )
            self.ffmpeg.run(command)
            shot_outputs.append(output)
        return shot_outputs

    def _render_audio(
        self,
        storyboard: Storyboard,
        duration: float,
        temp_dir: Path,
        config: RenderConfig,
    ) -> Path | None:
        planner = AudioPlanner(config)
        audio_output = temp_dir / "audio.m4a"
        command = planner.build_audio_mix_command(storyboard, duration, audio_output)
        if command is None:
            return None

        self.logger.info("Mixing audio...")
        self.ffmpeg.run(command)
        return audio_output

    def _render_manifest_audio(self, manifest, duration: float, temp_dir: Path, config: RenderConfig) -> Path | None:
        from manifest_audio import ManifestAudioPlanner

        planner = ManifestAudioPlanner(config)
        audio_output = temp_dir / "audio.m4a"
        command = planner.build_audio_mix_command(manifest, duration, audio_output)
        if command is None:
            return None

        self.logger.info("Mixing V2 audio...")
        self.ffmpeg.run(command)
        return audio_output

    def render_manifest_audio_preview(self, manifest_path: str | Path, output: str | Path) -> Path | None:
        """Create the exact FFmpeg audio mix used by the V2 render."""
        manifest_path = Path(manifest_path)
        manifest = self._parse_manifest(manifest_path)
        manifest = normalize_manifest_paths(manifest, project_dir=manifest_path.resolve().parent, renderer_root=self.renderer_root)
        rule_engine = StoryRuleEngine()
        for shot in manifest.shots:
            rule_engine.apply(shot)
        timeline = ManifestTimelineBuilder().build(manifest)
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        planner = __import__("manifest_audio", fromlist=["ManifestAudioPlanner"]).ManifestAudioPlanner(self._config_from_manifest(manifest))
        command = planner.build_audio_mix_command(manifest, timeline.total_duration, target)
        if command is None:
            return None
        self.ffmpeg.run(command)
        return target

    def render_manifest_preview(self, manifest_path: str | Path, output: str | Path) -> Path:
        """Render a full-quality preview with the exact V2 final-render pipeline."""
        manifest_path = Path(manifest_path)
        target = Path(output).resolve()
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["output"] = str(target)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".preview.json", dir=manifest_path.parent, delete=False, encoding="utf-8") as temporary:
            json.dump(payload, temporary, ensure_ascii=False)
            preview_manifest = Path(temporary.name)
        try:
            return self.render_manifest(preview_manifest, ignore_qc=True)
        finally:
            preview_manifest.unlink(missing_ok=True)

    def render_manifest_window(self, manifest_path: str | Path, output: str | Path, start: float, duration: float = 12.0) -> Path:
        """Render only a timeline window, preserving final-render settings."""
        source = Path(manifest_path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        end = start + duration
        cursor = 0.0
        scenes = []
        for scene in payload.get("scenes", []):
            scene_duration = float(scene.get("duration", scene.get("end", 0) - scene.get("start", 0)))
            scene_end = cursor + scene_duration
            overlap_start, overlap_end = max(start, cursor), min(end, scene_end)
            if overlap_end > overlap_start:
                item = dict(scene)
                item["duration"] = overlap_end - overlap_start
                item["start"] = sum(float(value.get("duration", 0)) for value in scenes)
                item["end"] = item["start"] + item["duration"]
                item["sfx"] = [dict(sfx, at=(cursor + float(sfx.get("at", 0)) - overlap_start)) for sfx in scene.get("sfx", []) if overlap_start <= cursor + float(sfx.get("at", 0)) < overlap_end]
                scenes.append(item)
            cursor = scene_end
        payload["scenes"] = scenes
        payload["audio_duration_seconds"] = sum(float(scene["duration"]) for scene in scenes)
        for key in ("music_cues", "ambience_cues", "subtitle_cues"):
            clipped = []
            for item in payload.get(key, []):
                item_start, item_end = float(item.get("start", 0)), float(item.get("end", 0))
                if item_end > start and item_start < end:
                    copy = dict(item); copy["start"] = max(item_start, start) - start; copy["end"] = min(item_end, end) - start; clipped.append(copy)
            payload[key] = clipped
        for track in payload.get("text_tracks", []):
            track["overlays"] = [dict(item, start=max(float(item.get("start", 0)), start) - start, end=min(float(item.get("end", 0)), end) - start) for item in track.get("overlays", []) if float(item.get("end", 0)) > start and float(item.get("start", 0)) < end]
        narration = payload.get("narration_clip")
        if isinstance(narration, dict):
            timeline_start = float(narration.get("timeline_start", 0))
            source_in = float(narration.get("source_in", 0))
            source_out = float(narration.get("source_out", source_in))
            narration_end = timeline_start + max(0, source_out - source_in)
            overlap_start, overlap_end = max(start, timeline_start), min(end, narration_end)
            if overlap_end > overlap_start:
                narration["source_in"] = source_in + overlap_start - timeline_start
                narration["source_out"] = source_in + overlap_end - timeline_start
                narration["timeline_start"] = overlap_start - start
            else:
                payload.pop("narration_clip", None)
                payload.pop("voice", None)
        target = Path(output).resolve(); payload["output"] = str(target)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".window.json", dir=source.parent, delete=False, encoding="utf-8") as temporary:
            json.dump(payload, temporary, ensure_ascii=False); window_manifest = Path(temporary.name)
        try:
            return self.render_manifest(window_manifest, ignore_qc=True)
        finally:
            window_manifest.unlink(missing_ok=True)

    @staticmethod
    def _parse_manifest(manifest_path: str | Path):
        path = Path(manifest_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("scenes"), list):
            return ManifestV23Parser().parse(path)
        return ManifestParser().parse(path)

    @staticmethod
    def _write_concat_file(scene_outputs: list[Path], path: Path) -> Path:
        lines = [f"file '{as_posix_for_ffmpeg(scene_path)}'" for scene_path in scene_outputs]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def _config_from_storyboard(storyboard: Storyboard) -> RenderConfig:
        return replace(
            RenderConfig(),
            width=storyboard.width,
            height=storyboard.height,
            fps=storyboard.fps,
            music_volume=storyboard.music_volume,
            voice_volume=storyboard.voice_volume,
            duck_amount=storyboard.duck_amount,
            duck_fade_duration=storyboard.duck_fade_duration,
        )

    @staticmethod
    def _config_from_manifest(manifest) -> RenderConfig:
        return replace(
            RenderConfig(),
            width=manifest.project.width,
            height=manifest.project.height,
            fps=manifest.project.fps,
            voice_volume=manifest.project.voice_volume,
            duck_amount=manifest.project.duck_amount,
            duck_fade_duration=manifest.project.duck_fade_duration,
        )
