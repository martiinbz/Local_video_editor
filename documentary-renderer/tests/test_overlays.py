from __future__ import annotations

from pathlib import Path

from PIL import Image

from overlays import OverlayRenderer


def test_overlay_renderer_generates_evidence_card_png(tmp_path: Path) -> None:
    output = tmp_path / "evidence.png"

    OverlayRenderer(width=1920, height=1080).generate_evidence_card(
        {
            "evidence_number": "03",
            "evidence_type": "REGISTRO TELEFÓNICO",
            "time": "23:17:42",
            "short_description": "Última llamada registrada",
        },
        output,
    )

    assert output.exists()
    with Image.open(output) as image:
        assert image.size == (1920, 1080)
        assert image.mode == "RGB"
