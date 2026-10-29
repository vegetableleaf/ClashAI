"""LEARNER-SCALE large-minibatch lr sweep under the FIXED per-update cap kl_stop_prev 0.02, with a WARMED Adam state:
each arm = a fresh B0 learner running 3 consecutive policy updates (u5, u6, u7) on 3 disjoint 256-match batches (the
persistent optimizer, as in the pilot), stored mode (v_old = the update-start model's V, stored_gate.with_v).
Per update: steps, stop KL (the overshoot over the cap), rows used, PPO seconds, and the HELD-OUT surrogate gain
    J(theta) = sum_rows w A (pi_theta / pi_0 - 1)   on a 4th disjoint 256-match batch never trained on
(pi_0 = B0, the policy that sampled it: an unbiased first-order estimate of the policy improvement over B0 in the held-out
advantage units; A from B0's critic, normalised over the held-out batch), with its per-match standard error.
Default arms: base (mb 256, lr 1e-5) and the large minibatches at lrs bracketing "~cap / 4 per step" (accum_gate).
LEARNER-SCALE2 (equal KL): --train DIR,DIR.. --held DIR,DIR.. (any sizes; --batch-matches per update, consecutive updates
from u5), arm "name:mb:lr:ka" (ka = kl_lr_target, the KL-adaptive lr), --epochs; J per held-out match is kept per arm and
update, and every arm's J is also compared PAIRED with the first arm's (same held-out matches: dJ +- se of the per-match
differences, much tighter than the two J's own se).

    source env.sh; cd $CB; $PY -u scratchpad/gauntlet/L74/plan1026/pilot/lrn/lr_sweep.py --config CFG \
        --keep /workspace/lrn/id1/keep --keep2 /workspace/lrn/id0_freshhead/keep --T-gate 0.3 --out /workspace/lrn/sweep/sweep.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stored_gate as SG  # noqa: E402
from stored_gate import R, LR, torch  # noqa: E402

ARMS = "base:256:1e-5,b32k:32768:1.5e-5,b32k:32768:2.5e-5,b32k:32768:4e-5,b65k:65536:1e-5,b65k:65536:1.4e-5,b65k:65536:2e-5"


@torch.no_grad()
def surrogate(model, Bh, cfg, chunk=1024):
    N = len(Bh["A"])
    x = []
    for s in range(0, N, chunk):
        idx = torch.arange(s, min(s + chunk, N), device=Bh["A"].device)
        t = R.policy_terms(model, Bh, idx, cfg["tau"], cfg["T"], T_gate=cfg.get("T_gate"))
        lp = t["lp_gate"] + t["lp_card"] + t["lp_cell"]
        x.append(Bh["w"][idx] * Bh["A"][idx] * (torch.exp(lp - Bh["lp_old"][idx]) - 1))
    x = torch.cat(x).double().cpu().numpy()
    m = Bh["match"].cpu().numpy()
    per = np.bincount(m, weights=x)
    return {"J": float(per.sum()), "se": float(np.sqrt(len(per)) * per.std(ddof=1)), "per": per.tolist()}


def paired(x, y):
    d = np.asarray(y) - np.asarray(x)
    return {"dJ": float(d.sum()), "se": float(np.sqrt(len(d)) * d.std(ddof=1))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--keep", type=Path, default=None)
    ap.add_argument("--keep2", type=Path, default=None)
    ap.add_argument("--train", default=None, help="comma-separated record dirs (with --held: replaces --keep / --keep2)")
    ap.add_argument("--held", default=None)
    ap.add_argument("--batch-matches", type=int, default=512)
    ap.add_argument("--updates", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=None, help="ppo_epochs override for every arm")
    ap.add_argument("--T-gate", type=float, required=True)
    ap.add_argument("--arms", default=ARMS, help="name:minibatch:lr,...")
    ap.add_argument("--micro", type=int, default=1024)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("overrides", nargs="*", help="config key=value overrides for every arm (e.g. mem_row_cache=true)")
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    base = {**R.load_config(SG.REPO / a.config, a.overrides, smoke=False), "T_gate": a.T_gate, "stored_values": True}
    load = (lambda ds: [LR.to_result(LR.decode(p.read_bytes())) for d in ds for p in sorted(Path(d).glob("*.rec"))])
    if a.train:
        tr, held = load(a.train.split(",")), load(a.held.split(","))
        n = a.batch_matches
        batches = [tr[i * n:(i + 1) * n] for i in range(min(a.updates, len(tr) // n))]
    else:
        allr = load((a.keep, a.keep2))
        batches, held = [allr[i::4] for i in range(3)], allr[3::4]
    if a.epochs:
        base["ppo_epochs"] = a.epochs
    real_ppo, ppo_s = R.ppo_update, []

    def timed(*x, **k):
        torch.cuda.synchronize(); t = time.perf_counter()
        out = real_ppo(*x, **k)
        torch.cuda.synchronize(); ppo_s.append(time.perf_counter() - t)
        return out
    R.ppo_update = timed
    out = {"config": {"T_gate": a.T_gate, "micro": a.micro, "batches": [len(b) for b in batches], "held": len(held)},
           "arms": {}}
    Bh = None
    for spec in a.arms.split(","):
        name, mb, lr, *ka = spec.split(":")
        mb, lr = int(mb), float(lr)
        cfg = {**base, "minibatch": mb, "lr": lr, **({"micro_batch": a.micro} if mb > a.micro else {}),
               **({"kl_lr_target": float(ka[0])} if ka else {})}
        L = SG.learner(cfg, f"sw_{name}")
        if Bh is None:                                        # held-out batch: B0's critic, built once
            Bn, _ = R.collate(held, float(cfg["adv_clip"]), **SG.collate_kw(cfg))
            Bh = R.to_device(Bn, L.dev)
            R.gae_batch(L.model, Bh, cfg)
            out["J_B0"] = surrogate(L.model, Bh, cfg)
        key = f"{name}_lr{lr:g}" + (f"_ka{ka[0]}" if ka else "")
        rows = []
        for i, b in enumerate(batches):
            ppo_s.clear()
            rec = SG.run_update(L, 5 + i, SG.with_v(L, cfg, b), {})
            row = {"u": 5 + i, "steps": rec.get("steps"), "kl_stop": rec.get("kl_stop"),
                   "rows_used": (rec.get("steps") or 0) * mb, "ppo_s": ppo_s[0], "wall_update_s": rec.get("wall_update_s"),
                   "kl": [rec.get(k) for k in ("kl_gate", "kl_card", "kl_cell")], "entropy": rec.get("entropy"),
                   "l_v": (rec.get("gae") or {}).get("l_v"), "grad_norm_mean": rec.get("grad_norm_mean"),
                   "lr_end": L.opt.param_groups[0]["lr"], "held": surrogate(L.model, Bh, cfg)}
            rows.append(row)
            print("arm", key, json.dumps({k: v for k, v in row.items() if k != "held"} | {"J": row["held"]["J"], "se": row["held"]["se"]}, default=str), flush=True)
        out["arms"][key] = rows
        first = next(iter(out["arms"].values()))
        out.setdefault("paired_vs_first", {})[key] = [paired(f["held"]["per"], r["held"]["per"]) for f, r in zip(first, rows)]
        print("paired", key, out["paired_vs_first"][key], flush=True)
        a.out.write_text(json.dumps(out, indent=1, default=str))
        del L
        torch.cuda.empty_cache()
    R.ppo_update = real_ppo


if __name__ == "__main__":
    main()
