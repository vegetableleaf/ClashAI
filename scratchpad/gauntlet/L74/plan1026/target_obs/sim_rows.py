"""TARGET-OBS: the SIM target rows of real recorded self-play matches (pod, crforge env as tobs_smoke.sh).
    python -B scratchpad/gauntlet/L74/plan1026/target_obs/sim_rows.py N_MATCHES
Tiny GenModel learner with the zero target layers vs a tiny plain GenModel (test_cue_inputs' harness); prints per
match: rows, matched tokens, target edges, edges onto the attacker's own side (must be 0), tower targets, tokens
targeted by a tower."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402
import torch  # noqa: E402

from pipeline import model_gen as MG  # noqa: E402
from pipeline import e1_eval as E  # noqa: E402
from pipeline import search_s0 as S  # noqa: E402
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from pipeline.tests.test_cue_inputs import HOGEQ, _vocab  # noqa: E402


def tiny(tgt, seed):
    torch.manual_seed(seed)
    net = MG.GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(_vocab())).eval()
    if tgt:
        net.add_target_in()
    return net


n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
tot = np.zeros(7, int)
for seed in range(n):
    pol = E.GenPolicy(tiny(True, seed), _vocab())
    opp = E.GenPolicy(tiny(False, 100 + seed), _vocab())
    got = []
    spec = {"tag": f"tgt:{seed}", "opp": {"id": "gen"}, "learner_deck": list(E.ICEBOW_ENGINE_DECK), "opp_deck": list(HOGEQ),
            "learner_side": seed % 2, "seed": seed}
    E.run_selfplay_batch(lambda: RoyaleSelfPlayEnv(tail_cap=7200), pol, {"gen": (opp, S.live_cfg(S.TAU_OPP, "lattice"))},
                         [(0, spec, 0)], dict(S.live_cfg(S.TAU_PLAIN, "lattice"), policy="sample", record=True), 1,
                         on_result=got.append)
    tj = got[0]["traj"]
    R, I, tok = tj["tgt"], tj["tgt_idx"], tj["tok"]
    known = R[..., 0] > 0
    own = 0
    for r, t in zip(*np.nonzero(I >= 0)):
        own += int((tok[r, t, 1] > 0) == (tok[r, I[r, t], 1] > 0))
    row = np.array([len(R), known.sum(), (I >= 0).sum(), own, (R[..., 2] > 0).sum(), (R[..., 7] > 0).sum(),
                    ((R[..., 0] > 0) & (R[..., 3] > 0)).sum()])
    tot += row
    print(f"match {seed}: rows {row[0]} known {row[1]} edges {row[2]} own-side edges {row[3]} tower targets {row[4]} "
          f"targeted by a tower {row[5]} attack frac > 0 {row[6]}", flush=True)
print("TOTAL rows known edges own_side tower_tgt by_tower frac>0", tot.tolist())
