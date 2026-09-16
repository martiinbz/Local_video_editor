"""Default renderer configuration."""

from __future__ import annotations

from dataclasses import dataclass

from constants import AUDIO_CODEC, VIDEO_CODEC


@dataclass(frozen=True)
class RenderConfig:
    """Rendering defaults used when the storyboard omits optional settings."""

    width: int = 1920
    height: int = 1080
    fps: int = 30
    transition_duration: float = 0.5
    motion_speed: float = 0.0015
    video_codec: str = VIDEO_CODEC
    audio_codec: str = AUDIO_CODEC
    bitrate: str = "12M"
    crf: int = 18
    preset: str = "medium"
    audio_bitrate: str = "192k"
    music_volume: float = 0.15
    voice_volume: float = 1.0
    duck_amount: float = 0.35
    duck_fade_duration: float = 0.5
