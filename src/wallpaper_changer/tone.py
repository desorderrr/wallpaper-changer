# -*- coding: utf-8 -*-
"""Image tone (dark/light) checking.

Tone matching uses the **median** luminance, not the mean: a mostly dark
wallpaper with a small bright sun (or a mostly light one with a dark
subject) keeps the correct classification, whereas the mean would be
dragged by the bright/dark area.
"""

from __future__ import annotations

import io

from PIL import Image

DARK_MAX_LUMA = 115  # median luminance at or below this -> dark image
LIGHT_MIN_LUMA = 140  # median luminance at or above this -> light image

_THUMBNAIL = (128, 128)


def _grayscale(img_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    img.thumbnail(_THUMBNAIL)
    return img


def luminance_profile(img_bytes: bytes) -> tuple[float, float]:
    """(median, mean) luminance (0-255) of an image from raw bytes."""
    histogram = _grayscale(img_bytes).histogram()
    total = sum(histogram)
    if not total:
        return 0.0, 0.0
    mean = sum(value * count for value, count in enumerate(histogram)) / total
    half = total / 2
    seen = 0
    median = 0.0
    for value, count in enumerate(histogram):
        seen += count
        if seen >= half:
            median = float(value)
            break
    return median, mean


def median_luminance(img_bytes: bytes) -> float:
    """Median luminance (0-255) — the value used for tone matching."""
    return luminance_profile(img_bytes)[0]


def mean_luminance(img_bytes: bytes) -> float:
    """Mean luminance (0-255) — kept for logging/diagnostics."""
    return luminance_profile(img_bytes)[1]


def tone_matches(luma: float, want_dark: bool) -> bool:
    """Check a median luminance against the dark/light thresholds."""
    if want_dark:
        return luma <= DARK_MAX_LUMA
    return luma >= LIGHT_MIN_LUMA
