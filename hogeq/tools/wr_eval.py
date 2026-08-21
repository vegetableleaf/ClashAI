"""Winrate of a checkpoint, measured well enough to answer "did that change help?".

    python tools/wr_eval.py <ckpt> [matches] [--vs OTHER] [--sampled]

WHY THIS EXISTS AT THIS SIZE. Every winrate quoted during the 2026-08-21 session came from 24-40
matches, and at ~10% winrate that is +/-9-11 points. Measured that day:

    untrained @seedsA  15.0% +/- 11.1     untrained @seedsB   0.0%
    best.pt @1500      10.0% +/-  9.3     run @7900           0.0%

Every interval overlapped every other one, and conclusions were drawn from them anyway -- including
two restart recommendations. Separating a 5-point difference at this winrate needs ~275 matches per
arm; a 3-point difference needs ~770. Anything smaller is a coin flip wearing a lab coat.

So this reports the 95% interval next to every number, refuses to call a difference that the
intervals do not support, and runs a FIXED opponent seed set so two checkpoints meet the same
opponents.

GREEDY vs SAMPLED: the trainer's own evaluate() thresholds the gate probability at
sim.ppo_gate_threshold, while training optimises a SAMPLED policy. Measured, the two differ by ~3
points of play rate and little else, but `--sampled` is here so the question stays answerable.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import numpy as np                                      # noqa: E402
import torch                                            # noqa: E402
import torch.nn as nn                                   # noqa: E402

from clashrl.config import Config                       # noqa: E402
from clashrl.model import PolicyNet                     # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEED0 = 31337                                            # FIXED, so two checkpoints meet the same bots


def _ci(w, n):
    """Winrate and the half-width of its 95% interval."""
    if n <= 0:
        return 0.0, 0.0
    p = w / n
    return 100.0 * p, 100.0 * 1.96 * math.sqrt(max(p * (1.0 - p), 1e-9) / n)


def evaluate(ckpt, n_matches, sampled=False, envs=8, untrained=False):
    cfg = Config.load(os.path.join(HERE, "..", "config", "config.yaml"))
    cfg.data.setdefault("action", {})["grid"] = [18, 24]
    st = torch.load(ckpt, map_location="cpu", weights_only=False)
    tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
    pool = [SimMatchEnv(cfg, seed=SEED0 + i) for i in range(envs)]
    e0 = pool[0]
    ich = int(st.get("in_ch") or 12)
    td = int(st.get("threat_dim") or e0.threat_dim)

    class M(nn.Module):
        def __init__(s):
            super().__init__()
            s.policy = PolicyNet(ich, e0.n_cards, e0.n_cells, threat_dim=td)
            s.gate = nn.Linear(s.policy.embed_dim, 2)

    net = M()
    if not untrained:
        net.policy.load_state_dict(st["model"])
        if "gate" in st:
            net.gate.load_state_dict(st["gate"])
    net.eval()
    mask = np.asarray(e0.actions.deployable_mask(False), dtype=bool)
    rng = np.random.default_rng(7)
    obs = [e.reset() for e in pool]
    w = l = d = plays = steps = 0
    with torch.no_grad():
        while w + l + d < n_matches:
            xb = torch.stack([torch.from_numpy(np.asarray(o)[:, :, :ich]).float().permute(2, 0, 1) / 255.0
                              for o in obs])
            hb = torch.stack([torch.from_numpy(np.asarray(e.hand_vec, np.float32)) for e in pool])
            nb = torch.stack([torch.from_numpy(np.asarray(e.next_vec, np.float32)) for e in pool])
            eb = torch.stack([torch.from_numpy(np.asarray(e.elixir_vec, np.float32)) for e in pool])
            tb = torch.stack([torch.from_numpy(
                np.pad(np.asarray(e.threat_vec, np.float32),
                       (0, max(0, td - len(e.threat_vec))))[:td]) for e in pool])
            z, cq, ceq = net.policy.forward_parts(xb, hb, nb, eb, tb)
            gq = net.gate(z)
            pg = torch.softmax(gq, dim=1)[:, 1].numpy()
            pc = torch.softmax(cq, dim=1).numpy()
            for i, e in enumerate(pool):
                steps += 1
                aff = [c for c in e._hand_ids()
                       if 0 <= c < len(e.specs) and e.eng.elixir[0] >= e.specs[c].elixir]
                go = (rng.random() < pg[i]) if sampled else (pg[i] > tau)
                if aff and go:
                    plays += 1
                    if sampled:
                        wts = np.asarray([pc[i][c] for c in aff], dtype=np.float64)
                        wts = wts / wts.sum()
                        ci = int(rng.choice(aff, p=wts))
                    else:
                        ci = max(aff, key=lambda c: float(cq[i, c]))
                    row = ceq[i, ci].numpy().copy()
                    if ci not in getattr(e, "anywhere_ids", set()):
                        row[~mask] = -1e9
                    if sampled:
                        p = np.exp(row - row.max())
                        cell = int(rng.choice(len(p), p=p / p.sum()))
                    else:
                        cell = int(np.argmax(row))
                    a = (1, ci, cell)
                else:
                    a = (0, 0, 0)
                o, _r, done, info = e.step(a)
                if done:
                    oc = (info or {}).get("outcome")
                    if oc == "win":
                        w += 1
                    elif oc == "loss":
                        l += 1
                    else:
                        d += 1
                    o = e.reset()
                obs[i] = o
    return {"w": w, "l": l, "d": d, "n": w + l + d, "matches": st.get("matches"),
            "plays": 100.0 * plays / max(1, steps)}


def _report(tag, r):
    p, h = _ci(r["w"], r["n"])
    print("  %-26s %3dW-%3dL-%3dD   winrate %5.1f%% +/- %4.1f  -> [%.1f, %.1f]   plays %4.1f%%"
          % (tag, r["w"], r["l"], r["d"], p, h, max(0.0, p - h), p + h, r["plays"]))
    return p, h


def main() -> int:
    args = [a for a in sys.argv[1:]]
    sampled = "--sampled" in args
    args = [a for a in args if a != "--sampled"]
    other = None
    if "--vs" in args:
        j = args.index("--vs")
        other = args[j + 1]
        args = args[:j] + args[j + 2:]
    ckpt = args[0] if args else "data/policy_ppo_drill.pt"
    n = int(args[1]) if len(args) > 1 else 275
    print("%d matches per arm, fixed opponent seeds, %s gate"
          % (n, "SAMPLED" if sampled else "greedy"))
    a = evaluate(ckpt, n, sampled=sampled)
    pa, ha = _report("%s (m=%s)" % (os.path.basename(ckpt), a["matches"]), a)
    if other:
        b = evaluate(other, n, sampled=sampled)
        pb, hb = _report("%s (m=%s)" % (os.path.basename(other), b["matches"]), b)
    else:
        b = evaluate(ckpt, n, sampled=sampled, untrained=True)
        pb, hb = _report("UNTRAINED baseline", b)
    print("")
    diff = pa - pb
    sep = math.sqrt(ha * ha + hb * hb)
    if abs(diff) > sep:
        print("  DIFFERENCE %+.1f points -- larger than the combined interval (%.1f). Real." % (diff, sep))
    else:
        print("  difference %+.1f points -- INSIDE the combined interval (%.1f)." % (diff, sep))
        print("  Not distinguishable at this sample size. Do not act on it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
