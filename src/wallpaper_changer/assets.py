# -*- coding: utf-8 -*-
"""App icon (generated in code, no external files)."""

from __future__ import annotations

from PIL import Image, ImageDraw


def make_icon_image(size: int = 64) -> Image.Image:
    """A circle half dark, half light."""
    s = max(16, int(size))
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = max(1, s // 32)
    d.ellipse((m, m, s - m, s - m), fill=(240, 240, 240, 255))
    d.pieslice((m, m, s - m, s - m), 90, 270, fill=(30, 30, 34, 255))
    d.ellipse((m, m, s - m, s - m), outline=(128, 128, 128, 255), width=max(1, s // 32))
    return img
