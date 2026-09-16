from __future__ import annotations

from pathlib import Path

from models import (
    Asset,
    AssetType,
    GenerationSource,
    Manifest,
    ProjectConfig,
    Shot,
    StoryFunction,
    VisualLevel,
    VisualType,
)
from qc import QualityControl


def test_qc_does_not_block_high_hero_usage(tmp_path: Path) -> None:
    image = tmp_path / "asset.jpeg"
    image.write_bytes(b"fake")
    manifest = Manifest(
        project=ProjectConfig(title="Test", output=tmp_path / "out.mp4"),
        assets={
            "ASSET_001": Asset(
                asset_id="ASSET_001",
                type=AssetType.IMAGE,
                generation_source=GenerationSource.FLOW,
                file=image,
                visual_level=VisualLevel.HERO,
            )
        },
        shots=[
            Shot(
                shot_id=f"SHOT_{index:03d}",
                asset_id="ASSET_001",
                duration=3,
                story_function=StoryFunction.CONTEXT,
                visual_type=VisualType.RECONSTRUCTION,
                visual_level=VisualLevel.HERO,
                importance=5,
            )
            for index in range(5)
        ],
    )

    report = QualityControl().check(manifest)

    assert not report.has_errors
    assert "HERO usage" not in report.text()


def test_qc_writes_report_file(tmp_path: Path) -> None:
    manifest = Manifest(project=ProjectConfig(title="Test", output=tmp_path / "out.mp4"), assets={}, shots=[])
    report_path = tmp_path / "qc_report.txt"

    QualityControl().write_report(QualityControl().check(manifest), report_path)

    assert "ERROR" in report_path.read_text(encoding="utf-8")
