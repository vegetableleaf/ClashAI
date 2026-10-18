"""S2-03: the 13k-band level table (D3 R0) = L74/levels/live_levels.py's exact builder run on the parity harness's per-match
summaries of the CXXXVIII logs that STARTED at >= 13,000 trophies (gate/live_targets.json 'start'; levels only, never
results). Source: FIN9 (P3 /workspace/results/FIN9/matches, the newest harness run; 48 of the 87 13k logs, up to 20:21 EDT).
    python levels13k.py SUMMARY_DIR   -> levels13k.json (+ the tower-16 share vs the current live_levels.json)"""
import json, sys
from collections import Counter
from pathlib import Path
R = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74")
sys.path.insert(0, str(R / "levels"))
import live_levels as LL
H = Path(__file__).resolve().parent
src = Path(sys.argv[1])
X = json.load(open(R / "stage2/gate/live_targets.json"))
k13 = {x["file"][:-6] for x in X if x["mark"] == "CXXXVIII" and x["start"] is not None and x["start"] >= 13000}
got = sorted(p.stem for p in (src / "matches").glob("live_play_*.json"))
assert got and set(got) <= k13, set(got) - k13
LL.main(str(H / "levels13k.json"), [str(src)])
for name, f in (("13k (new)", H / "levels13k.json"), ("current", R / "levels/live_levels.json")):
    t = json.load(open(f)); tw = Counter(p[1] for p in t["opp_profiles"]); n = len(t["opp_profiles"])
    cl = Counter(v for p in t["opp_profiles"] for v in p[2])
    print(f"{name:10s} profiles {n:3d}  tower-16 share {tw[16]}/{n} = {tw[16] / n:.1%}  towers {dict(sorted(tw.items()))}  "
          f"mean card level {sum(k * v for k, v in cl.items()) / sum(cl.values()):.2f}")
print("13k logs", len(k13), "with a harness summary", len(got))
