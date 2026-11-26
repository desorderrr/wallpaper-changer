# -*- coding: utf-8 -*-
"""Output resolution: screen detection and target size per source."""

from __future__ import annotations

import re
import subprocess
import sys

from . import config

BUCKETS = (1920, 2560, 3840)
DEFAULT_WIDTH = 1920

_screen_width: int | None = None


def _windows_width() -> int:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    widths: list[int] = []
    monitor_proc = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        wintypes.HANDLE,  # HMONITOR
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )

    def callback(hmonitor, hdc, rect, data):
        rect = rect.contents
        widths.append(int(rect.right - rect.left))
        return 1

    try:
        user32.EnumDisplayMonitors.argtypes = [
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            monitor_proc,
            wintypes.LPARAM,
        ]
        user32.EnumDisplayMonitors.restype = wintypes.BOOL
        if user32.EnumDisplayMonitors(None, None, monitor_proc(callback), 0) and widths:
            return max(widths)
    except Exception:  # noqa: BLE001 - fall back to the primary screen
        pass
    try:
        return int(user32.GetSystemMetrics(0))  # SM_CXSCREEN
    except Exception:  # noqa: BLE001
        return 0


def _linux_width() -> int:
    try:
        proc = subprocess.run(
            ["xrandr", "--query"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = proc.stdout or ""
    except (OSError, subprocess.SubprocessError):
        output = ""
    widths = []
    for line in output.splitlines():
        if " connected" not in line:
            continue
        match = re.search(r"(\d{3,5})x(\d{3,5})", line)
        if match:
            widths.append(int(match.group(1)))
    return max(widths) if widths else 0


def _macos_width() -> int:
    try:
        from AppKit import NSScreen

        widths = [
            round(screen.frame().size.width * screen.backingScaleFactor())
            for screen in NSScreen.screens()
        ]
        if widths:
            return max(widths)
    except Exception:  # noqa: BLE001 - pyobjc may be missing or headless
        pass
    return 0


def screen_width() -> int:
    """Width (physical pixels) of the widest monitor, cached after first use."""
    global _screen_width
    if _screen_width is None:
        width = 0
        try:
            if sys.platform == "win32":
                width = _windows_width()
            elif sys.platform == "darwin":
                width = _macos_width()
            else:
                width = _linux_width()
        except Exception:  # noqa: BLE001 - detection is best-effort
            width = 0
        _screen_width = width if width > 0 else DEFAULT_WIDTH
    return _screen_width


def target_width() -> int:
    """Image width (px) to request, from the resolution setting."""
    mode = config.get("resolution") or "auto"
    if mode == "high":
        return BUCKETS[-1]
    if mode == "low":
        return BUCKETS[0]
    width = screen_width()
    for bucket in BUCKETS:
        if width <= bucket:
            return bucket
    return BUCKETS[-1]


def height_for(width: int) -> int:
    """16:9 height for a given width (used by minimum-size filters)."""
    return round(width * 9 / 16)


def download_quality(width: int) -> int:
    """Unsplash JPEG quality: smaller files for smaller targets."""
    if width <= BUCKETS[0]:
        return 78
    if width <= BUCKETS[1]:
        return 82
    return 85


def reset_cache() -> None:
    """Forget the detected screen width (tests, monitor changes)."""
    global _screen_width
    _screen_width = None
