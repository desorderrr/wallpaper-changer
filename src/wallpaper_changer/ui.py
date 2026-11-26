# -*- coding: utf-8 -*-
"""Modern settings window (customtkinter) with preview."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from .assets import make_icon_image
from .config import APP_VERSION, get, interval_labels
from .i18n import t
from .platform import platform

THEME_OPTIONS = [
    ("auto", "Seguir o tema do sistema"),
    ("dark", "Sempre escuro"),
    ("light", "Sempre claro"),
]


def theme_options() -> list[tuple[str, str]]:
    """(id, translated label) pairs for the wallpaper tone."""
    return [(value, t(label)) for value, label in THEME_OPTIONS]


SOURCE_NAMES = {
    "unsplash": "Unsplash",
    "bing": "Bing",
    "wallhaven": "Wallhaven",
}


def _source_from_path(path: Path) -> str:
    stem = path.stem
    stem = stem.removeprefix("preview_")
    key = stem.split("_", 1)[0]
    if key == "local":
        return t("Pasta local")
    return SOURCE_NAMES.get(key, key.title())


class SettingsWindow(ctk.CTkToplevel):
    """Window with four tabs: General, Preview, Queries and About."""

    def __init__(
        self,
        master,
        *,
        on_save: Callable[[dict], str | None],
        on_close: Callable[[], None],
        change_wallpaper: Callable[[bool], tuple[bool, str]],
        status_text: Callable[[], str],
        open_folder: Callable[[], None],
        preview_candidate: Callable[[], tuple[bool, str, str | None]],
        apply_image: Callable[[str], tuple[bool, str]],
        list_recent: Callable[[], list],
        forget_history: Callable[[], None],
    ):
        super().__init__(master)
        self._on_save = on_save
        self._on_close = on_close
        self._change = change_wallpaper
        self._candidate = preview_candidate
        self._apply_image = apply_image
        self._recent = list_recent
        self._forget_history = forget_history
        self._status_q: queue.Queue = queue.Queue()

        self._selected_path: Path | None = None
        self._tiles: dict[str, tuple[ctk.CTkImage, ctk.CTkButton]] = {}
        self._preview_photo: ctk.CTkImage | None = None
        self._gallery_thumbs: list[ctk.CTkImage] = []
        self._gallery_loading = False
        self._gallery_select: str | None = None

        # tab names in the active language (used in _build_* and in poll)
        self._tab_names = {
            key: t(label)
            for key, label in (
                ("general", "Geral"),
                ("preview", "Pré-visualizar"),
                ("queries", "Pesquisas"),
                ("about", "Sobre"),
            )
        }

        self.title(t("WallpaperChanger — Definições"))
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.grid_columnconfigure(0, weight=1)

        # --- Header -----------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))

        icon_img = make_icon_image(48)
        self._icon = ctk.CTkImage(
            light_image=icon_img, dark_image=icon_img, size=(44, 44)
        )
        ctk.CTkLabel(header, image=self._icon, text="").pack(side="left")

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(
            titles,
            text="WallpaperChanger",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")
        self.header_status = ctk.CTkLabel(
            titles,
            text=status_text(),
            text_color=("gray40", "gray60"),
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
        )
        self.header_status.pack(anchor="w", fill="x")

        # --- Tabs -------------------------------------------------------
        self.tabs = ctk.CTkTabview(self, width=720, height=500)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        for name in self._tab_names.values():
            self.tabs.add(name)

        self._build_general(self.tabs.tab(self._tab_names["general"]))
        self._build_preview(self.tabs.tab(self._tab_names["preview"]))
        self._build_queries(self.tabs.tab(self._tab_names["queries"]))
        self._build_about(
            self.tabs.tab(self._tab_names["about"]), open_folder, forget_history
        )

        # --- Footer -----------------------------------------------------
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 16))

        self.status_label = ctk.CTkLabel(
            footer,
            text=t("Pronto."),
            text_color=("gray40", "gray60"),
            anchor="w",
            justify="left",
            wraplength=350,
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.save_btn = ctk.CTkButton(
            footer, text=t("Gravar"), width=100, command=self._save
        )
        self.save_btn.pack(side="right")
        ctk.CTkButton(
            footer,
            text=t("Cancelar"),
            width=90,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            command=self._close,
        ).pack(side="right", padx=8)
        self.change_btn = ctk.CTkButton(
            footer,
            text=t("Mudar agora"),
            width=110,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=self._change_now,
        )
        self.change_btn.pack(side="right")

        self._center()
        self.after(120, self._raise)
        self.after(300, self._poll)

    # ------------------------------------------------------------------
    # Building the tabs
    # ------------------------------------------------------------------
    def _build_sources_box(self, tab) -> None:
        box = ctk.CTkFrame(tab)
        box.grid(row=0, column=0, sticky="ew", pady=(8, 6), padx=4)
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            box,
            text=t("Fontes de imagens"),
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        self.var_unsplash = tk.BooleanVar(value=bool(get("use_unsplash")))
        self.var_bing = tk.BooleanVar(value=bool(get("use_bing")))
        self.var_wallhaven = tk.BooleanVar(value=bool(get("use_wallhaven")))
        self.var_local = tk.BooleanVar(value=bool(get("use_local")))

        row = ctk.CTkFrame(box, fg_color="transparent")
        row.grid(row=1, column=0, sticky="w", padx=8, pady=2)
        ctk.CTkCheckBox(row, text="Unsplash", variable=self.var_unsplash).pack(
            side="left", padx=4
        )
        ctk.CTkCheckBox(row, text=t("Bing (foto do dia)"), variable=self.var_bing).pack(
            side="left", padx=4
        )
        ctk.CTkCheckBox(row, text="Wallhaven", variable=self.var_wallhaven).pack(
            side="left", padx=4
        )
        ctk.CTkCheckBox(row, text=t("Pasta local"), variable=self.var_local).pack(
            side="left", padx=4
        )

        folder_row = ctk.CTkFrame(box, fg_color="transparent")
        folder_row.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 2))
        ctk.CTkLabel(folder_row, text=t("Pasta local")).pack(side="left")
        self.var_folder = tk.StringVar(value=get("local_folder") or "")
        ctk.CTkEntry(
            folder_row,
            textvariable=self.var_folder,
            width=430,
            placeholder_text=t("Escolhe uma pasta com os teus wallpapers…"),
        ).pack(side="left", padx=8, fill="x", expand=True)
        ctk.CTkButton(
            folder_row,
            text=t("Escolher…"),
            width=90,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=self._choose_folder,
        ).pack(side="left")

        self.var_key = tk.StringVar(value=get("unsplash_key") or "")
        ctk.CTkEntry(
            box,
            textvariable=self.var_key,
            width=650,
            placeholder_text=t("Cola aqui a API key do Unsplash…"),
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 0))
        ctk.CTkLabel(
            box,
            text=t(
                "API key gratuita em unsplash.com/developers — só para o Unsplash. "
                "O Wallhaven e o Bing não precisam."
            ),
            text_color=("gray45", "gray55"),
            font=ctk.CTkFont(size=11),
        ).grid(row=4, column=0, sticky="w", padx=12, pady=(2, 10))

    def _build_general(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        self._build_sources_box(tab)

        # Tone
        box2 = ctk.CTkFrame(tab)
        box2.grid(row=1, column=0, sticky="ew", pady=6, padx=4)
        ctk.CTkLabel(
            box2,
            text=t("Tom dos wallpapers"),
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self._theme_opts = theme_options()
        self._theme_label_to_value = {label: value for value, label in self._theme_opts}
        self._theme_value_to_label = {value: label for value, label in self._theme_opts}
        self.theme_seg = ctk.CTkSegmentedButton(
            box2,
            values=[label for _, label in self._theme_opts],
            width=620,
        )
        self.theme_seg.set(
            self._theme_value_to_label.get(get("theme_mode"), self._theme_opts[0][1])
        )
        self.theme_seg.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))

        # Interval + options
        box3 = ctk.CTkFrame(tab)
        box3.grid(row=2, column=0, sticky="ew", pady=6, padx=4)
        box3.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            box3,
            text=t("Intervalo de mudança"),
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self._interval_opts = interval_labels()
        self._label_to_value = {label: value for value, label in self._interval_opts}
        self._value_to_label = {value: label for value, label in self._interval_opts}
        self.var_interval = tk.StringVar(
            value=self._value_to_label.get(get("interval"), self._interval_opts[-1][1])
        )
        ctk.CTkOptionMenu(
            box3,
            values=list(self._label_to_value),
            variable=self.var_interval,
            width=240,
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        self.var_startup = tk.BooleanVar(value=platform.startup_enabled())
        self.var_onstart = tk.BooleanVar(value=bool(get("change_on_start")))
        self.var_paused = tk.BooleanVar(value=bool(get("paused")))
        ctk.CTkCheckBox(
            box3,
            text=t("Iniciar com o sistema"),
            variable=self.var_startup,
        ).grid(row=2, column=0, sticky="w", padx=12, pady=2)
        ctk.CTkCheckBox(
            box3,
            text=t("Mudar wallpaper quando o programa arranca"),
            variable=self.var_onstart,
        ).grid(row=3, column=0, sticky="w", padx=12, pady=2)
        ctk.CTkCheckBox(
            box3,
            text=t(
                'Pausar mudanças automáticas (o "Mudar agora" continua a funcionar)'
            ),
            variable=self.var_paused,
        ).grid(row=4, column=0, sticky="w", padx=12, pady=2)

        keep_row = ctk.CTkFrame(box3, fg_color="transparent")
        keep_row.grid(row=5, column=0, sticky="w", padx=12, pady=(8, 6))
        ctk.CTkLabel(keep_row, text=t("Guardar as últimas")).pack(side="left")
        self.var_keep = tk.StringVar(value=str(get("keep") or 20))
        ctk.CTkEntry(keep_row, textvariable=self.var_keep, width=60).pack(
            side="left", padx=6
        )
        ctk.CTkLabel(keep_row, text=t("imagens")).pack(side="left")

        # Resolution + language
        self._build_options_row(box3)

    def _build_options_row(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=6, column=0, sticky="w", padx=12, pady=(0, 12))

        ctk.CTkLabel(row, text=t("Resolução")).pack(side="left")
        self._res_label_to_value = {
            t("Automática (ecrã)"): "auto",
            t("Alta (4K)"): "high",
            t("Baixa (1080p)"): "low",
        }
        value_to_res_label = {v: k for k, v in self._res_label_to_value.items()}
        self.var_res = tk.StringVar(
            value=value_to_res_label.get(
                get("resolution") or "auto", t("Automática (ecrã)")
            )
        )
        ctk.CTkOptionMenu(
            row,
            values=list(self._res_label_to_value),
            variable=self.var_res,
            width=170,
        ).pack(side="left", padx=(8, 28))

        ctk.CTkLabel(row, text=t("Idioma")).pack(side="left")
        self._lang_label_to_value = {
            t("Automático"): "auto",
            t("Português"): "pt",
            "English": "en",
        }
        value_to_lang_label = {v: k for k, v in self._lang_label_to_value.items()}
        self.var_lang = tk.StringVar(
            value=value_to_lang_label.get(get("language") or "auto", t("Automático"))
        )
        ctk.CTkOptionMenu(
            row,
            values=list(self._lang_label_to_value),
            variable=self.var_lang,
            width=140,
        ).pack(side="left", padx=8)

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(
            initialdir=self.var_folder.get().strip() or None
        )
        if folder:
            self.var_folder.set(folder)

    def _build_preview(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=(8, 2))
        ctk.CTkLabel(
            top,
            text=t("Pré-visualização"),
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            top,
            text=t("Atualizar"),
            width=90,
            height=26,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=self._refresh_gallery,
        ).pack(side="right")

        self.preview_label = ctk.CTkLabel(
            tab,
            text=t('Ainda sem imagens. Usa "Nova sugestão".'),
            width=680,
            height=250,
            fg_color=("gray85", "gray18"),
            corner_radius=10,
        )
        self.preview_label.grid(row=1, column=0, sticky="ew", padx=6, pady=(2, 4))

        self.preview_info = ctk.CTkLabel(
            tab,
            text="",
            text_color=("gray40", "gray60"),
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left",
        )
        self.preview_info.grid(row=2, column=0, sticky="w", padx=8)

        self.gallery = ctk.CTkScrollableFrame(
            tab, orientation="horizontal", height=104, fg_color=("gray90", "gray14")
        )
        self.gallery.grid(row=3, column=0, sticky="ew", padx=6, pady=(4, 4))

        actions = ctk.CTkFrame(tab, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=6, pady=(0, 6))
        self.suggest_btn = ctk.CTkButton(
            actions,
            text=t("Nova sugestão"),
            width=130,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=self._suggest,
        )
        self.suggest_btn.pack(side="left")
        self.apply_btn = ctk.CTkButton(
            actions,
            text=t("Aplicar no ambiente de trabalho"),
            width=220,
            command=self._apply_selected,
            state="disabled",
        )
        self.apply_btn.pack(side="left", padx=8)
        self.preview_status = ctk.CTkLabel(
            actions,
            text="",
            text_color=("gray45", "gray55"),
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self.preview_status.pack(side="left", padx=6, fill="x", expand=True)

        # first gallery load
        self.after(250, self._refresh_gallery)

    def _build_queries(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab,
            text=t("Pesquisas no Unsplash (uma por linha)"),
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(10, 2))
        ctk.CTkLabel(
            tab,
            text=t("Usadas para escolher fotos com o tom certo em cada modo."),
            text_color=("gray45", "gray55"),
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))

        ctk.CTkLabel(tab, text=t("Modo escuro:"), anchor="w").grid(
            row=2, column=0, sticky="w", padx=8
        )
        self.txt_dark = ctk.CTkTextbox(tab, height=95, width=660)
        self.txt_dark.grid(row=3, column=0, sticky="ew", padx=8, pady=(2, 10))
        self.txt_dark.insert("1.0", "\n".join(get("queries_dark")))

        ctk.CTkLabel(tab, text=t("Modo claro:"), anchor="w").grid(
            row=4, column=0, sticky="w", padx=8
        )
        self.txt_light = ctk.CTkTextbox(tab, height=95, width=660)
        self.txt_light.grid(row=5, column=0, sticky="ew", padx=8, pady=(2, 10))
        self.txt_light.insert("1.0", "\n".join(get("queries_light")))

    def _build_about(
        self, tab, open_folder: Callable[[], None], forget_history: Callable[[], None]
    ) -> None:
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tab,
            text="WallpaperChanger v%s" % APP_VERSION,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(14, 4))
        ctk.CTkLabel(
            tab,
            justify="left",
            anchor="w",
            wraplength=640,
            text=t(
                "Muda o wallpaper automaticamente, sempre a condizer com o "
                "tema do sistema: modo escuro → wallpapers escuros, modo "
                "claro → wallpapers claros.\n\n"
                "Fontes: Unsplash (API key gratuita), Wallhaven (sem key) e "
                "Bing Photo of the Day (sem registo).\n\n"
                "Os wallpapers já usados ficam guardados num histórico — a app "
                "nunca repete uma imagem (podes esquecer o histórico aqui em baixo).\n\n"
                "Plataformas: Windows 11, macOS e Linux."
            ),
        ).grid(row=1, column=0, sticky="w", padx=10, pady=4)

        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.grid(row=2, column=0, sticky="w", padx=10, pady=(12, 10))
        ctk.CTkButton(
            row,
            text=t("Abrir pasta de imagens"),
            width=180,
            command=open_folder,
        ).pack(side="left")

        def forget():
            forget_history()
            self._set_status(t("Histórico de wallpapers usados esquecido."))
            self._refresh_gallery()
            self._set_preview_status(
                t("Histórico esquecido — as imagens podem repetir-se.")
            )

        ctk.CTkButton(
            row,
            text=t("Esquecer wallpapers usados"),
            width=200,
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            command=forget,
        ).pack(side="left", padx=8)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def _refresh_gallery(self, select: str | None = None) -> None:
        """Reload the gallery; image hashing runs in a worker."""
        if select is not None:
            self._gallery_select = select
        if self._gallery_loading:
            return  # já está um recarregamento em curso (usa o select novo)
        self._gallery_loading = True
        threading.Thread(target=self._gallery_worker, daemon=True).start()

    def _gallery_worker(self) -> None:
        try:
            paths = [str(p) for p in self._recent()]
        except Exception:  # noqa: BLE001 - the gallery must never break the UI
            paths = []
        self._status_q.put(("gallery", True, "", paths))

    def _rebuild_gallery(self, paths: list[str]) -> None:
        self._gallery_loading = False
        select = self._gallery_select
        self._gallery_select = None
        for child in self.gallery.winfo_children():
            child.destroy()
        self._tiles.clear()
        self._gallery_thumbs = []

        path_objs = [Path(p) for p in paths]
        if not path_objs:
            ctk.CTkLabel(
                self.gallery,
                text=t("Sem imagens guardadas ainda."),
                text_color=("gray45", "gray55"),
            ).pack(padx=10, pady=30)
            self.apply_btn.configure(state="disabled")
            self._selected_path = None
            return

        for path in path_objs:
            try:
                with Image.open(path) as img:
                    img.thumbnail((150, 84))
                    tile_img = ctk.CTkImage(
                        light_image=img, dark_image=img, size=img.size
                    )
            except Exception:  # noqa: BLE001 - invalid file: skip it
                continue
            self._gallery_thumbs.append(tile_img)
            btn = ctk.CTkButton(
                self.gallery,
                image=tile_img,
                text="",
                width=156,
                height=88,
                fg_color="transparent",
                hover_color=("gray80", "gray25"),
                border_width=2,
                border_color=("gray90", "gray14"),
                command=lambda p=path: self._select(p),
            )
            btn.pack(side="left", padx=4, pady=6)
            self._tiles[str(path)] = (tile_img, btn)

        target = select or (str(self._selected_path) if self._selected_path else None)
        chosen = Path(target) if target and target in self._tiles else path_objs[0]
        if chosen:
            self._select(chosen)

    def _select(self, path: Path) -> None:
        try:
            with Image.open(path) as img:
                size = img.size
                thumb = img.copy()
                thumb.thumbnail((680, 250))
                self._preview_photo = ctk.CTkImage(
                    light_image=thumb, dark_image=thumb, size=thumb.size
                )
        except Exception:  # noqa: BLE001
            self.preview_status.configure(text=t("Não consegui abrir esta imagem."))
            return
        self.preview_label.configure(image=self._preview_photo, text="")

        try:
            stat = path.stat()
            date = datetime.fromtimestamp(stat.st_mtime)
            info = "%s · %s · %d×%d" % (  # noqa: RUF001
                _source_from_path(path),
                date.strftime("%d/%m %H:%M"),
                size[0],
                size[1],
            )
            if get("paused"):
                info += " · " + t("mudanças em pausa")
        except OSError:
            info = str(path)
        self.preview_info.configure(text=info)

        for key, (_, btn) in self._tiles.items():
            is_sel = key == str(path)
            btn.configure(
                border_color=("#3a7ebf", "#4a9eff") if is_sel else ("gray90", "gray14")
            )
        self._selected_path = path
        self.apply_btn.configure(state="normal")

    def _suggest(self) -> None:
        self.suggest_btn.configure(state="disabled")
        self.apply_btn.configure(state="disabled")
        self.preview_status.configure(text=t("A procurar uma sugestão…"))
        threading.Thread(target=self._suggest_worker, daemon=True).start()

    def _suggest_worker(self) -> None:
        try:
            ok, msg, path = self._candidate()
        except Exception as e:  # noqa: BLE001
            ok, msg, path = False, t("Erro inesperado: %r") % e, None
        self._status_q.put(("preview", ok, msg, path))

    def _apply_selected(self) -> None:
        if not self._selected_path:
            return
        path = str(self._selected_path)
        self.apply_btn.configure(state="disabled")
        self.suggest_btn.configure(state="disabled")
        self.preview_status.configure(text=t("A aplicar…"))
        threading.Thread(target=self._apply_worker, args=(path,), daemon=True).start()

    def _apply_worker(self, path: str) -> None:
        try:
            ok, msg = self._apply_image(path)
        except Exception as e:  # noqa: BLE001
            ok, msg = False, t("Erro inesperado: %r") % e
        self._status_q.put(("applied", ok, msg, path))

    # ------------------------------------------------------------------
    # General actions
    # ------------------------------------------------------------------
    def _center(self) -> None:
        self.update_idletasks()
        w, h = 780, 740
        x = max(0, (self.winfo_screenwidth() - w) // 2)
        y = max(0, (self.winfo_screenheight() - h) // 3)
        self.geometry("%dx%d+%d+%d" % (w, h, x, y))

    def _raise(self) -> None:
        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _set_status(self, text: str, error: bool = False) -> None:
        try:
            self.status_label.configure(
                text=text,
                text_color=("#b3261e", "#f2b8b5") if error else ("gray40", "gray60"),
            )
        except tk.TclError:
            pass

    def _set_preview_status(self, text: str, error: bool = False) -> None:
        try:
            self.preview_status.configure(
                text=text,
                text_color=("#b3261e", "#f2b8b5") if error else ("gray45", "gray55"),
            )
        except tk.TclError:
            pass

    def _change_now(self) -> None:
        if str(self.change_btn.cget("state")) == "disabled":
            return
        self.change_btn.configure(state="disabled")
        self._set_status(t("A procurar um wallpaper novo…"))
        threading.Thread(target=self._change_worker, daemon=True).start()

    def _change_worker(self) -> None:
        try:
            ok, msg = self._change(True)
        except Exception as e:  # noqa: BLE001
            ok, msg = False, t("Erro inesperado: %r") % e
        self._status_q.put(("status", ok, msg, None))

    def _poll(self) -> None:
        try:
            while True:
                kind, ok, msg, extra = self._status_q.get_nowait()
                if kind == "status":
                    self._set_status(msg, error=not ok)
                    self.change_btn.configure(state="normal")
                    if ok:
                        self._refresh_gallery()
                elif kind == "preview":
                    self._set_preview_status(msg, error=not ok)
                    self.suggest_btn.configure(state="normal")
                    self.apply_btn.configure(
                        state="normal" if (ok and extra) else "disabled"
                    )
                    if ok and extra:
                        self._refresh_gallery(select=extra)
                elif kind == "applied":
                    self._set_preview_status(msg, error=not ok)
                    self.suggest_btn.configure(state="normal")
                    self.apply_btn.configure(state="normal")
                    if ok and extra:
                        self._selected_path = Path(extra)
                        self._refresh_gallery(select=extra)
                elif kind == "gallery":
                    self._rebuild_gallery(extra)
                try:
                    self.header_status.configure(text=self._header_text())
                except Exception:  # noqa: BLE001 - the window may have closed
                    pass
        except queue.Empty:
            pass
        try:
            self.after(300, self._poll)
        except tk.TclError:
            pass

    def _header_text(self) -> str:
        try:
            return self._header_provider()
        except Exception:  # noqa: BLE001 - the header is informational
            return ""

    def set_header_provider(self, provider: Callable[[], str]) -> None:
        self._header_provider = provider

    _header_provider = staticmethod(lambda: "")

    def _save(self) -> None:
        try:
            keep = max(5, min(200, int(self.var_keep.get())))
        except (ValueError, tk.TclError):
            self._set_status(
                t("O número de imagens a guardar deve ser 5–200."),  # noqa: RUF001
                error=True,
            )
            return
        folder = self.var_folder.get().strip()
        if self.var_local.get() and not folder:
            self._set_status(
                t(
                    "Escolhe a pasta dos teus wallpapers "
                    "(ou desativa a fonte Pasta local)."
                ),
                error=True,
            )
            return
        values = {
            "use_unsplash": self.var_unsplash.get(),
            "use_bing": self.var_bing.get(),
            "use_wallhaven": self.var_wallhaven.get(),
            "use_local": self.var_local.get(),
            "local_folder": folder,
            "paused": self.var_paused.get(),
            "unsplash_key": self.var_key.get().strip(),
            "theme_mode": self._theme_label_to_value.get(self.theme_seg.get(), "auto"),
            "language": self._lang_label_to_value.get(self.var_lang.get(), "auto"),
            "resolution": self._res_label_to_value.get(self.var_res.get(), "auto"),
            "interval": self._label_to_value.get(self.var_interval.get(), "daily"),
            "change_on_start": self.var_onstart.get(),
            "startup": self.var_startup.get(),
            "keep": keep,
            "queries_dark": [
                line.strip()
                for line in self.txt_dark.get("1.0", "end").splitlines()
                if line.strip()
            ],
            "queries_light": [
                line.strip()
                for line in self.txt_light.get("1.0", "end").splitlines()
                if line.strip()
            ],
        }
        error = self._on_save(values)
        if error:
            self._set_status(error, error=True)
        else:
            self._close()

    def _close(self) -> None:
        try:
            self.destroy()
        finally:
            self._on_close()
