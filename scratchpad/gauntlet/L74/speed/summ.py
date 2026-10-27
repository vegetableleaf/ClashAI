"""One line per run dir: matches/h, wall, server split, worker vCPU-s per match (CPU work, not waiting).
    python summ.py RUN_DIR [RUN_DIR ...]"""
import json
import statistics as st
import sys
from pathlib import Path

CPU = ("due", "prepare_row", "decide", "apply", "reset")
for d in map(Path, sys.argv[1:]):
    try:
        m = json.loads((d / "meta.json").read_text())
        s = json.loads((d / "batched_stats.json").read_text())
    except FileNotFoundError:
        print(d.name, "missing")
        continue
    ws = s["workers"]
    cpu = sum(sum(w["time_s"][k] for k in CPU) for w in ws)
    out = {"run": d.name, "N": m["matches"], "W": m["workers"], "fast": m.get("fast"), "amp": m.get("amp"),
           "matches_per_h": m["matches_per_h"], "wall_s": m["rollout_s"],
           "server": {k: s.get(k) for k in ("forward_s", "forward_stack_s", "forward_device_s", "cell_s", "wait_s",
                                            "forwards", "merged_calls", "rows")},
           "worker_vcpu_s_per_match": round(cpu / m["matches"], 3),
           "worker_mean": {k: round(st.fmean(w["time_s"][k] for w in ws), 1) for k in ws[0]["time_s"]}}
    print(json.dumps(out))
