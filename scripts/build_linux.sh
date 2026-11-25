#!/usr/bin/env bash
# Build WallpaperChanger for Linux (single binary)
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
