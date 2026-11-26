import os
import sys

import pytest

if os.environ.get("WPC_SKIP_UI_TESTS"):
    pytest.skip(
        "UI disabled in this environment (WPC_SKIP_UI_TESTS=1)",
        allow_module_level=True,
    )

customtkinter = pytest.importorskip("customtkinter")
pytest.importorskip("tkinter")


def _has_display() -> bool:
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


pytestmark = pytest.mark.skipif(not _has_display(), reason="no graphical display")


@pytest.fixture(scope="module")
def tk_root():
    """One Tk root per module: a second init can fail on broken Tcl installs."""
    try:
        root = customtkinter.CTk()
        root.withdraw()
        root.update_idletasks()
    except Exception as e:  # noqa: BLE001 - a broken Tk install is not a bug here
        pytest.skip("Tk is not usable on this runner: %r" % e)
    yield root
    try:
        root.destroy()
    except Exception:  # noqa: BLE001 - best-effort cleanup
        pass


def test_settings_window_builds_and_saves(data_dir, tk_root):
    closed = []
    saved = {}

    def on_save(values):
        saved.update(values)

    from wallpaper_changer.ui import SettingsWindow

    win = SettingsWindow(
        tk_root,
        on_save=on_save,
        on_close=lambda: closed.append(1),
        change_wallpaper=lambda manual: (True, "ok"),
        status_text=lambda: "Tema atual: escuro",
        open_folder=lambda: None,
        preview_candidate=lambda: (True, "ok", None),
        apply_image=lambda p: (True, "ok"),
        list_recent=list,
        forget_history=lambda: None,
    )
    tk_root.update_idletasks()
    assert win.winfo_exists()
    assert "Defini" in win.title()
    assert win.var_interval.get() in win._label_to_value
    assert hasattr(win, "var_wallhaven")
    assert hasattr(win, "var_paused")
    assert hasattr(win, "var_res")
    assert hasattr(win, "var_local")
    assert hasattr(win, "var_folder")
    assert win.tabs.tab("Pré-visualizar") is not None

    # pick an interval by label and make sure the id is what gets saved
    win.var_interval.set("Cada 1 hora")
    win._save()
    assert saved
    assert saved["interval"] == "1h"
    assert saved["theme_mode"] in ("auto", "dark", "light")
    assert saved["resolution"] in ("auto", "high", "low")
    assert saved["use_local"] is False
    assert saved["local_folder"] == ""
    assert isinstance(saved["queries_dark"], list)
    assert isinstance(saved["use_wallhaven"], bool)
    assert isinstance(saved["paused"], bool)
    assert closed == [1]


def test_local_source_requires_a_folder(data_dir, tk_root):
    saved = {}
    from wallpaper_changer.ui import SettingsWindow

    win = SettingsWindow(
        tk_root,
        on_save=lambda values: saved.update(values) or None,
        on_close=lambda: None,
        change_wallpaper=lambda manual: (True, "ok"),
        status_text=lambda: "",
        open_folder=lambda: None,
        preview_candidate=lambda: (True, "ok", None),
        apply_image=lambda p: (True, "ok"),
        list_recent=list,
        forget_history=lambda: None,
    )
    win.var_local.set(True)
    win.var_folder.set("")
    win._save()

    assert not saved  # save was refused, the window stays open
    assert "pasta" in win.status_label.cget("text").lower()


def test_settings_window_in_english(data_dir, tk_root, monkeypatch):
    """Labels and saved values must not depend on the active language."""
    from wallpaper_changer import i18n

    monkeypatch.setattr(i18n, "_current", "en")
    saved = {}

    from wallpaper_changer.ui import SettingsWindow

    win = SettingsWindow(
        tk_root,
        on_save=lambda values: saved.update(values) or None,
        on_close=lambda: None,
        change_wallpaper=lambda manual: (True, "ok"),
        status_text=lambda: "Current theme: dark",
        open_folder=lambda: None,
        preview_candidate=lambda: (True, "ok", None),
        apply_image=lambda p: (True, "ok"),
        list_recent=list,
        forget_history=lambda: None,
    )
    tk_root.update_idletasks()
    assert "Settings" in win.title()
    assert win.tabs.tab("General") is not None
    assert win.var_interval.get() in win._label_to_value

    win.var_interval.set("Every hour")
    win.var_lang.set("English")
    win.var_res.set("High (4K)")
    win._save()
    assert saved["interval"] == "1h"
    assert saved["language"] == "en"
    assert saved["resolution"] == "high"
    assert saved["theme_mode"] in ("auto", "dark", "light")
