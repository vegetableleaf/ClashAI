"""S2-02 / S2-08: swap the Hog rows of an existing full-pool run (e.g. the E4 promotion rows) for a candidate's Hog-pool rows,
keeping the full-pool run's Hog COUNT (its live-mirrored Hog proportion); candidate rows taken in seed order.
    python merge_rows.py OUT.jsonl "<full-pool glob>" "<candidate hog-pool glob>"  -> then gate_s2.py full on OUT.jsonl"""
import glob, json, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_eval")
from live_eval import classify
hog = lambda r: classify([c.split("@")[0] for c in r["opp_deck"]]).startswith("Hog")
load = lambda g: [json.loads(l) for f in sorted(glob.glob(g)) for l in open(f) if l.strip()]
base, cand = load(sys.argv[2]), sorted((r for r in load(sys.argv[3]) if hog(r)), key=lambda r: r["seed"])
keep = [r for r in base if not hog(r)]; n = len(base) - len(keep)
assert len(cand) >= n, f"candidate has {len(cand)} Hog rows, need {n}"
with open(sys.argv[1], "w") as f:
    for r in keep + cand[:n]: f.write(json.dumps(r) + "\n")
print(f"{sys.argv[1]}: {len(keep)} non-Hog base rows + {n} candidate Hog rows (of {len(cand)})")
