"""How many replays in the HF dump play a given deck EXACTLY (forms free)? Count before building anything."""
import re, sys, json, collections
from pathlib import Path
import polars as pl
HF = Path("scratchpad/gauntlet/L67/hf/replays")
def base(k): return re.sub(r"-ev\d+$", "", k)
DECKS = {
 "icebow": frozenset({"tornado","tesla","ice-wizard","x-bow","rocket","knight","the-log","skeletons"}),
 "hogeq":  frozenset({"hog-rider","firecracker","mighty-miner","tesla","the-log","earthquake","skeletons","ice-spirit"}),
}
hits = collections.Counter(); files = sorted(HF.glob("*.parquet"))
near = collections.Counter()
for i, f in enumerate(files):
    try:
        df = pl.read_parquet(f, columns=["payload_json"])
    except Exception as e:
        print("  read failed", f.name, e, flush=True); continue
    for raw in df["payload_json"].to_list():
        try:
            b = json.loads(raw)["battle"]
            sides = {}
            for side in ("team", "opponent"):
                pls = (b.get(side) or {}).get("players") or []
                if len(pls) == 1:
                    sides[side] = pls[0]
            if len(sides) != 2: continue
            for s in sides:
                ks = {base(c["card_key"]) for c in sides[s]["deck"]}
                for name, want in DECKS.items():
                    if ks == want: hits[name] += 1
                    elif len(ks & want) == 7: near[name] += 1
        except Exception:
            continue
    if i % 10 == 9:
        print(f"  scanned {i+1}/{len(files)} files: {dict(hits)}", flush=True)
print("EXACT deck sides found:", dict(hits))
print("7-of-8 near misses:", dict(near))
