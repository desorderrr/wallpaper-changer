import pytest

from wallpaper_changer import config, sources


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


def test_parse_bing_images():
    payload = {"images": [{"url": "/th?id=OHR.A_1920x1080.jpg"}]}
    assert sources.parse_bing_images(payload) == [
        "https://www.bing.com/th?id=OHR.A_1920x1080.jpg"
    ]
    assert sources.parse_bing_images({}) == []


def test_bing_fetch_uhd_fallback(monkeypatch):
    calls = []

    def fake_get(url, *a, **k):
        calls.append(url)
        if "HPImageArchive" in url:
            return FakeResponse(
                payload={"images": [{"url": "/th?id=OHR.A_1920x1080.jpg"}]}
            )
        if "UHD" in url:
            raise sources.requests.RequestException("sem 4K")
        return FakeResponse(content=b"JPEGDATA")

    monkeypatch.setattr(sources.requests, "get", fake_get)
    data = sources.fetch_bing()
    assert data == b"JPEGDATA"
    assert any("UHD" in u for u in calls)
    assert any("1920x1080" in u for u in calls)
