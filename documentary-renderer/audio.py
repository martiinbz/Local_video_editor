"""Audio mix planning."""

from __future__ import annotations

from pathlib import Path

from config import RenderConfig
from constants import FFMPEG_EXECUTABLE
from models import Storyboard
from utils import seconds


class AudioPlanner:
    """Build FFmpeg commands for narration and music mixing."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()

    def build_audio_mix_command(self, storyboard: Storyboard, duration: float, output: Path) -> list[str] | None:
        """Return a command that creates the final audio track, or None for silent videos."""

        sfx_cues = self._sfx_cues(storyboard)
        if storyboard.voice is None and storyboard.music is None and not sfx_cues:
            return None

        command = [FFMPEG_EXECUTABLE, "-y"]
        if storyboard.music is not None:
            command.extend(["-stream_loop", "-1", "-i", str(storyboard.music)])
        if storyboard.voice is not None:
            command.extend(["-i", str(storyboard.voice)])
        for cue, _ in sfx_cues:
            command.extend(["-i", str(cue.file)])

        filter_complex, map_label = self._filter_complex(storyboard, sfx_cues)
        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                map_label,
                "-t",
                seconds(duration),
                "-c:a",
                self.config.audio_codec,
                "-b:a",
                self.config.audio_bitrate,
                str(output),
            ]
        )
        return command

    def _filter_complex(self, storyboard: Storyboard, sfx_cues: list[tuple[object, float]] | None = None) -> tuple[str, str]:
        music_volume = storyboard.music_volume
        voice_volume = storyboard.voice_volume

        base_filter = ""
        base_label = ""
        if storyboard.music is not None and storyboard.voice is not None:
            threshold = max(0.001, storyboard.duck_amount)
            base_filter = (
                f"[0:a]volume={music_volume}[music];"
                f"[1:a]volume={voice_volume},asplit=2[voice_for_duck][voice_mix];"
                f"[music][voice_for_duck]sidechaincompress=threshold={threshold}:ratio=12:attack=20:release=800[ducked];"
                "[ducked][voice_mix]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[base]"
            )
            base_label = "[base]"
        elif storyboard.music is not None:
            base_filter = f"[0:a]volume={music_volume}[base]"
            base_label = "[base]"
        elif storyboard.voice is not None:
            base_filter = f"[0:a]volume={voice_volume}[base]"
            base_label = "[base]"

        if not sfx_cues:
            return base_filter.replace("[base]", "[aout]"), "[aout]"

        sfx_filters = []
        sfx_labels = []
        input_offset = int(storyboard.music is not None) + int(storyboard.voice is not None)
        for cue_index, (cue, absolute_at) in enumerate(sfx_cues):
            label = f"[sfx{cue_index}]"
            input_index = input_offset + cue_index
            delay_ms = round(absolute_at * 1000)
            sfx_filters.append(f"[{input_index}:a]volume={cue.volume},adelay={delay_ms}:all=1{label}")
            sfx_labels.append(label)

        inputs = "".join([base_label, *sfx_labels])
        mix = f"{inputs}amix=inputs={1 + len(sfx_labels)}:duration=longest:dropout_transition=0:normalize=0[aout]"
        return ";".join(filter(None, [base_filter, *sfx_filters, mix])), "[aout]"

    @staticmethod
    def _sfx_cues(storyboard: Storyboard) -> list[tuple[object, float]]:
        cues: list[tuple[object, float]] = []
        cursor = 0.0
        for scene in storyboard.scenes:
            for cue in scene.sfx:
                cues.append((cue, cursor + cue.at))
            cursor += float(scene.duration or 0)
        return cues
