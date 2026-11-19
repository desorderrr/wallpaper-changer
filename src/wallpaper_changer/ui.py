# -*- coding: utf-8 -*-
"""Janela de definições moderna (customtkinter)."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Callable

import customtkinter as ctk

from .assets import make_icon_image
from .config import APP_VERSION, INTERVAL_LABELS, get
from .platform import platform

THEME_LABELS = {
    "Seguir o tema do sistema": "auto",
    "Sempre escuro": "dark",
    "Sempre claro": "light",
}
THEME_TO_LABEL = {v: k for k, v in THEME_LABELS.items()}


class SettingsWindow(ctk.CTkToplevel):
    """Janela com três separadores: Geral, Pesquisas e Sobre."""

    def __init__(
        self,
        master,
        *,
        on_save: Callable[[dict], str | None],
        on_close: Callable[[], None],
        change_wallpaper: Callable[[bool], tuple[bool, str]],
        status_text: Callable[[], str],
        open_folder: Callable[[], None],
    ):
        super().__init__(master)
        self._on_save = on_save
        self._on_close = on_close
        self._change = change_wallpaper
        self._status_q: queue.Queue = queue.Queue()

        self.title("WallpaperChanger — Definições")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.grid_columnconfigure(0, weight=1)

        # --- Cabeçalho --------------------------------------------------
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
            titles, text="WallpaperChanger",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w")
        self.header_status = ctk.CTkLabel(
            titles, text=status_text(), text_color=("gray40", "gray60"),
            font=ctk.CTkFont(size=12), anchor="w", justify="left",
        )
        self.header_status.pack(anchor="w", fill="x")

        # --- Separadores -------------------------------------------------
        self.tabs = ctk.CTkTabview(self, width=660, height=420)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        for name in ("Geral", "Pesquisas", "Sobre"):
            self.tabs.add(name)

        self._build_general(self.tabs.tab("Geral"))
        self._build_queries(self.tabs.tab("Pesquisas"))
        self._build_about(self.tabs.tab("Sobre"), open_folder)

        # --- Rodapé -------------------------------------------------------
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 16))

        self.status_label = ctk.CTkLabel(
            footer, text="Pronto.", text_color=("gray40", "gray60"),
            anchor="w", justify="left", wraplength=330,
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.save_btn = ctk.CTkButton(
            footer, text="Gravar", width=100, command=self._save
        )
        self.save_btn.pack(side="right")
        ctk.CTkButton(
            footer, text="Cancelar", width=90, fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"), command=self._close,
        ).pack(side="right", padx=8)
        self.change_btn = ctk.CTkButton(
            footer, text="Mudar agora", width=110,
            fg_color=("gray75", "gray25"), hover_color=("gray65", "gray35"),
            command=self._change_now,
        )
        self.change_btn.pack(side="right")

        self._center()
        self.after(120, self._raise)
        self.after(300, self._poll)

    # ------------------------------------------------------------------
    # Construção dos separadores
    # ------------------------------------------------------------------
    def _build_general(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)

        # Fontes
        box = ctk.CTkFrame(tab)
        box.grid(row=0, column=0, sticky="ew", pady=(8, 6), padx=4)
        ctk.CTkLabel(
            box, text="Fontes de imagens",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 2))

        self.var_unsplash = tk.BooleanVar(value=bool(get("use_unsplash")))
        self.var_bing = tk.BooleanVar(value=bool(get("use_bing")))
        ctk.CTkCheckBox(box, text="Unsplash", variable=self.var_unsplash).grid(
            row=1, column=0, sticky="w", padx=12, pady=2)
        ctk.CTkCheckBox(
            box, text="Bing Photo of the Day (sem registo)", variable=self.var_bing,
        ).grid(row=1, column=1, sticky="w", padx=12, pady=2)

        self.var_key = tk.StringVar(value=get("unsplash_key") or "")
        key_entry = ctk.CTkEntry(
            box, textvariable=self.var_key, width=590,
            placeholder_text="Cola aqui a API key do Unsplash…",
        )
        key_entry.grid(row=2, column=0, columnspan=2, sticky="ew",
                       padx=12, pady=(8, 0))
        ctk.CTkLabel(
            box,
            text="Gratuita em unsplash.com/developers — só necessária para o Unsplash.",
            text_color=("gray45", "gray55"), font=ctk.CTkFont(size=11),
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(2, 10))

        # Tom
        box2 = ctk.CTkFrame(tab)
        box2.grid(row=1, column=0, sticky="ew", pady=6, padx=4)
        ctk.CTkLabel(
            box2, text="Tom dos wallpapers",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        self.theme_seg = ctk.CTkSegmentedButton(
            box2, values=list(THEME_LABELS), width=560,
        )
        self.theme_seg.set(
            THEME_TO_LABEL.get(get("theme_mode"), "Seguir o tema do sistema")
        )
        self.theme_seg.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))

        # Intervalo + opções
        box3 = ctk.CTkFrame(tab)
        box3.grid(row=2, column=0, sticky="ew", pady=6, padx=4)
        ctk.CTkLabel(
            box3, text="Intervalo de mudança",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self._label_to_value = {label: value for value, label in INTERVAL_LABELS}
        self._value_to_label = {value: label for value, label in INTERVAL_LABELS}
        self.var_interval = tk.StringVar(
            value=self._value_to_label.get(get("interval"), "Diário")
        )
        ctk.CTkOptionMenu(
            box3, values=list(self._label_to_value), variable=self.var_interval,
            width=220,
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        self.var_startup = tk.BooleanVar(value=platform.startup_enabled())
        self.var_onstart = tk.BooleanVar(value=bool(get("change_on_start")))
        ctk.CTkCheckBox(
            box3, text="Iniciar com o sistema", variable=self.var_startup,
        ).grid(row=2, column=0, sticky="w", padx=12, pady=2)
        ctk.CTkCheckBox(
            box3, text="Mudar wallpaper quando o programa arranca",
            variable=self.var_onstart,
        ).grid(row=3, column=0, sticky="w", padx=12, pady=2)

        keep_row = ctk.CTkFrame(box3, fg_color="transparent")
        keep_row.grid(row=4, column=0, sticky="w", padx=12, pady=(8, 12))
        ctk.CTkLabel(keep_row, text="Guardar as últimas").pack(side="left")
        self.var_keep = tk.StringVar(value=str(get("keep") or 20))
        ctk.CTkEntry(keep_row, textvariable=self.var_keep, width=60).pack(
            side="left", padx=6)
        ctk.CTkLabel(keep_row, text="imagens").pack(side="left")

    def _build_queries(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab, text="Pesquisas no Unsplash (uma por linha)",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(10, 2))
        ctk.CTkLabel(
            tab,
            text="Usadas para escolher fotos com o tom certo em cada modo.",
            text_color=("gray45", "gray55"), font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))

        ctk.CTkLabel(tab, text="Modo escuro:", anchor="w").grid(
            row=2, column=0, sticky="w", padx=8)
        self.txt_dark = ctk.CTkTextbox(tab, height=95, width=600)
        self.txt_dark.grid(row=3, column=0, sticky="ew", padx=8, pady=(2, 10))
        self.txt_dark.insert("1.0", "\n".join(get("queries_dark")))

        ctk.CTkLabel(tab, text="Modo claro:", anchor="w").grid(
            row=4, column=0, sticky="w", padx=8)
        self.txt_light = ctk.CTkTextbox(tab, height=95, width=600)
        self.txt_light.grid(row=5, column=0, sticky="ew", padx=8, pady=(2, 10))
        self.txt_light.insert("1.0", "\n".join(get("queries_light")))

    def _build_about(self, tab, open_folder: Callable[[], None]) -> None:
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tab, text="WallpaperChanger v%s" % APP_VERSION,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(14, 4))
        ctk.CTkLabel(
            tab, justify="left", anchor="w", wraplength=600,
            text=(
                "Muda o wallpaper automaticamente, sempre a condizer com o "
                "tema do sistema: modo escuro → wallpapers escuros, modo "
                "claro → wallpapers claros.\n\n"
                "Fontes: Unsplash (necessita API key gratuita) e Bing Photo "
                "of the Day (sem registo).\n\n"
                "Plataformas: Windows 11, macOS e Linux.\n\n"
                "As imagens ficam guardadas na tua pasta de dados."
            ),
        ).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        ctk.CTkButton(
            tab, text="Abrir pasta de imagens", width=180,
            command=open_folder,
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(12, 10))

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def _center(self) -> None:
        self.update_idletasks()
        w, h = 700, 660
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

    def _change_now(self) -> None:
        if str(self.change_btn.cget("state")) == "disabled":
            return
        self.change_btn.configure(state="disabled")
        self._set_status("A procurar um wallpaper novo…")
        threading.Thread(target=self._change_worker, daemon=True).start()

    def _change_worker(self) -> None:
        try:
            ok, msg = self._change(True)
        except Exception as e:  # noqa: BLE001 - mostrar qualquer falha ao utilizador
            ok, msg = False, "Erro inesperado: %r" % e
        self._status_q.put((ok, msg))

    def _poll(self) -> None:
        try:
            while True:
                ok, msg = self._status_q.get_nowait()
                self._set_status(msg, error=not ok)
                self.change_btn.configure(state="normal")
                try:
                    self.header_status.configure(text=self._header_text())
                except Exception:
                    pass
        except queue.Empty:
            pass
        try:
            self.after(300, self._poll)
        except tk.TclError:
            pass

    def _header_text(self) -> str:
        # atualiza resumo do cabeçalho; mantém o texto original se falhar
        try:
            return self._header_provider()
        except Exception:
            return ""

    def set_header_provider(self, provider: Callable[[], str]) -> None:
        self._header_provider = provider

    _header_provider = staticmethod(lambda: "")

    def _save(self) -> None:
        try:
            keep = max(5, min(200, int(self.var_keep.get())))
        except (ValueError, tk.TclError):
            self._set_status("O número de imagens a guardar deve ser 5–200.", error=True)
            return
        values = {
            "use_unsplash": self.var_unsplash.get(),
            "use_bing": self.var_bing.get(),
            "unsplash_key": self.var_key.get().strip(),
            "theme_mode": THEME_LABELS.get(
                self.theme_seg.get(), "auto"),
            "interval": self._label_to_value.get(self.var_interval.get(), "daily"),
            "change_on_start": self.var_onstart.get(),
            "startup": self.var_startup.get(),
            "keep": keep,
            "queries_dark": [
                l.strip() for l in
                self.txt_dark.get("1.0", "end").splitlines() if l.strip()
            ],
            "queries_light": [
                l.strip() for l in
                self.txt_light.get("1.0", "end").splitlines() if l.strip()
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
