"""R2 dry config validation through rl_royale's OWN code (CPU smoke impossible: the eval chain holds 16/16 cores at 100%
and a below-normal process got ~0.3 CPU-s per minute). load_config (CLI override parser) -> Learner.__init__
(condition_cfg, adv_cfg, init load, validate_league, league_decks + deck_weights on the ladder file) -> the first update's
league matchups via sample_matchups -> the actor cfgs the learner and the frozen opponents would run under."""
import os, sys, ctypes, json, collections
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"): os.environ[v] = "2"
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # below normal
from pathlib import Path
import subprocess
from pipeline import rl_royale as RL
HERE = Path(__file__).resolve().parent
# the override array exactly as run_r2.sh builds it (bash expands it; no copy to drift)
ovr = subprocess.run(["C:/Program Files/Git/bin/bash.exe", str(HERE / "print_ovr.sh")],     # Git bash, not WSL bash
                     capture_output=True, text=True, check=True).stdout.splitlines()
assert len(ovr) > 20 and ovr[-1].startswith("league_mix={"), ovr
ovr += ["learner_device=cpu", "actor_device=cpu"]
print("overrides:", ovr)
cfg = RL.load_config(RL.REPO / "scratchpad/gauntlet/L69/rl/r1_rl_royale.yaml", ovr, False)
print({k: cfg[k] for k in ("tau", "T", "league_mix", "league_icebow_share", "league_learner_icebow_share", "league_decks",
                           "league_deck_alpha", "league_deck_floor", "max_updates", "league_opp_policy", "n_actors", "init")})
d = HERE / "dryrun"; d.mkdir(exist_ok=True)
L = RL.Learner(cfg, "rseries_r2l_dry", d, d, RL.Log(d), False)
print("Learner init OK: gen", bool(L.gen), "grid", L.grid, "census decks", len(L.census), "p sum", float(L.census_p.sum()))
ms = RL.sample_matchups(L.rng, int(cfg["E"]), 0, [], cfg, L.census, L.census_p)
for m in ms:
    print(f"  {m['tag']} opp {m['opp']['type']:5s} learner {m['learner_deck_name']:7s} opp deck {m['opp_deck_name']:6s} {m['opp_deck']}")
base = dict(cfg, grid=L.grid)
a = RL.actor_cfg(base, "rollout", 0, "cpu"); o = {**a, "policy": cfg["league_opp_policy"], "record": False}
print("learner actor cfg: policy", a["policy"], "tau", a["tau"], "T", a["T"], "| opponent cfg: policy", o["policy"], "tau", o["tau"], "T", o["T"])
s = RL.actor_cfg(base, "screen", 0, "cpu"); print("held-out screen cfg: policy", s["policy"], "tau", s["tau"])
print("DRY VALIDATION PASS")
