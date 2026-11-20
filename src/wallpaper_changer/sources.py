# -*- coding: utf-8 -*-
"""Fontes de imagens: Unsplash, Wallhaven e Bing Photo of the Day.

Todas as funções recebem ``want_dark`` e tentam várias candidatas até
encontrar uma com o tom pedido (verificação por luminância).
"""
from __future__ import annotations

import random

import requests

from . import config, tone

UA = {"User-Agent": config.APP_NAME}
MAX_TONE_TRIES = 6


def download(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, timeout=timeout, headers=UA)
    r.raise_for_status()
    return r.content


def _matches(data: bytes, want_dark: bool) -> bool:
    try:
        return tone.tone_matches(tone.mean_luminance(data), want_dark)
    except Exception:  # noqa: BLE001 - imagem inválida conta como não compatível
        return False


# ---------------------------------------------------------------------------
# Unsplash
# ---------------------------------------------------------------------------
def fetch_unsplash(want_dark: bool) -> bytes:
    """Foto aleatória do Unsplash com o tom pedido (usa a API key das settings)."""
    key = config.get("unsplash_key") or ""
    if not key:
        raise RuntimeError(
            "Sem API key do Unsplash (gratuita em unsplash.com/developers)"
        )

    queries = config.get("queries_dark") if want_dark else config.get("queries_light")
    query = random.choice(queries or ["wallpaper"])
    color = "black" if want_dark else "white"

    def search(extra: dict) -> list:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={
                "query": query,
                "orientation": "landscape",
                "per_page": 30,
                "content_filter": "high",
                **extra,
            },
            headers={"Authorization": "Client-ID %s" % key},
            timeout=20,
        )
        if r.status_code == 401:
            raise RuntimeError("API key do Unsplash inválida")
        if r.status_code == 403:
            raise RuntimeError("Limite de pedidos do Unsplash excedido")
        r.raise_for_status()
        return r.json().get("results") or []

    results = search({"color": color})
    if not results:
        # repete sem o filtro de cor; a verificação de luminância garante o tom
        results = search({})
    if not results:
        raise RuntimeError("Sem resultados no Unsplash para: %s" % query)

    random.shuffle(results)
    for photo in results[:MAX_TONE_TRIES]:
        try:
            data = download(photo["urls"]["raw"] + "&w=2560&q=80&fit=max")
        except requests.RequestException:
            continue
        if _matches(data, want_dark):
            return data
    raise RuntimeError("Unsplash não devolveu fotos com o tom pedido; tenta de novo")


# ---------------------------------------------------------------------------
# Bing Photo of the Day
# ---------------------------------------------------------------------------
def parse_bing_images(payload: dict) -> list[str]:
    """Extrai os URLs das imagens do JSON do Bing."""
    out = []
    for item in payload.get("images") or []:
        u = item.get("url")
        if u:
            out.append("https://www.bing.com" + u)
    return out


def fetch_bing(want_dark: bool = True) -> bytes:
    """Foto do dia do Bing (sem API key), com variedade dos últimos dias."""
    r = requests.get(
        "https://www.bing.com/HPImageArchive.aspx",
        params={"format": "js", "idx": 0, "n": 8, "mkt": "pt-PT"},
        headers=UA,
        timeout=20,
    )
    r.raise_for_status()
    urls = parse_bing_images(r.json())
    if not urls:
        raise RuntimeError("Bing não devolveu imagens")

    rest = urls[1:]
    random.shuffle(rest)
    candidates = urls[:1] + rest[:2]
    for url in candidates:
        try:
            data = download(url.replace("1920x1080", "UHD"))
        except requests.RequestException:
            data = download(url)
        if _matches(data, want_dark):
            return data
    raise RuntimeError("Bing não tem imagens desse tom nos últimos dias")


# ---------------------------------------------------------------------------
# Wallhaven (sem API key; usa a API pública de pesquisa)
# ---------------------------------------------------------------------------
def fetch_wallhaven(want_dark: bool = True) -> bytes:
    api = "https://wallhaven.cc/api/v1/search"
    base = {
        "sorting": "random",
        "atleast": "2560x1440",
        "ratios": "landscape",
        "purity": "100",
        "categories": "111",
    }
    color = "000000" if want_dark else "ffffff"

    for extra in ({"colors": color}, {}):
        try:
            r = requests.get(
                api, params={**base, **extra}, headers=UA, timeout=20
            )
            r.raise_for_status()
            data = r.json().get("data") or []
        except requests.RequestException:
            data = []
        random.shuffle(data)
        for item in data[:MAX_TONE_TRIES]:
            url = item.get("path")
            if not url:
                continue
            thumb = (item.get("thumbs") or {}).get("large")
            try:
                if thumb and not _matches(download(thumb), want_dark):
                    continue
                image = download(url)
            except requests.RequestException:
                continue
            if _matches(image, want_dark):
                return image
    raise RuntimeError("Wallhaven não devolveu imagens com o tom pedido")
