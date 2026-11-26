# -*- coding: utf-8 -*-
"""WallpaperChanger — tray icon, scheduler and settings window."""

from __future__ import annotations

import ctypes
import io
import os
import queue
import random
import socket
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime

from PIL import Image

from . import config, history, i18n, resolution, sources, tone
from .assets import make_icon_image
from .config import APP_NAME, APP_VERSION, INTERVALS, get
from .i18n import t
from .platform import platform

_pystray = None


def _get_pystray():
    """Import pystray, with an X11 backend fallback on Linux.

    On some Linux setups `gi` exists but the GTK3 typelibs are missing, so
    pystray fails before trying the Xorg backend. In that case we force
    PYSTRAY_BACKEND=xorg (requires python-xlib).
    """
    global _pystray
    if _pystray is not None:
        return _pystray
    try:
        import pystray as mod
    except Exception:
        if not sys.platform.startswith("linux"):
            raise
        os.environ.setdefault("PYSTRAY_BACKEND", "xorg")
        try:
            import pystray as mod
        except Exception as e:
            raise RuntimeError(
                t(
                    "Não consegui iniciar a bandeja do sistema. No Linux instala "
                    "python-xlib (pip) ou python3-gi + gir1.2-gtk-3.0."
                )
            ) from e
    _pystray = mod
    return mod


# ---------------------------------------------------------------------------
# Runtime state (shown in the UI)
# ---------------------------------------------------------------------------
state: dict = {
    "last_change": None,
    "last_tone": None,
    "last_source": None,
    "last_path": None,
    "last_error": None,
}

_state_lock = threading.RLock()  # read in the UI, written by workers
_change_lock = threading.Lock()
_wake = threading.Event()  # settings changed -> reschedule
_ui_queue: queue.Queue[str] | None = None
_tray_icon = None
_settings_win = None
_instance_socket = None


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def effective_theme_is_dark() -> bool:
    mode = get("theme_mode")
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return not platform.is_light_theme()


def status_text() -> str:
    with _state_lock:
        snapshot = dict(state)
    tone_name = t("escuro") if effective_theme_is_dark() else t("claro")
    mode = {
        "auto": t("segue o sistema"),
        "dark": t("sempre escuro"),
        "light": t("sempre claro"),
    }.get(get("theme_mode"), t("segue o sistema"))
    parts = [t("Tema atual: %s (%s)") % (tone_name, mode)]
    if get("paused"):
        parts.append(t("mudanças automáticas em pausa"))
    if snapshot["last_source"]:
        src = {
            "unsplash": "Unsplash",
            "bing": "Bing",
            "wallhaven": "Wallhaven",
        }.get(snapshot["last_source"], snapshot["last_source"])
        parts.append(t("última fonte: %s") % src)
    if snapshot["last_change"]:
        parts.append(
            t("última troca: %s") % snapshot["last_change"].strftime("%d/%m %H:%M")
        )
    return " · ".join(parts)


