import threading
import time

from wallpaper_changer import app, config


def test_scheduler_fires_and_stops(data_dir, monkeypatch):
    calls = []
    monkeypatch.setitem(app.INTERVALS, "15m", 1)
    monkeypatch.setattr(
        app, "change_wallpaper", lambda: calls.append(1) or (True, "")
    )
    config.set_key("interval", "15m")

    t = threading.Thread(target=app.scheduler_loop, daemon=True)
    t.start()
    time.sleep(3.5)
    assert calls, "o agendador devia ter disparado"

    try:
        config.set_key("interval", "startup_only")
        app._wake.set()
        time.sleep(0.5)
        n = len(calls)
        time.sleep(2)
        assert len(calls) == n, "não devia disparar em 'apenas ao iniciar'"
    finally:
        # deixa a thread parada para não interferir com outros testes
        app._wake.set()
