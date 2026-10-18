"""Config check for the L74 combo arms: every combo yaml (+ Mark CXXXVIII's own training yaml with the combo init, the
historical-hash reference) through the TRAINER's loader and validators (rl_royale.load_config + adv_cfg + spell_cfg +
config_sha). Prints each arm's config sha and its spell keys; the arms must differ from combo_ctl ONLY in the keys named.
    cd CB && PYTHONPATH=. PY scratchpad/gauntlet/L74/combo/cfgcheck.py      -> CFGCHECK PASS / FAIL"""
import sys
from pathlib import Path

from pipeline import rl_royale as R

FD = Path("scratchpad/gauntlet/L74/combo/cfg")
ONE_CHANGE = {"combo_rew": {"spell_value_w"}, "combo_ctl_pipe": {"learner_pipeline_frac"},
              "combo_rew_pipe": {"spell_value_w", "learner_pipeline_frac"}}   # vs combo_ctl (rew_pipe: vs combo_rew = 1)
cfgs, bad = {}, 0
for p in sorted(FD.glob("combo_*.yaml")):
    try:
        cfg = R.load_config(p, [], False)
        R.adv_cfg(cfg)
        sv = R.spell_cfg(cfg)
        cfgs[p.stem] = cfg
        print(f"{p.stem:16} config sha {R.config_sha(cfg)[:12]} seed {cfg['seed']} init {cfg['init'].split('/')[-1]} "
              f"spell w {sv and sv['spell_value_w']} pipeline_frac {cfg.get('learner_pipeline_frac')} "
              f"cue {cfg.get('cue_inputs')} max_updates {cfg['max_updates']}")
    except BaseException as exc:            # SystemExit from the validators included
        bad += 1
        print(f"{p.name:22} REFUSED: {exc!r}")
ctl = cfgs.get("combo_ctl")
for name, want in ONE_CHANGE.items():
    if ctl is None or name not in cfgs:
        bad += 1
        print(f"missing {name} or combo_ctl")
        continue
    got = {k for k in set(ctl) | set(cfgs[name]) if ctl.get(k) != cfgs[name].get(k)}
    ok = got == want
    bad += not ok
    print(f"{name} vs combo_ctl differs in {sorted(got)} ({'OK' if ok else 'WANT ' + str(sorted(want))})")
if ctl is not None:                         # without the spell keys the control is Mark CXXXVIII's config (historical hash)
    plain = {k: v for k, v in ctl.items() if k not in R.SPELL_KEYS}
    print(f"combo_ctl without spell keys: config sha {R.config_sha(plain)[:12]} (= the key absent; spell_cfg "
          f"{R.spell_cfg(plain)})")
print("CFGCHECK", "PASS" if not bad else f"FAIL ({bad})")
sys.exit(1 if bad else 0)
