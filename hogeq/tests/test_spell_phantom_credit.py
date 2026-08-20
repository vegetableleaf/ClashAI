"""The phantom-credit bug: spell_waste stopped firing AND the whiffed cast still paid.

User, 2026-08-20: "spell waste is not triggering and the model is getting rewarded for casting
spells at nothing."

ONE mechanism produced both halves. The team tracker BRIDGES a track for team_forget_s (4.5 s) so
a real unit that the detector misses for a frame or two is not forgotten -- and a FALSE POSITIVE
is remembered for exactly as long. A rocket's whole flight is about a second, so at impact the
phantom was still "inside the blast": spell_whiffed() said hit, no waste was billed, and the
credit _wincon_exec_live paid at cast by aim geometry stood untouched. The model was being taught
that casting at ghosts pays.

The verdict now runs on FRESH sightings only (env.spell_verify_fresh_s, 0.8 s -- still several
perception periods at 10 Hz, so the measured 1-3 frame detector gaps are bridged), and a whiff
hands back what the cast was paid.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.replay_mine import Detection, TeamTracker    # noqa: E402
from clashrl.reward import spell_whiffed                  # noqa: E402


def _det(base, x, y, team="unknown"):
    return Detection(base, x, y, 0.05, 0.05, 0.9, team, None, None, None)


class FreshEvidenceTests(unittest.TestCase):
    """A verdict about what a spell HIT must not run on memory."""

    def _tracker_with_marching_enemy(self, base="knight"):
        tr = TeamTracker(own_cards=["hog_rider"])
        tr.tag([_det(base, 0.50, 0.50)], 0.0)
        tr.tag([_det(base, 0.50, 0.56)], 0.4)      # marching down -> enemy, corroborated
        return tr

    def test_the_reported_bug_a_vanished_phantom_no_longer_counts_as_a_hit(self):
        """The phantom is seen twice, then never again. 2 seconds later a spell lands on its last
        known spot: memory still 'sees' it (that is the bug), fresh evidence does not."""
        tr = self._tracker_with_marching_enemy()
        remembered = tr.enemy_tracks(2.4)                       # inside forget_s = 4.5
        fresh = tr.enemy_tracks(2.4, max_age=0.8)
        self.assertTrue(remembered, "probe broken: the track should still be remembered")
        self.assertEqual([], fresh, "a 2s-stale track was served as fresh evidence")
        self.assertFalse(spell_whiffed(0.50, 0.56, 3.0, remembered),
                         "probe broken: memory should have masked the whiff")
        self.assertTrue(spell_whiffed(0.50, 0.56, 3.0, fresh),
                        "the phantom cast is STILL not billed as a whiff")

    def test_a_real_unit_under_the_spell_is_not_billed(self):
        """The whole reason bridging exists: a unit the detector misses for a frame or two is
        genuinely there, and 0.8s is several perception periods at 10Hz."""
        tr = self._tracker_with_marching_enemy()
        tr.tag([], 0.6)                                          # one blinked pass
        fresh = tr.enemy_tracks(0.7, max_age=0.8)
        self.assertTrue(fresh, "a one-frame blink wrongly emptied the fresh view")
        self.assertFalse(spell_whiffed(0.50, 0.56, 3.0, fresh),
                         "a spell landing on a real (briefly blinked) unit was billed a whiff")

    def test_a_continuously_seen_unit_stays_fresh(self):
        tr = self._tracker_with_marching_enemy()
        t = 0.4
        for _ in range(10):
            t += 0.1
            tr.tag([_det("knight", 0.50, 0.56)], t)
        self.assertTrue(tr.enemy_tracks(t, max_age=0.8))

    def test_max_age_none_keeps_the_full_memory(self):
        """Callers that WANT memory (the threat gate, the advisor's situation) are unchanged."""
        tr = self._tracker_with_marching_enemy()
        self.assertTrue(tr.enemy_tracks(2.4), "the default view lost its bridging")


class ClawbackWiringTests(unittest.TestCase):
    """A whiffed spell must be strictly negative, not 'a small penalty minus what it banked'."""

    def _env_src(self):
        import io
        p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "env.py")
        with io.open(p, encoding="utf-8") as fh:
            return fh.read()

    def test_the_cast_credit_is_recorded_for_the_pending_spell(self):
        src = self._env_src()
        self.assertIn('self._last_cast_rec["paid"]', src,
                      "the reward tick no longer records what a cast was paid")

    def test_a_whiff_hands_the_credit_back(self):
        src = self._env_src()
        self.assertIn("spell_waste_clawback", src,
                      "a whiffed spell keeps the credit its aim geometry earned at cast")

    def test_the_verdict_uses_the_fresh_view(self):
        src = self._env_src()
        self.assertIn("max_age=self.spell_verify_fresh_s", src,
                      "the spell verdict went back to running on bridged memory")

    def test_the_verdict_is_logged(self):
        """The user could not tell a detector false positive from the model genuinely casting at
        nothing; the impact line prints fresh vs remembered counts so the two are separable."""
        src = self._env_src()
        self.assertIn("[spell]", src, "spell impact verdicts are silent again")
        self.assertIn("PHANTOM", src, "the phantom marker (fresh=0 but remembered>0) is gone")


