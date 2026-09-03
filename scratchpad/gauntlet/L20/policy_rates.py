"""Per-drill pass rates of trained checkpoints (GREEDY, masked like training) on the two new aggro drills and the
three old aggro-named ones. Read-only use of the checkpoints."""
import sys; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim import aggro_drills, scenarios
from clashrl.sim.drill_env import report
from clashrl.cli import _drill_policy_from_checkpoint
cfg = Config.load(); scenarios.load_all(); aggro_drills.register_all()
names = ["tank_for_bow", "bow_lane_choice", "knight_guards_the_bow", "nado_the_sneaky_lock", "nado_king_activation"]
for label, path in [("gate05 m5k", "../scratchpad/gauntlet/L16/gate05_m5k.pt"), ("policy_sim_ppo (pre-run)", "data/policy_sim_ppo.pt")]:
    print("\n=====", label, path)
    pol = _drill_policy_from_checkpoint(path, "cpu", spell_min_value=float(cfg.get("sim", "ppo_spell_min_value", default=0.0) or 0.0))
    report(cfg, names=names, reps=40, seed=5, policy=pol)
