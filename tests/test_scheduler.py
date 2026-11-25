import threading
import time

from wallpaper_changer import app, config


def test_scheduler_fires_and_stops(data_dir, monkeypatch):
    calls = []
    monkeypatch.setitem(app.INTERVALS, "15m", 1)
    monkeypatch.setattr(
        app, "change_wallpaper", lambda **k: calls.append(1) or (True, "")
    )
    config.set_key("paused", False)
    config.set_key("interval", "15m")

    threading.Thread(target=app.scheduler_loop, daemon=True).start()
    time.sleep(3.5)
    assert calls, "the scheduler should have fired"

    try:
        config.set_key("interval", "startup_only")
        app._wake.set()
        time.sleep(0.5)
        n = len(calls)
        time.sleep(2)
        assert len(calls) == n, "should not fire in 'startup only' mode"
    finally:
        app._wake.set()


def test_scheduler_does_not_fire_when_paused(data_dir, monkeypatch):
    calls = []
    monkeypatch.setitem(app.INTERVALS, "5m", 1)
    monkeypatch.setattr(
        app, "change_wallpaper", lambda **k: calls.append(1) or (True, "")
    )
    config.set_key("paused", True)
    config.set_key("interval", "5m")

    threaded = False
    try:
        threading.Thread(target=app.scheduler_loop, daemon=True).start()
        threaded = True
        time.sleep(3)
        assert not calls, "the scheduler must not change the wallpaper when paused"
    finally:
        config.set_key("interval", "startup_only")
        config.set_key("paused", False)
        app._wake.set()
        if threaded:
            time.sleep(0.3)
