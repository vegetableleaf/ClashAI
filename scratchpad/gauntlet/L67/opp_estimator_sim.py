"""L67h: how wrong is the OPPONENT-ELIXIR ESTIMATOR? Graded against ground truth, in the sim.

Two measurements pulled in opposite directions and this settles them:
  * LIVE (live_gate_elixir.json): supplying the estimate cuts the student's play rate up to 3.2x, and the
    worst value (a pinned 10) costs the most -- which is what the owner's freeze looks like.
  * PRO LABELS (opp_elixir_labels.json): on engine states, opp_known=1 beats opp unknown for gate accuracy
    even when the VALUE is a lie -- clean 0.8227, const-5 0.8142, pinned-10 0.8053, none 0.7549.
Those are different instruments (rate vs accuracy) and do not contradict. What neither answers is the question
that decides the wiring: IS THE ESTIMATE ANY GOOD? Live there is no ground truth; in the sim there is
(eng.elixir[1]), so the estimator can be graded directly under a detector that misses bodies at the measured
live rate (presence recall 0.855, HANDOFF board-24-5).

FIRST ATTEMPT WAS INVALID and is retracted here: it drove the match with act=(0,0,0), so our side never spent
and our elixir sat pinned at 10. The estimator reads the shared regeneration clock off MY elixir, so when my
elixir saturates the arithmetic has no clock at all -- it reported a -1.8 bias that was an artifact of the
harness, not of the estimator. This version plays the STUDENT, so both sides cycle like a real match.

Arms are exact, not approximate: both read the SAME books. The L67g fix charges each saturation correction to
`_opp_spent` and tracks the total in `_rebase`, so subtracting `_rebase` recovers what the pre-fix code would
have held on byte-identical detections.

usage: python scratchpad/gauntlet/L67/opp_estimator_sim.py --ckpt <pt> --matches 6 [--out <json>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


class _Det:
    """Duck-type of replay_mine.Detection, the shape OpponentElixirEstimator.update() reads."""

    def __init__(self, base, x, y):
        self.base = self.cls = str(base)
        self.cx, self.gy = float(x), float(y)
        self.team = "enemy"


def prefix_estimate(fix, my_elixir):
    """The PRE-L67g estimate, computed exactly from the shipped estimator's own books."""
    raw = float(my_elixir) + fix._my_spent - (fix._opp_spent - fix._rebase)
    return max(0.0, min(10.0, raw))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--matches", type=int, default=6)
    ap.add_argument("--seed0", type=int, default=770000)
    ap.add_argument("--tau", type=float, default=0.27)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    import random as _r

    import torch
    from clashrl.cards import CardDB
    from clashrl.config import Config
    from clashrl.opponent_elixir import OpponentElixirEstimator
    from clashrl.sim.env import SimMatchEnv
    from pipeline.model_v3 import S1Model, cell_xy, hand_mask_from_sc
    from pipeline.obs_contract import load_deck, to_tokens
    from student_sim import StudentActor

    torch.set_num_threads(1)
    cfg = Config.load()
    db = CardDB(path=Path("icebow/config/cards.yaml"))
    env = SimMatchEnv(cfg, seed=12345)
    env.domain_rand.enabled = False
    env.domain_rand.resample()
    env.opponent_provider = None
    env.reset()

    st = torch.load(a.ckpt, map_location="cpu")
    args = dict(st.get("args", {}) or {})
    grid = str(args.get("grid", "floor"))
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4)))
    model.load_state_dict(st["model"])
    model.eval()
    deck = load_deck("icebow")
    actor = StudentActor(env, model, deck, gate_tau=a.tau, degrade=True, grid=grid, torch=torch,
                         cell_xy=cell_xy, hand_mask_from_sc=hand_mask_from_sc, to_tokens=to_tokens)

    arms = {}
    for recall in (1.0, 0.855):
        ef, ep, pin_f, pin_p, n = [], [], 0, 0, 0
        for m in range(a.matches):
            rng = _r.Random(1234 + m)
            env.rng.seed(a.seed0 + m)
            env.reset()
            actor.reset()
            fix = OpponentElixirEstimator(db)
            fix.reset(my_elixir=float(env.eng.elixir[0]), now=0.0)
            for i in range(2000):
                act, _ = actor.act(i)
                if act[0] == 1:
                    fix.record_my_play(str(list(env.deck_keys)[int(act[1])]))
                _o, _r_, done, _info = env.step(act)
                eng = env.eng
                dets = [_Det(u.spec.base, u.x, u.y) for u in eng.units
                        if u.hp > 0 and int(u.team) == 1 and rng.random() <= recall]
                my_el = float(eng.elixir[0])
                e_fix = float(fix.update(my_el, dets, float(eng.t))) * 10.0
                e_pre = prefix_estimate(fix, my_el)
                truth = float(eng.elixir[1])
                ef.append(e_fix - truth)
                ep.append(e_pre - truth)
                pin_f += e_fix >= 9.999
                pin_p += e_pre >= 9.999
                n += 1
                if done:
                    break
        f, p = np.array(ef), np.array(ep)
        key = "recall_%g" % recall
        arms[key] = {"samples": int(n),
                     "shipped_mean_abs_err": round(float(np.abs(f).mean()), 3),
                     "shipped_bias": round(float(f.mean()), 3),
                     "shipped_frac_pinned10": round(float(pin_f / max(n, 1)), 3),
                     "prefix_mean_abs_err": round(float(np.abs(p).mean()), 3),
                     "prefix_bias": round(float(p.mean()), 3),
                     "prefix_frac_pinned10": round(float(pin_p / max(n, 1)), 3),
                     "truth_mean": None}
        print(key + ": " + json.dumps(arms[key]), flush=True)

    if a.out:
        a.out.write_text(json.dumps(arms, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
