"""The two user-reported pathing bugs, fixed 2026-08-19 from the datamined mechanics research.

MEASURED BEFORE: a Hog Rider blocked by ONE stationary defender dead-centre on its path stayed
latched FOREVER (60 s cap, same for knight / ice_golem / pekka / skeleton_king), because pure
radial separation cancelled the mover's own step head-on, tick after tick. And an 8-body push
took 24.7 s to fully cross the river with a 6.6 s dead stall, because two same-team walkers split
their separation symmetrically -- the follower was shoved BACKWARD every tick and the column's
net speed hit zero.

THE MECHANISMS (from the game-file datamine + the April-2025 pathfinding-rework notes + the
push-mechanics video): a blocked walker slides along the contact TANGENT toward its target,
mass-weighted (heavy, big-radius bodies -- Skeleton King, mass 10, radius 1.0 -- bend the path
less per tick, which is exactly why they are the designed blockers); and between two same-team
walkers the REAR pushes the FRONT -- a follower's velocity is never zeroed.

MEASURED AFTER: knight costs +0.6 s, ice_golem +0.8 s, pekka +1.5 s, skeleton_king +1.4 s over
the 6.5 s unblocked baseline -- graded by mass, never a latch. Cram: 17.3 s all-across, worst
stall 4.5 s.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.config import Config                       # noqa: E402
from clashrl.sim.engine import Unit, build_spec, _gap   # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SimMatchEnv(Config.load(), seed=3)

    def fresh(self):
        self.env.reset()
        e = self.env.eng
        e.units.clear()
        e.spells.clear()
        e.projectiles.clear()
        for t in e.towers[0] + e.towers[1]:
            t.hp = t.max_hp
        return e

    def spawn(self, e, team, key, x, y, hp_mult=1.0):
        sp = build_spec(e.db, key, 11)
        u = Unit(spec=sp, team=team, x=x, y=y, hp=sp.hp * hp_mult)
        u.deploy_left = 0.0
        e.units.append(u)
        return u

    def hog_time(self, blocker_key=None):
        """Seconds for a (durable) Hog to CONTACT our right princess tower, with an optional
        stationary blocker pinned dead-centre on its straight-line path."""
        e = self.fresh()
        hog = self.spawn(e, 1, "hog_rider", 14.5 / 18.0, 0.30, hp_mult=200.0)
        tower = e.towers[0][1]
        pin = None
        blk = None
        if blocker_key:
            t = 0.55
            blk = self.spawn(e, 0, blocker_key,
                             hog.x + (tower.x - hog.x) * t,
                             hog.y + (tower.y - hog.y) * t, hp_mult=400.0)
            pin = (blk.x, blk.y)
        for _ in range(600):
            if blk is not None:
                blk.x, blk.y = pin
            e.advance(0.1)
            if _gap(hog.x, hog.y, tower) <= hog.spec.reach + 0.62:
                return e.t
        return None


class DefenderStickTests(_Base):
    def test_a_knight_slows_the_hog_but_can_never_pin_it(self):
        base = self.hog_time()
        self.assertIsNotNone(base, "unblocked hog never arrived -- probe broken")
        blocked = self.hog_time("knight")
        self.assertIsNotNone(blocked, "REGRESSION: the hog latched on a single stationary knight")
        self.assertGreater(blocked, base, "the blocker must cost SOMETHING")
        self.assertLess(blocked - base, 4.0,
                        "a lone knight held the hog far longer than a slide-around arc")

    def test_the_designed_blockers_hold_longer_than_a_knight(self):
        """Skeleton King is mass 10 / radius 1.0 BY DESIGN; the slide is mass-weighted, so he
        must out-hold a mass-6 knight -- and still never pin."""
        kn = self.hog_time("knight")
        sk = self.hog_time("skeleton_king")
        self.assertIsNotNone(sk, "REGRESSION: skeleton_king latched the hog permanently")
        self.assertGreaterEqual(sk, kn,
                                "the designed blocker held the hog LESS than a plain knight")

    def test_an_attacking_blocker_is_not_slid_off_its_target(self):
        """The slide applies to WALKERS only: a unit that is attacking holds ground. A tanky
        attacker parked on our building keeps swinging at it rather than drifting."""
        e = self.fresh()
        tesla = self.spawn(e, 0, "tesla", 0.50, 0.60, hp_mult=400.0)   # must SURVIVE the probe
        pk = self.spawn(e, 1, "pekka", 0.50, 0.60 - (2.0) / 32.0, hp_mult=50.0)
        engaged_ticks = 0
        for _ in range(80):
            e.advance(0.1)
            if (pk.attacking or pk.locked) and _gap(pk.x, pk.y, tesla) <= pk.spec.reach + 1.0:
                engaged_ticks += 1
        self.assertGreater(engaged_ticks, 20,
                           "the pekka never settled into attacking the building -- either it "
                           "failed to engage or contact slid it off its target")


class BridgeFlowTests(_Base):
    ROWS = [("golem", 0.18), ("knight", 0.14), ("knight", 0.12), ("musketeer", 0.10),
            ("musketeer", 0.08), ("valkyrie", 0.06), ("goblins", 0.04), ("barbarians", 0.02)]

    def test_an_eight_body_push_crosses_without_a_long_jam(self):
        e = self.fresh()
        lane = 3.5 / 18.0
        us = [self.spawn(e, 1, k, lane + (i % 2) * 0.02 - 0.01, y, hp_mult=50.0)
              for i, (k, y) in enumerate(self.ROWS)]
        crossed = {}
        last_t = 0.0
        worst = 0.0
        for _ in range(350):                     # 35 s cap; measured healthy time is ~17 s
            e.advance(0.1)
            for u in us:
                if id(u) not in crossed and u.y > 0.50:
                    crossed[id(u)] = e.t
                    last_t = e.t
            if len(crossed) == len(us):
                break
            if crossed:
                worst = max(worst, e.t - last_t)
        self.assertEqual(len(us), len(crossed),
                         "REGRESSION: the push jammed at the bridge (only %d/%d crossed in 35 s)"
                         % (len(crossed), len(us)))
        self.assertLess(worst, 6.0,
                        "the column dead-stalled %.1f s between crossings" % worst)


if __name__ == "__main__":
    unittest.main(verbosity=1)
