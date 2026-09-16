"""V2 manifest audio mix planning."""

from __future__ import annotations

from pathlib import Path

from config import RenderConfig
from constants import FFMPEG_EXECUTABLE
from models import Manifest, MusicState
from utils import seconds


class ManifestAudioPlanner:
    """Build FFmpeg commands for V2 narration, music cues, ambience, and SFX."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()

    def build_audio_mix_command(self, manifest: Manifest, duration: float, output: Path) -> list[str] | None:
        music_cues = [cue for cue in manifest.music_cues if cue.state is not MusicState.SILENCE and cue.track is not None]
        ambience_cues = list(manifest.ambience_cues)
        sfx_cues = self._sfx_cues(manifest)
        if manifest.project.voice is None and not music_cues and not ambience_cues and not sfx_cues:
            return None

        command = [FFMPEG_EXECUTABLE, "-y"]
        input_labels: list[str] = []
        filters: list[str] = []
        input_index = 0

        voice_label = ""
        if manifest.project.voice is not None:
            command.extend(["-i", str(manifest.project.voice)])
            voice_label = "[voice]"
            narration = manifest.project.narration_clip
            voice_volume = narration.volume if narration is not None else manifest.project.voice_volume
            voice_filters: list[str] = []
            if narration is not None:
                trim = f"atrim=start={seconds(narration.source_in)}"
                if narration.source_out is not None:
                    trim += f":end={seconds(narration.source_out)}"
                voice_filters.extend(
                    [trim, "asetpts=PTS-STARTPTS", f"adelay={round(narration.timeline_start * 1000)}:all=1"]
                )
            voice_filters.append(f"volume={voice_volume}")
            voice_chain = ",".join(voice_filters)
            if music_cues:
                filters.append(
                    f"[{input_index}:a]{voice_chain},asplit=2[voice_for_duck][voice_mix]"
                )
            else:
                filters.append(f"[{input_index}:a]{voice_chain}[voice_mix]")
            input_labels.append("[voice_mix]")
            input_index += 1

        duckable_music_labels: list[str] = []
        for cue_index, cue in enumerate(music_cues):
            command.extend(["-stream_loop", "-1", "-i", str(cue.track)])
            label = f"[music{cue_index}]"
            cue_duration = max(0, cue.end - cue.start)
            delay_ms = round(cue.start * 1000)
            filters.append(
                f"[{input_index}:a]volume={cue.volume},atrim=0:{seconds(cue_duration)},"
                f"adelay={delay_ms}:all=1{label}"
            )
            duckable_music_labels.append(label)
            input_index += 1

        for cue_index, cue in enumerate(ambience_cues):
            command.extend(["-stream_loop", "-1", "-i", str(cue.file)])
            label = f"[ambience{cue_index}]"
            cue_duration = max(0, cue.end - cue.start)
            delay_ms = round(cue.start * 1000)
            filters.append(
                f"[{input_index}:a]volume={cue.volume},atrim=0:{seconds(cue_duration)},"
                f"adelay={delay_ms}:all=1{label}"
            )
            input_labels.append(label)
            input_index += 1

        for cue_index, (cue, absolute_at) in enumerate(sfx_cues):
            command.extend(["-i", str(cue.file)])
            label = f"[sfx{cue_index}]"
            delay_ms = round(absolute_at * 1000)
            filters.append(f"[{input_index}:a]volume={cue.volume},adelay={delay_ms}:all=1{label}")
            input_labels.append(label)
            input_index += 1

        if duckable_music_labels:
            joined_music = "".join(duckable_music_labels)
            if len(duckable_music_labels) == 1:
                filters.append(f"{joined_music}anull[music_bus]")
            else:
                filters.append(f"{joined_music}amix=inputs={len(duckable_music_labels)}:normalize=0[music_bus]")
            if manifest.project.voice is not None:
                threshold = max(0.001, manifest.project.duck_amount)
                filters.append(
                    f"[music_bus][voice_for_duck]sidechaincompress=threshold={threshold}:"
                    "ratio=12:attack=20:release=800[ducked_music]"
                )
                input_labels.insert(0, "[ducked_music]")
            else:
                input_labels.insert(0, "[music_bus]")

        if manifest.project.voice is not None and voice_label:
            # voice_mix was already added to input_labels; voice_for_duck only feeds sidechain.
            pass

        if not input_labels:
            return None

        filters.append(
            f"{''.join(input_labels)}amix=inputs={len(input_labels)}:"
            "duration=longest:dropout_transition=0:normalize=0[aout]"
        )
        command.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[aout]",
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

    @staticmethod
    def _sfx_cues(manifest: Manifest) -> list[tuple[object, float]]:
        cues: list[tuple[object, float]] = []
        cursor = 0.0
        for shot in manifest.shots:
            for cue in shot.sfx:
                cues.append((cue, cursor + cue.at))
            cursor += shot.duration
        return cues
