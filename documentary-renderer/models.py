"""Typed storyboard and timeline models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class StrEnum(str, Enum):
    """Enum that compares naturally with storyboard string values."""

    @classmethod
    def from_value(cls, raw: str) -> "StrEnum":
        try:
            return cls(raw)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"Invalid {cls.__name__} '{raw}'. Allowed values: {allowed}") from exc


class SceneType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


class MotionType(StrEnum):
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    PAN_UP = "pan_up"
    PAN_DOWN = "pan_down"
    ZOOM_LEFT = "zoom_left"
    ZOOM_RIGHT = "zoom_right"
    ZOOM_UP = "zoom_up"
    ZOOM_DOWN = "zoom_down"
    CROP_PUSH = "crop_push"
    FOCAL_ZOOM = "focal_zoom"
    STATIC = "static"


class TransitionType(StrEnum):
    FADE = "fade"
    CROSSFADE = "crossfade"
    HARD_CUT = "hard_cut"
    DIP_TO_BLACK = "dip_to_black"


class VisualLevel(StrEnum):
    GRAPHIC = "GRAPHIC"
    CINEMATIC = "CINEMATIC"
    HERO = "HERO"


class StoryFunction(StrEnum):
    HOOK = "HOOK"
    CONTEXT = "CONTEXT"
    SETUP = "SETUP"
    QUESTION = "QUESTION"
    CLUE = "CLUE"
    EVIDENCE = "EVIDENCE"
    ESCALATION = "ESCALATION"
    CONTRADICTION = "CONTRADICTION"
    REVEAL = "REVEAL"
    CONSEQUENCE = "CONSEQUENCE"
    EMOTIONAL = "EMOTIONAL"
    THEORY = "THEORY"
    RESOLUTION = "RESOLUTION"
    REFLECTION = "REFLECTION"


class VisualType(StrEnum):
    RECONSTRUCTION = "RECONSTRUCTION"
    CHARACTER = "CHARACTER"
    LOCATION = "LOCATION"
    OBJECT = "OBJECT"
    EVIDENCE = "EVIDENCE"
    DOCUMENT = "DOCUMENT"
    CASE_FILE = "CASE_FILE"
    TIMELINE = "TIMELINE"
    MAP = "MAP"
    QUOTE = "QUOTE"
    ABSTRACT = "ABSTRACT"
    REVEAL = "REVEAL"


class CropType(StrEnum):
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE = "close"
    FOCAL = "focal"


class AssetType(StrEnum):
    IMAGE = "image"


class GenerationSource(StrEnum):
    FLOW = "flow"
    RENDERER = "renderer"


class MusicState(StrEnum):
    MYSTERY = "MYSTERY"
    INVESTIGATION = "INVESTIGATION"
    TENSION = "TENSION"
    EMOTIONAL = "EMOTIONAL"
    REVELATION = "REVELATION"
    NEUTRAL_DARK = "NEUTRAL_DARK"
    SILENCE = "SILENCE"


class OverlayType(StrEnum):
    CASE_FILE = "CASE_FILE"
    EVIDENCE = "EVIDENCE"
    DOCUMENT = "DOCUMENT"
    TIMELINE = "TIMELINE"
    MAP = "MAP"
    QUOTE = "QUOTE"
    DATE = "DATE"
    LOCATION = "LOCATION"
    THEORY = "THEORY"


@dataclass(frozen=True, slots=True)
class SoundEffectCue:
    """A sound effect placed at a relative timestamp inside a scene."""

    name: str
    file: Path
    at: float
    volume: float = 0.9


@dataclass(frozen=True, slots=True)
class OverlaySpec:
    """Renderer-generated graphic asset specification."""

    type: OverlayType
    data: dict


@dataclass(frozen=True, slots=True)
class NarrationClip:
    """Non-destructive placement and source trim for narration audio."""

    file: Path
    timeline_start: float = 0.0
    source_in: float = 0.0
    source_out: float | None = None
    volume: float = 1.0


@dataclass(frozen=True, slots=True)
class VisualKeyframe:
    time: float
    scale: float = 1.0
    x: float = 0.5
    y: float = 0.5
    rotation: float = 0.0


@dataclass(frozen=True, slots=True)
class VisualEffect:
    id: str
    type: str
    start: float
    end: float
    intensity: float = 0.5
    enabled: bool = True
    params: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TextOverlay:
    id: str
    text: str
    start: float
    end: float
    font: Path | None = None
    font_size: int = 48
    color: str = "#ffffff"
    opacity: float = 1.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: str = "center"
    x: float = 0.5
    y: float = 0.85
    outline: float = 2.0
    shadow: float = 0.0
    animation_in: str = "none"
    animation_out: str = "none"
    transition_duration: float = 0.3


@dataclass(frozen=True, slots=True)
class TextTrack:
    id: str
    name: str
    overlays: list[TextOverlay] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Top-level V2 project settings."""

    title: str
    output: Path
    width: int = 1920
    height: int = 1080
    fps: int = 30
    voice: Path | None = None
    narration_clip: NarrationClip | None = None
    transcript: Path | None = None
    accent_color: str = "#A33A2A"
    voice_volume: float = 1.0
    duck_amount: float = 0.35
    duck_fade_duration: float = 0.5


