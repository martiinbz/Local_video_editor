"""FFmpeg command construction and execution."""

from __future__ import annotations

import subprocess
from pathlib import Path

from config import RenderConfig
from constants import FFMPEG_EXECUTABLE, PIXEL_FORMAT
from exceptions import FFmpegError
from ffmpeg_runtime import resolve_ffmpeg_executable
from models import Asset, Scene, Shot, TextOverlay
from motion import MotionFilterFactory
from transitions import TransitionFilterFactory
from utils import seconds


class FFmpegBuilder:
    """Build and run FFmpeg commands."""

    def __init__(
        self,
        motion_factory: MotionFilterFactory | None = None,
        transition_factory: TransitionFilterFactory | None = None,
    ) -> None:
        self.motion_factory = motion_factory or MotionFilterFactory()
        self.transition_factory = transition_factory or TransitionFilterFactory()

    def build_image_scene_command(self, scene: Scene, output: Path, config: RenderConfig) -> list[str]:
        """Build a command that renders one image scene to a normalized MP4."""

        video_filter = self._join_filters(
            self.motion_factory.build(scene, config),
            self.transition_factory.build_video_filter(scene),
        )
        return [
            FFMPEG_EXECUTABLE,
            "-y",
            "-loop",
            "1",
            "-i",
            str(scene.file),
            "-t",
            seconds(scene.duration or 1),
            "-vf",
            video_filter,
            "-r",
            str(config.fps),
            "-an",
            *self._video_export_args(config),
            str(output),
        ]

    def build_image_shot_command(self, shot: Shot, asset: Asset, output: Path, config: RenderConfig) -> list[str]:
        """Build a command that renders one V2 manifest image shot."""

        video_filter = self._join_filters(
            self.motion_factory.build_for_shot(shot, config),
            self.transition_factory.build_shot_video_filter(shot),
        )
        return [
            FFMPEG_EXECUTABLE,
            "-y",
            "-loop",
            "1",
            "-i",
            str(asset.file),
            "-t",
            seconds(shot.duration),
            "-vf",
            video_filter,
            "-r",
            str(config.fps),
            "-an",
            *self._video_export_args(config),
            str(output),
        ]

    def build_video_scene_command(self, scene: Scene, output: Path, config: RenderConfig) -> list[str]:
        """Build a command that trims and normalizes one video scene."""

        command = [FFMPEG_EXECUTABLE, "-y"]
        if scene.start_time is not None:
            command.extend(["-ss", seconds(scene.start_time)])
        command.extend(["-i", str(scene.file)])
        if scene.end_time is not None and scene.start_time is not None:
            command.extend(["-t", seconds(scene.end_time - scene.start_time)])
        elif scene.duration is not None:
            command.extend(["-t", seconds(scene.duration)])

        base_filter = (
            f"scale={config.width}:{config.height}:force_original_aspect_ratio=increase,"
            f"crop={config.width}:{config.height},setsar=1,fps={config.fps},format={PIXEL_FORMAT}"
        )
        video_filter = self._join_filters(base_filter, self.transition_factory.build_video_filter(scene))
        command.extend(["-vf", video_filter, "-an", *self._video_export_args(config), str(output)])
        return command

    def build_concat_command(self, concat_file: Path, output: Path, config: RenderConfig) -> list[str]:
        """Build a command that concatenates normalized scene segments."""

        return [
            FFMPEG_EXECUTABLE,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ]

    def build_mux_command(self, video: Path, audio: Path | None, output: Path, config: RenderConfig) -> list[str]:
        """Build a command that muxes rendered video and optional audio."""

        command = [FFMPEG_EXECUTABLE, "-y", "-i", str(video)]
        if audio is not None:
            command.extend(["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", config.audio_codec])
        else:
            command.extend(["-c:v", "copy", "-an"])
        command.extend(["-movflags", "+faststart", str(output)])
        return command

    def build_text_overlay_command(self, video: Path, overlays: list[TextOverlay], output: Path, config: RenderConfig) -> list[str]:
        filters = [self._drawtext_filter(item, config) for item in overlays if item.text and item.end > item.start]
        filter_text = ",".join(filters)
        if len(filter_text) <= 8_000:
            return [
                FFMPEG_EXECUTABLE,
                "-y",
                "-i",
                str(video),
                "-vf",
                filter_text,
                "-an",
                *self._video_export_args(config),
                str(output),
            ]

        filter_script = output.with_suffix(".filters.txt")
        filter_script.write_text(f"[0:v]{filter_text}[v]\n", encoding="utf-8")
        return [
            FFMPEG_EXECUTABLE,
            "-y",
            "-i",
            str(video),
            "-filter_complex_script",
            str(filter_script),
            "-map",
            "[v]",
            "-an",
            *self._video_export_args(config),
            str(output),
        ]

    @staticmethod
    def _drawtext_filter(item: TextOverlay, config: RenderConfig) -> str:
        text = item.text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace("\n", "\\n")
        font_path = item.font or FFmpegBuilder._default_font_path()
        if font_path and Path(font_path).suffix.lower() not in {".ttf", ".otf", ".ttc"}:
            font_path = FFmpegBuilder._default_font_path()
        font = f"fontfile='{str(font_path).replace(chr(92), '/').replace(':', chr(92) + ':')}':" if font_path else ""
        if item.align == "left":
            x = f"w*{item.x:g}"
        elif item.align == "right":
            x = f"w*{item.x:g}-text_w"
        else:
            x = f"w*{item.x:g}-text_w/2"
        y = f"h*{item.y:g}-text_h/2"
        duration = max(0.01, item.transition_duration)
        entrance_end = item.start + duration
        exit_start = item.end - duration
        if item.animation_in == "slide_left":
            x = f"if(lt(t,{entrance_end:g}),-text_w+(({x})+text_w)*(t-{item.start:g})/{duration:g},{x})"
        elif item.animation_in == "slide_right":
            x = f"if(lt(t,{entrance_end:g}),w+(({x})-w)*(t-{item.start:g})/{duration:g},{x})"
        elif item.animation_in == "slide_up":
            y = f"if(lt(t,{entrance_end:g}),-text_h+(({y})+text_h)*(t-{item.start:g})/{duration:g},{y})"
        elif item.animation_in == "slide_down":
            y = f"if(lt(t,{entrance_end:g}),h+(({y})-h)*(t-{item.start:g})/{duration:g},{y})"
        if item.animation_out == "slide_left":
            x = f"if(gt(t,{exit_start:g}),({x})+(-text_w-({x}))*(t-{exit_start:g})/{duration:g},{x})"
        elif item.animation_out == "slide_right":
            x = f"if(gt(t,{exit_start:g}),({x})+(w-({x}))*(t-{exit_start:g})/{duration:g},{x})"
        elif item.animation_out == "slide_up":
            y = f"if(gt(t,{exit_start:g}),({y})+(-text_h-({y}))*(t-{exit_start:g})/{duration:g},{y})"
        elif item.animation_out == "slide_down":
            y = f"if(gt(t,{exit_start:g}),({y})+(h-({y}))*(t-{exit_start:g})/{duration:g},{y})"
        alpha = f"{max(0, min(1, item.opacity)):g}"
        if item.animation_in == "fade":
            alpha = f"{alpha}*min(1,max(0,(t-{item.start:g})/{duration:g}))"
        if item.animation_out == "fade":
            alpha += f"*min(1,max(0,({item.end:g}-t)/{duration:g}))"
        return (
            f"drawtext={font}text='{text}':fontsize={item.font_size}:fontcolor={item.color}:"
            f"alpha='{alpha}':x='{x}':y='{y}':borderw={item.outline:g}:bordercolor=black:"
            f"shadowx={item.shadow:g}:shadowy={item.shadow:g}:enable='between(t,{item.start:g},{item.end:g})'"
        )

    @staticmethod
    def _default_font_path() -> Path | None:
        candidates = (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        )
        return next((path for path in candidates if path.is_file()), None)

    def run(self, command: list[str]) -> None:
        """Execute an FFmpeg command and raise a meaningful failure."""

        try:
            executable = resolve_ffmpeg_executable()
            resolved_command = [executable, *command[1:]] if command and command[0] == FFMPEG_EXECUTABLE else command
            subprocess.run(resolved_command, check=True)
        except FileNotFoundError as exc:
            raise FFmpegError(str(exc)) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(f"ffmpeg failed with exit code {exc.returncode}.") from exc

    @staticmethod
    def _video_export_args(config: RenderConfig) -> list[str]:
        return [
            "-c:v",
            config.video_codec,
            "-preset",
            config.preset,
            "-crf",
            str(config.crf),
            "-b:v",
            config.bitrate,
            "-pix_fmt",
            PIXEL_FORMAT,
            "-movflags",
            "+faststart",
        ]

    @staticmethod
    def _join_filters(*filters: str) -> str:
        return ",".join(item for item in filters if item)
