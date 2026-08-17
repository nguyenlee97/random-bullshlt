"""Image preparation for Zalo OA's JPG/PNG, 1 MB media contract."""
from __future__ import annotations

from dataclasses import dataclass
import io

from PIL import Image, ImageOps


ZALO_IMAGE_MAX_BYTES = 1_000_000
# Leave room for provider-side interpretation and metadata differences.
ZALO_IMAGE_SAFE_BYTES = 950_000


@dataclass(frozen=True)
class PreparedZaloImage:
    data: bytes
    content_type: str
    changed: bool
    original_bytes: int
    width: int
    height: int


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    output = io.BytesIO()
    image.save(
        output, format="JPEG", quality=quality, optimize=True,
        progressive=True, subsampling="4:2:0",
    )
    return output.getvalue()


def prepare_zalo_image(
    image_bytes: bytes,
    content_type: str,
    *,
    max_bytes: int = ZALO_IMAGE_SAFE_BYTES,
) -> PreparedZaloImage:
    """Return a provider-safe image and whether a full-resolution fallback helps."""
    if not image_bytes:
        raise ValueError("image is empty")
    if max_bytes <= 0 or max_bytes > ZALO_IMAGE_MAX_BYTES:
        raise ValueError("max_bytes must be between 1 and Zalo's 1 MB limit")

    source_type = str(content_type or "").split(";", 1)[0].strip().lower()
    with Image.open(io.BytesIO(image_bytes)) as opened:
        image_format = str(opened.format or "").upper()
        image = ImageOps.exif_transpose(opened).convert("RGB")

    width, height = image.size
    source_matches_format = (
        (source_type == "image/jpeg" and image_format == "JPEG")
        or (source_type == "image/png" and image_format == "PNG")
    )
    if (
        len(image_bytes) <= max_bytes
        and source_matches_format
    ):
        return PreparedZaloImage(
            data=image_bytes, content_type=source_type, changed=False,
            original_bytes=len(image_bytes), width=width, height=height,
        )

    working = image
    if max(working.size) > 2200:
        working.thumbnail((2200, 2200), Image.Resampling.LANCZOS)

    for _resize_round in range(9):
        for quality in (88, 82, 76, 70, 64, 58, 50, 42, 34):
            encoded = _encode_jpeg(working, quality)
            if len(encoded) <= max_bytes:
                return PreparedZaloImage(
                    data=encoded, content_type="image/jpeg", changed=True,
                    original_bytes=len(image_bytes), width=working.width,
                    height=working.height,
                )
        next_size = (
            max(320, int(working.width * 0.82)),
            max(240, int(working.height * 0.82)),
        )
        if next_size == working.size:
            break
        working = working.resize(next_size, Image.Resampling.LANCZOS)

    raise ValueError("image could not be reduced below Zalo's 1 MB limit")
