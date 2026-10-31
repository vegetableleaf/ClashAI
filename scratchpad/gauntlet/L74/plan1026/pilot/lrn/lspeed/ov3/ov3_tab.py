"""LEARNER-SPEED overlap v3: per-update table from each run's train_log.jsonl + fastloop throughput.jsonl.
    python3 ov3_tab.py RUN [RUN ...]   (cwd /workspace/lspeed)"""
import json
import sys
from pathlib import Path

CB = Path("/workspace/lspeed/cbo")
f = (lambda x, n=4: "-" if x is None else f"{x:.{n}f}")
for run in sys.argv[1:]:
    tl = [json.loads(l) for l in (CB / f"scratchpad/gauntlet/L68/rl/{run}/train_log.jsonl").read_text().splitlines() if l.strip()]
    tl = [r for r in tl if r.get("type") == "update"]
    tp = {}
    p = Path(f"/workspace/lspeed/ov3/{run}/throughput.jsonl")
    if p.exists():
        for l in p.read_text().splitlines():
            if l.strip():
                d = json.loads(l)
                tp[d.get("update")] = d
    print(f"== {run}")
    print("u | steps | stop | kl g/c/x (last-epoch mean) | clip | first ratio_maxdev | is_maxdev_first | is_trunc_ep0 | "
          "win | stale | wave_s | wall_s | upd_s")
    for r in tl:
        u = r["update"]
        dc = r.get("decoupled") or {}
        fm = r.get("first_minibatch") or {}
        t = tp.get(u, {})
        print(f"{u} | {r.get('steps')} | {(r.get('kl_stop') or {}).get('kl') if isinstance(r.get('kl_stop'), dict) else r.get('kl_stop')} | "
              f"{f(r.get('kl_gate'))} {f(r.get('kl_card'))} {f(r.get('kl_cell'))} | {f(r.get('clip_frac'), 3)} | "
              f"{f(fm.get('ratio_maxdev'), 3)} | {f(dc.get('is_maxdev_first'), 3)} | {f(dc.get('is_trunc_frac_ep0'), 4)} | "
              f"{f(r.get('winrate'), 3)} | {t.get('staleness')} | {f(t.get('wave_s'), 0)} | {f(t.get('wall_s'), 0)} | "
              f"{f(r.get('wall_update_s'), 0)}")
