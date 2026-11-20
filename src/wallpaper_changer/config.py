# -*- coding: utf-8 -*-
"""Configurações, caminhos e utilidades comuns."""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

APP_NAME = "WallpaperChanger"
APP_VERSION = "2.2.0"

DEFAULTS = {
    "interval": "daily",           # startup_only | 5m | 10m | 15m | 30m | 1h | 2h | 3h | 6h | 12h | daily
    "theme_mode": "auto",          # auto (segue o sistema) | dark | light
    "use_unsplash": True,
    "use_bing": True,
    "use_wallhaven": False,
    "paused": False,               # pausa as mudanças automáticas
    "change_on_start": True,
    "unsplash_key": "",
    "keep": 20,
    "queries_dark": [
        "dark minimal wallpaper",
        "dark nature landscape",
        "dark abstract background",
        "night city dark",
    ],
    "queries_light": [
        "minimal light wallpaper",
        "white minimal architecture",
        "bright nature landscape",
        "light pastel abstract",
    ],
}

INTERVALS = {
    "5m": 5 * 60,
    "10m": 10 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "3h": 3 * 60 * 60,
    "6h": 6 * 60 * 60,
    "12h": 12 * 60 * 60,
    "daily": 24 * 60 * 60,
}

INTERVAL_LABELS = [
    ("startup_only", "Apenas ao iniciar"),
    ("5m", "Cada 5 minutos"),
    ("10m", "Cada 10 minutos"),
    ("15m", "Cada 15 minutos"),
    ("30m", "Cada 30 minutos"),
    ("1h", "Cada 1 hora"),
    ("2h", "Cada 2 horas"),
    ("3h", "Cada 3 horas"),
    ("6h", "Cada 6 horas"),
    ("12h", "Cada 12 horas"),
    ("daily", "Diário"),
]

_lock = threading.RLock()
_settings = dict(DEFAULTS)


# ---------------------------------------------------------------------------
# Caminhos (por sistema operativo; WPC_DATA_DIR permite override em testes)
# ---------------------------------------------------------------------------
def data_dir() -> Path:
    override = os.environ.get("WPC_DATA_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "WallpaperChanger"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "WallpaperChanger"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "wallpaper-changer"


def image_dir() -> Path:
    return data_dir() / "wallpapers"


def settings_file() -> Path:
    return data_dir() / "settings.json"


def log_file() -> Path:
    return data_dir() / "log.txt"


def ensure_dirs() -> None:
    image_dir().mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def load_settings() -> None:
    global _settings
    stored = {}
    migrated = False
    try:
        with open(settings_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                stored = data
    except (OSError, ValueError):
        pass
    _settings = dict(DEFAULTS)
    _settings.update({k: v for k, v in stored.items() if k in DEFAULTS})

    # Migração/validação de valores antigos (ex.: nomes em vez de ids)
    labels_to_values = {label: value for value, label in INTERVAL_LABELS}
    if (
        _settings.get("interval") not in INTERVALS
        and _settings.get("interval") != "startup_only"
    ):
        old_interval = _settings.get("interval")
        _settings["interval"] = labels_to_values.get(old_interval, "daily")
        migrated = True
    if _settings.get("theme_mode") not in ("auto", "dark", "light"):
        _settings["theme_mode"] = "auto"
        migrated = True
    try:
        keep = max(5, min(200, int(_settings.get("keep") or 20)))
        if keep != _settings.get("keep"):
            migrated = True
        _settings["keep"] = keep
    except (TypeError, ValueError):
        _settings["keep"] = 20
        migrated = True
    for key in ("queries_dark", "queries_light"):
        val = _settings.get(key)
        if not isinstance(val, list) or not val:
            _settings[key] = list(DEFAULTS[key])
            migrated = True

    if migrated and stored:
        save_settings()


def save_settings() -> None:
    ensure_dirs()
    with _lock:
        data = dict(_settings)
    tmp = settings_file().with_suffix(".json.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, settings_file())
    except OSError as e:
        log("Erro ao gravar settings: %s" % e)


def get(key):
    with _lock:
        return _settings.get(key)


def _validated(key, value):
    """Normaliza valores problemáticos antes de gravar."""
    if key in ("queries_dark", "queries_light"):
        if not isinstance(value, list) or not value:
            return list(DEFAULTS[key])
    return value


def set_key(key, value) -> None:
    set_many({key: value})


def set_many(values: dict) -> None:
    """Atualiza várias keys e grava o ficheiro uma única vez."""
    with _lock:
        for key, value in values.items():
            _settings[key] = _validated(key, value)
    save_settings()


def log(msg: str) -> None:
    try:
        ensure_dirs()
        with open(log_file(), "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def self_command() -> list[str]:
    """Comando para relançar a app (usado no arranque automático)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "wallpaper_changer"]
