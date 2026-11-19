@echo off
REM Compila o WallpaperChanger para Windows (exe standalone)
cd /d "%~dp0.."
pip install -e ".[dev]"
python scripts\make_icon.py
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name WallpaperChanger --icon icon.ico ^
  --hidden-import pystray._win32 ^
  --collect-all customtkinter --paths src scripts\launcher.py
if exist "dist\WallpaperChanger.exe" (
    echo.
    echo OK: dist\WallpaperChanger.exe criado.
) else (
    echo.
    echo ERRO: a compilacao falhou.
)
pause
