"""Pro tempo from the driven pilot corpus (native-engine logs): plays/min per side before 2:00 (ticks < 2400) and in
double elixir + overtime, elixir at play, first-play tick. Compare to L74/human/BEHAVIOUR.md (live 12k humans: ppm_2x 8.6,
SIM 12.2). Sample N replays (light CPU).  Usage: python pro_tempo.py CORPUS_DIR N"""
import json, random, sys, statistics as st
from pathlib import Path
files = sorted(Path(sys.argv[1]).glob("s[0-3]/replay_*.json"))
random.Random(0).shuffle(files)
p1, p2, el, first, react = [], [], [], [], []
for f in files[: int(sys.argv[2])]:
    r = json.load(open(f))
    end = int(r["final"]["tick"])
    if end < 2600:              # 3-crown before double elixir: no 2x window
        continue
    log = [e for e in r["log"] if e.get("accepted")]
    for s in (0, 1):
        t = [e["tick"] for e in log if e["side"] == s]
        p1.append(sum(x < 2400 for x in t) / (2400 / 1200))
        p2.append(sum(x >= 2400 for x in t) / ((end - 2400) / 1200))
        el += [e["elixir_before"] for e in log if e["side"] == s]
        if t: first.append(t[0])
        other = [e["tick"] for e in log if e["side"] != s]
        for o in other:         # share of the other side's plays answered within 3 s (60 ticks)
            react.append(any(o < x <= o + 60 for x in t))
q = lambda v: f"median {st.median(v):.2f} mean {st.mean(v):.2f} n {len(v)}"
print("ppm_1x", q(p1)); print("ppm_2x", q(p2)); print("elixir_before", q(el)); print("first_tick", q(first))
print("react_3s share", f"{sum(react)/len(react):.3f} n {len(react)}")
