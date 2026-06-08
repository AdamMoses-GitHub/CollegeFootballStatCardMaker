from PIL import Image


def apply_export_margin(
    img: Image.Image, bg_color: str, margin_pct: float
) -> Image.Image:
    """Add a proportional border around the image.

    margin_pct is a percentage of the card dimensions (e.g. 5.0 = 5%).
    Returns the original image unchanged when margin_pct <= 0.
    """
    if margin_pct <= 0:
        return img
    pad_x = max(1, round(img.width * margin_pct / 100))
    pad_y = max(1, round(img.height * margin_pct / 100))
    canvas = Image.new(
        img.mode,
        (img.width + pad_x * 2, img.height + pad_y * 2),
        bg_color,
    )
    canvas.paste(img, (pad_x, pad_y))
    return canvas
