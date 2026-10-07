"""Integration check: branch_score on a REAL branching.BranchRunner result (gen_v32_s0, fv5): T1's end snapshots
(prepared learner side, env detached) scored by every kind, and branch_label. One point, k 2, horizon 10 s and end."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validate as V           # noqa: E402

S, E, BS = V.S, V.E, V.BS
from pipeline.branching import BranchRunner, BranchSpec     # noqa: E402


def arm_decide(self, m, ds, arm, p, enc, heads, allowed, plain, st, rng, stalled=False):
    if self.done or not (0.2 <= p <= 0.65) or int(m.env.tick) < 1000:
        return plain
    self.done = True
    br = BranchRunner(self.make_env, self.learner, self.opps, self.lcfg, device="cpu")
    phi = self.phi
    for hz in (10.0, None):
        t = time.perf_counter()
        r = br.pair(m, ds, BranchSpec(hold_s=4.0, horizon_s=hz, k=2, seed=7))
        print(f"horizon {hz}: tick {r.tick} p {r.p_play:.3f} outcomes {r.play_outcome} {r.hold_outcome} "
              f"wall {time.perf_counter() - t:.1f}s", flush=True)
        for kind in BS.KINDS:
            try:
                print(f"  {kind}: label {BS.branch_label(r, kind, phi=phi)}  play scores "
                      f"{[round(BS.score(e, o, kind=kind, phi=phi), 4) for e, o in zip(r.play_end, r.play_outcome)]}",
                      flush=True)
            except ValueError as ex:
                print(f"  {kind}: ValueError {ex}", flush=True)
    raise SystemExit(0)


V.ValRunner.arm_decide = arm_decide
args = {"gen": V.V32, "opp_gen": V.GEN1, "opp_gen_sha256": None, "s1": S.S1_CKPT, "opps": ["gen"], "threads": 2,
        "tail_cap": 7200, "horizon": 12.0, "interval": 1, "topk": 4, "cells": 3, "device": "cpu", "search_min_p": 0.0,
        "rollout_self": "idle", "forms_mode": "deck", "hero_abilities": True, "ability_policy": "v2", "census": V.EVO,
        "tau_plain": 0.35, "phi": V.V32, "k": 2, "band": [0.2, 0.65], "holds": [4.0], "hold_tau": 0.55,
        "horizons": [10.0], "opp_T": 0.3, "opp_tau": 0.35, "per_stratum": [1, 0, 0], "crn_check": False}
V._init(args)
run = S._W["runner"]
run.done = False
m, _ = S.setup_job(run, S._W["census"], "gen", 3)
m.opp.cfg = {**m.opp.cfg, "policy": "sample", "T": 0.3, "tau": 0.35}    # R3-like sampled opponent
V._play(run, m)
