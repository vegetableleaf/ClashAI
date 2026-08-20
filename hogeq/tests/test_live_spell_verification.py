"""Live spell-impact verification + the threat-gate memory fix (2026-08-19, user reports).

THE BUG SET, as reported and confirmed:
1. "the live training results never displays spell_waste even when the model misses every single
   spell" -- true by construction: env.py's own note says the spell-impact frame sampler was
   RETIRED, so live spells were scored at cast by aim geometry (_wincon_exec_live) and a rocket
   into empty grass paid like a hit. `spell_waste` existed only in the sim.
2. No pricing for a tornado that pulls enemies into a BETTER position for them.
3. "the advisor suggests HOLD despite the enemy making several plays" -- the _needs_answer gate
   read only d.team == "enemy" from the LATEST detector pass, so (a) a threat that blinked out on
   the decision tick (the detector misses units in ~31% of passes) made the board read quiet: the
   model FORGOT an enemy it had seen; the tracker's bridged tracks now feed the gate too.

The evaluators are pure functions in reward.py (testable without a live window); the queue and
gate wiring are exercised through minimal stand-ins shaped like the live objects.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.reward import nado_regressed, spell_whiffed          # noqa: E402
from clashrl.replay_mine import Detection, TeamTracker            # noqa: E402


class SpellWhiffTests(unittest.TestCase):
    def test_empty_blast_is_a_whiff(self):
        self.assertTrue(spell_whiffed(0.5, 0.3, 0.12, []))

    def test_an_enemy_inside_the_blast_is_not(self):
        self.assertFalse(spell_whiffed(0.5, 0.3, 0.12, [(0.55, 0.33, 0, 0)]))

    def test_a_live_tower_aim_is_exempt(self):
        """Rocket/EQ chip on a standing tower is a legitimate cast, never a whiff."""
        self.assertFalse(spell_whiffed(0.25, 0.21, 0.12, [],
                                       tower_anchors=[(0.25, 0.21)], tower_alive=[True]))

    def test_a_dead_tower_is_no_exemption(self):
        """Rocketing rubble is exactly the waste this term exists to price."""
        self.assertTrue(spell_whiffed(0.25, 0.21, 0.12, [],
                                      tower_anchors=[(0.25, 0.21)], tower_alive=[False]))

    def test_the_tracker_bridges_a_detector_blink(self):
        """The whole reason tracks (not raw detections) feed the verdict: a unit the detector
        missed THIS pass is still in the tracker's memory, so the landed spell is not billed."""
        tr = TeamTracker(own_cards=["hog_rider"])
        d0 = Detection("knight", 0.50, 0.60, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d0], 0.0)
        d1 = Detection("knight", 0.50, 0.66, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d1], 0.5)                                  # marching down -> enemy
        tr.tag([], 1.0)                                    # the detector BLINKS: empty pass
        tracks = tr.enemy_tracks(1.2)
        self.assertTrue(tracks, "the tracker forgot the enemy after one missed pass")
        self.assertFalse(spell_whiffed(0.50, 0.66, 0.12, tracks),
                         "a spell landing on a remembered enemy was billed as a whiff")


class NadoRegressionTests(unittest.TestCase):
    MY = [(0.25, 0.80), (0.72, 0.80)]

    def test_pulled_closer_and_alive_is_bad(self):
        self.assertTrue(nado_regressed([(0.5, 0.55)], [(0.5, 0.62, 0, 0)], self.MY))

    def test_pulled_units_that_died_are_not_billed(self):
        self.assertFalse(nado_regressed([(0.5, 0.55)], [], self.MY))

    def test_pulled_away_from_us_is_fine(self):
        self.assertFalse(nado_regressed([(0.5, 0.55)], [(0.5, 0.50, 0, 0)], self.MY))

    def test_sub_tile_drift_is_free(self):
        self.assertFalse(nado_regressed([(0.5, 0.55)], [(0.5, 0.559, 0, 0)], self.MY))


class SimNadoBadTests(unittest.TestCase):
    """The engine-truth twin, through the real _nado_watch machinery."""

    @classmethod
    def setUpClass(cls):
        from clashrl.config import Config
        from clashrl.sim.env import SimMatchEnv
        cls.env = SimMatchEnv(Config.load(), seed=5)

    def _run_watch(self, survivor_moves_to):
        from clashrl.sim.engine import Unit, build_spec
        env = self.env
        env.reset()
        e = env.eng
        e.units.clear()
        sp = build_spec(e.db, "knight", 11)
        u = Unit(spec=sp, team=1, x=0.50, y=0.55, hp=sp.hp * 50)
        u.deploy_left = 0.0
        e.units.append(u)
        env._nado_watch = [{"t0": e.t, "cx": 0.50, "cy": 0.55, "pulled": [u],
                            "pulled_at": [(u.x, u.y)], "targeters": [],
                            "king_was_asleep": False, "early_done": True}]
        e.t += 4.0                                      # expire the watch
        u.x, u.y = survivor_moves_to
        before = dict(getattr(env.rw_stats, "run", {}) or {})
        credit = env._nado_shaping()
        return credit

    def test_a_survivor_dragged_toward_our_tower_is_billed(self):
        credit = self._run_watch((0.50, 0.66))          # ~3.5 tiles closer to our towers
        self.assertLess(credit, 0.0, "the bad pull was not billed")

    def test_a_survivor_left_farther_away_is_not(self):
        credit = self._run_watch((0.50, 0.47))
        self.assertGreaterEqual(credit, 0.0)


