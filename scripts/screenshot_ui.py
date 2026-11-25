# -*- coding: utf-8 -*-
"""Dev utility: capture the settings window."""

import ctypes
import ctypes.wintypes as wt
import os
import time
from pathlib import Path

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:  # noqa: BLE001 - DPI awareness is optional in this script
    pass

import customtkinter as ctk
from PIL import Image

from wallpaper_changer import config
from wallpaper_changer.app import open_image_folder, status_text
from wallpaper_changer.ui import SettingsWindow

# --- Win32 declarations with correct types (64-bit) -----------------------
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.GetWindowDC.restype = wt.HDC
user32.GetWindowDC.argtypes = [wt.HWND]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.PrintWindow.restype = wt.BOOL
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.GetDIBits.argtypes = [
    wt.HDC,
    wt.HBITMAP,
    wt.UINT,
    wt.UINT,
    ctypes.c_void_p,
    ctypes.c_void_p,
    wt.UINT,
]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def grab_window(hwnd: int) -> Image.Image:
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    if not user32.PrintWindow(hwnd, mdc, 2):  # PW_RENDERFULLCONTENT
        gdi32.BitBlt(mdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = w
    bmi.bmiHeader.biHeight = -h
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)

    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return img


def main() -> None:
    config.load_settings()
    # Never capture real keys for repository screenshots
    config._settings["unsplash_key"] = "exemplo-chave-falsa-000000000000"
    light = bool(os.environ.get("WPC_SHOT_LIGHT"))
    if light:
        ctk.set_appearance_mode("light")
    suffix = "-light" if light else ""
    Path("docs").mkdir(exist_ok=True)
    root = ctk.CTk()
    root.withdraw()
    win = SettingsWindow(
        root,
        on_save=lambda values: None,
        on_close=lambda: None,
        change_wallpaper=lambda manual: (True, "ok"),
        status_text=status_text,
        open_folder=open_image_folder,
        preview_candidate=lambda: (False, "", None),
        apply_image=lambda path: (True, "ok"),
        list_recent=__import__(
            "wallpaper_changer.app", fromlist=["app"]
        ).list_recent_images,
        forget_history=lambda: None,
    )
    win.set_header_provider(status_text)
    win.deiconify()
    win.lift()
    win.attributes("-topmost", True)
    win.geometry("780x740+80+80")
    for _ in range(40):
        root.update()
        time.sleep(0.1)

    for tab, filename in (
        ("Geral", "docs/screenshot%s.png" % suffix),
        ("Pré-visualizar", "docs/screenshot-preview%s.png" % suffix),
        ("Pesquisas", "docs/screenshot-pesquisas%s.png" % suffix),
        ("Sobre", "docs/screenshot-sobre%s.png" % suffix),
    ):
        win.tabs.set(tab)
        for _ in range(8):
            root.update()
            time.sleep(0.05)
        img = grab_window(int(win.wm_frame(), 16))
        img.save(filename)
        print("saved", filename, img.size)

    win.destroy()
    root.destroy()


if __name__ == "__main__":
    main()
