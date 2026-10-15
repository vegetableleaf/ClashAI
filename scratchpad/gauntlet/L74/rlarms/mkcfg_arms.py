"""Reward-architecture arms (owner-approved 10-14, L74/reward/REWARD_ARCHITECTURE.md), each ONE change vs rltest_ctrl
(r1's exact config continued 60 policy updates from newsim_base_main_u0060, 10-13).
    python mkcfg_arms.py ARM OUT.yaml      ARM = gae (F1) | opp (F3) | kl_imit (F6)
kl_imit needs KL_IMIT (below, not in git: icebow/data/) on the pod -> put it in ckpts.tgz; checked here by sha256.
"""
import hashlib
import sys

import torch
import yaml

RL = "icebow/data/bench/rl_royale"
arm, out = sys.argv[1], sys.argv[2]
c = dict(torch.load(f"{RL}/newsim_r1/newsim_base_r1_final_grafted.pt", map_location="cpu", weights_only=False)["rl"]["config"])
c.update(init=f"{RL}/newsim_base_main/newsim_base_main_u0060.pt", league_decks="icebow/data/rltest/decks_rl.json",
         max_updates=60)
GAE = dict(advantage="gae", critic_warmup_updates=5, gae_lambda=0.95, gae_gamma=0.999, gae_gamma_unit="tick",
           gae_gamma_tick=0.99994, vf_coef=0.5, shaping="none", max_updates=65)
OPP = dict(league_opp_T=0.05)
TG = dict(T_gate=0.1)          # F4: the learner's gate temperature (built 10-13; GAP: T .5 sampling loses 25 pp vs greedy)
# F6: the pure imitation generalist imit_v32 (fv5; L74/econ2/PRO_EAGERNESS.md), the gate's KL anchor
KL_IMIT, KL_IMIT_SHA = ("icebow/data/pipeline/gen_v32_s0/gen_s0.pt",
                        "61011b6ce5e655c0f66c875ee844685373cc6370051f9eccba1e1d79de1a0569")
if arm == "kl_imit":  # F6 ONE change: KL_gate to the imitation model instead of the run's own init; card / cell unchanged
    if hashlib.sha256(open(KL_IMIT, "rb").read()).hexdigest() != KL_IMIT_SHA:
        raise SystemExit(f"{KL_IMIT}: sha256 is not {KL_IMIT_SHA[:16]}... (ship it in ckpts.tgz)")
    c.update(kl_ref_gate=KL_IMIT)
elif arm == "gae":    # F1 per-decision credit: R2's GAE settings without its shaping; 5 critic-only updates -> 65 = 60 policy
    c.update(GAE)
elif arm in ("gae_opp", "gae_tg", "gae_opp_tg"):   # overnight factorial on the foundations (F1 x F3 x F4)
    c.update(GAE)
    if "opp" in arm:
        c.update(OPP)
    if "tg" in arm:
        c.update(TG)
elif arm == "opp":  # F3 calibrated opponents, ONE lever: every league opponent decisive (T .05 instead of the learner's .5;
    # calibration: E4 @ .03 low-elixir penalty +23.0 vs live +26.9, E4 @ .1 +17.1; calib_20261014.txt). r1's PFSP pool and
    # its 5 exploiter externals stay exactly as they were (adding E4 / gen_v1 to the pool = a later, separate arm).
    c.update(league_opp_T=0.05)
else:
    raise SystemExit(f"unknown arm {arm!r}")
yaml.safe_dump(c, open(out, "w"), sort_keys=False)
print(arm, {k: c[k] for k in ("advantage", "max_updates", "league_pfsp", "T", "kl_ref_gate") if k in c}, c.get("league_opp_T"))