class ThreatGateMemoryTests(unittest.TestCase):
    """The HOLD bug: the gate must triage the tracker's remembered enemies, not just the pass."""

    def _gate(self, dets, tracker):
        """Replicates train_rl._needs_answer's structure against stand-ins (it is a closure)."""
        import time as _t
        from clashrl import threat_value
        from clashrl.cards import CardDB
        from clashrl.config import Config
        db = CardDB(Config.load())
        seen, bases = [], []
        for d in dets:
            if d.team == "enemy" and float(getattr(d, "gy", 0.0)) >= 0.42:
                bases.append(str(d.base))
                seen.append((float(d.cx), float(getattr(d, "gy", 0.0)), str(d.base)))
        for tr in tracker.enemy_tracks(_t.time(), with_base=True):
            x, y, b = float(tr[0]), float(tr[1]), (str(tr[4]) if len(tr) > 4 and tr[4] else "")
            if y < 0.42 or not b:
                continue
            if any(abs(x - sx) + abs(y - sy) < 0.06 and b == sb for sx, sy, sb in seen):
                continue
            bases.append(b)
            seen.append((x, y, b))
        if not bases:
            return False
        return threat_value.group_ignore_frac(db, bases, tower_level=15) >= threat_value.IGNORE_FRAC

    def _tracker_with_marching_enemy(self, base="pekka"):
        import time as _t
        now = _t.time()
        tr = TeamTracker(own_cards=["hog_rider", "tesla", "earthquake"])
        d0 = Detection(base, 0.50, 0.55, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d0], now - 1.0)
        d1 = Detection(base, 0.50, 0.62, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d1], now - 0.5)                         # marching down -> enemy
        return tr

    def test_a_blinked_out_threat_still_needs_an_answer(self):
        """The reported failure: enemy seen, detector blinks on the decision tick, gate said
        quiet, advisor said HOLD. The tracker's memory now keeps the gate honest."""
        import time as _t
        tr = self._tracker_with_marching_enemy()
        tr.tag([], _t.time())                            # the decision-tick blink: empty pass
        self.assertTrue(self._gate([], tr),
                        "an empty detector pass made a remembered P.E.K.K.A read as a quiet board")

    def test_a_genuinely_quiet_board_still_reads_quiet(self):
        tr = TeamTracker(own_cards=["hog_rider"])
        self.assertFalse(self._gate([], tr))

    def test_no_double_count_when_both_see_the_same_unit(self):
        """A unit present in BOTH the pass and the memory is one threat, not two: a lone
        skeletons group must stay ignorable even counted through both paths."""
        import time as _t
        now = _t.time()
        tr = TeamTracker(own_cards=["hog_rider"])
        d0 = Detection("skeletons", 0.50, 0.55, 0.04, 0.04, 0.9, "unknown", None, None, None)
        tr.tag([d0], now - 1.0)
        d1 = Detection("skeletons", 0.50, 0.60, 0.04, 0.04, 0.9, "unknown", None, None, None)
        tr.tag([d1], now - 0.5)
        live = Detection("skeletons", 0.50, 0.60, 0.04, 0.04, 0.9, "enemy", None, None, None)
        self.assertFalse(self._gate([live], tr),
                         "one skeletons group was double-counted into a real threat")


class AdvisorSituationMemoryTests(unittest.TestCase):
    """The other half of the HOLD report: the gate remembering is not enough if the ADVISOR's
    situation string still describes one detector pass -- the LLM was literally told "nothing on
    the board" while a remembered enemy marched. Replicates _situation's memory-append block
    (it is a closure in train_rl, like _needs_answer above)."""

    class _Warp:
        def frame_to_board(self, x, y):
            return x, y                                  # identity: frame coords ARE board coords

    def _remembered_groups(self, dets, tracker):
        import time as _t
        seen_xy = [(float(d.cx), float(d.gy), str(d.base)) for d in dets if d.team == "enemy"]
        groups = {}
        w = self._Warp()
        for tr in tracker.enemy_tracks(_t.time(), with_base=True):
            x, y, b = float(tr[0]), float(tr[1]), (str(tr[4]) if len(tr) > 4 and tr[4] else "")
            if not b:
                continue
            if any(abs(x - sx) + abs(y - sy) < 0.06 and b == sb for sx, sy, sb in seen_xy):
                continue
            seen_xy.append((x, y, b))
            bx, by = w.frame_to_board(x, y)
            where = ("deep in your half" if by > 0.66 else
                     "in your half" if by > 0.52 else
                     "at the bridge" if by > 0.44 else "on their side")
            lane = "left" if bx < 0.42 else "right" if bx > 0.58 else "centre"
            groups[(b.replace("_", " "), where + ", briefly out of sight", lane)] = 1
        return groups

    def _marching(self, base="knight"):
        import time as _t
        now = _t.time()
        tr = TeamTracker(own_cards=["hog_rider", "tesla"])
        d0 = Detection(base, 0.50, 0.55, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d0], now - 1.0)
        d1 = Detection(base, 0.50, 0.62, 0.05, 0.05, 0.9, "unknown", None, None, None)
        tr.tag([d1], now - 0.5)
        return tr

    def test_a_blinked_enemy_is_still_described_to_the_advisor(self):
        import time as _t
        tr = self._marching()
        tr.tag([], _t.time())                            # the advisor-tick blink
        groups = self._remembered_groups([], tr)
        self.assertTrue(any(n == "knight" and "briefly out of sight" in wh
                            for (n, wh, _l) in groups),
                        "the advisor was told nothing about a remembered marching knight")

    def test_a_unit_the_pass_already_reports_is_not_repeated_from_memory(self):
        tr = self._marching()
        live = Detection("knight", 0.50, 0.62, 0.05, 0.05, 0.9, "enemy", None, None, None)
        self.assertEqual({}, self._remembered_groups([live], tr),
                         "the same knight was described twice (once live, once from memory)")


if __name__ == "__main__":
    unittest.main(verbosity=1)
