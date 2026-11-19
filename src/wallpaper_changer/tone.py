# -*- coding: utf-8 -*-
"""Verificação do tom (escuro/claro) das imagens."""
from __future__ import annotations

import io

from PIL import Image, ImageStat

DARK_MAX_LUMA = 115   # média de luminância abaixo disto -> imagem escura
LIGHT_MIN_LUMA = 140  # média de luminância acima disto -> imagem clara


def mean_luminance(img_bytes: bytes) -> float:
    """Média de luminância (0-255) de uma imagem a partir de bytes."""
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    img.thumbnail((128, 128))
    return ImageStat.Stat(img).mean[0]


def tone_matches(luma: float, want_dark: bool) -> bool:
    if want_dark:
        return luma <= DARK_MAX_LUMA
    return luma >= LIGHT_MIN_LUMA
