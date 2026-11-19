# -*- coding: utf-8 -*-
"""Fontes de imagens: Unsplash (API) e Bing Photo of the Day."""
from __future__ import annotations

import random

import requests

from . import config

UA = {"User-Agent": config.APP_NAME}


def download(url: str, timeout: int = 30) -> bytes:
    r = requests.get(url, timeout=timeout, headers=UA)
    r.raise_for_status()
    return r.content


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

    photo = random.choice(results)
    url = photo["urls"]["raw"] + "&w=2560&q=80&fit=max"
    return download(url)


def parse_bing_images(payload: dict) -> list[str]:
    """Extrai os URLs das imagens do JSON do Bing."""
    out = []
    for item in payload.get("images") or []:
        u = item.get("url")
        if u:
            out.append("https://www.bing.com" + u)
    return out


def fetch_bing() -> bytes:
    """Foto do dia do Bing (sem API key), tentando a versão 4K."""
    r = requests.get(
        "https://www.bing.com/HPImageArchive.aspx",
        params={"format": "js", "idx": 0, "n": 1, "mkt": "pt-PT"},
        headers=UA,
        timeout=20,
    )
    r.raise_for_status()
    urls = parse_bing_images(r.json())
    if not urls:
        raise RuntimeError("Bing não devolveu imagens")
    url = urls[0]
    try:
        return download(url.replace("1920x1080", "UHD"))
    except requests.RequestException:
        return download(url)
