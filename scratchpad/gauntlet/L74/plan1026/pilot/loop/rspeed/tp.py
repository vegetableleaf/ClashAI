"""throughput.jsonl + gpu.jsonl of a fastloop run dir -> per-update summary (producer wall spread, stage split, GPU)."""
import json, statistics as st, sys
from pathlib import Path
d = Path(sys.argv[1])
gpu = [json.loads(l) for l in (d / "gpu.jsonl").read_text().splitlines() if l.strip()]
prev_tm = {}
for l in (d / "throughput.jsonl").read_text().splitlines():
    u = json.loads(l)
    if u["matches"] < 200:            # the B6 warm start wave
        tag = "B6"
    else:
        tag = f"u{u['update']:04d}"
    pr = u["producers"]
    walls = sorted(p["wall_s"] for p in pr.values())
    t1, t0 = u["t"], u["t"] - u["wall_s"]
    win = [g for g in gpu if t0 <= g["t"] <= t1]
    util = st.mean(float(g["gpu"][0][1]) for g in win) if win else None
    mem = max(int(g["gpu"][0][2]) for g in win) if win else None
    pm = sorted(int(p[1]) for g in win[-3:] for p in g["procs"])
    stages = {}
    for k, p in pr.items():
        tm = p.get("time", {})
        for s, v in tm.items():
            dv = v - prev_tm.get((k, s), 0.0)
            stages.setdefault(s, []).append(dv)
            prev_tm[(k, s)] = v
    print(f"{tag}: {u['matches']} matches {u['wall_s']:.1f} s = {u['matches_per_h']:.0f}/h rows/s {u['rows_per_s']:.0f}; "
          f"producer wall min/med/max {walls[0]:.1f}/{st.median(walls):.1f}/{walls[-1]:.1f}; GPU util mean {util} % "
          f"(n={len(win)}), GPU mem max {mem} MiB; per-process MiB (last samples) {pm[:3]}..{pm[-3:]}")
    print("   per-producer stage s (min/median/max):", {s: (round(min(v), 1), round(st.median(v), 1), round(max(v), 1)) for s, v in stages.items()})
