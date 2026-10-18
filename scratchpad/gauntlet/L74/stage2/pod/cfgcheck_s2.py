"""S2-02 / S2-07 acceptance: both Phase C yamls through the TRAINER's loader + validators (rl_royale.load_config, adv_cfg,
config_sha); the RESOLVED configs must differ only in init. Prints each config sha and the init's feature version.
    cd CHECKOUT && PYTHONPATH=. PY scratchpad/gauntlet/L74/stage2/pod/cfgcheck_s2.py"""
import sys
import torch
from pipeline import rl_royale as R
D = "scratchpad/gauntlet/L74/stage2/cfg/"
res = {}
for n in ("s2_hog_e4", "s2_hog_il"):
    c = R.load_config(D + n + ".yaml", [], False); R.adv_cfg(c)
    ick = torch.load(c["init"], map_location="cpu", weights_only=False)
    res[n] = c
    print(f"{n}: config sha {R.config_sha(c)[:12]} init {c['init']} gen {bool(ick.get('gen'))} fv {ick['args'].get('feature_version')} "
          f"refine heads {sorted({k.split('.')[0] for k in ick['model'] if k.startswith(('cell_refine', 'tower_refine', 'cue_in'))})} "
          f"live_levels {c.get('live_levels')} opp_tower_troops {c.get('opp_tower_troops')} frozen {c.get('league_frozen_opponent')}")
a, b = res.values()
diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
print("resolved diff:", diff)
print("CFGCHECK_S2", "PASS" if diff == ["init"] else "FAIL")
sys.exit(0 if diff == ["init"] else 1)
