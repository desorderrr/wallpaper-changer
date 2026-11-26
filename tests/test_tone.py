# -*- coding: utf-8 -*-
"""Tests for tone (dark/light) detection."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from wallpaper_changer import tone


def img_bytes(color, size=(64, 64)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


def split_img_bytes(left_pct, left_color, right_color, size=(64, 64)):
    """Image split vertically: left_pct% of the columns in left_color."""
    img = Image.new("RGB", size, right_color)
    draw = ImageDraw.Draw(img)
    cut = round(size[0] * left_pct / 100)
    draw.rectangle((0, 0, cut - 1, size[1] - 1), fill=left_color)
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def test_luminance_dark_and_light():
    assert tone.mean_luminance(img_bytes((5, 5, 5))) <= 115
    assert tone.mean_luminance(img_bytes((250, 250, 250))) >= 140


def test_median_and_mean_profile():
    median, mean = tone.luminance_profile(img_bytes((120, 120, 120)))
    assert 115 <= median <= 125
    assert 115 <= mean <= 125


def test_tone_matching():
    dark = tone.median_luminance(img_bytes((10, 10, 10)))
    light = tone.median_luminance(img_bytes((245, 245, 245)))
    assert tone.tone_matches(dark, want_dark=True)
    assert not tone.tone_matches(light, want_dark=True)
    assert tone.tone_matches(light, want_dark=False)
    assert not tone.tone_matches(dark, want_dark=False)


def test_median_ignores_large_bright_area_in_dark_image():
    # 56% dark + 44% bright: the mean is pulled above the dark limit,
    # but the median stays dark (the fix we want).
    data = split_img_bytes(56, (10, 10, 10), (255, 255, 255))
    median, mean = tone.luminance_profile(data)
    assert mean > tone.DARK_MAX_LUMA
    assert median <= tone.DARK_MAX_LUMA
    assert tone.tone_matches(median, want_dark=True)


def test_median_keeps_bright_image_light():
    # 55% bright + 45% black: the mean stays below the light limit,
    # but the median is light.
    data = split_img_bytes(55, (150, 150, 150), (0, 0, 0))
    median, mean = tone.luminance_profile(data)
    assert mean < tone.LIGHT_MIN_LUMA
    assert median >= tone.LIGHT_MIN_LUMA
    assert tone.tone_matches(median, want_dark=False)