def save_image(img_bytes: bytes, prefix: str):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    # Never store more pixels than the screen needs (big Wallhaven/Bing files).
    target = resolution.target_width()
    if img.width > target:
        height = max(1, round(img.height * target / img.width))
        img = img.resize((target, height), Image.LANCZOS)
    path = config.image_dir() / (
        "%s_%s.jpg" % (prefix, datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    )
    img.save(path, "JPEG", quality=90)
    return path


def cleanup_images() -> None:
    keep = int(get("keep") or 20)
    try:
        files = sorted((p.stat().st_mtime, p) for p in config.image_dir().glob("*.jpg"))
        for _, old in files[: max(0, len(files) - keep)]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def _enabled_sources() -> list[tuple[str, str, object]]:
    """(id, name, fetch function) of the active sources, in random order."""
    entries: list[tuple[str, str, object]] = []
    if get("use_unsplash"):
        entries.append(("unsplash", "Unsplash", sources.fetch_unsplash))
    if get("use_wallhaven"):
        entries.append(("wallhaven", "Wallhaven", sources.fetch_wallhaven))
    if get("use_bing"):
        entries.append(("bing", "Bing", sources.fetch_bing))
    random.shuffle(entries)
    return entries


def change_wallpaper(manual: bool = False) -> tuple[bool, str]:
    """Change the wallpaper respecting the theme. Returns (success, message)."""
    if not _change_lock.acquire(blocking=False):
        return False, t("Já existe uma troca de wallpaper em curso.")
    try:
        return _do_change(manual=manual)
    finally:
        _change_lock.release()


def _do_change(manual: bool = False) -> tuple[bool, str]:
    if get("paused") and not manual:
        return False, t("Mudanças automáticas em pausa.")

    want_dark = effective_theme_is_dark()
    tone_name = "escuro" if want_dark else "claro"

    enabled = _enabled_sources()
    if not enabled:
        return False, t("Nenhuma fonte ativa. Ativa o Unsplash, o Bing ou o Wallhaven.")

    last_error = ""
    for src, name, fetch in enabled:
        try:
            data = fetch(want_dark)

            luma = tone.mean_luminance(data)
            config.log("Source %s: luma=%.0f (wanted %s)" % (name, luma, tone_name))
            if not tone.tone_matches(luma, want_dark):
                last_error = t("%s devolveu uma imagem com o tom errado") % name
                continue
            if history.is_duplicate(data):
                last_error = t("%s devolveu um wallpaper repetido") % name
                config.log("Duplicate from %s ignored" % name)
                continue

            path = save_image(data, src)
            try:
                platform.set_wallpaper(path)
            except Exception:
                # do not leave orphan files when applying fails
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            cleanup_images()
            history.add(data, src, path)
            with _state_lock:
                state.update(
                    last_change=datetime.now(),
                    last_tone=tone_name,
                    last_source=src,
                    last_path=str(path),
                    last_error=None,
                )
            config.log("Wallpaper %s applied: %s" % (tone_name, path))
            return True, t("Wallpaper %s aplicado (%s).") % (t(tone_name), name)
        except Exception as e:  # noqa: BLE001 - any source may fail
            last_error = "%s: %s" % (name, e)
            config.log("Error in %s: %r" % (name, e))

    msg = t("Não consegui obter uma imagem %s agora. %s") % (t(tone_name), last_error)

    # Offline fallback: reuse a saved wallpaper with the right tone.
    with _state_lock:
        current = state.get("last_path")
    fallback = history.pick_for_tone(want_dark, exclude=current)
    if fallback is not None:
        try:
            platform.set_wallpaper(fallback)
        except Exception as e:  # noqa: BLE001 - fall back to the error below
            config.log("Fallback failed: %r" % e)
        else:
            with _state_lock:
                state.update(
                    last_change=datetime.now(),
                    last_tone=tone_name,
                    last_source=_source_key(fallback),
                    last_path=str(fallback),
                    last_error=None,
                )
            config.log("Fallback: reused saved wallpaper %s" % fallback)
            return True, t(
                "Sem imagens novas — reutilizei um wallpaper %s guardado."
            ) % t(tone_name)

    with _state_lock:
        state["last_error"] = msg
    config.log(msg)
    return False, msg


def _source_key(path) -> str:
    """Extract the source from the filename (e.g. preview_unsplash_2026...)."""
    stem = path.stem
    stem = stem.removeprefix("preview_")
    return stem.split("_", 1)[0]


def obtain_candidate() -> tuple[bool, str, str | None]:
    """Fetch an image (without applying it) for the preview."""
    want_dark = effective_theme_is_dark()
    tone_name = "escuro" if want_dark else "claro"
    enabled = _enabled_sources()
    if not enabled:
        return (
            False,
            t("Nenhuma fonte ativa. Ativa o Unsplash, o Bing ou o Wallhaven."),
            None,
        )

    errors: list[str] = []
    for src, name, fetch in enabled:
        try:
            data = fetch(want_dark)
            if not tone.tone_matches(tone.mean_luminance(data), want_dark):
                errors.append(t("%s: tom errado") % name)
                continue
            if history.is_duplicate(data):
                errors.append(t("%s: wallpaper já usado") % name)
                config.log("Repeated suggestion from %s ignored" % name)
                continue
            path = save_image(data, "preview_" + src)
            return True, t("Sugestão do %s (tom %s).") % (name, t(tone_name)), str(path)
        except Exception as e:  # noqa: BLE001
            errors.append("%s: %s" % (name, e))
            config.log("Error in suggestion (%s): %r" % (name, e))
    return (
        False,
        t("Não consegui obter uma sugestão. %s") % "; ".join(errors[-2:]),
        None,
    )


def apply_file(path) -> tuple[bool, str]:
    """Apply an existing image file."""
    from pathlib import Path as _Path

    path = _Path(path)
    try:
        platform.set_wallpaper(path)
        cleanup_images()
        history.add_path(path, _source_key(path))
        tone_name = "escuro" if effective_theme_is_dark() else "claro"
        with _state_lock:
            state.update(
                last_change=datetime.now(),
                last_tone=tone_name,
                last_source=_source_key(path),
                last_path=str(path),
                last_error=None,
            )
        config.log("Wallpaper applied manually: %s" % path)
        return True, t("Wallpaper aplicado.")
    except Exception as e:  # noqa: BLE001
        config.log("Error applying %s: %r" % (path, e))
        return False, t("Não consegui aplicar o wallpaper: %s") % e


def list_recent_images(limit: int = 24) -> list:
    """Saved images (without perceptual duplicates), newest first."""
    try:
        files = sorted(
            config.image_dir().glob("*.jpg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return []

    unique: list = []
    seen: list[str] = []
    for path in files:
        ah = history.ahash_path(path)
        if ah:
            if any(history.is_similar_hash(ah, other) for other in seen):
                continue
            seen.append(ah)
        unique.append(path)
        if len(unique) >= limit:
            break
    return unique


def forget_history() -> None:
    """Forget used wallpapers (allows seeing them again)."""
    history.reset()
    config.log("Used wallpaper history forgotten")


# ---------------------------------------------------------------------------
# Scheduler + theme watcher
# ---------------------------------------------------------------------------
def scheduler_loop() -> None:
    while True:
        interval = get("interval")
        if interval == "startup_only" or interval not in INTERVALS:
            _wake.wait()
            _wake.clear()
            continue
        if _wake.wait(INTERVALS[interval]):
            _wake.clear()
            continue
        if get("paused"):
            config.log("Automatic changes paused; cycle skipped")
            continue
        config.log("Scheduled cycle (%s)" % interval)
        ok, msg = change_wallpaper()
        if not ok:
            config.log(msg)


def theme_watcher_loop() -> None:
    last = platform.is_light_theme()
    while True:
        time.sleep(15)
        try:
            current = platform.is_light_theme()
            if current != last:
                last = current
                if get("theme_mode") == "auto":
                    config.log(
                        "System theme changed to %s" % ("light" if current else "dark")
                    )
                    change_wallpaper()
        except Exception as e:  # noqa: BLE001
            config.log("Error in theme watcher: %r" % e)


# ---------------------------------------------------------------------------
# Tray
# ---------------------------------------------------------------------------
def _notify(icon, msg: str) -> None:
    try:
        (icon or _tray_icon).notify(msg, APP_NAME)
    except Exception:  # noqa: BLE001 - notifications are best-effort
        config.log("(notification unavailable) %s" % msg)


def _apply_settings(values: dict) -> str | None:
    config.set_many(
        {
            "use_unsplash": values["use_unsplash"],
            "use_bing": values["use_bing"],
            "use_wallhaven": values.get("use_wallhaven", False),
            "paused": values.get("paused", False),
            "unsplash_key": values["unsplash_key"],
            "theme_mode": values["theme_mode"],
            "language": values.get("language", "auto"),
            "resolution": values.get("resolution", "auto"),
            "interval": values["interval"],
            "change_on_start": values["change_on_start"],
            "keep": values["keep"],
            "queries_dark": values["queries_dark"],
            "queries_light": values["queries_light"],
        }
    )
    i18n.apply_language()
    if _tray_icon is not None:  # refresh the tray for the new language
        try:
            _tray_icon.menu = build_menu()
            _tray_icon.update_menu()
        except Exception:  # noqa: BLE001 - the tray returns to normal on restart
            config.log("Could not refresh the tray menu")
    if values["startup"] != platform.startup_enabled() and not platform.set_startup(
        values["startup"]
    ):
        return t("Não consegui alterar o arranque automático do sistema.")
    _wake.set()
    return None


def open_image_folder() -> None:
    try:
        config.image_dir().mkdir(parents=True, exist_ok=True)
        platform.open_folder(config.image_dir())
    except Exception as e:  # noqa: BLE001
        config.log("Error opening folder: %r" % e)


def build_menu():
    pystray = _get_pystray()

    def change_now(icon, item=None):
        def work():
            _ok, msg = change_wallpaper(manual=True)
            _notify(icon, msg)

        threading.Thread(target=work, daemon=True).start()

    def interval_action(value):
        def handler(icon, item=None):
            config.set_key("interval", value)
            _wake.set()

        return handler

    def theme_action(value):
        def handler(icon, item=None):
            config.set_key("theme_mode", value)
            _wake.set()
            if value != "auto":
                threading.Thread(
                    target=lambda: change_wallpaper(manual=True), daemon=True
                ).start()

        return handler

    def toggle_startup(icon, item=None):
        ok = platform.set_startup(not platform.startup_enabled())
        if ok:
            _notify(
                icon,
                t("Arranque com o sistema: %s")
                % ("ON" if platform.startup_enabled() else "OFF"),
            )
        else:
            _notify(icon, t("Não consegui alterar o arranque automático."))

    def toggle_change_on_start(icon, item=None):
        config.set_key("change_on_start", not get("change_on_start"))

    def toggle_pause(icon, item=None):
        config.set_key("paused", not get("paused"))
        _wake.set()
        _notify(
            icon,
            t("Mudanças automáticas: %s")
            % (t("EM PAUSA") if get("paused") else t("ATIVAS")),
        )

    def toggle_source(key):
        def handler(icon, item=None):
            config.set_key(key, not get(key))

        return handler

    return pystray.Menu(
        pystray.MenuItem(t("Mudar agora"), change_now, default=True),
        pystray.MenuItem(
            t("Pausar mudanças automáticas"),
            toggle_pause,
            checked=lambda item: bool(get("paused")),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            t("Intervalo"),
            pystray.Menu(
                *[
                    pystray.MenuItem(
                        label,
                        interval_action(value),
                        radio=True,
                        checked=lambda item, v=value: get("interval") == v,
                    )
                    for value, label in config.interval_labels()
                ]
            ),
        ),
        pystray.MenuItem(
            t("Tema dos wallpapers"),
            pystray.Menu(
                pystray.MenuItem(
                    t("Seguir o tema do sistema"),
                    theme_action("auto"),
                    radio=True,
                    checked=lambda item: get("theme_mode") == "auto",
                ),
                pystray.MenuItem(
                    t("Sempre escuro"),
                    theme_action("dark"),
                    radio=True,
                    checked=lambda item: get("theme_mode") == "dark",
                ),
                pystray.MenuItem(
                    t("Sempre claro"),
                    theme_action("light"),
                    radio=True,
                    checked=lambda item: get("theme_mode") == "light",
                ),
            ),
        ),
        pystray.MenuItem(
            t("Fontes"),
            pystray.Menu(
                pystray.MenuItem(
                    "Unsplash",
                    toggle_source("use_unsplash"),
                    checked=lambda item: bool(get("use_unsplash")),
                ),
                pystray.MenuItem(
                    "Bing Photo of the Day",
                    toggle_source("use_bing"),
                    checked=lambda item: bool(get("use_bing")),
                ),
                pystray.MenuItem(
                    t("Wallhaven (sem key)"),
                    toggle_source("use_wallhaven"),
                    checked=lambda item: bool(get("use_wallhaven")),
                ),
            ),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            t("Iniciar com o sistema"),
            toggle_startup,
            checked=lambda item: platform.startup_enabled(),
        ),
        pystray.MenuItem(
            t("Mudar wallpaper ao arrancar o programa"),
            toggle_change_on_start,
            checked=lambda item: bool(get("change_on_start")),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            t("Definições..."), lambda icon, item=None: _ui_queue.put("settings")
        ),
        pystray.MenuItem(
            t("Abrir pasta de imagens"), lambda icon, item=None: open_image_folder()
        ),
        pystray.MenuItem(
            t("Esquecer wallpapers usados"),
            lambda icon, item=None: (
                forget_history(),
                _notify(icon, t("Histórico de repetições esquecido.")),
            ),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            t("Sair"), lambda icon, item=None: (icon.stop(), _ui_queue.put("quit"))
        ),
    )


def on_ready(icon) -> None:
    global _tray_icon
    _tray_icon = icon
    icon.visible = True  # required when using a custom setup
    config.log("App started v%s (%s)" % (APP_VERSION, platform.name))

    def initial_change():
        if get("change_on_start"):
            time.sleep(2)
            change_wallpaper()

    threading.Thread(target=initial_change, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    threading.Thread(target=theme_watcher_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# UI (Tk on the main thread)
# ---------------------------------------------------------------------------
def _open_settings(root) -> None:
    global _settings_win
    if _settings_win is not None:
        try:
            if _settings_win.winfo_exists():
                _settings_win.deiconify()
                _settings_win.lift()
                _settings_win.focus_force()
                return
        except Exception:  # noqa: BLE001 - window closed in the meantime
            pass
        _settings_win = None

    from .ui import SettingsWindow

    def on_close():
        global _settings_win
        _settings_win = None

    try:
        _settings_win = SettingsWindow(
            root,
            on_save=_apply_settings,
            on_close=on_close,
            change_wallpaper=change_wallpaper,
            status_text=status_text,
            open_folder=open_image_folder,
            preview_candidate=obtain_candidate,
            apply_image=apply_file,
            list_recent=list_recent_images,
            forget_history=forget_history,
        )
        _settings_win.set_header_provider(status_text)
    except Exception:  # noqa: BLE001 - log the traceback and continue
        config.log("Error opening settings:\n%s" % traceback.format_exc())
        _settings_win = None


def _make_root():
    import customtkinter as ctk

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw()
    try:
        root.iconphoto(True, make_icon_image())
    except Exception:  # noqa: BLE001 - the icon is cosmetic
        pass
    return root


def _run_ui(root) -> None:
    def poll():
        try:
            cmd = _ui_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            if cmd == "quit":
                root.quit()
                return
            if cmd == "settings":
                _open_settings(root)
        root.after(150, poll)

    root.after(150, poll)
    root.mainloop()


# ---------------------------------------------------------------------------
# Single instance
# ---------------------------------------------------------------------------
def acquire_single_instance() -> bool:
    global _instance_socket
    if sys.platform == "win32":
        ERROR_ALREADY_EXISTS = 183
        ctypes.windll.kernel32.CreateMutexW(
            None, False, "Local\\WallpaperChanger_Mutex"
        )
        return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 47653))
        s.listen(1)
        _instance_socket = s
        return True
    except OSError:
        s.close()
        return False


def warn_dialog(msg: str) -> None:
    """Show a message to the user on any system."""
    try:
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(None, msg, APP_NAME, 0x40)
        elif sys.platform == "darwin":
            # escape backslashes first to avoid creating escape sequences
            safe = msg.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            script = 'display dialog "%s" buttons {"OK"} with title "%s"' % (
                safe,
                APP_NAME,
            )
            subprocess.run(["osascript", "-e", script], timeout=10)
        else:
            subprocess.run(["notify-send", APP_NAME, msg], timeout=10)
    except Exception:  # noqa: BLE001 - the warning is best-effort
        pass


def warn_already_running() -> None:
    msg = t(
        "O WallpaperChanger já está em execução.\n\n"
        "Procura o ícone (círculo meio-escuro / meio-claro) na bandeja "
        "do sistema."
    )
    config.log("Another instance is already running; exiting.")
    warn_dialog(msg)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    global _ui_queue

    try:
        pystray = _get_pystray()
    except Exception as e:  # noqa: BLE001
        config.log("Error loading the tray: %r" % e)
        warn_dialog(str(e))
        return

    config.ensure_dirs()
    config.load_settings()
    i18n.apply_language()

    if not acquire_single_instance():
        warn_already_running()
        return

    try:
        seeded = history.seed_from_folder()
        if seeded:
            config.log("Initial history: %d existing images marked" % seeded)
    except Exception as e:  # noqa: BLE001
        config.log("Error seeding history: %r" % e)
    _ui_queue = queue.Queue()
    if "--settings" in sys.argv:  # open settings at startup
        _ui_queue.put("settings")

    # On macOS Tk and pystray share the same NSApplication: the main window
    # is created first and the tray integrates into the Tk loop.
    root = _make_root()

    icon_kwargs = {}
    if sys.platform == "darwin":  # pragma: no cover - depende do SO
        try:
            from AppKit import NSApplication

            icon_kwargs["nsapplication"] = NSApplication.sharedApplication()
        except ImportError:
            pass

    icon = pystray.Icon(
        APP_NAME,
        icon=make_icon_image(),
        title=APP_NAME,
        menu=build_menu(),
        **icon_kwargs,
    )
    if sys.platform == "darwin":  # pragma: no cover
        icon.run_detached(setup=on_ready)
    else:

        def run_tray():
            try:
                icon.run(setup=on_ready)
            except Exception as e:  # noqa: BLE001
                config.log("Error in the system tray: %r" % e)
                warn_dialog(t("Não consegui iniciar a bandeja do sistema: %s") % e)

        threading.Thread(target=run_tray, daemon=True).start()

    try:
        _run_ui(root)
    finally:
        config.log("Application stopped")


if __name__ == "__main__":
    main()
