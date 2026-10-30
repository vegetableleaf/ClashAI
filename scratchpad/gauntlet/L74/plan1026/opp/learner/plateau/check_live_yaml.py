"""Laptop-only config check of opp_learner_calib_live.yaml through rl_royale's own validators (no rollout)."""
import sys, os, yaml
sys.path.insert(0, r"C:/Users/benpe/ClashBot"); os.chdir(r"C:/Users/benpe/ClashBot")
from pipeline import rl_royale as R, adaptive_opponents as AO
for name in ("opp_learner_calib.yaml", "opp_learner_calib_live.yaml"):
    c = yaml.safe_load(open("scratchpad/gauntlet/L74/plan1026/opp/learner/" + name, encoding="utf-8"))
    c.update(init="opp_ckpt/opp_m10_s0_sim.pt", beta0=0.003, beta_min=0.003, beta_max=0.003, lr=3e-5, th_anchor=10.0)
    R.validate_league(c); AO.validate(c)
    print(name, "validate_league + AO.validate OK; exploiters", R.exploiter_league(c) is not None,
          "| live stack fields", len(R.league_opp_live(c) or {}),
          "| frozen pool", AO.opponent_pool([], c, {}) if c.get("league_frozen_opponent") else "-")
