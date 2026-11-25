# -*- coding: utf-8 -*-
"""Common interface for the operating-system layer."""

from __future__ import annotations

import subprocess
from pathlib import Path


class BasePlatform:
    name = "Generic"

    def is_light_theme(self) -> bool:
        """True when the system is in light mode."""
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
    """Run a command and return (success, stdout+stderr)."""
    try:
        p = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0, out.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)


def theme_is_light(apps_value: int | None, system_value: int | None) -> bool:
    """Decide light/dark mode from the Windows registry keys.

    "App mode" (AppsUseLightTheme) is what most users change in
    Settings → Colors, so it takes priority; "Windows mode"
    (SystemUsesLightTheme) is the fallback.
    """
    if apps_value is not None:
        return bool(apps_value)
    if system_value is not None:
        return bool(system_value)
    return True
