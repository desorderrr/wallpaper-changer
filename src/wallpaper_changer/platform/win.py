# -*- coding: utf-8 -*-
"""Windows backend: theme, wallpaper, startup."""

from __future__ import annotations

import ctypes
import os
import subprocess
import winreg
from pathlib import Path

from ..i18n import t
from .base import BasePlatform, theme_is_light

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "WallpaperChanger"

SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02


def _read_dword(key, name: str) -> int | None:
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return int(value)
    except OSError:
        return None


class Platform(BasePlatform):
    name = "Windows"

    # -- theme --------------------------------------------------------
    def is_light_theme(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as k:
                apps = _read_dword(k, "AppsUseLightTheme")
                system = _read_dword(k, "SystemUsesLightTheme")
                return theme_is_light(apps, system)
        except OSError:
            return True

    # -- wallpaper ----------------------------------------------------
    def set_wallpaper(self, path: Path) -> None:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER,
            0,
            str(path),
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
        )
        if not ok:
            raise OSError(t("SystemParametersInfoW falhou"))

    # -- startup with Windows ------------------------------------------
    def startup_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, RUN_VALUE)
                return True
        except OSError:
            return False

    def set_startup(self, enable: bool) -> bool:
        from ..config import self_command

        try:
            if enable:
                # CreateKeyEx: on fresh profiles the Run key may not exist
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
                ) as k:
                    value = subprocess.list2cmdline(self_command())
                    winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, value)
            else:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
                    ) as k:
                        winreg.DeleteValue(k, RUN_VALUE)
                except FileNotFoundError:
                    pass
            return True
        except OSError:
            return False

    # -- misc ----------------------------------------------------------
    def open_folder(self, path: Path) -> None:
        os.startfile(str(path))  # noqa: S606
