import io

import pytest
from PIL import Image

from wallpaper_changer import config, sources


def img(color):
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
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

    monkeypatch.setattr(sources.requests, "get", fake_get)
    with pytest.raises(RuntimeError, match="inválida"):
        sources.fetch_unsplash(True)


# --- Bing ------------------------------------------------------------------
def test_parse_bing_images():
    payload = {"images": [{"url": "/th?id=OHR.A_1920x1080.jpg"}]}
    assert sources.parse_bing_images(payload) == [
        "https://www.bing.com/th?id=OHR.A_1920x1080.jpg"
    ]
    assert sources.parse_bing_images({}) == []


def test_bing_returns_dark_and_tries_uhd(monkeypatch):
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

    monkeypatch.setattr(sources.requests, "get", fake_get)
    data = sources.fetch_bing(True)
    assert data == dark
    assert any("UHD" in u for u in calls)


def test_bing_picks_matching_tone(monkeypatch):
    light = img((250, 250, 250))
    dark = img((5, 5, 5))

    def fake_get(url, *a, **k):
        if "HPImageArchive" in url:
            return FakeResponse(payload={"images": [
                {"url": "/th?id=LIGHT_1920x1080.jpg"},
                {"url": "/th?id=DARK_1920x1080.jpg"},
            ]})
        if "LIGHT" in url:
            return FakeResponse(content=light)
        return FakeResponse(content=dark)

    monkeypatch.setattr(sources.requests, "get", fake_get)
    assert sources.fetch_bing(True) == dark
    assert sources.fetch_bing(False) == light


# --- Wallhaven -------------------------------------------------------------
def test_wallhaven_fetches_dark(monkeypatch):
    dark = img((8, 8, 8))

    def fake_get(url, *a, **k):
        if "api/v1/search" in url:
            return FakeResponse(payload={"data": [{
                "path": "https://w/full.jpg",
                "thumbs": {"large": "https://w/thumb.jpg"},
            }]})
        return FakeResponse(content=dark)

    monkeypatch.setattr(sources.requests, "get", fake_get)
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
            return FakeResponse(payload={"data": [{
                "path": "https://w/full.jpg",
                "thumbs": {"large": "https://w/thumb.jpg"},
            }]})
        return FakeResponse(content=dark)

    monkeypatch.setattr(sources.requests, "get", fake_get)
    assert sources.fetch_wallhaven(True) == dark
    assert any("colors" in p for p in searches)
    assert any("colors" not in p for p in searches)


def test_wallhaven_wrong_tone_raises(monkeypatch):
    light = img((250, 250, 250))

    def fake_get(url, *a, **k):
        if "api/v1/search" in url:
            return FakeResponse(payload={"data": [{
                "path": "https://w/full.jpg",
                "thumbs": {"large": "https://w/thumb.jpg"},
            }]})
        return FakeResponse(content=light)

    monkeypatch.setattr(sources.requests, "get", fake_get)
    with pytest.raises(RuntimeError, match="tom"):
        sources.fetch_wallhaven(True)
