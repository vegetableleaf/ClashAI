"""Download one reference picture per card, so cards can be RECOGNISED instead of renamed by hand.

Source: the same Clash Royale Fandom wiki that `card_import.py` already reads, via the
same MediaWiki API. Each card page carries its card picture as the page image; the file
itself is served from the wiki's image host. Images land in `templates/cardart/<key>.png`
(and `<key>_evo.png` for evolutions) and are used offline from then on.

Run once, and again after new cards are released:
    .\\.venv\\Scripts\\python.exe run.py cards-art
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

WIKI = "https://clashroyale.fandom.com/api.php"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ClashBotResearch/1.0"
THUMB = 220                      # px wide; big enough to match against, small enough to store
BATCH = 40                       # titles per API call


def _api(params: dict) -> dict:
    url = WIKI + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def art_dir(cfg) -> Path:
    return Path(cfg.path(cfg.get("hand", "art_dir", default="templates/cardart")))


def wanted_titles(db) -> Dict[str, str]:
    """{card key -> wiki page title}. Evolutions live on a `<Card>/Evolution` subpage."""
    out: Dict[str, str] = {}
    for key, card in db.cards.items():
        display = card.get("display")
        if not display:
            continue
        if key.endswith("_evo"):
            base = db.cards.get(key[:-4], {})
            if not base.get("display"):
                continue
            out[key] = f"{base['display']}/Evolution"
        else:
            out[key] = str(display)
    return out


def import_card_art(cfg, only_missing: bool = True, limit: Optional[int] = None) -> None:
    from .cards import CardDB
    db = CardDB(cfg)
    out_dir = art_dir(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)

    titles = wanted_titles(db)
    if only_missing:
        titles = {k: t for k, t in titles.items() if not (out_dir / f"{k}.png").exists()}
    if limit:
        titles = dict(list(titles.items())[:limit])
    if not titles:
        print(f"[cards-art] all pictures are already in {out_dir}. "
              "--refresh re-downloads them.")
        return
    print(f"[cards-art] fetching {len(titles)} card pictures from the Fandom wiki into {out_dir}",
          flush=True)

    by_title = {t: k for k, t in titles.items()}
    items: List[str] = list(titles.values())
    got = missing = failed = 0
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        try:
            d = _api({"action": "query", "titles": "|".join(chunk), "prop": "pageimages",
                      "piprop": "thumbnail|name", "pithumbsize": THUMB, "redirects": 1})
        except Exception as exc:                            # noqa: BLE001
            print(f"[cards-art] request failed: {exc!r}")
            break
        # a redirect changes the title, so map the answer back through the redirect table
        redirects = {r["to"]: r["from"] for r in d.get("query", {}).get("redirects", [])}
        norm = {n["to"]: n["from"] for n in d.get("query", {}).get("normalized", [])}
        for page in d.get("query", {}).get("pages", {}).values():
            title = page.get("title", "")
            orig = redirects.get(title, title)
            orig = norm.get(orig, orig)
            key = by_title.get(orig) or by_title.get(title)
            if key is None:
                continue
            src = (page.get("thumbnail") or {}).get("source")
            if not src:
                missing += 1
                continue
            try:
                data = _fetch(src)
            except Exception:                               # noqa: BLE001
                failed += 1
                continue
            (out_dir / f"{key}.png").write_bytes(data)
            got += 1
        print(f"[cards-art] {min(i + BATCH, len(items))}/{len(items)} requested, {got} downloaded",
              flush=True)
        time.sleep(0.2)                                     # be gentle on the wiki

    print(f"[cards-art] done: {got} pictures downloaded, {missing} pages without a picture, "
          f"{failed} downloads failed. Folder: {out_dir}")
    if missing:
        print("[cards-art] cards without a wiki picture are skipped during deck recognition.")
