"""python train_boot.py ARGS...: python -m pipeline.rl_royale ARGS with one shim for ROYALE_HEROIW_PRESS=live.
rl_royale's loadability env (Learner._entries: RoyalePoolEnv(decision_ticks=...), no hero abilities) refuses the live
IW rule at construction ('Live IW press rule needs hero_abilities and ability_policy v2'), so a training run can never
use it. The shim builds THAT env with the press mode off (it never presses: it only checks deck loadability); every
env that plays (hero_abilities True, ability_policy v2) is built unchanged, with the live rule."""
import os, runpy, sys
from pipeline import royale_env
_init = royale_env.RoyalePoolEnv.__init__
def _patched(self, *a, **k):
    if not k.get('hero_abilities') and os.environ.get('ROYALE_HEROIW_PRESS') == 'live':
        os.environ['ROYALE_HEROIW_PRESS'] = 'off'
        try:
            return _init(self, *a, **k)
        finally:
            os.environ['ROYALE_HEROIW_PRESS'] = 'live'
    return _init(self, *a, **k)
royale_env.RoyalePoolEnv.__init__ = _patched
sys.argv = ['rl_royale'] + sys.argv[1:]
runpy.run_module('pipeline.rl_royale', run_name='__main__', alter_sys=True)
