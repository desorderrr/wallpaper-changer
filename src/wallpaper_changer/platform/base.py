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


def theme_is_light(apps_value: int | None, system_value: int | None) -> bool:
    """Decide o modo claro/escuro a partir das chaves do Windows.

    O "modo das aplicações" (AppsUseLightTheme) é o que a maioria dos
    utilizadores muda em Definições → Cores, por isso tem prioridade;
    o "modo do Windows" (SystemUsesLightTheme) é o fallback.
    """
    if apps_value is not None:
        return bool(apps_value)
    if system_value is not None:
        return bool(system_value)
    return True
