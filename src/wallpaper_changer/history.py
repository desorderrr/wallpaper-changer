# -*- coding: utf-8 -*-
"""Histórico de wallpapers já usados (para nunca repetir).

Guarda um hash exato (sha256) e um hash percetual (aHash 8x8) de cada
imagem aplicada. O aHash apanha a mesma foto mesmo que seja recomprimida
ou redimensionada.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import config

MAX_ITEMS = 500
HAMMING_MAX = 2  # distância máxima no aHash para considerar "a mesma imagem"

_lock = threading.RLock()
_items: list[dict] | None = None


def history_file() -> Path:
    return config.data_dir() / "history.json"


def _load() -> list[dict]:
    global _items
    if _items is not None:
        return _items
    try:
        data = json.loads(history_file().read_text(encoding="utf-8"))
        raw = data.get("items") if isinstance(data, dict) else []
        _items = [
            i for i in raw
            if isinstance(i, dict) and isinstance(i.get("ahash"), str)
        ]
    except (OSError, ValueError):
        _items = []
    return _items


def _save() -> None:
    try:
        config.ensure_dirs()
        tmp = history_file().with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps({"items": _load()[-MAX_ITEMS:]}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, history_file())
    except OSError:
        pass


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fingerprint(data: bytes) -> tuple[str, int]:
    """(aHash 8x8, luminância média) — juntos identificam a imagem."""
    img = Image.open(io.BytesIO(data)).convert("L").resize((8, 8))
    if hasattr(img, "get_flattened_data"):
        pixels = list(img.get_flattened_data())
    else:  # Pillow < 13
        pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return "%016x" % bits, int(round(avg))


def ahash(data: bytes) -> str:
    """Hash percetual 8x8 (64 bits em hex)."""
    return _fingerprint(data)[0]


def ahash_path(path) -> str | None:
    try:
        return ahash(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def _hamming(a: str, b: str) -> int:
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except ValueError:
        return 64


def is_similar_hash(a: str, b: str) -> bool:
    return len(a) == len(b) and _hamming(a, b) <= HAMMING_MAX


def _similar(ahash_a: str, ahash_b: str) -> bool:
    return is_similar_hash(ahash_a, ahash_b)


def is_duplicate(data: bytes) -> bool:
    """True se esta imagem (bytes) já foi usada."""
    try:
        sha = _sha(data)
        ah, luma = _fingerprint(data)
    except (OSError, ValueError):
        return False
    with _lock:
        for item in _load():
            if item.get("sha") == sha:
                return True
            other = item.get("ahash")
            if not isinstance(other, str) or not _similar(ah, other):
                continue
            other_luma = item.get("luma")
            # a luminância evita falsos positivos em imagens "lisas"
            if other_luma is None or abs(luma - int(other_luma)) <= 12:
                return True
    return False


def _build_item(data: bytes, source: str, path=None) -> dict:
    sha = _sha(data)
    ah, luma = _fingerprint(data)
    return {
        "sha": sha,
        "ahash": ah,
        "luma": luma,
        "source": source,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "path": str(path) if path else "",
    }


def add(data: bytes, source: str, path=None) -> None:
    """Regista uma imagem como usada."""
    try:
        item = _build_item(data, source, path)
    except (OSError, ValueError):
        return
    with _lock:
        items = _load()
        items.append(item)
        del items[:-MAX_ITEMS]
        _save()


def add_path(path, source: str) -> None:
    try:
        add(Path(path).read_bytes(), source, path)
    except OSError:
        pass


def reset() -> None:
    """Esquece o histórico (permite voltar a usar as mesmas imagens)."""
    global _items
    with _lock:
        _items = []
        try:
            history_file().unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def count() -> int:
    with _lock:
        return len(_load())


def seed_from_folder() -> int:
    """Na primeira execução, marca as imagens já guardadas como usadas."""
    with _lock:
        if _load():
            return 0
    try:
        files = sorted(
            config.image_dir().glob("*.jpg"),
            key=lambda p: p.stat().st_mtime,
        )
    except OSError:
        return 0
    new_items = []
    for path in files[-MAX_ITEMS:]:
        try:
            new_items.append(_build_item(path.read_bytes(), "existing", path))
        except (OSError, ValueError):
            continue
    if not new_items:
        return 0
    with _lock:
        items = _load()
        items.extend(new_items)
        del items[:-MAX_ITEMS]
        _save()
    return len(new_items)
