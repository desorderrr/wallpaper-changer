# -*- coding: utf-8 -*-
"""Image sources: Unsplash, Wallhaven and Bing Photo of the Day.

Every function takes ``want_dark`` and tries several candidates until it
finds one with the requested tone (checked by luminance).
"""

from __future__ import annotations

import random

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import config, history, tone
from .i18n import t

UA = {"User-Agent": config.APP_NAME}
MAX_TONE_TRIES = 6

_session: requests.Session | None = None


def _http_get(url: str, **kwargs) -> requests.Response:
    """GET with a shared session, retries and exponential backoff.

    Transient errors (network, 429, 5xx) are retried instead of aborting
    the whole source cycle.
    """
    global _session
    if _session is None:
        _session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
        _session.headers.update(UA)
    return _session.get(url, **kwargs)


def download(url: str, timeout: int = 30) -> bytes:
    r = _http_get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def _acceptable(data: bytes, want_dark: bool) -> bool:
    """Valid image, with the requested tone, not used yet."""
    try:
        if not tone.tone_matches(tone.mean_luminance(data), want_dark):
            return False
    except Exception:  # noqa: BLE001 - invalid image counts as not matching
        return False
    return not history.is_duplicate(data)


# ---------------------------------------------------------------------------
# Unsplash
# ---------------------------------------------------------------------------
def fetch_unsplash(want_dark: bool) -> bytes:
    """Random Unsplash photo with the requested tone (uses the settings key)."""
    key = config.get("unsplash_key") or ""
    if not key:
        raise RuntimeError(
            t("Sem API key do Unsplash (gratuita em unsplash.com/developers)")
        )

    queries = config.get("queries_dark") if want_dark else config.get("queries_light")
    query = random.choice(queries or ["wallpaper"])
    color = "black" if want_dark else "white"

    def search(extra: dict) -> list:
        r = _http_get(
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
            raise RuntimeError(t("API key do Unsplash inválida"))
        if r.status_code == 403:
            raise RuntimeError(t("Limite de pedidos do Unsplash excedido"))
        r.raise_for_status()
        return r.json().get("results") or []

    results = search({"color": color})
    if not results:
        # retry without the colour filter; luminance checking guarantees the tone
        results = search({})
    if not results:
        raise RuntimeError(t("Sem resultados no Unsplash para: %s") % query)

    random.shuffle(results)
    for photo in results[:MAX_TONE_TRIES]:
        try:
            data = download(photo["urls"]["raw"] + "&w=2560&q=80&fit=max")
        except requests.RequestException:
            continue
        if _acceptable(data, want_dark):
            return data
    raise RuntimeError(
        t("Unsplash não devolveu fotos novas com o tom pedido; tenta de novo")
    )


# ---------------------------------------------------------------------------
# Bing Photo of the Day
# ---------------------------------------------------------------------------
def parse_bing_images(payload: dict) -> list[str]:
    """Extract image URLs from the Bing JSON payload."""
    out = []
    for item in payload.get("images") or []:
        u = item.get("url")
        if u:
            out.append("https://www.bing.com" + u)
    return out


def _bing_candidates(payload: dict) -> list[tuple[str | None, str]]:
    """(thumbnail, full image) for each day, at suitable sizes."""
    out: list[tuple[str | None, str]] = []
    for item in payload.get("images") or []:
        base = item.get("urlbase")
        url = item.get("url") or ""
        if base:
            thumb = "https://www.bing.com" + base + "_480x270.jpg"
            full = "https://www.bing.com" + base + "_1920x1080.jpg"
        elif url:
            full = ("https://www.bing.com" + url) if url.startswith("/") else url
            thumb = None
        else:
            continue
        out.append((thumb, full))
    return out


def fetch_bing(want_dark: bool = True) -> bytes:
    """Bing photo of the day (no API key), with variety from recent days."""
    r = _http_get(
        "https://www.bing.com/HPImageArchive.aspx",
        params={"format": "js", "idx": 0, "n": 8, "mkt": "pt-PT"},
        timeout=20,
    )
    r.raise_for_status()
    entries = _bing_candidates(r.json())
    if not entries:
        raise RuntimeError(t("Bing não devolveu imagens"))

    head, tail = entries[:1], entries[1:]
    random.shuffle(tail)
    for thumb, full in head + tail:
        try:
            # check the thumbnail first (fast) for tone and repetition
            if thumb and not _acceptable(download(thumb), want_dark):
                continue
            try:
                data = (
                    download(full.replace("1920x1080", "UHD"))
                    if "1920x1080" in full
                    else download(full)
                )
            except requests.RequestException:
                data = download(full)
        except requests.RequestException:
            continue
        if _acceptable(data, want_dark):
            return data
    raise RuntimeError(t("Bing não tem imagens novas desse tom nos últimos dias"))


# ---------------------------------------------------------------------------
# Wallhaven (no API key; uses the public search API)
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
            r = _http_get(api, params={**base, **extra}, timeout=20)
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
                if thumb and not _acceptable(download(thumb), want_dark):
                    continue
                image = download(url)
            except requests.RequestException:
                continue
            if _acceptable(image, want_dark):
                return image
    raise RuntimeError(t("Wallhaven não devolveu imagens novas com o tom pedido"))
