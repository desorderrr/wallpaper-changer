import io

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
        last_change=None,
        last_tone=None,
        last_source=None,
        last_path=None,
        last_error=None,
    )
    yield
    app.state.update(
        last_change=None,
        last_tone=None,
        last_source=None,
        last_path=None,
        last_error=None,
    )


@pytest.fixture()
def bing_only(data_dir, monkeypatch):
    config.set_key("theme_mode", "dark")
    config.set_key("use_unsplash", False)
    config.set_key("use_bing", True)
    config.set_key("use_wallhaven", False)
    config.set_key("paused", False)
    applied = []
    monkeypatch.setattr(app.platform, "set_wallpaper", applied.append)
    return applied


def test_dark_flow_end_to_end(bing_only, monkeypatch):
    monkeypatch.setattr(
        app.sources, "fetch_bing", lambda want_dark=True: img((8, 8, 8))
    )
    ok, msg = app.change_wallpaper()

    assert ok
    assert "escuro" in msg
    assert bing_only and bing_only[0].exists()
    assert app.state["last_source"] == "bing"
    assert app.state["last_tone"] == "escuro"
    assert app.state["last_path"] == str(bing_only[0])


def test_light_flow_end_to_end(bing_only, monkeypatch):
    config.set_key("theme_mode", "light")
    monkeypatch.setattr(
        app.sources, "fetch_bing", lambda want_dark=True: img((248, 248, 248))
    )
    ok, msg = app.change_wallpaper()
    assert ok and "claro" in msg
    assert bing_only


def test_tone_mismatch_fails_gracefully(bing_only, monkeypatch):
    monkeypatch.setattr(
        app.sources, "fetch_bing", lambda want_dark=True: img((250, 250, 250))
    )
    ok, msg = app.change_wallpaper()
    assert not ok
    assert "Não consegui" in msg
    assert not bing_only


def test_no_sources_enabled(data_dir):
    config.set_key("use_unsplash", False)
    config.set_key("use_bing", False)
    config.set_key("use_wallhaven", False)
    ok, msg = app.change_wallpaper()
    assert not ok
    assert "Nenhuma fonte" in msg


def test_only_wallhaven_selected(data_dir, monkeypatch):
    config.set_key("theme_mode", "dark")
    config.set_key("use_unsplash", False)
    config.set_key("use_bing", False)
    config.set_key("use_wallhaven", True)
    applied = []
    monkeypatch.setattr(app.platform, "set_wallpaper", applied.append)
    monkeypatch.setattr(
        app.sources, "fetch_wallhaven", lambda want_dark=True: img((9, 9, 9))
    )
    ok, msg = app.change_wallpaper()
    assert ok and "Wallhaven" in msg
    assert applied


def test_paused_blocks_automatic_but_not_manual(bing_only, monkeypatch):
    config.set_key("paused", True)
    monkeypatch.setattr(
        app.sources, "fetch_bing", lambda want_dark=True: img((8, 8, 8))
    )

    ok, msg = app.change_wallpaper()
    assert not ok
    assert "pausa" in msg.lower()
    assert not bing_only

    ok2, _ = app.change_wallpaper(manual=True)
    assert ok2
    assert bing_only


def test_change_lock(data_dir):
    assert app._change_lock.acquire(blocking=False)
    try:
        ok, msg = app.change_wallpaper()
        assert not ok
        assert "curso" in msg
    finally:
        app._change_lock.release()


def test_repeated_wallpaper_is_blocked(bing_only, monkeypatch):
    monkeypatch.setattr(
        app.sources, "fetch_bing", lambda want_dark=True: img((8, 8, 8))
    )
    ok1, _ = app.change_wallpaper()
    assert ok1

    ok2, msg = app.change_wallpaper()
    assert not ok2
    assert "repet" in msg.lower()


def test_obtain_candidate_and_apply(bing_only, monkeypatch):
    monkeypatch.setattr(
        app.sources, "fetch_bing", lambda want_dark=True: img((10, 10, 10))
    )

    ok, _msg, path = app.obtain_candidate()
    assert ok
    assert path and path.endswith(".jpg")
    from pathlib import Path

    assert Path(path).exists()

    ok2, _msg2 = app.apply_file(path)
    assert ok2
    assert bing_only
    assert app.state["last_path"] == path


def test_obtain_candidate_skips_duplicates(bing_only, monkeypatch):
    data = img((10, 10, 10))
    monkeypatch.setattr(app.sources, "fetch_bing", lambda want_dark=True: data)

    ok1, _, path1 = app.obtain_candidate()
    assert ok1 and path1

    # mark the image as used and request another suggestion
    app.history.add(data, "bing")
    ok2, msg2, path2 = app.obtain_candidate()
    assert not ok2 and path2 is None
    assert "usado" in msg2


def test_failed_apply_removes_orphan_file(bing_only, monkeypatch):
    monkeypatch.setattr(
        app.sources, "fetch_bing", lambda want_dark=True: img((8, 8, 8))
    )

    def fail(_path):
        raise OSError("failed to apply")

    monkeypatch.setattr(app.platform, "set_wallpaper", fail)
    ok, _msg = app.change_wallpaper()
    assert not ok
    assert len(list(config.image_dir().glob("*.jpg"))) == 0


def test_obtain_candidate_no_sources(data_dir):
    config.set_key("use_unsplash", False)
    config.set_key("use_bing", False)
    config.set_key("use_wallhaven", False)
    ok, _msg, path = app.obtain_candidate()
    assert not ok and path is None


def test_list_recent_images_order(data_dir):
    a = config.image_dir() / "unsplash_20260101_000000_000001.jpg"
    a.write_bytes(b"x")
    b = config.image_dir() / "bing_20260102_000000_000002.jpg"
    b.write_bytes(b"x")
    import os

    os.utime(a, (1000, 1000))
    os.utime(b, (2000, 2000))
    result = app.list_recent_images()
    assert result[0].name.startswith("bing")


def test_cleanup_keeps_only_limit(data_dir):
    config.set_key("keep", 3)
    for i in range(6):
        (config.image_dir() / ("x%d.jpg" % i)).write_bytes(b"x")
    app.cleanup_images()
    assert len(list(config.image_dir().glob("*.jpg"))) == 3


def test_save_image_downscales_to_resolution(data_dir, monkeypatch):
    from wallpaper_changer import resolution

    monkeypatch.setattr(resolution, "_screen_width", 1920)
    config.set_key("resolution", "low")
    big = io.BytesIO()
    Image.new("RGB", (3840, 2160), (5, 5, 5)).save(big, "PNG")

    path = app.save_image(big.getvalue(), "downscale")
    with Image.open(path) as saved:
        assert saved.size == (1920, 1080)


def test_save_image_does_not_upscale(data_dir, monkeypatch):
    from wallpaper_changer import resolution

    monkeypatch.setattr(resolution, "_screen_width", 3840)
    config.set_key("resolution", "high")
    small = io.BytesIO()
    Image.new("RGB", (1280, 720), (5, 5, 5)).save(small, "PNG")

    path = app.save_image(small.getvalue(), "keep")
    with Image.open(path) as saved:
        assert saved.size == (1280, 720)


def test_status_text_contains_state(bing_only):
    config.set_key("theme_mode", "dark")
    assert "escuro" in app.status_text()
    config.set_key("paused", True)
    assert "pausa" in app.status_text()


def test_menu_builds(data_dir):
    menu = app.build_menu()
    items = list(menu)
    assert len(items) >= 9
