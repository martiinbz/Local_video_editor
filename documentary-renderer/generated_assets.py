"""Generate renderer-owned visual assets declared in V2 manifests."""

from __future__ import annotations

from pathlib import Path

from models import GenerationSource, Manifest, OverlayType
from overlays import OverlayRenderer


class GeneratedAssetBuilder:
    """Materialize `generation_source=renderer` overlay assets as PNG files."""

    def __init__(self, base_dir: str | Path = ".") -> None:
        self.base_dir = Path(base_dir)

    def build(self, manifest: Manifest) -> None:
        renderer = OverlayRenderer(
            width=manifest.project.width,
            height=manifest.project.height,
            accent_color=manifest.project.accent_color,
        )
        output_dir = self.base_dir / "generated"
        for asset in manifest.assets.values():
            if asset.generation_source is not GenerationSource.RENDERER or asset.overlay is None:
                continue
            output = output_dir / f"{asset.asset_id}.png"
            self._generate(renderer, asset.overlay.type, asset.overlay.data, output)
            asset.file = output

    @staticmethod
    def _generate(renderer: OverlayRenderer, overlay_type: OverlayType, data: dict, output: Path) -> None:
        if overlay_type is OverlayType.EVIDENCE:
            renderer.generate_evidence_card(data, output)
            return
        if overlay_type is OverlayType.CASE_FILE:
            renderer.generate_case_file(data, output)
            return
        if overlay_type is OverlayType.QUOTE:
            renderer.generate_quote(data, output)
            return
        if overlay_type is OverlayType.TIMELINE:
            renderer.generate_timeline(data, output)
            return
        if overlay_type is OverlayType.MAP:
            renderer.generate_map(data, output)
            return
        if overlay_type in (OverlayType.DOCUMENT, OverlayType.DATE, OverlayType.LOCATION, OverlayType.THEORY):
            renderer.generate_document(data, output)
            return
        raise ValueError(f"Unsupported overlay type: {overlay_type.value}")
