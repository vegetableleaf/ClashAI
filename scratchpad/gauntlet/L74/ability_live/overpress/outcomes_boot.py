"""python outcomes_boot.py SCRIPT ARGS...: run SCRIPT with royale_env.RoyalePoolEnv(ability_outcomes=True) forced, so every
eval row carries ability_stats (learner presses, elixir, enemy bodies in radius, hit / killed within 2 s). Read-only
tally (royale_env._ab_track / _ab_resolve: no RNG, no state edits) -> the games are unchanged.
OVERPRESS_AB_MODE=sample (optional): the learned ability head decodes as in RL rollouts (Bernoulli) instead of the
eval's greedy p > 0.5 (rl_royale.load_ability_head); unset = unchanged."""
import os, runpy, sys
from pipeline import royale_env
_init = royale_env.RoyalePoolEnv.__init__
def _patched(self, *a, **k):
    k["ability_outcomes"] = True
    _init(self, *a, **k)
royale_env.RoyalePoolEnv.__init__ = _patched
if os.environ.get("OVERPRESS_AB_MODE"):
    from pipeline import rl_royale
    _load = rl_royale.load_ability_head
    def _load_mode(*a, **k):
        r = _load(*a, **k)
        if r is not None:
            r["mode"] = os.environ["OVERPRESS_AB_MODE"]
        return r
    rl_royale.load_ability_head = _load_mode
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))   # as "python SCRIPT" does
runpy.run_path(sys.argv[0], run_name="__main__")
