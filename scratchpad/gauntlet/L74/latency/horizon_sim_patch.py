"""Patch an ISOLATED copy of the VM pipeline (~/afford/mine/pipeline, never ~/ClashBot) for the L74 horizon A/B.
Adds, all default-neutral, for the LEARNER only (search_s0.live_cfg is shared with the opponent, so it is not touched):
  env LR_DELAY  (default 26): cfg action_delay_ticks
  env LR_EXTRAP (default 26): cfg extrapolate_ticks
  env LR_AFFORD (default unset): cfg afford_ticks (pipeline.e1_eval, this branch)
Run on the VM:  ~/venv/bin/python horizon_sim_patch.py ~/afford/mine/pipeline"""
import pathlib
import sys

P = pathlib.Path(sys.argv[1])
OLD = "    learner_cfg = live_cfg(args.get('tau_plain', TAU_PLAIN), gi['grid'], dev)\n"
NEW = (OLD +
       "    import os as _os\n"
       "    learner_cfg['action_delay_ticks'] = int(_os.environ.get('LR_DELAY', '26'))\n"
       "    learner_cfg['extrapolate_ticks'] = int(_os.environ.get('LR_EXTRAP', '26'))\n"
       "    if _os.environ.get('LR_AFFORD'):\n"
       "        learner_cfg['afford_ticks'] = int(_os.environ['LR_AFFORD'])\n")
t = (P / "search_s0.py").read_text()
if NEW not in t:
    assert t.count(OLD) == 1, t.count(OLD)
    (P / "search_s0.py").write_text(t.replace(OLD, NEW))
print("patched", P)
