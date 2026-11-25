# -*- coding: utf-8 -*-
"""Image tone (dark/light) checking."""

from __future__ import annotations

import io

from PIL import Image, ImageStat

DARK_MAX_LUMA = 115  # mean luminance below this -> dark image
LIGHT_MIN_LUMA = 140  # mean luminance above this -> light image


def mean_luminance(img_bytes: bytes) -> float:
    """Mean luminance (0-255) of an image, from raw bytes."""
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    img.thumbnail((128, 128))
    return ImageStat.Stat(img).mean[0]


def tone_matches(luma: float, want_dark: bool) -> bool:
    if want_dark:
        return luma <= DARK_MAX_LUMA
    return luma >= LIGHT_MIN_LUMA