class DefensiveBowTests(unittest.TestCase):
    """FULL BAR + THEY ARE BUILDING IN THE BACK -> a DEFENSIVE bow (user rule, 2026-08-20).

    And the user's correction that made it right: "if enemy is building troops in the back it's
    no longer a quiet board." The gate only ever triaged OUR half, so a golem assembling behind
    their king read as nothing-to-answer and the loop went hunting for a PRESSURE play -- which
    is exactly how the offensive bow came to look correct against a push already paid for.
    """

    @classmethod
    def setUpClass(cls):
        from clashrl.cards import CardDB
        from clashrl.config import Config
        cls.db = CardDB(Config.load())

    def massing(self, units):
        from clashrl import threat_value as tv
        return tv.massing_in_back(self.db, units)

    def test_a_tank_parked_in_their_back_is_building(self):
        self.assertTrue(self.massing([(0.50, 0.15, "golem")]))

    def test_a_lone_cheap_cycle_card_is_not_building(self):
        """Cycling a 1-elixir card in the back is not a beatdown; answering it would be the
        premature-defence habit the triage tier exists to stop."""
        self.assertFalse(self.massing([(0.50, 0.15, "skeletons")]))

    def test_support_stacked_behind_counts(self):
        self.assertTrue(self.massing([(0.40, 0.18, "giant"), (0.40, 0.12, "witch")]))

    def test_once_it_crosses_the_river_it_is_an_ordinary_defence(self):
        """The signature needs BOTH halves. With something committed on our half this is a normal
        defence and the counter table owns it -- not a bow-placement decision."""
        self.assertFalse(self.massing([(0.50, 0.15, "golem"), (0.70, 0.55, "hog_rider")]))

    def test_a_unit_at_the_bridge_is_not_in_the_back(self):
        self.assertFalse(self.massing([(0.50, 0.40, "giant")]))

    def test_an_empty_board_is_not_building(self):
        self.assertFalse(self.massing([]))

    def test_the_gate_no_longer_calls_it_quiet(self):
        import io as _io
        p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "train_rl.py")
        with _io.open(p, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("A BACK BUILD IS NOT A QUIET BOARD", src,
                      "the threat gate went back to reading a back build as quiet")
        self.assertIn("massing_in_back", src)

    def test_the_forward_snap_is_skipped_while_they_build(self):
        """env.step's lane/lock/depth snap is what makes a bow OFFENSIVE; running it on a
        defensive bow would drag it back to the bridge and undo the whole rule."""
        import io as _io
        p = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "env.py")
        with _io.open(p, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("_enemy_massing_back", src)
        self.assertIn("_defensive_bow_cell", src)


if __name__ == "__main__":
    unittest.main(verbosity=1)
