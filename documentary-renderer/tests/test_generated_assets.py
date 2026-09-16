from __future__ import annotations

import json
from pathlib import Path

from generated_assets import GeneratedAssetBuilder
from manifest_parser import ManifestParser
from manifest_validator import ManifestValidator
from models import GenerationSource, OverlayType


def test_manifest_parser_accepts_renderer_overlay_asset_without_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "project": {"title": "Test", "output": str(tmp_path / "out.mp4")},
                "assets": [
                    {
                        "asset_id": "ASSET_EVIDENCE_001",
                        "type": "image",
                        "generation_source": "renderer",
                        "visual_level": "GRAPHIC",
                        "overlay": {
                            "type": "EVIDENCE",
                            "data": {
                                "evidence_number": "03",
                                "evidence_type": "REGISTRO TELEFÓNICO",
                                "time": "23:17:42",
                                "short_description": "Última llamada registrada",
                            },
                        },
                    }
                ],
                "shots": [
                    {
                        "shot_id": "SHOT_001",
                        "asset_id": "ASSET_EVIDENCE_001",
                        "duration": 4,
                        "story_function": "EVIDENCE",
                        "visual_type": "EVIDENCE",
                        "visual_level": "GRAPHIC",
                        "importance": 6,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = ManifestParser().parse(manifest_path)

    asset = manifest.assets["ASSET_EVIDENCE_001"]
    assert asset.generation_source is GenerationSource.RENDERER
    assert asset.file is None
    assert asset.overlay is not None
    assert asset.overlay.type is OverlayType.EVIDENCE


def test_generated_asset_builder_creates_overlay_file_before_validation(tmp_path: Path) -> None:
    manifest = ManifestParser().parse(
        tmp_path / "manifest.json"
        if False
        else _write_overlay_manifest(tmp_path, "QUOTE", {"quote": "La llamada nunca apareció", "source": "Informe policial"})
    )

    GeneratedAssetBuilder(base_dir=tmp_path).build(manifest)

    asset = manifest.assets["ASSET_OVERLAY_001"]
    assert asset.file == tmp_path / "generated" / "ASSET_OVERLAY_001.png"
    assert asset.file.exists()
    ManifestValidator().validate(manifest)


def test_generated_asset_builder_uses_generated_folder_next_to_project_manifest(tmp_path: Path) -> None:
    project_dir = tmp_path / "projects" / "case-a"
    project_dir.mkdir(parents=True)
    manifest = ManifestParser().parse(
        _write_overlay_manifest(project_dir, "TIMELINE", {"events": [{"time": "22:17", "label": "SALE"}]})
    )

    GeneratedAssetBuilder(base_dir=project_dir).build(manifest)

    assert manifest.assets["ASSET_OVERLAY_001"].file == project_dir / "generated" / "ASSET_OVERLAY_001.png"


def _write_overlay_manifest(tmp_path: Path, overlay_type: str, data: dict) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "project": {"title": "Test", "output": str(tmp_path / "out.mp4")},
                "assets": [
                    {
                        "asset_id": "ASSET_OVERLAY_001",
                        "type": "image",
                        "generation_source": "renderer",
                        "visual_level": "GRAPHIC",
                        "overlay": {"type": overlay_type, "data": data},
                    }
                ],
                "shots": [
                    {
                        "shot_id": "SHOT_001",
                        "asset_id": "ASSET_OVERLAY_001",
                        "duration": 4,
                        "story_function": "EVIDENCE",
                        "visual_type": overlay_type if overlay_type != "QUOTE" else "QUOTE",
                        "visual_level": "GRAPHIC",
                        "importance": 6,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path
