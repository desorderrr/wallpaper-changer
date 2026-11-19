#!/usr/bin/env bash
# Compila o WallpaperChanger para Linux (binário único)
set -e
cd "$(dirname "$0")/.."
pip install -e ".[dev]"
python scripts/make_icon.py
python -m PyInstaller --noconfirm --onefile \
  --name wallpaper-changer \
  --hidden-import pystray._xorg \
  --collect-all customtkinter --paths src scripts/launcher.py
echo
echo "OK: dist/wallpaper-changer"
