"""LOOP-LRN diagnosis: why kl_stop_prev 0.02 fires after 3-7 steps in final_gate.py (pilot.yaml, T_gate 0.1) when the
10-28 account-1 gates stopped at ~145. Hypotheses: (H1) T_gate 0.1 makes the gate KL grow ~9x faster; (H2) the kept
records were sampled at T_gate 0.3 (the pod's pilot.yaml before c78d7a9), so a T_gate 0.1 learner is off-policy on the gate.
  1. records: on gate-sampled rows, which T_gate reproduces the stored lp_gate from p_gate and the row's tau (max |diff|)
  2. one stored-mode update (u 5, batch 0 of final_gate's 3) at T_gate 0.1 and 0.3: steps, the stop, the first minibatch's
     ratio / lp diffs, and the per-step KL (gate, card, cell) of the first 10 minibatches

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/tgate_probe.py \
        --config scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml --keep /workspace/lrn/id1/keep \
        --keep2 /workspace/lrn/id0_freshhead/keep
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402
from stored_gate import R, LR, torch  # noqa: E402


def lp_gate(p, tau, played, T):
    z = np.log(p) - np.log1p(-p)
    x = (z - np.log(tau / (1 - tau))) / T
    return np.where(played, -np.logaddexp(0, -x), -np.logaddexp(0, x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--keep2", type=Path, required=True)
    a = ap.parse_args()
    base = R.load_config(SG.REPO / a.config, [], smoke=False)
    for name, keep in (("id1", a.keep), ("id0", a.keep2)):
        diffs = {0.1: 0.0, 0.3: 0.0}
        for p in sorted(keep.glob("*.rec"))[:40]:
            t = LR.decode(p.read_bytes())["traj"]
            gs = t["gate_sampled"].astype(bool)
            tau = t["gate_tau"] if "gate_tau" in t else np.full(len(gs), float(base["tau"]))
            for T in diffs:
                d = np.abs(lp_gate(t["p_gate"][gs], tau[gs], t["played"][gs], T) - t["lp_gate"][gs])
                diffs[T] = max(diffs[T], float(d.max()) if len(d) else 0.0)
        print("records", name, "max |lp_gate - recomputed| by T_gate:", json.dumps(diffs), flush=True)
    allr = [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep.glob("*.rec"))] + \
        [LR.to_result(LR.decode(p.read_bytes())) for p in sorted(a.keep2.glob("*.rec"))]
    batch = allr[0::3]
    real = R.minibatch_loss
    for tg in (0.1, 0.3):
        cfg = {**base, "T_gate": tg, "stored_values": True, "ent_init_rows": None, "lazy_refine": True, "ent_pair_every": 1}
        L = SG.learner(cfg, f"tg{tg}")
        kls = []

        def spy(*x, **k):
            loss, st = real(*x, **k)
            kls.append([round(st[h], 6) for h in ("kl_gate", "kl_card", "kl_cell")] + [round(st["ratio_maxdev"], 4),
                                                                                      round(st["clip_frac"], 4)])
            return loss, st
        R.minibatch_loss = spy
        try:
            rec = SG.run_update(L, 5, SG.with_v(L, cfg, batch), {})
        finally:
            R.minibatch_loss = real
        print("update T_gate", tg, json.dumps({"steps": rec.get("steps"), "kl_stop": rec.get("kl_stop"),
                                                 "first_minibatch": rec["first_minibatch"], "clip_frac": rec["clip_frac"],
                                                 "rows": rec["rows"]}, default=str), flush=True)
        print("  per minibatch [kl_gate, kl_card, kl_cell, ratio_maxdev, clip_frac]:", kls[:10], flush=True)
        del L
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
