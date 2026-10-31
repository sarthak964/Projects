import base64
import io
from pathlib import Path

from PIL import Image, ImageOps

# Refuse absurdly large images (decompression bombs). Pillow raises an error
# at roughly twice this value.
Image.MAX_IMAGE_PIXELS = 40_000_000

ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


class InvalidImageError(ValueError):
    pass


def inspect_image(data: bytes) -> tuple[str, str]:
    """
    Checks the bytes really are a JPEG/PNG/WebP image (not just named like one).
    Returns (content_type, file_extension) or raises InvalidImageError.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except Exception:
        raise InvalidImageError("File is not a valid image")

    if fmt not in ALLOWED_FORMATS:
        raise InvalidImageError("Only JPEG, PNG or WebP images are allowed")

    return ALLOWED_FORMATS[fmt]


def to_data_url(path: Path | str, max_side: int = 1280) -> str:
    """
    Downscales a stored photo (the original on disk is left untouched) and
    returns it as a base64 data URL the vision model can read.
    """
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80)

    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{encoded}"
