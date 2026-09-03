"""LOCK-AWARE target predictor (HANDOFF §5cb, GAUNTLET L27). `interactions.predict_targets` gains an
optional per-unit `Hint` (engaged / deploying); with `hints=None` it is the historical memoryless
read (measured L27: the same 74.2% agreement on the same 60,599 samples as L17), with hints it
keeps a swinging unit's target, gives a deploying unit none, and keeps a building idle when nothing
is inside its arms (95.8% agreement on the engine, up from 74.2%). The sim feeds the hints only
under `observation.lock_aware_targets` (default off: live has no track memory yet)."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np                              # noqa: E402
from clashrl.config import Config               # noqa: E402
from clashrl import interactions                # noqa: E402
from clashrl.interactions import Hint           # noqa: E402
from clashrl.sim import view                    # noqa: E402
from clashrl.sim.env import SimMatchEnv         # noqa: E402
from clashrl.sim.engine import Unit, build_spec  # noqa: E402

MY_T = [(0.25, 0.80, True), (0.75, 0.80, True), (0.50, 0.91, True)]
EN_T = [(0.25, 0.20, True), (0.75, 0.20, True), (0.50, 0.09, True)]


def _cfg(**over):
    cfg = Config.load()
    data = copy.deepcopy(cfg.data)
    data.setdefault("observation", {}).update(over)
    return Config(data=data, root=cfg.root)


class PredictorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SimMatchEnv(Config.load(), seed=0).db

    def test_no_hints_is_the_memoryless_read(self):
        units = [("enemy", "knight", 0.50, 0.60), ("mine", "musketeer", 0.50, 0.70),
                 ("enemy", "hog_rider", 0.30, 0.50)]
        a = interactions.predict_targets(units, MY_T, EN_T, self.db)
        b = interactions.predict_targets(units, MY_T, EN_T, self.db, None)
        self.assertEqual(a, b)
        va = interactions.interaction_vector(units, MY_T, EN_T, self.db)
        vb = interactions.interaction_vector(units, MY_T, EN_T, self.db, hints=None)
        self.assertTrue(np.array_equal(va, vb))
        # an all-default hint list = the same targets as no hints for units that are not buildings
        c = interactions.predict_targets(units, MY_T, EN_T, self.db, [Hint()] * 3)
        self.assertEqual(a, c)

    def test_engaged_hint_keeps_the_farther_target(self):
        # the knight is swinging at our musketeer; a closer skeleton lands next to it
        units = [("enemy", "knight", 0.50, 0.60), ("mine", "musketeer", 0.50, 0.66),
                 ("mine", "skeletons", 0.52, 0.60)]
        memoryless = interactions.predict_targets(units, MY_T, EN_T, self.db)
        self.assertEqual(memoryless[0][:2], ("unit", 2), "memoryless: the nearer skeleton")
        hinted = interactions.predict_targets(units, MY_T, EN_T, self.db,
                                              [Hint(engaged=("unit", 1)), None, None])
        self.assertEqual(hinted[0][:2], ("unit", 1), "engaged: it keeps the musketeer")
        # an engaged hint pointing at a DEAD tower or the wrong side is ignored, not trusted
        dead = [(0.25, 0.80, False), (0.75, 0.80, True), (0.50, 0.91, True)]
        h2 = interactions.predict_targets(units, dead, EN_T, self.db,
                                          [Hint(engaged=("tower", 0)), None, None])
        self.assertEqual(h2[0][:2], ("unit", 2))
        h3 = interactions.predict_targets(units, MY_T, EN_T, self.db,
                                          [Hint(engaged=("unit", 0)), None, None])
        self.assertEqual(h3[0][:2], ("unit", 2), "cannot be engaged on itself / own side")

    def test_deploying_hint_gives_no_target(self):
        units = [("enemy", "hog_rider", 0.50, 0.55)]
        (k, i, d), = interactions.predict_targets(units, MY_T, EN_T, self.db, [Hint(deploying=True)])
        self.assertIsNone(k)
        (px, py, urg), = interactions.mover_forecast(units, MY_T, EN_T, self.db,
                                                     hints=[Hint(deploying=True)])
        self.assertEqual((px, py, urg), (0.50, 0.55, 0.0), "forecast in place, no urgency")
        v = interactions.interaction_vector(units, MY_T, EN_T, self.db, hints=[Hint(deploying=True)])
        self.assertEqual(float(v.sum()), 0.0, "lights no tower dim while deploying")

    def test_building_idles_unless_something_is_in_reach(self):
        units = [("mine", "tesla", 0.50, 0.75), ("enemy", "knight", 0.50, 0.40)]
        memoryless = interactions.predict_targets(units, MY_T, EN_T, self.db)
        self.assertEqual(memoryless[0][0], "tower", "memoryless: 'nearest tower' it can never reach")
        hinted = interactions.predict_targets(units, MY_T, EN_T, self.db, [None, None])
        self.assertIsNone(hinted[0][0], "lock-aware: nothing in its arms -> idle")
        close = [("mine", "tesla", 0.50, 0.75), ("enemy", "knight", 0.50, 0.71)]
        hinted = interactions.predict_targets(close, MY_T, EN_T, self.db, [None, None])
        self.assertEqual(hinted[0][:2], ("unit", 1))
        # siege building in range of a princess -> that tower; a tesla in the same spot -> idle
        bow = [("mine", "x_bow", 0.25, 0.50)]
        self.assertEqual(interactions.predict_targets(bow, MY_T, EN_T, self.db, [None])[0][:2],
                         ("tower", 0))
        tes = [("mine", "tesla", 0.25, 0.50)]
        self.assertIsNone(interactions.predict_targets(tes, MY_T, EN_T, self.db, [None])[0][0])


class SimWiringTests(unittest.TestCase):
    def _board(self, cfg):
        env = SimMatchEnv(cfg, seed=0)
        env.reset()
        e = env.eng; e.units.clear(); e.spells.clear(); e.projectiles.clear()
        tw = e.towers[0][0]                                     # our left princess
        hs = build_spec(env.db, "hog_rider", 11)
        hog = Unit(spec=hs, team=1, x=tw.x, y=tw.y - (hs.reach + 0.5) / 32.0, hp=hs.hp)
        e.units.append(hog)
        e.advance(0.3)
        self.assertTrue(hog.locked, "the hog is swinging at the princess")
        self.assertIs(hog.target, tw)
        ks = build_spec(env.db, "knight", 11)
        fresh = Unit(spec=ks, team=0, x=0.5, y=0.7, hp=ks.hp)
        fresh.deploy_left = 1.0
        e.units.append(fresh)
        return env, hog, fresh

    def test_engine_hints_are_aligned_and_read_lock_state(self):
        env, hog, fresh = self._board(Config.load())
        units, my_t, en_t, hs = view.interaction_state(env.eng, 0, None, hints=True)
        self.assertEqual(len(units), len(hs))
        alive = [u for u in env.eng.units if u.hp > 0 and getattr(u.spec, "base", None) is not None]
        h_hog = hs[alive.index(hog)]
        self.assertEqual(h_hog.engaged, ("tower", 0), "locked on OUR left princess = 'mine' tower 0")
        self.assertFalse(h_hog.deploying)
        self.assertTrue(hs[alive.index(fresh)].deploying)
        # the 3-tuple form is untouched
        self.assertEqual(len(view.interaction_state(env.eng, 0, None)), 3)

    def test_flag_gates_the_hints_into_the_obs(self):
        env, hog, fresh = self._board(_cfg(lock_aware_targets=False))
        self.assertIsNone(env._interaction_state()[3], "flag off: memoryless, every ckpt's read")
        env2, hog2, fresh2 = self._board(_cfg(lock_aware_targets=True))
        hs = env2._interaction_state()[3]
        self.assertIsNotNone(hs)
        self.assertTrue(any(h.engaged == ("tower", 0) for h in hs))


if __name__ == "__main__":
    unittest.main()
