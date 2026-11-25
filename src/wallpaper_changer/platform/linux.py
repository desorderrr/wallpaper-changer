# -*- coding: utf-8 -*-
"""Backend Linux: tema, wallpaper por ambiente de trabalho e autostart XDG."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import quote

from ..i18n import t
from .base import BasePlatform, run


# ---------------------------------------------------------------------------
# Parsers (funções puras, testáveis)
# ---------------------------------------------------------------------------
def parse_color_scheme(value: str) -> bool | None:
    """'prefer-dark' -> False (não é claro), 'prefer-light' -> True, resto None."""
    v = value.strip().strip("'\"")
    if v == "prefer-dark":
        return False
    if v == "prefer-light":
        return True
    return None


def parse_gtk_theme(value: str) -> bool | None:
    """Nome do tema GTK -> True se claro."""
    v = value.strip().strip("'\"")
    if not v:
        return None
    return "dark" not in v.lower()


def parse_kde_colorscheme(text: str) -> bool | None:
    """Conteúdo do kdeglobals -> True se claro."""
    for line in text.splitlines():
        if line.strip().startswith("ColorScheme="):
            scheme = line.split("=", 1)[1].strip().lower()
            return "dark" not in scheme
    return None


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------
def _gsettings_get(schema: str, key: str) -> str | None:
    ok, out = run(["gsettings", "get", schema, key])
    return out if ok else None


def autostart_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "autostart" / "wallpaper-changer.desktop"


class Platform(BasePlatform):
    name = "Linux"

    # -- tema ---------------------------------------------------------
    def is_light_theme(self) -> bool:
        cs = _gsettings_get("org.gnome.desktop.interface", "color-scheme")
        if cs is not None:
            parsed = parse_color_scheme(cs)
            if parsed is not None:
                return parsed

        gtk = _gsettings_get("org.gnome.desktop.interface", "gtk-theme")
        if gtk is not None:
            parsed = parse_gtk_theme(gtk)
            if parsed is not None:
                return parsed

        # KDE
        try:
            kdeglobals = Path.home() / ".config" / "kdeglobals"
            if kdeglobals.exists():
                parsed = parse_kde_colorscheme(
                    kdeglobals.read_text(encoding="utf-8", errors="ignore")
                )
                if parsed is not None:
                    return parsed
        except OSError:
            pass

        env = os.environ.get("GTK_THEME", "")
        return ":dark" not in env.lower()

    # -- wallpaper ----------------------------------------------------
    def set_wallpaper(self, path: Path) -> None:
        p = str(path)
        uri = "file://" + quote(p)
        de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        errors: list[str] = []

        def attempt(desc: str, args: list[str]) -> bool:
            ok, out = run(args)
            if not ok:
                errors.append("%s: %s" % (desc, out))
            return ok

        def set_gnome() -> bool:
            if not attempt(
                "gnome",
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri",
                    uri,
                ],
            ):
                return False
            # melhor esforço para o modo escuro (chave pode não existir)
            run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.background",
                    "picture-uri-dark",
                    uri,
                ]
            )
            return True

        def set_cinnamon() -> bool:
            return attempt(
                "cinnamon",
                [
                    "gsettings",
                    "set",
                    "org.cinnamon.desktop.background",
                    "picture-uri",
                    uri,
                ],
            )

        def set_mate() -> bool:
            return attempt(
                "mate",
                ["gsettings", "set", "org.mate.background", "picture-filename", p],
            )

        def set_kde() -> bool:
            script = (
                "var ds = desktops();"
                "for (var i = 0; i < ds.length; i++) {"
                'ds[i].wallpaperPlugin = "org.kde.image";'
                'ds[i].currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];'
                'ds[i].writeConfig("Image", "%s");}' % uri
            )
            for tool in ("qdbus6", "qdbus"):
                if shutil.which(tool) and attempt(
                    tool,
                    [
                        tool,
                        "org.kde.plasmashell",
                        "/PlasmaShell",
                        "org.kde.PlasmaShell.evaluateScript",
                        script,
                    ],
                ):
                    return True
            return False

        def set_xfce() -> bool:
            _ok, out = run(["xfconf-query", "-c", "xfce4-desktop", "-l"])
            props = [line for line in out.splitlines() if line.endswith("/last-image")]
            done = False
            for prop in props:
                if attempt(
                    "xfce",
                    ["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", p],
                ):
                    done = True
            return done

        def set_feh() -> bool:
            if os.environ.get("DISPLAY") and shutil.which("feh"):
                return attempt("feh", ["feh", "--bg-fill", p])
            return False

        if "cinnamon" in de:
            ordered = [set_cinnamon, set_gnome, set_feh]
        elif "mate" in de:
            ordered = [set_mate, set_gnome, set_feh]
        elif any(k in de for k in ("kde", "plasma")):
            ordered = [set_kde, set_feh]
        elif "xfce" in de:
            ordered = [set_xfce, set_feh]
        elif any(k in de for k in ("gnome", "unity", "pop")):
            ordered = [set_gnome, set_feh]
        else:
            # ambiente desconhecido: tenta genéricos
            ordered = [set_gnome, set_cinnamon, set_mate, set_kde, set_xfce, set_feh]

        for fn in ordered:
            try:
                if fn():
                    return
            except Exception as e:  # noqa: BLE001 - continua para o próximo método
                errors.append("%s: %r" % (fn.__name__, e))

        raise RuntimeError(
            t(
                "Não consegui definir o wallpaper neste ambiente "
                "(XDG_CURRENT_DESKTOP=%r). %s"
            )
            % (de, " | ".join(errors[-3:]))
        )

    # -- arranque com o sistema ----------------------------------------
    def startup_enabled(self) -> bool:
        return autostart_path().exists()

    def set_startup(self, enable: bool) -> bool:
        from ..config import self_command

        target = autostart_path()
        try:
            if enable:
                target.parent.mkdir(parents=True, exist_ok=True)
                exec_cmd = " ".join(
                    '"%s"' % a if " " in a else a for a in self_command()
                )
                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=WallpaperChanger\n"
                    "Comment=Wallpapers automáticos escuros/claros\n"
                    "Exec=%s\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n" % exec_cmd
                )
                target.write_text(content, encoding="utf-8")
                return True
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            return True
        except OSError:
            return False

    # -- diversos -------------------------------------------------------
    def open_folder(self, path: Path) -> None:
        run(["xdg-open", str(path)])
