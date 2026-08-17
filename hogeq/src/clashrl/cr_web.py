"""Clash Royale data fetching that does not get blocked.

WHY THIS EXISTS
---------------
Card research in this project kept hitting walls that had nothing to do with the data being
unavailable: Fandom card PAGES return 402 to a plain urllib request (the workaround was to go
through `api.php` for raw wikitext, which works but only covers the wiki), and the community
stat sites that publish balance changes, matchup tables and meta decks -- RoyaleAPI, Deck Shop,
StatsRoyale -- sit behind Cloudflare and simply refuse a scripted GET. So every stat that lives
outside the wiki had to be curated by hand, which is exactly where wrong numbers creep in.

Scrapling (github.com/D4Vinci/Scrapling) fixes the transport half of that. This module wraps it
with the parts a research tool actually needs:

  * ESCALATION, cheapest first. A plain HTTP GET with browser TLS impersonation handles most
    sites; only if that is blocked (403/402/429, a Cloudflare interstitial, or an empty body)
    does it fall back to a real browser via StealthyFetcher, which costs seconds and needs the
    browser binaries from `scrapling install`. Most calls never reach that.
  * AN ON-DISK CACHE, because research re-reads the same page many times while a question is
    refined, and hammering a community site for the same bytes is both rude and a good way to
    get an IP banned. Cached entries are plain files under data/webcache/ keyed by URL hash.
  * WIKITEXT SHORTCUT. For the CR wiki the api.php route is still strictly better than scraping
    rendered HTML -- it returns the `#vardefine` values the card tables are built from, which is
    where the exact per-level numbers live. `wiki_text()` keeps that path.

Nothing here is imported by the bot at runtime; it is a research tool for offline data work
(card curation, balance-change sweeps, meta-deck imports). Keeping it out of the hot path is
deliberate -- the live loop must never depend on the network.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
_WIKI_API = "https://clashroyale.fandom.com/api.php"
_BLOCKED_MARKERS = ("just a moment", "cf-browser-verification", "attention required",
                    "enable javascript and cookies", "access denied")


def _cache_dir(root: Optional[Path] = None) -> Path:
    d = (root or Path(__file__).resolve().parents[2] / "data") / "webcache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(url: str, root: Optional[Path] = None) -> Path:
    return _cache_dir(root) / (hashlib.sha1(url.encode("utf-8")).hexdigest()[:20] + ".json")


def _looks_blocked(html: str) -> bool:
    """Cloudflare (and friends) answer 200 with an interstitial, so status alone is not enough."""
    if not html or len(html) < 400:
        return True
    low = html[:4000].lower()
    return any(m in low for m in _BLOCKED_MARKERS)


def fetch(url: str, max_age_s: float = 86400.0, force_browser: bool = False,
          timeout: float = 30.0) -> dict:
    """Fetch ``url``, escalating only as far as needed. Returns
    ``{"url", "status", "html", "via", "cached"}``; ``html`` is "" when every route failed.

    ``via`` is one of cache | http | stealth | urllib, which is worth logging when a source
    starts needing the expensive route -- that is usually the site tightening its protection.
    """
    cp = _cache_path(url)
    if cp.exists() and not force_browser:
        try:
            hit = json.loads(cp.read_text(encoding="utf-8"))
            if time.time() - float(hit.get("t", 0)) <= max_age_s and hit.get("html"):
                return {**hit, "via": "cache", "cached": True}
        except Exception:  # noqa: BLE001
            pass

    out = {"url": url, "status": 0, "html": "", "via": "none", "cached": False}
    if not force_browser:
        try:
            from scrapling.fetchers import Fetcher
            r = Fetcher.get(url, impersonate="chrome", timeout=timeout)
            html = getattr(r, "html_content", None) or str(getattr(r, "body", "") or "")
            status = int(getattr(r, "status", 0) or 0)
            if status and status < 400 and not _looks_blocked(html):
                out = {"url": url, "status": status, "html": html, "via": "http", "cached": False}
        except Exception:  # noqa: BLE001
            pass

    if not out["html"]:
        # Real browser: solves Cloudflare interstitials/Turnstile. Needs `scrapling install`
        # to have been run once; if the binaries are missing this raises and we fall through.
        try:
            from scrapling.fetchers import StealthyFetcher
            r = StealthyFetcher.fetch(url, headless=True, network_idle=True,
                                      solve_cloudflare=True, timeout=timeout * 1000)
            html = getattr(r, "html_content", None) or str(getattr(r, "body", "") or "")
            if html and not _looks_blocked(html):
                out = {"url": url, "status": int(getattr(r, "status", 200) or 200),
                       "html": html, "via": "stealth", "cached": False}
        except Exception:  # noqa: BLE001
            pass

    if not out["html"]:
        try:                                     # last resort: the plain stdlib path
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                html = r.read().decode("utf-8", "replace")
            if html and not _looks_blocked(html):
                out = {"url": url, "status": 200, "html": html, "via": "urllib", "cached": False}
        except Exception:  # noqa: BLE001
            pass

    if out["html"]:
        try:
            cp.write_text(json.dumps({**out, "t": time.time()}), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    return out


def select(url: str, css: str, text: bool = True, **kw) -> list:
    """Fetch ``url`` and return every match of a CSS selector (text by default).

    Uses Scrapling's Selector, whose ADAPTIVE matching survives the layout churn these
    community sites are prone to -- the reason to parse with it rather than a regex.
    """
    html = fetch(url, **kw)["html"]
    if not html:
        return []
    from scrapling import Selector
    page = Selector(html)
    got = page.css(css)
    return [(g.text or "").strip() if text else g for g in got]


def fetch_raw(url: str, max_age_s: float = 86400.0, timeout: float = 30.0) -> str:
    """The response body VERBATIM -- for JSON/text endpoints, never HTML pages.

    Scrapling parses everything it fetches as an HTML document, so a JSON API answer comes back
    wrapped (`<html><body><p>{...`) with entities re-encoded -- MEASURED on api.php, where the
    wikitext came out corrupted (`<span style='\"color:'>`) and json.loads then failed. API
    endpoints are also not the things that block us: the Fandom 402 applies to PAGE requests,
    while api.php answers a plain urllib GET happily. So raw fetches take the stdlib path and
    Scrapling is reserved for the HTML pages that actually need it.
    """
    cp = _cache_path("RAW::" + url)
    if cp.exists():
        try:
            hit = json.loads(cp.read_text(encoding="utf-8"))
            if time.time() - float(hit.get("t", 0)) <= max_age_s and hit.get("body"):
                return hit["body"]
        except Exception:  # noqa: BLE001
            pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""
    try:
        cp.write_text(json.dumps({"body": body, "t": time.time()}), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return body


def wiki_text(page: str, timeout: float = 30.0) -> str:
    """Raw WIKITEXT of a Clash Royale wiki page via api.php.

    Kept as its own route because it is strictly better than scraping the rendered page: the
    per-level numbers this project curates from (`{{#vardefine:hp_11|...}}` and the attribute
    tables) exist in the source and are formatted away in the HTML. Fandom PAGE requests answer
    402 to scripts; api.php does not.
    """
    q = urllib.parse.urlencode({"action": "parse", "page": page, "prop": "wikitext",
                                "format": "json", "formatversion": "2"})
    raw = fetch_raw(f"{_WIKI_API}?{q}", timeout=timeout)
    if not raw:
        return ""
    try:
        return json.loads(raw)["parse"]["wikitext"]
    except Exception:  # noqa: BLE001
        return ""


def card_stats(card: str) -> dict:
    """`{vardefine_name: value}` for one card -- the per-level table the wiki is built from."""
    import re
    wt = wiki_text(card)
    return {m.group(1).strip(): m.group(2).strip()
            for m in re.finditer(r"\{\{#vardefine:([^|}]+)\|([^}]*)\}\}", wt)}
