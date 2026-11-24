# -*- coding: utf-8 -*-
"""Backend macOS: tema, wallpaper (AppleScript) e arranque (LaunchAgent)."""

from __future__ import annotations

import plistlib
from pathlib import Path

from .base import BasePlatform, run

LAUNCH_LABEL = "com.wallpaperchanger.agent"


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / (LAUNCH_LABEL + ".plist")


def parse_defaults(stdout: str, returncode: int) -> bool:
    """Converte a saída de `defaults read -g AppleInterfaceStyle` em claro/escuro."""
    if returncode != 0:
        return True  # a chave não existe -> modo claro
    return "dark" not in stdout.strip().lower()


class Platform(BasePlatform):
    name = "macOS"

    # -- tema ---------------------------------------------------------
    def is_light_theme(self) -> bool:
        ok, out = run(["defaults", "read", "-g", "AppleInterfaceStyle"])
        return parse_defaults(out, 0 if ok else 1)

    # -- wallpaper ----------------------------------------------------
    def set_wallpaper(self, path: Path) -> None:
        safe = str(path).replace("\\", "\\\\").replace('"', '\\"')
        script = (
            'tell application "System Events" to tell every desktop '
            'to set picture to POSIX file "%s"' % safe
        )
        ok, out = run(["osascript", "-e", script])
        if not ok:
            raise RuntimeError("osascript falhou: %s" % out)

    # -- arranque com o sistema ----------------------------------------
    def startup_enabled(self) -> bool:
        return launch_agent_path().exists()

    def set_startup(self, enable: bool) -> bool:
        from ..config import self_command

        plist = launch_agent_path()
        try:
            if enable:
                plist.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "Label": LAUNCH_LABEL,
                    "ProgramArguments": self_command(),
                    "RunAtLoad": True,
                    "ProcessType": "Interactive",
                }
                with open(plist, "wb") as f:
                    plistlib.dump(data, f)
                run(["launchctl", "unload", "-w", str(plist)])
                ok, _ = run(["launchctl", "load", "-w", str(plist)])
                return ok or plist.exists()
            run(["launchctl", "unload", "-w", str(plist)])
            try:
                plist.unlink()
            except FileNotFoundError:
                pass
            return True
        except OSError:
            return False

    # -- diversos -------------------------------------------------------
    def open_folder(self, path: Path) -> None:
        run(["open", str(path)])
