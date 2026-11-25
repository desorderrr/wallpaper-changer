#!/usr/bin/env bash
# Build WallpaperChanger for macOS (.app)
set -e
cd "$(dirname "$0")/.."
pip install -e ".[dev]"
python scripts/make_icon.py
python -m PyInstaller --noconfirm --onefile --windowed \
  --name WallpaperChanger --icon icon.icns \
  --hidden-import pystray._darwin \
  --collect-all customtkinter --paths src scripts/launcher.py
echo
echo "OK: dist/WallpaperChanger.app"
