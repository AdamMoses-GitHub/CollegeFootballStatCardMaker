from __future__ import annotations

import os
from dataclasses import dataclass

from PIL import Image


def _validate_color(color: str) -> str:
    """Return color if it looks like a valid hex string, else white."""
    if isinstance(color, str) and color.startswith("#") and len(color) in (4, 7):
        return color
    return "#FFFFFF"


@dataclass
class CardConfig:
    width_in: float = 6.0
    height_in: float = 4.0
    dpi: int = 300
    bg_color: str = "#FFFFFF"

    @property
    def width_px(self) -> int:
        return round(self.width_in * self.dpi)

    @property
    def height_px(self) -> int:
        return round(self.height_in * self.dpi)

    @property
    def is_landscape(self) -> bool:
        return self.width_in >= self.height_in

    def new_canvas(self) -> Image.Image:
        return Image.new(
            "RGB",
            (self.width_px, self.height_px),
            _validate_color(self.bg_color),
        )

    def export(self, image: Image.Image, path: str, fmt: str = "PNG") -> str:
        """Write image to path.  Creates parent directories.  Returns the final path."""
        fmt = fmt.upper()
        # Fix extension to match format
        base, _ = os.path.splitext(path)
        ext = ".jpg" if fmt == "JPEG" else f".{fmt.lower()}"
        final_path = base + ext

        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        if fmt == "JPEG" and image.mode == "RGBA":
            # Flatten alpha onto white background for JPEG
            bg = Image.new("RGB", image.size, "#FFFFFF")
            bg.paste(image, mask=image.split()[3])
            image = bg
        elif image.mode != "RGB" and fmt == "JPEG":
            image = image.convert("RGB")

        image.save(final_path, format=fmt)
        return final_path
