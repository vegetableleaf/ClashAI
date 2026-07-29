"""Import the current top meta decks from the OFFICIAL Clash Royale API into config/meta_decks.yaml,
so the sim's opponents reflect what's actually played right now.

Data source (sanctioned, no scraping): the official API (https://developer.clashroyale.com) -- top
global players -> their recent BATTLE LOGS -> the 8-card decks both sides used -> tallied by frequency
-> the top N. Needs a FREE API token (IP-locked to where you run this): create one at
developer.clashroyale.com, then set it in the env var named by `sim.api_token_env`
(default CLASHRL_CR_API_TOKEN). Without a token this prints instructions and leaves the curated
config/meta_decks.yaml in place.

Best-effort: the rankings endpoint/season can change; on an error the message says so and the curated
fallback keeps working. Card names are mapped to KB keys (evolutions fold to their base).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


def _name_to_key(name: str) -> str:
    k = name.lower().replace(".", "").replace("'", "")
    return re.sub(r"[ \-]+", "_", k).strip("_")


def _get(url: str, token: str, timeout: float = 20.0):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def import_decks(cfg, limit: int = 100, players: int = 120) -> None:
    from .cards import CardDB
    db = CardDB(cfg)
    token_env = cfg.get("sim", "api_token_env", default="CLASHRL_CR_API_TOKEN")
    token = os.environ.get(token_env, "").strip()
    out_path = Path(cfg.path(cfg.get("sim", "meta_decks_file", default="config/meta_decks.yaml")))
    if not token:
        print(f"[decks-import] no API token. Get a FREE one at https://developer.clashroyale.com "
              f"(create a key locked to THIS machine's public IP), then set env {token_env} and re-run.\n"
              f"  Until then the curated {out_path.name} is used as-is.")
        return
    base = cfg.get("sim", "api_base", default="https://api.clashroyale.com/v1")

    # 1) top global players
    try:
        top = _get(f"{base}/locations/global/rankings/players?limit={players}", token)
        tags = [p["tag"] for p in top.get("items", [])][:players]
    except urllib.error.HTTPError as e:
        print(f"[decks-import] rankings fetch failed (HTTP {e.code}). A 403 = bad token / wrong IP; "
              "a 404 = the endpoint/season moved. Curated decks kept.")
        return
    except Exception as e:  # noqa: BLE001
        print(f"[decks-import] rankings fetch failed: {e!r}. Curated decks kept.")
        return
    if not tags:
        print("[decks-import] no players returned; curated decks kept.")
        return

    # 2) their battle logs -> tally 8-card decks (both sides)
    tally: Counter = Counter()
    seen = 0
    for i, tag in enumerate(tags):
        enc = urllib.parse.quote(tag, safe="")
        try:
            battles = _get(f"{base}/players/{enc}/battlelog", token)
        except Exception:  # noqa: BLE001 -- skip a player we can't read
            continue
        for b in battles:
            for side in ("team", "opponent"):
                for entry in b.get(side, []):
                    keys = []
                    for c in entry.get("cards", []):
                        k = _name_to_key(c.get("name", ""))
                        base_k = k[:-4] if k.endswith("_evo") else k
                        if db.get(base_k):
                            keys.append(base_k)
                    if len(keys) == 8:
                        tally[tuple(sorted(keys))] += 1
                        seen += 1
        if (i + 1) % 20 == 0:
            print(f"[decks-import] scanned {i + 1}/{len(tags)} players, {seen} decks so far...")
        time.sleep(0.12)                                     # be gentle on the API

    if not tally:
        print("[decks-import] no valid decks parsed; curated decks kept.")
        return

    top_decks = tally.most_common(limit)
    lines = ["# Imported from the official Clash Royale API (top-player battle logs).",
             f"# {time.strftime('%Y-%m-%d %H:%M')} -- {len(top_decks)} decks from {len(tags)} players, "
             f"{seen} deck-sightings. Regenerate with `run.py decks-import`.",
             "decks:"]
    for n, (cards, count) in enumerate(top_decks, 1):
        lines.append(f"  - {{name: meta_{n:03d}, weight: {count}, cards: [{', '.join(cards)}]}}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[decks-import] wrote {len(top_decks)} decks -> {out_path} "
          f"(most common: {'/'.join(top_decks[0][0][:3])}... x{top_decks[0][1]})")
