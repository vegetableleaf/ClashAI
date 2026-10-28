"""LEARNER-SCALE micro_batch build check on real records (one policy update u5, stored mode, v_old = the update-start
model's V as stored_gate.py, T_gate = the records' own). Arms, each from the same fresh B0 learner:
  base     minibatch 256                                   (today's pilot learner)
  acc64    minibatch 256, micro_batch 64                   identity: weights max |diff| vs base, monitors rel diff
  big<MB>  minibatch MB, micro_batch --micro, lr x sqrt(MB / 256) (Adam square-root rule), kl_stop_prev 0.02 as pilot
-> steps, kl_stop, KL / clip / entropy / l_v monitors, ppo seconds, rows used, GPU peak.

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/accum_gate.py --config CFG \
        --keep /workspace/lrn/id1/keep --T-gate 0.3 --big 32768,65536 --micro 1024 --out /workspace/lrn/accum/gate.json
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402
from stored_gate import R, LR, torch  # noqa: E402

KEYS = ("kl_gate", "kl_card", "kl_cell", "clip_frac", "ratio_mean", "steps", "grad_norm_mean")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--T-gate", type=float, required=True)
    ap.add_argument("--big", default="32768,65536")
    ap.add_argument("--micro", type=int, default=1024)
    ap.add_argument("--arms", default="base,acc64,big")
    ap.add_argument("--big-lr", type=float, default=None, help="bigc arms' lr (default: the config's)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    base = {**R.load_config(SG.REPO / a.config, [], smoke=False), "T_gate": a.T_gate, "stored_values": True}
    res = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))]
    real_ppo, ppo_s = R.ppo_update, []

    def timed(*x, **k):
        torch.cuda.synchronize(); t = time.perf_counter()
        out = real_ppo(*x, **k)
        torch.cuda.synchronize(); ppo_s.append(time.perf_counter() - t)
        return out
    R.ppo_update = timed
    arms = []
    want = a.arms.split(",")
    if "base" in want:
        arms.append(("base", {}))
    if "acc64" in want:
        arms.append(("acc64", {"micro_batch": 64}))
    if "cache" in want:                                       # mem_row_cache: expect bit-identical weights to base
        arms.append(("cache", {"mem_row_cache": True}))
    if "bigc" in want:                                        # the large minibatch with the cache (time only)
        for mb in [int(x) for x in a.big.split(",")]:
            arms.append((f"big{mb}c", {"minibatch": mb, "micro_batch": a.micro, "lr": a.big_lr or float(base["lr"]),
                                        "mem_row_cache": True}))
    if "big" in want:
        for mb in [int(x) for x in a.big.split(",")]:
            arms.append((f"big{mb}", {"minibatch": mb, "micro_batch": a.micro, "lr": float(base["lr"]) * math.sqrt(mb / 256)}))
    out, W = {"config": {"T_gate": a.T_gate, "micro": a.micro, "lr_base": base["lr"]}, "arms": {}}, {}
    for name, kv in arms:
        cfg = {**base, **kv}
        L = SG.learner(cfg, f"acc_{name}")
        ppo_s.clear()
        torch.cuda.reset_peak_memory_stats()
        rec = SG.run_update(L, 5, SG.with_v(L, cfg, res), {})
        row = {k: rec.get(k) for k in KEYS} | {"kl_stop": rec.get("kl_stop"), "entropy": rec.get("entropy"),
               "l_v": (rec.get("gae") or {}).get("l_v"), "ppo_s": ppo_s[0], "wall_update_s": rec.get("wall_update_s"),
               "gpu_peak_mb": torch.cuda.max_memory_allocated() / 2 ** 20, **kv,
               "rows_used": (rec.get("steps") or 0) * int(cfg["minibatch"])}
        W[name] = {n: v.detach().cpu().double().clone() for n, v in L.model.state_dict().items()}
        if name != "base" and "base" in W:
            row["max_abs_weight_vs_base"] = max(float((W[name][n] - W["base"][n]).abs().max()) for n in W[name])
        out["arms"][name] = row
        print("arm", name, json.dumps(row, default=str), flush=True)
        del L
        torch.cuda.empty_cache()
    R.ppo_update = real_ppo
    if "base" in out["arms"] and "acc64" in out["arms"]:
        b, c = out["arms"]["base"], out["arms"]["acc64"]
        rel = {k: abs(c[k] - b[k]) / max(abs(b[k]), 1e-12) for k in ("kl_gate", "kl_card", "kl_cell", "clip_frac", "l_v")
               if b.get(k) is not None}
        out["identity"] = {"max_abs_weight": c["max_abs_weight_vs_base"], "rel": rel, "steps": [b["steps"], c["steps"]],
                           "pass": c["max_abs_weight_vs_base"] <= 1e-5 and b["steps"] == c["steps"]
                           and max(rel.values()) <= 1e-3}
        print("IDENTITY", json.dumps(out["identity"]), flush=True)
    a.out.write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
