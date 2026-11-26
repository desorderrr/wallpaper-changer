# -*- coding: utf-8 -*-
"""Tests for the resolution setting and screen detection."""

from __future__ import annotations

import pytest

from wallpaper_changer import config, resolution


@pytest.fixture(autouse=True)
def reset_screen_cache():
    resolution.reset_cache()
    yield
    resolution.reset_cache()


def test_target_width_modes(data_dir, monkeypatch):
    monkeypatch.setattr(resolution, "_screen_width", 3000)
    config.set_key("resolution", "auto")
    assert resolution.target_width() == 3840
    config.set_key("resolution", "high")
    assert resolution.target_width() == 3840
    config.set_key("resolution", "low")
    assert resolution.target_width() == 1920


def test_auto_buckets(data_dir, monkeypatch):
    config.set_key("resolution", "auto")
    cases = {1366: 1920, 1600: 1920, 1920: 1920, 2560: 2560, 3000: 3840, 5120: 3840}
    for screen, expected in cases.items():
        monkeypatch.setattr(resolution, "_screen_width", screen)
        assert resolution.target_width() == expected


def test_screen_width_falls_back_to_default(data_dir, monkeypatch):
    monkeypatch.setattr(resolution, "_screen_width", None)
    monkeypatch.setattr(resolution.sys, "platform", "linux")
    monkeypatch.setattr(resolution, "_linux_width", lambda: 0)
    assert resolution.screen_width() == resolution.DEFAULT_WIDTH


def test_screen_width_detects_linux_xrandr(data_dir, monkeypatch):
    monkeypatch.setattr(resolution, "_screen_width", None)
    monkeypatch.setattr(resolution.sys, "platform", "linux")
    monkeypatch.setattr(resolution, "_linux_width", lambda: 2560)
    assert resolution.screen_width() == 2560


def test_height_and_quality():
    assert resolution.height_for(1920) == 1080
    assert resolution.height_for(2560) == 1440
    assert resolution.height_for(3840) == 2160
    assert resolution.download_quality(1920) < resolution.download_quality(3840)


def test_invalid_resolution_is_normalised(data_dir):
    config.settings_file().write_text('{"resolution": "8k"}', encoding="utf-8")
    config.load_settings()
    assert config.get("resolution") == "auto"
