"""Successor config check (factorial/cfgcheck.py + the one-change rule): every successor yaml through the TRAINER's own
loader and validators (rl_royale.load_config + adv_cfg + config_sha), and each arm's raw yaml differs from succ_ctl.yaml
in EXACTLY its intended keys (the arm's one change), nothing else; init = Mark CXXXVIII raw (u0130), seed 74, 65 updates.
    cd CHECKOUT && PYTHONPATH=. PY scratchpad/gauntlet/L74/successor/cfg/cfgcheck.py     -> CFGCHECK PASS / FAIL"""
import sys
from pathlib import Path

import yaml

from pipeline import rl_royale as R

D = Path("scratchpad/gauntlet/L74/successor/cfg")
INIT = "icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130.pt"
TS = {"shaping_ts_w_own", "shaping_ts_w_foe", "shaping_ts_w_tb", "shaping_ts_h_power"}
EXPECT = {"succ_ctl": set(), "succ_levels": {"live_levels"}, "succ_tower": {"shaping"} | TS,
          "succ_hist": {"league_decks"}, "succ_troops": {"opp_tower_troops"}, "succ_exploit": {"league_exploiters"}}
raw = {n: yaml.safe_load((D / f"{n}.yaml").read_text(encoding="utf-8")) for n in EXPECT}
bad, shas = 0, {}
for n, want in EXPECT.items():
    y, c = raw[n], raw["succ_ctl"]
    diff = {k for k in set(y) | set(c) if y.get(k) != c.get(k)}
    ok = diff == want and y["init"] == INIT and y["seed"] == 74 and y["max_updates"] == 65 and y.get("cue_inputs") is True
    try:
        cfg = R.load_config(D / f"{n}.yaml", [], False)
        adv = R.adv_cfg(cfg)
        shas[n] = R.config_sha(cfg)[:12]
        msg = f"config sha {shas[n]} shaping {adv.get('shaping')} live_levels {bool(cfg.get('live_levels'))} decks {cfg['league_decks']}"
    except BaseException as exc:                             # SystemExit from the validators included
        ok, msg = False, f"REFUSED: {exc!r}"
    bad += not ok
    print(f"{n:13} {'ok ' if ok else 'BAD'} diff vs ctl {sorted(diff)}  {msg}")
if len(set(shas.values())) != len(shas):
    bad += 1
    print("duplicate config shas")
print("CFGCHECK", "PASS" if not bad else f"FAIL ({bad})")
sys.exit(1 if bad else 0)
