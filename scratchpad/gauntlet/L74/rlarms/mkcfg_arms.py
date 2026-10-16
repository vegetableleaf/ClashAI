"""Reward-architecture arms (owner-approved 10-14, L74/reward/REWARD_ARCHITECTURE.md), each ONE change vs rltest_ctrl
(r1's exact config continued 60 policy updates from newsim_base_main_u0060, 10-13).
    python mkcfg_arms.py ARM OUT.yaml      ARM = gae (F1) | opp (F3) | kl_imit (F6) | gae_solv (A2) | gae_tower (A1+A1b)
    | gae_trade (A3, step 5) | gae_live (F1 + live-mirrored opponent decks, 10-15) | gae_c2 (C2) | gae_f2 (F2) | gae_f6lo (F6')
    | gae_c1 (C1 stage A) | bait_gae (= gae; run through L74/bait/bait_rl.py) | exploit / gae_exploit (O2, 10-16)
kl_imit / gae_f6lo need KL_IMIT (below, not in git: icebow/data/) on the pod -> put it in ckpts.tgz; checked here by sha256.
gae_solv / gae_tower (step 3) = arm gae + ONE potential (reward_shaping solvency / tower_score), its weights pinned in
the yaml from reward_shaping.STATE_PHI_DEFAULTS (PYTHONPATH = the repo); pre-flight: L74/reward/preflight_a1a2.py.
gae_c2 / gae_f2 = arm gae + ONE change, rl_royale ``critic_ctx``: the critic also sees the opponent's archetype (+ tank
flag) [C2, "arch"], or archetype + match phase + crown state [F2, "full"]; public context only, policy unchanged.
gae_f6lo (F6', lead design 10-15) = arm gae + the gate anchored to KL_IMIT ONLY on rows with own elixir < 4.0, with its
own coefficient beta_g targeting 0.5 x its update-0 KL (rl_royale kl_ref_gate_max_elixir / kl_ref_gate_target_frac);
the >= 4 elixir rows keep the init ref and the shared leash.
gae_c1 (C1 stage A, owner-approved 10-15) = arm gae + ONE change, rl_royale ``posture_head``: a learned posture
(defend / balanced / pressure = gate tau +0.10 / 0 / -0.10, re-chosen every 200 ticks, sampled in training) from g + the
public ctx row. The actors record ctx rows for the head WITHOUT critic_ctx (the critic stays the plain one), so the arm
differs from gae by the posture keys only.
exploit (O2 exploiter league, owner 10-16) = arm gae's recipe, league replaced: the LEARNER plays the struggle pool
(L74/exploit/decks_struggle.json, weight n_lost; league_learner_icebow_share 0), the ONLY opponent is the frozen live model
F1 u250 (league_frozen_opponent -> icebow deck, AO), decoded greedy (league_opp_policy live, tau = the run's .27: the
trainer has no livecal rule layer, so not the D3 stack), unstyled (opp_style off), no PFSP / externals.
gae_exploit = arm gae + ONE change, rl_royale ``league_exploiters``: share .3 of the icebow learner's matchups vs the
trained exploiter (EXPLOITER_CKPT env, default the exploit run's u0065) playing struggle-pool decks; file checked here.
"""
import os
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
# O2 (10-16): the frozen live model F1 u250 (the exploiter's opponent) and the struggle pool (L74/exploit/struggle_pool.py)
F1_U250, F1_U250_SHA = (f"{RL}/rlarm_gae/rlarm_gae_u0250_grafted.pt",
                        "00c845c084ee828e614760f2e753d1623c5c4125c6fe4a951236ebbb4cdd1b0c")
STRUGGLE = "scratchpad/gauntlet/L74/exploit/decks_struggle.json"
if arm in ("kl_imit", "gae_f6lo") and hashlib.sha256(open(KL_IMIT, "rb").read()).hexdigest() != KL_IMIT_SHA:
    raise SystemExit(f"{KL_IMIT}: sha256 is not {KL_IMIT_SHA[:16]}... (ship it in ckpts.tgz)")
if arm == "kl_imit":  # F6 ONE change: KL_gate to the imitation model instead of the run's own init; card / cell unchanged
    c.update(kl_ref_gate=KL_IMIT)
elif arm == "gae_f6lo":   # F6': F1 + the imitation gate anchor on the < 4 elixir rows only, own coefficient
    c.update(GAE, kl_ref_gate=KL_IMIT, kl_ref_gate_max_elixir=4.0, kl_ref_gate_target_frac=0.5)
