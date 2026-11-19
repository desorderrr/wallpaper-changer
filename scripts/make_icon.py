# -*- coding: utf-8 -*-
"""Gera os ícones de empacotamento (ico/png e icns no macOS)."""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent


def draw(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size // 32
    d.ellipse((m, m, size - m, size - m), fill=(240, 240, 240, 255))
    d.pieslice((m, m, size - m, size - m), 90, 270, fill=(30, 30, 34, 255))
    d.ellipse((m, m, size - m, size - m), outline=(128, 128, 128, 255),
              width=max(1, size // 32))
    return img


def main() -> None:
    img = draw()
    png = ROOT / "icon.png"
    img.save(png)
    img.save(ROOT / "icon.ico", sizes=[
        (16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)
    ])
    print("icon.ico e icon.png criados")

    if sys.platform == "darwin":
        iconset = ROOT / "icon.iconset"
        iconset.mkdir(exist_ok=True)
        for size in (16, 32, 64, 128, 256, 512):
            img.resize((size, size)).save(iconset / f"icon_{size}x{size}.png")
            img.resize((size * 2, size * 2)).save(
                iconset / f"icon_{size}x{size}@2x.png")
        try:
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset),
                 "-o", str(ROOT / "icon.icns")],
                check=True,
            )
            print("icon.icns criado")
        except (OSError, subprocess.CalledProcessError) as e:
            print("aviso: não foi possível criar icon.icns:", e)


if __name__ == "__main__":
    main()
