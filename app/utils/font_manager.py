from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

_FONT_DIR = Path(__file__).parent.parent.parent / "assets" / "fonts" / "Roboto"

_FONT_FILES: dict[tuple, str] = {
    ("Roboto", False, False, False): "Roboto-Regular.ttf",
    ("Roboto", True,  False, False): "Roboto-Bold.ttf",
    ("Roboto", False, True,  False): "RobotoCondensed-Regular.ttf",
    ("Roboto", True,  True,  False): "RobotoCondensed-Bold.ttf",
    ("Roboto", False, False, True):  "Roboto-Italic.ttf",
}


@lru_cache(maxsize=256)
def get_font(
    size: int,
    bold: bool = False,
    condensed: bool = False,
    italic: bool = False,
    family: str = "Roboto",
) -> ImageFont.FreeTypeFont:
    key = (family, bold, condensed, italic)
    filename = _FONT_FILES.get(key, "Roboto-Regular.ttf")
    path = _FONT_DIR / filename
    if not path.exists():
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)
