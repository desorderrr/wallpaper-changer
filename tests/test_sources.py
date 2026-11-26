import io

import pytest
from PIL import Image

from wallpaper_changer import config, history, sources


def img(color):
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
    return b.getvalue()


def local_png(color, size=(1280, 720)):
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, "PNG")
    return b.getvalue()


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise sources.requests.HTTPError("status %d" % self.status_code)


# --- Unsplash --------------------------------------------------------------
def test_unsplash_without_key(data_dir):
    config.set_key("unsplash_key", "")
    with pytest.raises(RuntimeError, match="API key"):
        sources.fetch_unsplash(True)


def test_unsplash_invalid_key(data_dir, monkeypatch):
    config.set_key("unsplash_key", "invalida")

    def fake_get(*a, **k):
        return FakeResponse(401)

    monkeypatch.setattr(sources, "_http_get", fake_get)
    with pytest.raises(RuntimeError, match="inválida"):
        sources.fetch_unsplash(True)


# --- Bing ------------------------------------------------------------------
def test_parse_bing_images():
    payload = {"images": [{"url": "/th?id=OHR.A_1920x1080.jpg"}]}
    assert sources.parse_bing_images(payload) == [
        "https://www.bing.com/th?id=OHR.A_1920x1080.jpg"
    ]
    assert sources.parse_bing_images({}) == []


def test_bing_returns_dark_and_tries_uhd(data_dir, monkeypatch):
    config.set_key("resolution", "high")
    dark = img((5, 5, 5))
    calls = []

    def fake_get(url, *a, **k):
        calls.append(url)
        if "HPImageArchive" in url:
            return FakeResponse(
                payload={"images": [{"url": "/th?id=OHR.A_1920x1080.jpg"}]}
            )
        if "UHD" in url:
            raise sources.requests.RequestException("sem 4K")
        return FakeResponse(content=dark)

    monkeypatch.setattr(sources, "_http_get", fake_get)
    data = sources.fetch_bing(True)
    assert data == dark
    assert any("UHD" in u for u in calls)


def test_bing_picks_matching_tone(monkeypatch):
    light = img((250, 250, 250))
    dark = img((5, 5, 5))

    def fake_get(url, *a, **k):
        if "HPImageArchive" in url:
            return FakeResponse(
                payload={
                    "images": [
                        {"url": "/th?id=LIGHT_1920x1080.jpg"},
                        {"url": "/th?id=DARK_1920x1080.jpg"},
                    ]
                }
            )
        if "LIGHT" in url:
            return FakeResponse(content=light)
        return FakeResponse(content=dark)

    monkeypatch.setattr(sources, "_http_get", fake_get)
    assert sources.fetch_bing(True) == dark
    assert sources.fetch_bing(False) == light


# --- Wallhaven -------------------------------------------------------------
def test_wallhaven_fetches_dark(monkeypatch):
    dark = img((8, 8, 8))

    def fake_get(url, *a, **k):
        if "api/v1/search" in url:
            return FakeResponse(
                payload={
                    "data": [
                        {
                            "path": "https://w/full.jpg",
                            "thumbs": {"large": "https://w/thumb.jpg"},
                        }
                    ]
                }
            )
        return FakeResponse(content=dark)

    monkeypatch.setattr(sources, "_http_get", fake_get)
    assert sources.fetch_wallhaven(True) == dark


def test_wallhaven_color_filter_fallback(monkeypatch):
    dark = img((8, 8, 8))
    searches = []

    def fake_get(url, *a, **k):
        if "api/v1/search" in url:
            params = k.get("params") or {}
            searches.append(params)
            if "colors" in params:
                return FakeResponse(payload={"data": []})
            return FakeResponse(
                payload={
                    "data": [
                        {
                            "path": "https://w/full.jpg",
                            "thumbs": {"large": "https://w/thumb.jpg"},
                        }
                    ]
                }
            )
        return FakeResponse(content=dark)

    monkeypatch.setattr(sources, "_http_get", fake_get)
    assert sources.fetch_wallhaven(True) == dark
    assert any("colors" in p for p in searches)
    assert any("colors" not in p for p in searches)


def test_wallhaven_wrong_tone_raises(monkeypatch):
    light = img((250, 250, 250))

    def fake_get(url, *a, **k):
        if "api/v1/search" in url:
            return FakeResponse(
                payload={
                    "data": [
                        {
                            "path": "https://w/full.jpg",
                            "thumbs": {"large": "https://w/thumb.jpg"},
                        }
                    ]
                }
            )
        return FakeResponse(content=light)

    monkeypatch.setattr(sources, "_http_get", fake_get)
    with pytest.raises(RuntimeError, match="tom"):
        sources.fetch_wallhaven(True)


