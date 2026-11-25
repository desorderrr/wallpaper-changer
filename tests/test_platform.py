import sys

import pytest

from wallpaper_changer import platform as platform_mod


def test_platform_selection():
    expected = {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")
    assert platform_mod.platform.name == expected


def test_theme_is_light_prefers_apps_mode():
    from wallpaper_changer.platform.base import theme_is_light

    # "app mode" takes priority over "Windows mode"
    assert theme_is_light(1, 0) is True
    assert theme_is_light(0, 1) is False
    assert theme_is_light(1, 1) is True
    assert theme_is_light(0, 0) is False
    # fallback when the apps key is missing
    assert theme_is_light(None, 1) is True
    assert theme_is_light(None, 0) is False
    assert theme_is_light(None, None) is True


# --- Linux (pure functions) ------------------------------------------------
def test_parse_color_scheme():
    from wallpaper_changer.platform.linux import parse_color_scheme

    assert parse_color_scheme("'prefer-dark'") is False
    assert parse_color_scheme("'prefer-light'") is True
    assert parse_color_scheme("'default'") is None


def test_parse_gtk_theme():
    from wallpaper_changer.platform.linux import parse_gtk_theme

    assert parse_gtk_theme("'Adwaita'") is True
    assert parse_gtk_theme("'Adwaita-dark'") is False
    assert parse_gtk_theme("") is None


def test_parse_kde_colorscheme():
    from wallpaper_changer.platform.linux import parse_kde_colorscheme

    assert parse_kde_colorscheme("[General]\nColorScheme=BreezeDark\n") is False
    assert parse_kde_colorscheme("[General]\nColorScheme=BreezeLight\n") is True
    assert parse_kde_colorscheme("[General]\n") is None


# --- macOS (pure function) --------------------------------------------------
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_macos_parse_defaults():
    from wallpaper_changer.platform.macos import parse_defaults

    assert parse_defaults("Dark\n", 0) is False
    assert parse_defaults("", 1) is True


# --- Windows (real registry, read-only) -----------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_theme_bool():
    assert isinstance(platform_mod.platform.is_light_theme(), bool)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_startup_roundtrip():
    p = platform_mod.platform
    was = p.startup_enabled()
    try:
        assert p.set_startup(True)
        assert p.startup_enabled()
        assert p.set_startup(False)
        assert not p.startup_enabled()
    finally:
        p.set_startup(was)
