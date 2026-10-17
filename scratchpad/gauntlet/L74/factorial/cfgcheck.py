"""Pod-side config check: every factorial yaml (+ the base) through the TRAINER's own loader and validators
(rl_royale.load_config + adv_cfg + config_sha), so a key the trainer would refuse fails here, not 30 h into the batch.
    cd CB && PYTHONPATH=. PY scratchpad/gauntlet/L74/factorial/cfgcheck.py      -> one line per yaml, CFGCHECK PASS / FAIL"""
import sys
from pathlib import Path

from pipeline import rl_royale as R

FD = Path("scratchpad/gauntlet/L74/factorial")
paths = [Path("scratchpad/gauntlet/L74/troops/gae_f36_u250.yaml")] + sorted((FD / "cfg").glob("fact*.yaml"))
shas, bad = {}, 0
for p in paths:
    try:
        cfg = R.load_config(p, [], False)
        adv = R.adv_cfg(cfg)
        shas[p.name] = R.config_sha(cfg)[:12]
        print(f"{p.name:22} config sha {shas[p.name]} seed {cfg['seed']} shaping {adv.get('shaping')} "
              f"cue {bool(cfg.get('cue_inputs'))} exploiters {cfg.get('league_exploiters') is not None} "
              f"troops {cfg.get('opp_tower_troops') is not None} live_levels {bool(cfg.get('live_levels'))}")
    except BaseException as exc:            # SystemExit from the validators included
        bad += 1
        print(f"{p.name:22} REFUSED: {exc!r}")
if len(set(shas.values())) != len(shas):
    bad += 1
    print("duplicate config shas")
print("CFGCHECK", "PASS" if not bad else f"FAIL ({bad})")
sys.exit(1 if bad else 0)
