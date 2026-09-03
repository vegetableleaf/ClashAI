"""`nado_retarget` was UNREACHABLE (HANDOFF §5bq.3): the retarget-candidate test was centre-to-centre while
the engine engages centre-to-hitbox-EDGE, so a hog locked on our princess (settled 2.20 tiles from her
centre) was never a `targeter` and the 0.4 credit never paid in any run. `env.nado_retarget_reach_fix`
(default false) switches to the engine's `_gap`. This is `scratchpad/gauntlet/L16/retarget_reach.py` as a
regression test: same board, both flag states, no policy involved."""
from __future__ import annotations

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                                         # noqa: E402
from clashrl.sim.engine import Unit, build_spec, tile_dist                # noqa: E402
from clashrl.sim.env import SimMatchEnv                                   # noqa: E402


def _env(fix: bool) -> SimMatchEnv:
    cfg = Config.load()
    data = copy.deepcopy(cfg.data)
    data.setdefault("env", {})["nado_retarget_reach_fix"] = bool(fix)
    env = SimMatchEnv(Config(data=data, root=cfg.root)); env.rng.seed(0); env.reset()
    e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear()
    return env


def _hog_on_our_princess(env):
    """A hog locked on our left princess, then a tornado 4 tiles toward the bridge from it."""
    e = env.eng; tw = e.towers[0][0]
    hog = build_spec(env.db, "hog_rider", 11)
    u = Unit(spec=hog, team=1, x=tw.x, y=tw.y - (hog.reach + 0.5) / 32.0, hp=hog.hp); e.units.append(u)
    e.advance(0.3)                                                   # let it lock
    assert getattr(u, "target", None) is tw, "board setup: the hog must be locked on the tower"
    d0 = tile_dist(u.x, u.y, tw.x, tw.y)
    sp = env.specs[env.deck_keys.index("tornado")]
    nx, ny = u.x, u.y - 4.0 / 32.0
    e.elixir[0] = 10.0
    assert e.deploy(0, sp, nx, ny)
    env._register_nado(nx, ny, sp)
    return u, tw, d0, env._nado_watch[-1]


class NadoRetargetReachTests(unittest.TestCase):
    def test_hog_settles_inside_engine_reach_but_outside_the_old_test(self):
        env = _env(False)
        u, tw, d0, w = _hog_on_our_princess(env)
        self.assertGreater(d0, u.spec.reach + 1.0)                   # the old centre-to-centre test
        self.assertLess(d0, u.spec.reach + 1.0 + 1.5)                # ...misses by the tower's body

    def test_flag_off_never_lists_a_targeter(self):
        env = _env(False)
        u, tw, d0, w = _hog_on_our_princess(env)
        self.assertEqual(w["targeters"], [])
        for _ in range(25):
            env.eng.advance(0.1)
            if (env.eng.t - w["t0"]) <= env.nado_pull_window:
                env._nado_catch(w)
        self.assertEqual(w["targeters"], [])                          # not via the catch path either

    def test_flag_on_lists_the_hog_and_the_pull_earns_the_retarget(self):
        env = _env(True)
        u, tw, d0, w = _hog_on_our_princess(env)
        self.assertEqual([t[0] for t in w["targeters"]], [u])
        self.assertIs(w["targeters"][0][1], tw)
        for _ in range(25):
            env.eng.advance(0.1)
            if (env.eng.t - w["t0"]) <= env.nado_pull_window:
                env._nado_catch(w)
        d1 = tile_dist(u.x, u.y, tw.x, tw.y)
        # the credit's own predicate (env.py `_nado_credit`): pulled >= 1.6 tiles off the tower
        self.assertGreaterEqual(d1, d0 + 1.6, "the pull must move the hog off the tower by 1.6 tiles")
        self.assertGreater(u.hp, 0)


if __name__ == "__main__":
    unittest.main()
