import io
from pathlib import Path

import pytest
from PIL import Image

from wallpaper_changer import app, config


def img(color):
    b = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(b, "PNG")
    return b.getvalue()


@pytest.fixture(autouse=True)
def clean_state():
    app.state.update(
        last_change=None, last_tone=None, last_source=None, last_error=None
    )
    yield
    app.state.update(
        last_change=None, last_tone=None, last_source=None, last_error=None
    )


def test_dark_flow_end_to_end(data_dir, monkeypatch):
    config.set_key("theme_mode", "dark")
    config.set_key("use_unsplash", False)
    config.set_key("use_bing", True)
    monkeypatch.setattr(app.sources, "fetch_bing", lambda: img((8, 8, 8)))
    applied = []
    monkeypatch.setattr(app.platform, "set_wallpaper", lambda p: applied.append(p))

    ok, msg = app.change_wallpaper()

    assert ok
    assert "escuro" in msg
    assert applied and Path(applied[0]).exists()
    assert app.state["last_source"] == "bing"
    assert app.state["last_tone"] == "escuro"


def test_light_flow_end_to_end(data_dir, monkeypatch):
    config.set_key("theme_mode", "light")
    config.set_key("use_unsplash", False)
    monkeypatch.setattr(app.sources, "fetch_bing", lambda: img((248, 248, 248)))
    applied = []
    monkeypatch.setattr(app.platform, "set_wallpaper", lambda p: applied.append(p))

    ok, msg = app.change_wallpaper()
    assert ok and "claro" in msg
    assert applied


def test_tone_mismatch_fails_gracefully(data_dir, monkeypatch):
    config.set_key("theme_mode", "dark")
    config.set_key("use_unsplash", False)
    monkeypatch.setattr(app.sources, "fetch_bing", lambda: img((250, 250, 250)))
    applied = []
    monkeypatch.setattr(app.platform, "set_wallpaper", lambda p: applied.append(p))

    ok, msg = app.change_wallpaper()
    assert not ok
    assert "Não consegui" in msg
    assert not applied


def test_no_sources_enabled(data_dir):
    config.set_key("use_unsplash", False)
    config.set_key("use_bing", False)
    ok, msg = app.change_wallpaper()
    assert not ok
    assert "Nenhuma fonte" in msg


def test_change_lock(data_dir):
    assert app._change_lock.acquire(blocking=False)
    try:
        ok, msg = app.change_wallpaper()
        assert not ok
        assert "curso" in msg
    finally:
        app._change_lock.release()


def test_cleanup_keeps_only_limit(data_dir):
    config.set_key("keep", 3)
    for i in range(6):
        (config.image_dir() / ("x%d.jpg" % i)).write_bytes(b"x")
    app.cleanup_images()
    assert len(list(config.image_dir().glob("*.jpg"))) == 3


def test_status_text_contains_theme(data_dir):
    config.set_key("theme_mode", "dark")
    assert "escuro" in app.status_text()
    config.set_key("theme_mode", "light")
    assert "claro" in app.status_text()


def test_menu_builds(data_dir):
    menu = app.build_menu()
    items = list(menu)
    assert len(items) >= 8
