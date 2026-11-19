# -*- coding: utf-8 -*-
"""Interface comum da camada de sistema operativo."""
from __future__ import annotations

import subprocess
from pathlib import Path


class BasePlatform:
    name = "Generic"

    def is_light_theme(self) -> bool:
        """True se o sistema está em modo claro."""
        return True

    def set_wallpaper(self, path: Path) -> None:
        raise NotImplementedError

    def startup_enabled(self) -> bool:
        return False

    def set_startup(self, enable: bool) -> bool:
        return False

    def open_folder(self, path: Path) -> None:
        raise NotImplementedError


def run(args: list[str], timeout: int = 20) -> tuple[bool, str]:
    """Corre um comando e devolve (sucesso, saída+erros)."""
    try:
        p = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0, out.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
