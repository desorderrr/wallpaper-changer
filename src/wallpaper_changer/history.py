# -*- coding: utf-8 -*-
"""History of used wallpapers (so they are never repeated).

Stores an exact hash (sha256) and a perceptual hash (8x8 aHash) of every
applied image. The aHash catches the same photo even when recompressed
or resized.
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
HAMMING_MAX = 2  # max aHash distance to consider "the same image"

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
            i for i in raw if isinstance(i, dict) and isinstance(i.get("ahash"), str)
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
    """(8x8 aHash, mean luminance) — together they identify the image."""
    img = Image.open(io.BytesIO(data)).convert("L").resize((8, 8))
    if hasattr(img, "get_flattened_data"):
        pixels = list(img.get_flattened_data())
    else:  # Pillow < 13
        pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return "%016x" % bits, round(avg)


def ahash(data: bytes) -> str:
    """8x8 perceptual hash (64 bits in hex)."""
    return _fingerprint(data)[0]


def ahash_path(path) -> str | None:
    try:
        return ahash(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def _hamming(a: str, b: str) -> int:
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except ValueError:
        return 64


def is_similar_hash(a: str, b: str) -> bool:
    return len(a) == len(b) and _hamming(a, b) <= HAMMING_MAX


def _similar(ahash_a: str, ahash_b: str) -> bool:
    return is_similar_hash(ahash_a, ahash_b)


def is_duplicate(data: bytes) -> bool:
    """True if this image (bytes) was already used."""
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
            # luminance avoids false positives on "flat" images
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
    """Record an image as used."""
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
    """Forget the history (allows reusing the same images)."""
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
    """On first run, mark already saved images as used."""
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
