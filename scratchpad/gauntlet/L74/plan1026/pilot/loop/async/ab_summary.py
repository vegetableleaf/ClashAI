"""LOOP-ASYNC: compact A/B summary from the pod files (run in /workspace/async): per run the update period / updates/h
(throughput t, median diff over u >= 2), PPO steps, first-minibatch max|r-1|, clip_frac, decoupled monitors (u >= 2),
and the held-out eval (J +- se, KL(B0 -> theta) cell / gate) per update.  usage: python ab_summary.py TAG [TAG ...]"""
import json
import statistics
import sys
from pathlib import Path


def jl(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]


for tag in sys.argv[1:]:
    D = Path(f"ab_{tag}")
    for s in (1028, 2029):
        for m in (0, 1):
            run = f"async_{tag}_s{s}_m{m}"
            tp = jl(D / run / "throughput.jsonl")
            t = [x["t"] for x in tp]
            per = statistics.median([b - a for a, b in zip(t[1:], t[2:])])
            ups = [r for r in jl(f"cb/scratchpad/gauntlet/L68/rl/{run}/train_log.jsonl") if r.get("type") == "update"]
            late = [r for r in ups if r["update"] >= 2]
            dc = [r.get("decoupled") or {} for r in late]
            print(f"{run}: period {per:.1f}s = {3600 / per:.2f} upd/h | steps u2+ {[r['steps'] for r in late]} | "
                  f"r1dev {[round(r['first_minibatch']['ratio_maxdev'], 3) for r in late]} | clip "
                  f"{[round(r['clip_frac'], 3) for r in late]} | is_maxdev {[round(d.get('is_maxdev_first') or 0, 2) for d in dc]}"
                  f" trunc {[round(d.get('is_trunc_frac_ep0') or 0, 3) for d in dc]}")
        ev = D / f"eval_s{s}.json"
        if ev.exists():
            e = json.loads(ev.read_text())
            for arm, rows in e["arms"].items():
                print(f"  eval s{s} {arm}: J " + " ".join(f"{r['J']['J']:+.4f}" for r in rows) + " | se "
                      + " ".join(f"{r['J']['se']:.4f}" for r in rows) + " | KLcell "
                      + " ".join(f"{r['kl_b0']['cell']:.4f}" for r in rows) + " | KLgate "
                      + " ".join(f"{r['kl_b0']['gate']:.4f}" for r in rows))
