# -*- coding: utf-8 -*-
"""Backend Windows: tema, wallpaper, arranque automático."""
from __future__ import annotations

import ctypes
import os
import subprocess
import winreg
from pathlib import Path

from .base import BasePlatform

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "WallpaperChanger"

SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02


class Platform(BasePlatform):
    name = "Windows"

    # -- tema ---------------------------------------------------------
    def is_light_theme(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as k:
                try:
                    val, _ = winreg.QueryValueEx(k, "SystemUsesLightTheme")
                except OSError:
                    val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                return bool(val)
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
            raise OSError("SystemParametersInfoW falhou")

    # -- arranque com o Windows ----------------------------------------
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
                # CreateKeyEx porque em perfis novos a chave Run pode não existir
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

    # -- diversos -------------------------------------------------------
    def open_folder(self, path: Path) -> None:
        os.startfile(str(path))  # noqa: S606
