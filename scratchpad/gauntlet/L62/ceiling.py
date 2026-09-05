#!/usr/bin/env python
"""L62 -- how many MORE battles would convert if the crawl backfilled x/y for the tags it recorded
without positions.  Same tests as build_pool.convert(), with the positional test removed."""
from __future__ import annotations
import collections, csv, json, sys
from pathlib import Path

L62 = Path(__file__).resolve().parent
REPO = L62.parents[2]
sys.path.insert(0, str(L62))
sys.path.insert(0, str(REPO / "research" / "ext" / "cr-native-sandbox"))
sys.path.insert(0, str(REPO / "research" / "sandbox_tools"))
import build_pool as BP  # noqa: E402
import replay_drive as RD  # noqa: E402

battles, plays, _ = BP.load_snapshot()
pool_tags = {json.loads(l)["tag"] for l in (REPO / "icebow" / "data" / "ghost_pool" / "pool.jsonl").open(encoding="utf-8")}
out = collections.Counter()
recoverable_decks = set()
recoverable_tags = []
for b in battles:
    tag = b["replay_tag"]
    if tag in pool_tags:
        out["already_converted"] += 1
        continue
    rows = plays.get(tag, [])
    if not rows:
        out["no_plays_rows"] += 1
        continue
    try:
        decks = {s: BP.deck_for(b, s) for s in (0, 1)}
    except ValueError as exc:
        out["deck_" + str(exc).split(":")[0]] += 1
        continue
    ok = True
    for side in (0, 1):
        by = {d["slug"]: d for d in decks[side]}
        sp = [r for r in rows if r["attr_s"] == ("blue" if side == 1 else "red") and r["attr_ability"] == "0"]
        if any(r["attr_card"] not in by for r in sp):
            out["play_outside_deck"] += 1; ok = False; break
        seq = [by[r["attr_card"]]["card_id"] for r in sorted(sp, key=lambda r: int(r["play_index"]))]
        if not seq:
            out["side_no_plays"] += 1; ok = False; break
        if not RD.infer_deals(seq, [d["card_id"] for d in decks[side]]):
            out["no_consistent_deal"] += 1; ok = False; break
    if ok:
        out["would_convert_if_positioned"] += 1
        recoverable_tags.append(tag)
        recoverable_decks.add(tuple(sorted((d["slug"], d["form"]) for d in decks[0])))

pool_decks = set()
for l in (REPO / "icebow" / "data" / "ghost_pool" / "pool.jsonl").open(encoding="utf-8"):
    r = json.loads(l)
    pool_decks.add(tuple(sorted((c["slug"], c["form"]) for c in r["ghost_deck"])))
res = dict(out)
res["recoverable_distinct_ghost_decks"] = len(recoverable_decks)
res["recoverable_decks_NOT_in_pool"] = len(recoverable_decks - pool_decks)
res["pool_distinct_ghost_decks"] = len(pool_decks)
res["union_distinct_ghost_decks"] = len(recoverable_decks | pool_decks)
(L62 / "ceiling.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