elif arm == "gae":    # F1 per-decision credit: R2's GAE settings without its shaping; 5 critic-only updates -> 65 = 60 policy
    c.update(GAE)
elif arm == "bait_gae":   # 10-16 friend's bait deck: arm gae's config exactly; the learner deck is set by L74/bait/bait_rl.py
    c.update(GAE)
elif arm in ("gae_solv", "gae_tower", "gae_trade"):   # steps 3/5: F1 + ONE potential; same init, warm-up (5), scale 1.5
    from pipeline.reward_shaping import STATE_PHI_DEFAULTS
    c.update(GAE)
    mode, pre = {"gae_solv": ("solvency", "shaping_solv_"), "gae_tower": ("tower_score", "shaping_ts_"),
                 "gae_trade": ("trade", "shaping_tr_")}[arm]
    if arm == "gae_trade" and c.get("opp_elixir") not in ("counter", "counter_all"):
        raise SystemExit("gae_trade: r1's config must use the public opp_elixir counter")
    c.update(shaping=mode, **{k: v for k, v in STATE_PHI_DEFAULTS.items() if k.startswith(pre)})
elif arm == "gae_c1":   # C1 stage A: F1 + the posture head (defaults: every 200 ticks, dtau +.10/0/-.10, ent .01)
    c.update(GAE, posture_head=True)
elif arm in ("gae_c2", "gae_f2"):   # C2 / F2: F1 + a context-aware critic (rl_royale CtxHead), nothing else
    c.update(GAE, critic_ctx={"gae_c2": "arch", "gae_f2": "full"}[arm])
elif arm in ("gae_opp", "gae_tg", "gae_opp_tg"):   # overnight factorial on the foundations (F1 x F3 x F4)
    c.update(GAE)
    if "opp" in arm:
        c.update(OPP)
    if "tg" in arm:
        c.update(TG)
elif arm == "gae_live":   # 10-15 owner-approved matchup mix: F1 + ONE change, opponent decks = the LIVE-MIRRORED pool
    # (L74/mix/live_pool.py: 1,919 live 12k opponents completed from IL_Replay; sides = n_live + n_lost)
    c.update(GAE)
    c.update(league_decks="scratchpad/gauntlet/L74/mix/decks_live_train.json")
elif arm == "opp":  # F3 calibrated opponents, ONE lever: every league opponent decisive (T .05 instead of the learner's .5;
    # calibration: E4 @ .03 low-elixir penalty +23.0 vs live +26.9, E4 @ .1 +17.1; calib_20261014.txt). r1's PFSP pool and
    # its 5 exploiter externals stay exactly as they were (adding E4 / gen_v1 to the pool = a later, separate arm).
    c.update(league_opp_T=0.05)
elif arm == "exploit":   # O2: learner = struggle-pool decks vs the frozen live model F1 u250 (icebow), nothing else
    if hashlib.sha256(open(F1_U250, "rb").read()).hexdigest() != F1_U250_SHA:
        raise SystemExit(f"{F1_U250}: sha256 is not {F1_U250_SHA[:16]}...")
    c.update(GAE, league_decks=STRUGGLE, league_learner_icebow_share=0.0, league_frozen_opponent=F1_U250,
             league_pfsp="off", league_external=[], opp_style="off", league_opp_policy="live")
elif arm == "gae_exploit":   # O2 league integration: F1 + ONE change, 30% of matchups vs the exploiter on struggle decks
    ck = os.environ.get("EXPLOITER_CKPT", f"{RL}/rlarm_exploit/rlarm_exploit_u0065.pt")
    if not os.path.isfile(ck):
        raise SystemExit(f"gae_exploit: exploiter checkpoint {ck} not found (train arm exploit first, or EXPLOITER_CKPT=)")
    c.update(GAE, league_exploiters={"ckpt": ck, "decks": STRUGGLE, "share": 0.3})
else:
    raise SystemExit(f"unknown arm {arm!r}")
yaml.safe_dump(c, open(out, "w"), sort_keys=False)
print(arm, {k: c[k] for k in ("advantage", "max_updates", "league_pfsp", "T", "kl_ref_gate", "shaping",
                              "shaping_critic_scale", "critic_ctx", "kl_ref_gate_max_elixir",
                              "kl_ref_gate_target_frac", "posture_head", "league_frozen_opponent", "league_exploiters",
                              "league_decks", "league_opp_policy") if k in c}, c.get("league_opp_T"))
