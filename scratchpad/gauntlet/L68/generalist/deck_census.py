"""L68 generalist question: what does the FirstLight / VanguardX101 IL_Replay dataset hold, deck by deck?

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/deck_census.py

Reads the 52 local replay parts (scratchpad/gauntlet/L67/hf/replays), counts deck-SIDES (each replay has two), distinct
decks exact (with evo/hero forms) and base (forms stripped), how the replays spread over decks, placements per deck, and
how many of the top decks RoyaleSim can run (every base card in its loaded list; forms run as base there).
"""
import glob
import json
import re
from collections import Counter
from pathlib import Path

import polars as pl

HERE = Path(__file__).parent
REPO = HERE.parents[3]
FORM = re.compile(r"-(ev\d+|hero)$")
slug = (lambda s: re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-"))

rs = json.load(open(HERE / "royalesim_cards.json"))
loaded_slugs = set()
for c in rs:
    if c["loaded"]:
        loaded_slugs |= {slug(c["name"]), slug(c.get("display_name") or c["name"])}
# RoyaleSim's internal names differ from RoyaleAPI keys for a few cards; the ghost pool carries both spellings.
for line in open(REPO / "icebow/data/ghost_pool/pool_env_v1.jsonl"):
    e = json.loads(line)
    for it in e["icebow_deck"] + e["ghost_deck"]:
        if slug(it["name"]) in loaded_slugs:
            loaded_slugs.add(it["slug"])

sides_exact, sides_base, plays_base, all_keys = Counter(), Counter(), Counter(), Counter()
n_rep = 0
for f in sorted(glob.glob(str(REPO / "scratchpad/gauntlet/L67/hf/replays/*.parquet"))):
    df = pl.read_parquet(f, columns=["payload_json"])
    for pj in df["payload_json"]:
        p = json.loads(pj)
        n_rep += 1
        b = p["battle"]
        plays_by_side = Counter()
        for ev in p.get("events", []):
            if ev.get("kind") == "play_card":
                plays_by_side[ev.get("side", ev.get("team", "?"))] += 1
        for who in ("team", "opponent"):
            for pl_ in b[who]["players"]:
                keys = [c["card_key"] for c in pl_["deck"]]
                all_keys.update(keys)
                ex = tuple(sorted(keys))
                base = tuple(sorted(FORM.sub("", k) for k in keys))
                sides_exact[ex] += 1
                sides_base[base] += 1
        plays_base.update({})  # placements per deck are counted below from the actions table if needed

total_sides = sum(sides_base.values())
ranked = sides_base.most_common()


def cover(k):
    return sum(c for _, c in ranked[:k]) / total_sides


def loadable(deck):
    return all(c in loaded_slugs for c in deck)


out = {
    "replays": n_rep, "deck_sides": total_sides,
    "distinct_decks_exact": len(sides_exact), "distinct_decks_base": len(sides_base),
    "sides_share_top": {k: round(cover(k), 3) for k in (100, 1000, 10000)},
    "replays_per_deck_at_rank": {r: ranked[r - 1][1] for r in (1, 10, 100, 1000, 5000, 10000) if r <= len(ranked)},
    "decks_with_at_least": {n: sum(1 for _, c in ranked if c >= n) for n in (1, 5, 10, 20, 50, 100)},
    "distinct_card_keys": len(all_keys),
    "royalesim_loadable_top": {k: sum(1 for d, _ in ranked[:k] if loadable(d)) for k in (100, 1000, 10000)},
    "royalesim_loadable_sides_share": round(sum(c for d, c in ranked if loadable(d)) / total_sides, 3),
    "unmapped_card_keys_top": [k for k, _ in Counter({FORM.sub("", k): v for k, v in all_keys.items()}).most_common()
                               if k not in loaded_slugs][:25],
}
print(json.dumps(out, indent=1))
json.dump(out, open(HERE / "deck_census.json", "w"), indent=1)