@dataclass(slots=True)
class Asset:
    """A reusable visual source in a V2 manifest."""

    asset_id: str
    type: AssetType
    generation_source: GenerationSource
    file: Path | None
    visual_level: VisualLevel
    overlay: OverlaySpec | None = None
    focal_points: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(slots=True)
class Shot:
    """One rendered presentation of an asset."""

    shot_id: str
    asset_id: str
    duration: float
    story_function: StoryFunction
    visual_type: VisualType
    visual_level: VisualLevel
    importance: int
    crop: CropType = CropType.WIDE
    motion: MotionType = MotionType.STATIC
    transition: TransitionType = TransitionType.HARD_CUT
    focal_point: tuple[float, float] | None = None
    transition_duration: float | None = None
    motion_speed: float | None = None
    sfx: list[SoundEffectCue] = field(default_factory=list)
    keyframes: list[VisualKeyframe] = field(default_factory=list)
    effects: list[VisualEffect] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MusicCue:
    state: MusicState
    start: float
    end: float
    volume: float = 0.12
    track: Path | None = None


@dataclass(frozen=True, slots=True)
class AmbienceCue:
    name: str
    file: Path
    start: float
    end: float
    volume: float = 0.04


@dataclass(slots=True)
class Manifest:
    """Complete V2 render request."""

    project: ProjectConfig
    assets: dict[str, Asset]
    shots: list[Shot]
    music_cues: list[MusicCue] = field(default_factory=list)
    ambience_cues: list[AmbienceCue] = field(default_factory=list)
    subtitle_file: Path | None = None
    subtitle_cues: list[TextOverlay] = field(default_factory=list)
    text_tracks: list[TextTrack] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TimelineShot:
    index: int
    source: Shot
    asset: Asset
    start_time: float
    end_time: float
    duration: float


@dataclass(frozen=True, slots=True)
class ManifestTimeline:
    shots: list[TimelineShot] = field(default_factory=list)
    total_duration: float = 0.0


@dataclass(slots=True)
class Scene:
    """One storyboard scene."""

    type: SceneType
    file: Path
    duration: float | None = None
    motion: MotionType = MotionType.STATIC
    transition: TransitionType = TransitionType.HARD_CUT
    transition_duration: float | None = None
    motion_speed: float | None = None
    start_time: float | None = None
    end_time: float | None = None
    sfx: list[SoundEffectCue] = field(default_factory=list)


@dataclass(slots=True)
class Storyboard:
    """Complete render request loaded from JSON."""

    scenes: list[Scene]
    output: Path
    width: int = 1920
    height: int = 1080
    fps: int = 30
    voice: Path | None = None
    music: Path | None = None
    music_volume: float = 0.15
    voice_volume: float = 1.0
    duck_amount: float = 0.35
    duck_fade_duration: float = 0.5


@dataclass(frozen=True, slots=True)
class TimelineScene:
    """Scene with calculated timeline timestamps."""

    index: int
    source: Scene
    start_time: float
    end_time: float
    duration: float
    transition: TransitionType
    motion: MotionType


@dataclass(frozen=True, slots=True)
class Timeline:
    """Calculated sequence of scenes."""

    scenes: list[TimelineScene] = field(default_factory=list)
    total_duration: float = 0.0
