"""Prewarm engine_env.py's deal cache from the L61 batch records, which already contain the FINAL
(permuted) deck order the engine produced for seed 424242.  Saves one engine reset per first-touch
episode for the 211 tags the L61 batch converted.  Nothing here touches the engine."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REC = ROOT / "scratchpad/gauntlet/ext/batch_v2"
POOL = ROOT / "icebow/data/ghost_pool/pool.jsonl"
OUT = Path(__file__).resolve().parent / "deal_cache.json"

pool = {}
for line in POOL.read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        pool[r["tag"]] = r

cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
n, skip = 0, 0
for p in sorted(REC.glob("replay_*.json")):
    tag = p.stem[len("replay_"):]
    e = pool.get(tag)
    if e is None:
        skip += 1; continue
    rec = json.loads(p.read_text(encoding="utf-8"))
    if rec["deal_probe"]["position_based"] is not True:
        skip += 1; continue
    decks = {int(e["icebow_side"]): e["icebow_deck"], int(e["ghost_side"]): e["ghost_deck"]}
    ent, ok = {}, True
    for s in (0, 1):
        by_key = {(it["name"] + ("@" + it["form"] if it["form"] != "base" else "")): it for it in decks[s]}
        names = rec["final_decks"][str(s)]
        if sorted(by_key) != sorted(names):
            ok = False; break
        ent[str(s)] = [int(by_key[nm]["card_id"]) for nm in names]
    if not ok:
        skip += 1; continue
    cache[tag] = ent
    n += 1
OUT.write_text(json.dumps(cache), encoding="utf-8")
print(f"deal cache: {n} tags prewarmed, {skip} skipped -> {OUT} (total {len(cache)})")
