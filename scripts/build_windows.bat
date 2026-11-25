@echo off
REM Build WallpaperChanger for Windows (standalone exe)
cd /d "%~dp0.."
pip install -e ".[dev]"
python scripts\make_icon.py
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name WallpaperChanger --icon icon.ico ^
  --hidden-import pystray._win32 ^
  --collect-all customtkinter --paths src scripts\launcher.py
if exist "dist\WallpaperChanger.exe" (
    echo.
    echo OK: dist\WallpaperChanger.exe created.
) else (
    echo.
    echo ERROR: the build failed.
)
pause
