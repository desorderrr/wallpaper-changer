# -*- coding: utf-8 -*-
"""WallpaperChanger — ícone na bandeja, agendador e janela de definições."""
from __future__ import annotations

import ctypes
import io
import os
import queue
import random
import socket
import sys
import threading
import time
import traceback
from datetime import datetime

from PIL import Image

from . import config, history, sources, tone
from .assets import make_icon_image
from .config import APP_NAME, APP_VERSION, INTERVALS, get
from .platform import platform

_pystray = None


def _get_pystray():
    """Importa o pystray, com fallback para o backend X11 no Linux.

    Em alguns Linux o `gi` existe mas faltam os typelibs do GTK3, o que faz
    o pystray rebentar antes de tentar o backend Xorg. Nesses casos forçamos
    PYSTRAY_BACKEND=xorg (requer python-xlib).
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
                "Não consegui iniciar a bandeja do sistema. No Linux instala "
                "python-xlib (pip) ou python3-gi + gir1.2-gtk-3.0."
            ) from e
    _pystray = mod
    return mod

# ---------------------------------------------------------------------------
# Estado de execução (mostrado na UI)
# ---------------------------------------------------------------------------
state: dict = {
    "last_change": None,
    "last_tone": None,
    "last_source": None,
    "last_path": None,
    "last_error": None,
}

_change_lock = threading.Lock()
_wake = threading.Event()          # sinaliza mudança de settings -> reagenda
_ui_queue: "queue.Queue[str] | None" = None
_tray_icon = None
_settings_win = None
_instance_socket = None


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------
def effective_theme_is_dark() -> bool:
    mode = get("theme_mode")
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return not platform.is_light_theme()


def status_text() -> str:
    tone_name = "escuro" if effective_theme_is_dark() else "claro"
    mode = {
        "auto": "segue o sistema",
        "dark": "sempre escuro",
        "light": "sempre claro",
    }.get(get("theme_mode"), "segue o sistema")
    parts = ["Tema atual: %s (%s)" % (tone_name, mode)]
    if get("paused"):
        parts.append("mudanças automáticas em pausa")
    if state["last_source"]:
        src = {
            "unsplash": "Unsplash",
            "bing": "Bing",
            "wallhaven": "Wallhaven",
        }.get(state["last_source"], state["last_source"])
        parts.append("última fonte: %s" % src)
    if state["last_change"]:
        parts.append("última troca: %s" % state["last_change"].strftime("%d/%m %H:%M"))
    return " · ".join(parts)


def save_image(img_bytes: bytes, prefix: str):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    path = config.image_dir() / (
        "%s_%s.jpg" % (prefix, datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    )
    img.save(path, "JPEG", quality=90)
    return path


def cleanup_images() -> None:
    keep = int(get("keep") or 20)
    try:
        files = sorted(
            ((p.stat().st_mtime, p) for p in config.image_dir().glob("*.jpg"))
        )
        for _, old in files[: max(0, len(files) - keep)]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def _enabled_sources(want_dark: bool) -> list[tuple[str, str, object]]:
    """(id, nome, função de fetch) das fontes ativas, por ordem aleatória."""
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
    """Troca o wallpaper respeitando o tema. Devolve (sucesso, mensagem)."""
    if not _change_lock.acquire(blocking=False):
        return False, "Já existe uma troca de wallpaper em curso."
    try:
        return _do_change(manual=manual)
    finally:
        _change_lock.release()


def _do_change(manual: bool = False) -> tuple[bool, str]:
    if get("paused") and not manual:
        return False, "Mudanças automáticas em pausa."

    want_dark = effective_theme_is_dark()
    tone_name = "escuro" if want_dark else "claro"

    enabled = _enabled_sources(want_dark)
    if not enabled:
        return False, "Nenhuma fonte ativa. Ativa o Unsplash, o Bing ou o Wallhaven."

    last_error = ""
    for src, name, fetch in enabled:
        try:
            data = fetch(want_dark)

            luma = tone.mean_luminance(data)
            config.log("Fonte %s: luma=%.0f (queria %s)" % (name, luma, tone_name))
            if not tone.tone_matches(luma, want_dark):
                last_error = "%s devolveu uma imagem com o tom errado" % name
                continue
            if history.is_duplicate(data):
                last_error = "%s devolveu um wallpaper repetido" % name
                config.log("Repetido de %s ignorado" % name)
                continue

            path = save_image(data, src)
            platform.set_wallpaper(path)
            cleanup_images()
            history.add(data, src, path)
            state.update(
                last_change=datetime.now(),
                last_tone=tone_name,
                last_source=src,
                last_path=str(path),
                last_error=None,
            )
            config.log("Wallpaper %s aplicado: %s" % (tone_name, path))
            return True, "Wallpaper %s aplicado (%s)." % (tone_name, name)
        except Exception as e:  # noqa: BLE001 - qualquer fonte pode falhar
            last_error = "%s: %s" % (name, e)
            config.log("Erro em %s: %r" % (name, e))

    msg = "Não consegui obter uma imagem %s agora. %s" % (tone_name, last_error)
    state["last_error"] = msg
    config.log(msg)
    return False, msg


def _source_key(path) -> str:
    """Extrai a fonte do nome do ficheiro (ex.: preview_unsplash_2026...)."""
    stem = path.stem
    if stem.startswith("preview_"):
        stem = stem[len("preview_"):]
    return stem.split("_", 1)[0]


def obtain_candidate() -> tuple[bool, str, str | None]:
    """Obtém uma imagem (sem aplicar) para a pré-visualização."""
    want_dark = effective_theme_is_dark()
    tone_name = "escuro" if want_dark else "claro"
    enabled = _enabled_sources(want_dark)
    if not enabled:
        return False, "Nenhuma fonte ativa. Ativa o Unsplash, o Bing ou o Wallhaven.", None

    errors: list[str] = []
    for src, name, fetch in enabled:
        try:
            data = fetch(want_dark)
            if not tone.tone_matches(tone.mean_luminance(data), want_dark):
                errors.append("%s: tom errado" % name)
                continue
            path = save_image(data, "preview_" + src)
            return True, "Sugestão do %s (tom %s)." % (name, tone_name), str(path)
        except Exception as e:  # noqa: BLE001
            errors.append("%s: %s" % (name, e))
            config.log("Erro na sugestão (%s): %r" % (name, e))
    return False, "Não consegui obter uma sugestão. " + "; ".join(errors[-2:]), None


def apply_file(path) -> tuple[bool, str]:
    """Aplica um ficheiro de imagem já existente."""
    from pathlib import Path as _Path

    path = _Path(path)
    try:
        platform.set_wallpaper(path)
        cleanup_images()
        history.add_path(path, _source_key(path))
        tone_name = "escuro" if effective_theme_is_dark() else "claro"
        state.update(
            last_change=datetime.now(),
            last_tone=tone_name,
            last_source=_source_key(path),
            last_path=str(path),
            last_error=None,
        )
        config.log("Wallpaper aplicado manualmente: %s" % path)
        return True, "Wallpaper aplicado."
    except Exception as e:  # noqa: BLE001
        config.log("Erro ao aplicar %s: %r" % (path, e))
        return False, "Não consegui aplicar o wallpaper: %s" % e


def list_recent_images(limit: int = 24) -> list:
    """Imagens guardadas (sem duplicados percetuais), da mais recente."""
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
    """Esquece os wallpapers usados (permite voltar a vê-los)."""
    history.reset()
    config.log("Histórico de wallpapers usados esquecido")


# ---------------------------------------------------------------------------
# Agendador + vigilante do tema
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
            config.log("Mudanças automáticas em pausa; ciclo ignorado")
            continue
        config.log("Ciclo agendado (%s)" % interval)
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
                        "Tema do sistema mudou para %s"
                        % ("claro" if current else "escuro")
                    )
                    change_wallpaper()
        except Exception as e:  # noqa: BLE001
            config.log("Erro no vigilante de tema: %r" % e)


# ---------------------------------------------------------------------------
# Tray
# ---------------------------------------------------------------------------
def _notify(icon, msg: str) -> None:
    try:
        (icon or _tray_icon).notify(msg, APP_NAME)
    except Exception:
        config.log("(notificação indisponível) %s" % msg)


def _apply_settings(values: dict) -> str | None:
    config.set_many({
        "use_unsplash": values["use_unsplash"],
        "use_bing": values["use_bing"],
        "use_wallhaven": values.get("use_wallhaven", False),
        "paused": values.get("paused", False),
        "unsplash_key": values["unsplash_key"],
        "theme_mode": values["theme_mode"],
        "interval": values["interval"],
        "change_on_start": values["change_on_start"],
        "keep": values["keep"],
        "queries_dark": values["queries_dark"],
        "queries_light": values["queries_light"],
    })
    if values["startup"] != platform.startup_enabled():
        if not platform.set_startup(values["startup"]):
            return "Não consegui alterar o arranque automático do sistema."
    _wake.set()
    return None


def open_image_folder() -> None:
    try:
        config.image_dir().mkdir(parents=True, exist_ok=True)
        platform.open_folder(config.image_dir())
    except Exception as e:  # noqa: BLE001
        config.log("Erro ao abrir pasta: %r" % e)


def build_menu():
    pystray = _get_pystray()

    def change_now(icon, item=None):
        def work():
            ok, msg = change_wallpaper(manual=True)
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
                "Arranque com o sistema: %s"
                % ("ON" if platform.startup_enabled() else "OFF"),
            )
        else:
            _notify(icon, "Não consegui alterar o arranque automático.")

    def toggle_change_on_start(icon, item=None):
        config.set_key("change_on_start", not get("change_on_start"))

    def toggle_pause(icon, item=None):
        config.set_key("paused", not get("paused"))
        _wake.set()
        _notify(
            icon,
            "Mudanças automáticas: %s"
            % ("EM PAUSA" if get("paused") else "ATIVAS"),
        )

    def toggle_source(key):
        def handler(icon, item=None):
            config.set_key(key, not get(key))

        return handler

    return pystray.Menu(
        pystray.MenuItem("Mudar agora", change_now, default=True),
        pystray.MenuItem(
            "Pausar mudanças automáticas", toggle_pause,
            checked=lambda item: bool(get("paused")),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Intervalo",
            pystray.Menu(*[
                pystray.MenuItem(
                    label, interval_action(value), radio=True,
                    checked=lambda item, v=value: get("interval") == v,
                )
                for value, label in config.INTERVAL_LABELS
            ]),
        ),
        pystray.MenuItem(
            "Tema dos wallpapers",
            pystray.Menu(
                pystray.MenuItem(
                    "Seguir o tema do sistema", theme_action("auto"),
                    radio=True, checked=lambda item: get("theme_mode") == "auto",
                ),
                pystray.MenuItem(
                    "Sempre escuro", theme_action("dark"),
                    radio=True, checked=lambda item: get("theme_mode") == "dark",
                ),
                pystray.MenuItem(
                    "Sempre claro", theme_action("light"),
                    radio=True, checked=lambda item: get("theme_mode") == "light",
                ),
            ),
        ),
        pystray.MenuItem(
            "Fontes",
            pystray.Menu(
                pystray.MenuItem(
                    "Unsplash", toggle_source("use_unsplash"),
                    checked=lambda item: bool(get("use_unsplash")),
                ),
                pystray.MenuItem(
                    "Bing Photo of the Day", toggle_source("use_bing"),
                    checked=lambda item: bool(get("use_bing")),
                ),
                pystray.MenuItem(
                    "Wallhaven (sem key)", toggle_source("use_wallhaven"),
                    checked=lambda item: bool(get("use_wallhaven")),
                ),
            ),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Iniciar com o sistema", toggle_startup,
            checked=lambda item: platform.startup_enabled(),
        ),
        pystray.MenuItem(
            "Mudar wallpaper ao arrancar o programa", toggle_change_on_start,
            checked=lambda item: bool(get("change_on_start")),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Definições...", lambda icon, item=None: _ui_queue.put("settings")
        ),
        pystray.MenuItem(
            "Abrir pasta de imagens", lambda icon, item=None: open_image_folder()
        ),
        pystray.MenuItem(
            "Esquecer wallpapers usados",
            lambda icon, item=None: (
                forget_history(),
                _notify(icon, "Histórico de repetições esquecido."),
            ),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Sair", lambda icon, item=None: (icon.stop(), _ui_queue.put("quit"))
        ),
    )


def on_ready(icon) -> None:
    global _tray_icon
    _tray_icon = icon
    icon.visible = True  # obrigatório quando se usa setup personalizado
    config.log("Arranque da aplicação v%s (%s)" % (APP_VERSION, platform.name))

    def initial_change():
        if get("change_on_start"):
            time.sleep(2)
            change_wallpaper()

    threading.Thread(target=initial_change, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    threading.Thread(target=theme_watcher_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# UI (Tk na thread principal)
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
        except Exception:
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
    except Exception:
        config.log("Erro ao abrir definições:\n%s" % traceback.format_exc())
        _settings_win = None


def _make_root():
    import customtkinter as ctk

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw()
    try:
        root.iconphoto(True, make_icon_image())
    except Exception:
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
# Instância única
# ---------------------------------------------------------------------------
def acquire_single_instance() -> bool:
    global _instance_socket
    if sys.platform == "win32":
        ERROR_ALREADY_EXISTS = 183
        ctypes.windll.kernel32.CreateMutexW(
            None, False, "Global\\WallpaperChanger_Mutex"
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
    """Mostra uma mensagem ao utilizador em qualquer sistema."""
    try:
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(None, msg, APP_NAME, 0x40)
        elif sys.platform == "darwin":
            script = 'display dialog "%s" buttons {"OK"} with title "%s"' % (
                msg.replace('"', '\\"').replace("\n", "\\n"),
                APP_NAME,
            )
            os.system('osascript -e \'%s\'' % script)
        else:
            os.system(
                'notify-send "%s" "%s" 2>/dev/null || echo "%s"'
                % (APP_NAME, msg.replace('"', "'").replace("\n", " "), msg)
            )
    except Exception:
        pass


def warn_already_running() -> None:
    msg = (
        "O WallpaperChanger já está em execução.\n\n"
        "Procura o ícone (círculo meio-escuro / meio-claro) na bandeja "
        "do sistema."
    )
    config.log("Já existe uma instância em execução; a sair.")
    warn_dialog(msg)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    global _ui_queue

    try:
        pystray = _get_pystray()
    except Exception as e:  # noqa: BLE001
        config.log("Erro ao carregar a bandeja: %r" % e)
        warn_dialog(str(e))
        return

    if not acquire_single_instance():
        warn_already_running()
        return

    config.ensure_dirs()
    config.load_settings()
    try:
        seeded = history.seed_from_folder()
        if seeded:
            config.log("Histórico inicial: %d imagens existentes marcadas" % seeded)
    except Exception as e:  # noqa: BLE001
        config.log("Erro ao semear histórico: %r" % e)
    _ui_queue = queue.Queue()
    if "--settings" in sys.argv:  # abrir as definições ao arrancar
        _ui_queue.put("settings")

    # Em macOS o Tk e o pystray partilham o mesmo NSApplication: a janela
    # principal é criada primeiro e a tray integra-se no loop do Tk.
    root = _make_root()

    icon_kwargs = {}
    if sys.platform == "darwin":  # pragma: no cover - depende do SO
        try:
            from AppKit import NSApplication

            icon_kwargs["nsapplication"] = NSApplication.sharedApplication()
        except ImportError:
            pass

    icon = pystray.Icon(
        APP_NAME, icon=make_icon_image(), title=APP_NAME,
        menu=build_menu(), **icon_kwargs,
    )
    if sys.platform == "darwin":  # pragma: no cover
        icon.run_detached(setup=on_ready)
    else:
        threading.Thread(
            target=icon.run, kwargs={"setup": on_ready}, daemon=True
        ).start()

    try:
        _run_ui(root)
    finally:
        config.log("Aplicação terminada")


if __name__ == "__main__":
    main()
