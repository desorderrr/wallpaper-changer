# -*- coding: utf-8 -*-
"""Traduções da interface (português como base, inglês disponível).

As strings em português são as chaves do catálogo: quando o idioma ativo
é o português (ou a chave não existe), devolve-se o próprio texto. Sem
ficheiros .mo — o catálogo vive aqui e é empacotado sem configuração extra.
"""

from __future__ import annotations

import ctypes
import os
import sys

LANGUAGES = ("pt", "en")

CATALOGS: dict[str, dict[str, str]] = {
    "pt": {},
    "en": {
        # --- estado / tema -------------------------------------------------
        "escuro": "dark",
        "claro": "light",
        "segue o sistema": "follows the system",
        "sempre escuro": "always dark",
        "sempre claro": "always light",
        "Tema atual: %s (%s)": "Current theme: %s (%s)",
        "mudanças automáticas em pausa": "automatic changes paused",
        "última fonte: %s": "last source: %s",
        "última troca: %s": "last change: %s",
        # --- troca de wallpaper -------------------------------------------
        "Já existe uma troca de wallpaper em curso.": "A wallpaper change is already in progress.",
        "Mudanças automáticas em pausa.": "Automatic changes are paused.",
        "Nenhuma fonte ativa. Ativa o Unsplash, o Bing ou o Wallhaven.": "No source is enabled. Enable Unsplash, Bing or Wallhaven.",
        "%s devolveu uma imagem com o tom errado": "%s returned an image with the wrong tone",
        "%s devolveu um wallpaper repetido": "%s returned a repeated wallpaper",
        "Não consegui obter uma imagem %s agora. %s": "Could not get a %s image right now. %s",
        "Wallpaper %s aplicado (%s).": "Wallpaper %s applied (%s).",
        "Wallpaper aplicado.": "Wallpaper applied.",
        "Não consegui aplicar o wallpaper: %s": "Could not apply the wallpaper: %s",
        "Não consegui alterar o arranque automático do sistema.": "Could not change the system startup setting.",
        # --- sugestões (pré-visualização) ---------------------------------
        "%s: tom errado": "%s: wrong tone",
        "%s: wallpaper já usado": "%s: wallpaper already used",
        "Sugestão do %s (tom %s).": "Suggestion from %s (%s tone).",
        "Não consegui obter uma sugestão. %s": "Could not get a suggestion. %s",
        # --- bandeja (menu e notificações) --------------------------------
        "Mudar agora": "Change now",
        "Pausar mudanças automáticas": "Pause automatic changes",
        "Intervalo": "Interval",
        "Tema dos wallpapers": "Wallpaper theme",
        "Seguir o tema do sistema": "Follow the system theme",
        "Sempre escuro": "Always dark",
        "Sempre claro": "Always light",
        "Fontes": "Sources",
        "Wallhaven (sem key)": "Wallhaven (no key)",
        "Iniciar com o sistema": "Start with the system",
        "Mudar wallpaper ao arrancar o programa": "Change wallpaper when the app starts",
        "Definições...": "Settings...",
        "Abrir pasta de imagens": "Open image folder",
        "Esquecer wallpapers usados": "Forget used wallpapers",
        "Sair": "Quit",
        "Arranque com o sistema: %s": "Start with the system: %s",
        "Mudanças automáticas: %s": "Automatic changes: %s",
        "EM PAUSA": "PAUSED",
        "ATIVAS": "ACTIVE",
        "Não consegui alterar o arranque automático.": "Could not change the startup setting.",
        "Histórico de repetições esquecido.": "Wallpaper history forgotten.",
        "O WallpaperChanger já está em execução.\n\n"
        "Procura o ícone (círculo meio-escuro / meio-claro) na bandeja "
        "do sistema.": "WallpaperChanger is already running.\n\n"
        "Look for the icon (half-dark / half-light circle) in the "
        "system tray.",
        "Não consegui iniciar a bandeja do sistema. No Linux instala "
        "python-xlib (pip) ou python3-gi + gir1.2-gtk-3.0.": "Could not start the system tray. On Linux install python-xlib "
        "(pip) or python3-gi + gir1.2-gtk-3.0.",
        "Não consegui iniciar a bandeja do sistema: %s": "Could not start the system tray: %s",
        # --- intervalos ----------------------------------------------------
        "Apenas ao iniciar": "Only at startup",
        "Cada 5 minutos": "Every 5 minutes",
        "Cada 10 minutos": "Every 10 minutes",
        "Cada 15 minutos": "Every 15 minutes",
        "Cada 30 minutos": "Every 30 minutes",
        "Cada 1 hora": "Every hour",
        "Cada 2 horas": "Every 2 hours",
        "Cada 3 horas": "Every 3 hours",
        "Cada 6 horas": "Every 6 hours",
        "Cada 12 horas": "Every 12 hours",
        "Diário": "Daily",
        # --- janela de definições -----------------------------------------
        "WallpaperChanger — Definições": "WallpaperChanger — Settings",
        "Geral": "General",
        "Pré-visualizar": "Preview",
        "Pesquisas": "Queries",
        "Sobre": "About",
        "Fontes de imagens": "Image sources",
        "Bing (foto do dia)": "Bing (photo of the day)",
        "Podes escolher só uma fonte ou combinar várias.": "You can pick a single source or combine several.",
        "Cola aqui a API key do Unsplash…": "Paste your Unsplash API key here…",
        "API key gratuita em unsplash.com/developers — só para o Unsplash. "
        "O Wallhaven e o Bing não precisam.": "Free API key at unsplash.com/developers — for Unsplash only. "
        "Wallhaven and Bing don't need one.",
        "Tom dos wallpapers": "Wallpaper tone",
        "Intervalo de mudança": "Change interval",
        "Mudar wallpaper quando o programa arranca": "Change wallpaper when the app starts",
        'Pausar mudanças automáticas (o "Mudar agora" continua a funcionar)': 'Pause automatic changes ("Change now" keeps working)',
        "Guardar as últimas": "Keep the last",
        "imagens": "images",
        "Idioma": "Language",
        "Automático": "Automatic",
        "Português": "Português",
        "Pré-visualização": "Preview",
        "Atualizar": "Refresh",
        'Ainda sem imagens. Usa "Nova sugestão".': 'No images yet. Use "New suggestion".',
        "Nova sugestão": "New suggestion",
        "Aplicar no ambiente de trabalho": "Apply to desktop",
        "Sem imagens guardadas ainda.": "No saved images yet.",
        "Não consegui abrir esta imagem.": "Could not open this image.",
        "A procurar uma sugestão…": "Looking for a suggestion…",
        "A aplicar…": "Applying…",
        "A procurar um wallpaper novo…": "Looking for a new wallpaper…",
        "Pronto.": "Ready.",
        "Gravar": "Save",
        "Cancelar": "Cancel",
        "Pesquisas no Unsplash (uma por linha)": "Unsplash queries (one per line)",
        "Usadas para escolher fotos com o tom certo em cada modo.": "Used to pick photos with the right tone for each mode.",
        "Modo escuro:": "Dark mode:",
        "Modo claro:": "Light mode:",
        "Histórico de wallpapers usados esquecido.": "Wallpaper history forgotten.",
        "Histórico esquecido — as imagens podem repetir-se.": "History forgotten: images may repeat.",
        "O número de imagens a guardar deve ser 5–200.":  # noqa: RUF001
        "The number of images to keep must be 5-200.",
        "Erro inesperado: %r": "Unexpected error: %r",
        "mudanças em pausa": "changes paused",
        "Muda o wallpaper automaticamente, sempre a condizer com o "
        "tema do sistema: modo escuro → wallpapers escuros, modo "
        "claro → wallpapers claros.\n\n"
        "Fontes: Unsplash (API key gratuita), Wallhaven (sem key) e "
        "Bing Photo of the Day (sem registo).\n\n"
        "Os wallpapers já usados ficam guardados num histórico — a app "
        "nunca repete uma imagem (podes esquecer o histórico aqui em baixo).\n\n"
        "Plataformas: Windows 11, macOS e Linux.": "Changes the wallpaper automatically, always matching the "
        "system theme: dark mode → dark wallpapers, light mode → "
        "light wallpapers.\n\n"
        "Sources: Unsplash (free API key), Wallhaven (no key) and "
        "Bing Photo of the Day (no sign-up).\n\n"
        "Used wallpapers are kept in a history — the app never "
        "repeats an image (you can forget the history below).\n\n"
        "Platforms: Windows 11, macOS and Linux.",
        # --- fontes de imagens --------------------------------------------
        "Sem API key do Unsplash (gratuita em unsplash.com/developers)": "No Unsplash API key (free at unsplash.com/developers)",
        "API key do Unsplash inválida": "Invalid Unsplash API key",
        "Limite de pedidos do Unsplash excedido": "Unsplash request limit exceeded",
        "Sem resultados no Unsplash para: %s": "No Unsplash results for: %s",
        "Unsplash não devolveu fotos novas com o tom pedido; tenta de novo": "Unsplash returned no new photos with the requested tone; "
        "try again",
        "Bing não devolveu imagens": "Bing returned no images",
        "Bing não tem imagens novas desse tom nos últimos dias": "Bing has no new images with that tone in the last few days",
        "Wallhaven não devolveu imagens novas com o tom pedido": "Wallhaven returned no new images with the requested tone",
        # --- plataforma ---------------------------------------------------
        "Não consegui definir o wallpaper neste ambiente "
        "(XDG_CURRENT_DESKTOP=%r). %s": "Could not set the wallpaper in this environment "
        "(XDG_CURRENT_DESKTOP=%r). %s",
        "osascript falhou: %s": "osascript failed: %s",
        "SystemParametersInfoW falhou": "SystemParametersInfoW failed",
    },
}

_current = "pt"


def t(text: str) -> str:
    """Traduz uma string de interface para o idioma atual."""
    return CATALOGS.get(_current, {}).get(text, text)


def set_language(lang: str) -> None:
    """Escolhe o idioma ativo (valores em LANGUAGES)."""
    global _current
    if lang in CATALOGS:
        _current = lang


def current_language() -> str:
    return _current


def detect_system_language() -> str:
    """Idioma da interface do sistema: 'pt' se português, senão 'en'."""
    if sys.platform == "win32":
        try:
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if langid & 0x3FF == 0x16:  # LANG_PORTUGUESE
                return "pt"
            return "en"
        except Exception:  # noqa: BLE001 - a deteção é best-effort
            pass
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var) or ""
        base = val.split(".")[0].split("_")[0].split("-")[0].lower()
        if base:
            return base if base in CATALOGS else "en"
    return "en"


def apply_language() -> None:
    """Aplica o idioma das settings (auto -> deteta o do sistema)."""
    from . import config  # import local para evitar ciclo

    mode = config.get("language") or "auto"
    set_language(detect_system_language() if mode == "auto" else mode)