# --- resolution -------------------------------------------------------------
def test_unsplash_requests_target_width(data_dir, monkeypatch):
    config.set_key("unsplash_key", "k")
    config.set_key("resolution", "high")
    downloads = []

    def fake_get(url, *a, **k):
        if "api.unsplash.com" in url:
            return FakeResponse(
                payload={"results": [{"urls": {"raw": "https://img.example/raw.jpg"}}]}
            )
        downloads.append(url)
        return FakeResponse(content=img((5, 5, 5)))

    monkeypatch.setattr(sources, "_http_get", fake_get)
    sources.fetch_unsplash(True)
    assert downloads
    assert "w=3840" in downloads[0]


def test_wallhaven_uses_resolution_bucket(data_dir, monkeypatch):
    config.set_key("resolution", "low")
    seen = []

    def fake_get(url, *a, **k):
        if "api/v1/search" in url:
            seen.append(k.get("params") or {})
            return FakeResponse(
                payload={
                    "data": [
                        {
                            "path": "https://w/full.jpg",
                            "thumbs": {"large": "https://w/thumb.jpg"},
                        }
                    ]
                }
            )
        return FakeResponse(content=img((8, 8, 8)))

    monkeypatch.setattr(sources, "_http_get", fake_get)
    assert sources.fetch_wallhaven(True) == img((8, 8, 8))
    assert seen[0]["atleast"] == "1920x1080"


def test_bing_low_skips_uhd(data_dir, monkeypatch):
    config.set_key("resolution", "low")
    calls = []

    def fake_get(url, *a, **k):
        calls.append(url)
        if "HPImageArchive" in url:
            return FakeResponse(
                payload={"images": [{"url": "/th?id=OHR.A_1920x1080.jpg"}]}
            )
        return FakeResponse(content=img((5, 5, 5)))

    monkeypatch.setattr(sources, "_http_get", fake_get)
    sources.fetch_bing(True)
    assert not any("UHD" in u for u in calls)


def test_bing_high_tries_uhd(data_dir, monkeypatch):
    config.set_key("resolution", "high")
    calls = []

    def fake_get(url, *a, **k):
        calls.append(url)
        if "HPImageArchive" in url:
            return FakeResponse(
                payload={"images": [{"url": "/th?id=OHR.A_1920x1080.jpg"}]}
            )
        return FakeResponse(content=img((5, 5, 5)))

    monkeypatch.setattr(sources, "_http_get", fake_get)
    sources.fetch_bing(True)
    assert any("UHD" in u for u in calls)


# --- Local folder -----------------------------------------------------------
def test_local_without_folder_raises(data_dir):
    config.set_key("local_folder", "")
    with pytest.raises(RuntimeError, match="pasta local"):
        sources.fetch_local(True)


def test_local_picks_image_of_the_right_tone(data_dir, tmp_path):
    folder = tmp_path / "collection"
    folder.mkdir()
    dark = local_png((8, 8, 8))
    light = local_png((250, 250, 250))
    (folder / "dark.png").write_bytes(dark)
    (folder / "light.png").write_bytes(light)
    config.set_key("local_folder", str(folder))

    assert sources.fetch_local(True) == dark
    assert sources.fetch_local(False) == light


def test_local_includes_subfolders(data_dir, tmp_path):
    folder = tmp_path / "collection"
    nested = folder / "holidays" / "2026"
    nested.mkdir(parents=True)
    dark = local_png((10, 10, 10))
    (nested / "photo.png").write_bytes(dark)
    config.set_key("local_folder", str(folder))

    assert sources.fetch_local(True) == dark


def test_local_skips_duplicates_and_small_images(data_dir, tmp_path):
    folder = tmp_path / "collection"
    folder.mkdir()
    repeated = local_png((8, 8, 8))
    small = local_png((5, 5, 5), size=(320, 180))
    (folder / "repeated.png").write_bytes(repeated)
    (folder / "small.png").write_bytes(small)
    config.set_key("local_folder", str(folder))
    history.add(repeated, "local")

    with pytest.raises(RuntimeError, match="tom"):
        sources.fetch_local(True)


def test_local_invalid_folder_raises(data_dir, tmp_path):
    config.set_key("local_folder", str(tmp_path / "does-not-exist"))
    with pytest.raises(RuntimeError, match="inválida"):
        sources.fetch_local(True)
