"""L68 generalist PILOT slice: top-100 base decks by deck-side count, each capped at its first 200 sides in replay order.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/generalist/pilot_select.py

Same counting as deck_census.py (every player of both sides, forms stripped: -ev<N> / -hero). Replay order = parts
sorted by name, rows in file order. Writes pilot_tags.json: [{"tag", "sides": {"team"|"opponent": "<deck key>"}}],
deck key = the 8 sorted base card keys joined by ",".
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
TOP, CAP = 100, 200


def replays():
    for f in sorted(glob.glob(str(REPO / "scratchpad/gauntlet/L67/hf/replays/*.parquet"))):
        df = pl.read_parquet(f, columns=["replay_tag", "payload_json"])
        for tag, pj in zip(df["replay_tag"], df["payload_json"]):
            b = json.loads(pj)["battle"]
            yield tag, {who: [",".join(sorted(FORM.sub("", c["card_key"]) for c in p["deck"])) for p in b[who]["players"]]
                        for who in ("team", "opponent")}


rows = list(replays())
count = Counter(k for _, sides in rows for ks in sides.values() for k in ks)
top = {k for k, _ in count.most_common(TOP)}
taken, sel = Counter(), []
for tag, sides in rows:
    pick = {}
    for who, ks in sides.items():
        if len(ks) == 1 and ks[0] in top and taken[ks[0]] < CAP:
            taken[ks[0]] += 1
            pick[who] = ks[0]
    if pick:
        sel.append({"tag": tag, "sides": pick})
not_1v1 = sum(1 for _, s in rows if any(len(ks) != 1 for ks in s.values()) and any(k in top for ks in s.values() for k in ks))
print(json.dumps({"replays_scanned": len(rows), "top_decks": len(top), "min_top_count": min(count[k] for k in top),
                  "sides": sum(taken.values()), "replays": len(sel), "both_sides": sum(len(s["sides"]) == 2 for s in sel),
                  "decks_short_of_cap": sum(taken[k] < CAP for k in top), "top_deck_in_non_1v1_replay": not_1v1}))
(HERE / "pilot_tags.json").write_text(json.dumps(sel), encoding="utf-8")
