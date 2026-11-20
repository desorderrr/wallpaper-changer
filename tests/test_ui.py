import os
import sys

import pytest

if os.environ.get("WPC_SKIP_UI_TESTS"):
    pytest.skip(
        "UI desativada neste ambiente (WPC_SKIP_UI_TESTS=1)",
        allow_module_level=True,
    )

customtkinter = pytest.importorskip("customtkinter")
pytest.importorskip("tkinter")


def _has_display() -> bool:
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


pytestmark = pytest.mark.skipif(not _has_display(), reason="sem display gráfico")


def test_settings_window_builds_and_saves(data_dir):
    root = customtkinter.CTk()
    root.withdraw()
    closed = []
    saved = {}

    def on_save(values):
        saved.update(values)
        return None

    try:
        from wallpaper_changer.ui import SettingsWindow

        win = SettingsWindow(
            root,
            on_save=on_save,
            on_close=lambda: closed.append(1),
            change_wallpaper=lambda manual: (True, "ok"),
            status_text=lambda: "Tema atual: escuro",
            open_folder=lambda: None,
            preview_candidate=lambda: (True, "ok", None),
            apply_image=lambda p: (True, "ok"),
            list_recent=lambda: [],
        )
        root.update_idletasks()
        assert win.winfo_exists()
        assert "Defini" in win.title()
        assert win.var_interval.get() in win._label_to_value
        assert hasattr(win, "var_wallhaven")
        assert hasattr(win, "var_paused")
        assert win.tabs.tab("Pré-visualizar") is not None

        # escolher um intervalo pelo nome e garantir que grava o id correto
        win.var_interval.set("Cada 1 hora")
        win._save()
        assert saved
        assert saved["interval"] == "1h"
        assert saved["theme_mode"] in ("auto", "dark", "light")
        assert isinstance(saved["queries_dark"], list)
        assert isinstance(saved["use_wallhaven"], bool)
        assert isinstance(saved["paused"], bool)
        assert closed == [1]
    finally:
        try:
            root.destroy()
        except Exception:
            pass
