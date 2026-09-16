"""Renderer-generated V2 graphic overlays."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class OverlayRenderer:
    """Generate noir case-file graphic cards as PNG images."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        accent_color: str = "#A33A2A",
        background_color: str = "#d8cfbd",
    ) -> None:
        self.width = width
        self.height = height
        self.accent_color = accent_color
        self.background_color = background_color

    def generate_evidence_card(self, data: dict[str, Any], output: str | Path) -> Path:
        image = self._base_image()
        draw = ImageDraw.Draw(image)
        title_font = self._font(82)
        body_font = self._font(46)
        mono_font = self._font(64)

        margin_x = 220
        draw.rectangle((margin_x, 180, self.width - margin_x, self.height - 180), outline="#1d1a17", width=4)
        draw.line((margin_x, 305, self.width - margin_x, 305), fill=self.accent_color, width=8)
        draw.text((margin_x + 70, 215), f"EVIDENCIA {data.get('evidence_number', '')}", fill="#171411", font=title_font)
        draw.text((margin_x + 70, 380), str(data.get("evidence_type", "")).upper(), fill="#171411", font=body_font)
        draw.text((margin_x + 70, 505), str(data.get("time", "")), fill=self.accent_color, font=mono_font)
        draw.text((margin_x + 70, 650), str(data.get("short_description", ""))[:90], fill="#171411", font=body_font)

        return self._save(image, output)

    def generate_case_file(self, data: dict[str, Any], output: str | Path) -> Path:
        image = self._base_image()
        draw = ImageDraw.Draw(image)
        title_font = self._font(76)
        body_font = self._font(44)
        margin_x = 180
        y = 190
        rows = [
            f"EXPEDIENTE Nº {data.get('case_number', '')}",
            str(data.get("subject", "")).upper(),
            str(data.get("location", "")).upper(),
            str(data.get("date", "")).upper(),
            f"ESTADO: {str(data.get('status', '')).upper()}",
        ]
        for index, row in enumerate(rows):
            font = title_font if index == 0 else body_font
            fill = self.accent_color if index == 4 else "#171411"
            draw.text((margin_x, y), row, fill=fill, font=font)
            y += 135 if index == 0 else 105
        return self._save(image, output)

    def generate_quote(self, data: dict[str, Any], output: str | Path) -> Path:
        image = self._base_image()
        draw = ImageDraw.Draw(image)
        quote_font = self._font(72)
        source_font = self._font(36)
        quote = f"“{str(data.get('quote', '')).strip()}”"
        source = str(data.get("source", "")).strip()
        draw.text((220, 300), self._wrap(quote, 34), fill="#171411", font=quote_font, spacing=18)
        if source:
            draw.line((220, 760, 520, 760), fill=self.accent_color, width=6)
            draw.text((220, 795), source.upper(), fill="#171411", font=source_font)
        return self._save(image, output)

    def generate_timeline(self, data: dict[str, Any], output: str | Path) -> Path:
        image = self._base_image()
        draw = ImageDraw.Draw(image)
        title_font = self._font(62)
        time_font = self._font(46)
        body_font = self._font(42)
        events = list(data.get("events", []))[:5]
        draw.text((180, 140), str(data.get("title", "CRONOLOGÍA")).upper(), fill="#171411", font=title_font)
        x_line = 320
        y = 300
        draw.line((x_line, y - 40, x_line, y + 120 * max(1, len(events))), fill=self.accent_color, width=6)
        for event in events:
            draw.ellipse((x_line - 16, y - 16, x_line + 16, y + 16), fill=self.accent_color)
            draw.text((380, y - 34), str(event.get("time", "")), fill=self.accent_color, font=time_font)
            draw.text((620, y - 30), str(event.get("label", "")).upper(), fill="#171411", font=body_font)
            y += 120
        return self._save(image, output)

    def generate_map(self, data: dict[str, Any], output: str | Path) -> Path:
        image = self._base_image()
        draw = ImageDraw.Draw(image)
        title_font = self._font(58)
        label_font = self._font(34)
        points = list(data.get("points", []))
        lines = list(data.get("lines", []))
        draw.text((150, 110), str(data.get("title", "MAPA")).upper(), fill="#171411", font=title_font)
        box = (180, 220, self.width - 180, self.height - 140)
        draw.rectangle(box, outline="#1d1a17", width=4)
        draw.line((box[0], box[3] - 120, box[2], box[1] + 70), fill="#b8ad9b", width=2)
        draw.line((box[0] + 160, box[1], box[2] - 220, box[3]), fill="#b8ad9b", width=2)
        coords = []
        for point in points:
            x = box[0] + float(point.get("x", 0.5)) * (box[2] - box[0])
            y = box[1] + float(point.get("y", 0.5)) * (box[3] - box[1])
            coords.append((x, y, str(point.get("label", ""))))
        for line in lines:
            try:
                a, b = int(line[0]), int(line[1])
                draw.line((coords[a][0], coords[a][1], coords[b][0], coords[b][1]), fill=self.accent_color, width=5)
            except (IndexError, TypeError, ValueError):
                continue
        for x, y, label in coords:
            draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=self.accent_color)
            draw.text((x + 22, y - 18), label.upper(), fill="#171411", font=label_font)
        return self._save(image, output)

    def generate_document(self, data: dict[str, Any], output: str | Path) -> Path:
        image = self._base_image(background="#cfc5b3")
        draw = ImageDraw.Draw(image)
        title_font = self._font(58)
        body_font = self._font(36)
        draw.rectangle((300, 120, self.width - 300, self.height - 110), fill="#eee5d3", outline="#1d1a17", width=3)
        draw.text((380, 200), str(data.get("title", "DOCUMENTO")).upper(), fill="#171411", font=title_font)
        y = 330
        for line in str(data.get("body", "")).splitlines()[:10]:
            draw.text((380, y), line[:70], fill="#171411", font=body_font)
            y += 58
        stamp = str(data.get("stamp", "")).upper()
        if stamp:
            draw.rectangle((1180, 720, 1540, 830), outline=self.accent_color, width=6)
            draw.text((1210, 755), stamp[:16], fill=self.accent_color, font=body_font)
        return self._save(image, output)

    def _base_image(self, background: str | None = None) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height), background or self.background_color)
        draw = ImageDraw.Draw(image)
        for x in range(0, self.width, 7):
            shade = 212 + (x % 23)
            draw.line((x, 0, x, self.height), fill=(shade, max(190, shade - 10), max(170, shade - 24)))
        return image

    @staticmethod
    def _wrap(text: str, width: int) -> str:
        words = text.split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            if sum(len(item) + 1 for item in current) + len(word) > width and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)

    @staticmethod
    def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        try:
            return ImageFont.truetype("arial.ttf", size=size)
        except OSError:
            return ImageFont.load_default()

    @staticmethod
    def _save(image: Image.Image, output: str | Path) -> Path:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return path
