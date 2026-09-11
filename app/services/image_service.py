"""Optional downscaling of uploaded photos before they're classified/stored.

This exists purely to keep S3 storage/traffic small for a personal project —
it's not required for correctness, and MobileNetV2 resizes to 224x224
internally regardless of what we hand it. To turn it off entirely, set
RESIZE_MAX_DIMENSION=0 in .env.
"""

import io

from PIL import Image

_CONTENT_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png"}


def resize_image(image_bytes, max_dimension, content_type=None):
    """Downscale image_bytes so neither side exceeds max_dimension.

    Preserves the original format (JPEG stays JPEG, PNG stays PNG) and
    aspect ratio, and never upscales. Returns (bytes, content_type)
    unchanged if max_dimension is falsy or the image already fits.
    """
    if not max_dimension:
        return image_bytes, content_type

    image = Image.open(io.BytesIO(image_bytes))
    if max(image.size) <= max_dimension:
        return image_bytes, content_type

    image_format = image.format or "JPEG"
    if image_format == "JPEG" and image.mode != "RGB":
        image = image.convert("RGB")

    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue(), _CONTENT_TYPES.get(image_format, content_type)
