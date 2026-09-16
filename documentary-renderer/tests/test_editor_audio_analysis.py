from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from editor.backend.audio_analysis import AudioAnalysisService


def write_tone(path: Path, duration: float = 0.25, frequency: float = 440) -> None:
    sample_rate = 8000
    frames = int(sample_rate * duration)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        samples = [int(20000 * math.sin(2 * math.pi * frequency * index / sample_rate)) for index in range(frames)]
        output.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def test_reads_metadata_and_builds_normalized_waveform(tmp_path: Path) -> None:
    audio = tmp_path / "tone.wav"
    write_tone(audio)
    service = AudioAnalysisService(tmp_path / "cache")

    metadata = service.metadata(audio)
    waveform = service.waveform(audio, points=256)

    assert metadata["duration"] == 0.25
    assert waveform["duration"] == 0.25
    assert waveform["points"] == 256
    assert len(waveform["peaks"]) == 256
    assert all(len(pair) == 2 for pair in waveform["peaks"])
    assert all(-1 <= value <= 1 for pair in waveform["peaks"] for value in pair)


def test_waveform_cache_key_changes_when_audio_changes(tmp_path: Path) -> None:
    audio = tmp_path / "tone.wav"
    cache = tmp_path / "cache"
    write_tone(audio, duration=0.2)
    service = AudioAnalysisService(cache)

    first = service.waveform(audio, points=256)
    service.waveform(audio, points=256)
    assert len(list(cache.glob("*.json"))) == 1

    write_tone(audio, duration=0.4, frequency=220)
    second = service.waveform(audio, points=256)

    assert second["duration"] != first["duration"]
    assert len(list(cache.glob("*.json"))) == 2
