"""Reaction latency + phantom-track fixes (user reports, 2026-08-20 night).

REPORT 1: "responds to a hog rider at the bridge 4-5 seconds after it was placed." The healthy
chain is ~1.3 s; the 4-5 s sessions were the degraded one -- the perception thread dying SILENTLY
(the act loop falls back to 1 Hz synchronous detection with nothing in the log), motion
classification then needing seconds, and the pre-fix advisor burning 0.9 s per call. Pinned here:
the wake event now fires on a FRESH first sighting on the enemy side (placement IS the
commitment -- waiting for the classifier costs 0.3-0.7 s of hog march), and the loop self-heals.

REPORT 2: "a single flicker is eliciting a response... whiffed spells in random tiles." Exactly
right: a 1-frame phantom classified enemy by the side prior / a bar misread became a TRACK served
for forget_s = 4.5 s -- the threat gate opened and the spell wheels aimed at it. Tracks now carry
a sighting count and are served only at >= min_hits (2); the gate's live-det path demands the
same corroboration.
"""
from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.replay_mine import Detection, TeamTracker    # noqa: E402


def _det(base, x, y, team="unknown"):
    return Detection(base, x, y, 0.05, 0.05, 0.9, team, None, None, None)


class TrackCorroborationTests(unittest.TestCase):
    """min_hits: a 1-frame phantom must never be SERVED as an enemy."""

    def test_a_single_frame_phantom_is_not_served(self):
        """Deep in the enemy half the side prior calls a det 'enemy' on FIRST sighting -- that
        verdict may stand, but serving it before a second sighting is what armed the spell
        wheels at empty tiles."""
        tr = TeamTracker(own_cards=["x_bow"])
        tr.tag([_det("knight", 0.50, 0.20)], 0.0)          # one flicker, deep enemy side
        self.assertEqual([], tr.enemy_tracks(0.1),
                         "a single-frame phantom was served as an enemy track")

    def test_a_second_sighting_makes_it_real(self):
        tr = TeamTracker(own_cards=["x_bow"])
        tr.tag([_det("knight", 0.50, 0.20)], 0.0)
        tr.tag([_det("knight", 0.50, 0.21)], 0.15)         # re-sighted ~one perception period later
        self.assertTrue(tr.enemy_tracks(0.2), "a corroborated enemy was not served")

    def test_the_blink_bridge_still_works_after_corroboration(self):
        """The forget_s gap-bridging must survive the min_hits change: 2 sightings then a blink
        still serves the remembered track."""
        tr = TeamTracker(own_cards=["x_bow"])
        tr.tag([_det("knight", 0.50, 0.60)], 0.0)
        tr.tag([_det("knight", 0.50, 0.66)], 0.5)          # marching down -> enemy, hits=2
        tr.tag([], 1.0)                                    # detector blink
        self.assertTrue(tr.enemy_tracks(1.2), "the blink bridge was lost")

    def test_detections_carry_their_corroboration_count(self):
        tr = TeamTracker(own_cards=["x_bow"])
        d1 = _det("knight", 0.50, 0.60)
        tr.tag([d1], 0.0)
        self.assertEqual(1, d1.trk_hits)
        d2 = _det("knight", 0.50, 0.62)
        tr.tag([d2], 0.2)
        self.assertEqual(2, d2.trk_hits)


class WakeEventTests(unittest.TestCase):
    """_should_wake: placement is the commitment -- don't wait for the classifier."""

    def _loop(self, own_cards=("x_bow", "tesla")):
        from clashrl.perception import PerceptionLoop

        class _Cfg:
            def get(self, *a, **k):
                return k.get("default")
        loop = PerceptionLoop.__new__(PerceptionLoop)     # no thread, no capture: just the logic
        loop._cnt_hist = __import__("collections").deque()
        loop._half_hist = __import__("collections").deque()
        loop._tracker = TeamTracker(own_cards=list(own_cards))
        loop.wakes = 0
        loop.passes = 0
        return loop

    def test_a_fresh_first_sighting_on_their_side_wakes_the_act_loop(self):
        """The old rule waited for team == 'enemy' (motion needs 0.3-0.7 s of march). A fresh
        track at the bridge that is not one of OUR cards is a commitment worth waking for NOW."""
        loop = self._loop()
        dets = [_det("hog_rider", 0.72, 0.45)]
        loop._tracker.tag(dets, time.time())               # annotates trk_hits = 1
        self.assertTrue(loop._should_wake(dets, time.time()),
                        "a fresh enemy-side placement did not wake the act loop")

    def test_our_own_fresh_card_does_not_wake_it(self):
        """Placed where WE can actually place -- our half. (Deep in the ENEMY half even an
        own-deck base classifies enemy by side prior, and waking would be right: the opponent
        can run our cards.)"""
        loop = self._loop()
        dets = [_det("tesla", 0.50, 0.60)]                 # our tesla, our half
        loop._tracker.tag(dets, time.time())
        self.assertFalse(loop._should_wake(dets, time.time()),
                         "our own placement woke the act loop")

    def test_a_persisting_unit_does_not_wake_it_twice(self):
        """Only the FIRST sighting is an event; the same unit re-sighted is not a new commitment
        (the enemy-count edge rule handles genuine count rises)."""
        loop = self._loop()
        now = time.time()
        d1 = [_det("hog_rider", 0.72, 0.45)]
        loop._tracker.tag(d1, now)
        self.assertTrue(loop._should_wake(d1, now))
        d2 = [_det("hog_rider", 0.72, 0.47)]
        loop._tracker.tag(d2, now + 0.1)
        self.assertFalse(loop._should_wake(d2, now + 0.1),
                         "the same unit fired a second wake with no count edge")

    def test_an_unowned_unit_deep_in_our_half_wakes_via_the_veto(self):
        """Writing this test found a reaction path FASTER than the placement trigger: a card we
        do not own, sighted deep in OUR half, cannot be ours (deck veto) -- the tracker calls it
        enemy on the FIRST sighting and the original count-edge rule wakes immediately. A tunnel
        Miner or a deep Goblin Barrel gets a wake with zero classification delay."""
        loop = self._loop(own_cards=("x_bow", "tesla"))    # no knight in this deck
        dets = [_det("knight", 0.30, 0.62)]                # deep our half, first sighting
        loop._tracker.tag(dets, time.time())
        self.assertEqual("enemy", dets[0].team,
                         "the deck veto no longer classifies an unowned deep unit as enemy")
        self.assertTrue(loop._should_wake(dets, time.time()),
                        "an enemy materialising deep in our half did not wake the act loop")

    def test_an_enemy_crossing_into_our_half_wakes_the_act_loop(self):
        """The commitment the old rules missed: a unit we have tracked all along steps into our
        half. No new sighting, no rise in the total -- so nothing fired, and the act loop could
        sit out the rest of its paced wait (MEASURED at 0.49s, the largest slice of reaction
        time) before noticing the push that needs answering."""
        import time as _t
        loop = self._loop()
        now = _t.time()
        their_side = [_det("giant", 0.50, 0.30)]
        loop._tracker.tag(their_side, now - 0.5)
        loop._should_wake(their_side, now - 0.5)            # prime the history
        crossed = [_det("giant", 0.50, 0.50)]               # now on OUR half
        loop._tracker.tag(crossed, now)
        self.assertTrue(loop._should_wake(crossed, now),
                        "a tracked enemy crossing the river did not wake the act loop")

    def test_a_unit_that_stays_on_our_half_does_not_re_fire(self):
        """The edge is a RISE in how many are on our side, not a level -- otherwise every pass
        while a push is parked in our half would wake the loop and thrash the decision rate."""
        import time as _t
        loop = self._loop()
        now = _t.time()
        here = [_det("giant", 0.50, 0.50)]
        loop._tracker.tag(here, now - 0.5)
        loop._should_wake(here, now - 0.5)
        loop._tracker.tag(here, now)
        self.assertFalse(loop._should_wake(here, now),
                         "a stationary push re-fired the wake every pass")


class GatePhantomTests(unittest.TestCase):
    """The threat gate must not triage a 1-frame phantom (mirrors _needs_answer's det path)."""

    def _gate_counts(self, d):
        """The live-det condition from train_rl._needs_answer, verbatim."""
        return (d.team == "enemy" and float(getattr(d, "gy", 0.0)) >= 0.42
                and int(getattr(d, "trk_hits", 2) or 2) >= 2)

    def test_a_one_frame_phantom_does_not_open_the_gate(self):
        tr = TeamTracker(own_cards=["x_bow"])
        d = _det("pekka", 0.50, 0.60)
        d.bar_vote = "enemy"                               # the bar misread that births phantoms
        tr.tag([d], 0.0)
        if d.team == "enemy":                              # verdict may or may not fire rank 3
            self.assertFalse(self._gate_counts(d),
                             "a single-frame enemy det was allowed to open the threat gate")

    def test_a_corroborated_enemy_still_opens_it(self):
        tr = TeamTracker(own_cards=["x_bow"])
        tr.tag([_det("pekka", 0.50, 0.55)], 0.0)
        d = _det("pekka", 0.50, 0.62)
        tr.tag([d], 0.5)                                   # marching down, hits=2
        self.assertEqual("enemy", d.team)
        self.assertTrue(self._gate_counts(d), "a real corroborated enemy no longer opens the gate")

    def test_dets_without_the_annotation_still_count(self):
        """Sources that don't annotate corroboration (older paths, tests) default to counting."""
        d = _det("pekka", 0.50, 0.62, team="enemy")
        self.assertTrue(self._gate_counts(d))


class LeakGuardTests(unittest.TestCase):
    """The offense window: a greedy WAIT at full elixir on a quiet board becomes the pressure
    play (replicates the train_rl conversion, which is a closure)."""

    CARDS = ["tornado", "tesla", "tesla_evo", "ice_wizard", "x_bow", "rocket", "knight",
             "knight_evo", "the_log", "skeletons"]
    COST = {"tornado": 3, "tesla": 4, "tesla_evo": 4, "ice_wizard": 3, "x_bow": 6,
            "rocket": 6, "knight": 3, "knight_evo": 3, "the_log": 2, "skeletons": 1}

    def _convert(self, action, na, elixir, hand=("x_bow", "knight", "the_log", "skeletons"),
                 guard=9.5):
        hand_vec = [1.0 if c in hand else 0.0 for c in self.CARDS]
        if action[0] == 0 and not na and elixir >= guard:
            bow = next((i for i, v in enumerate(hand_vec)
                        if v > 0.5 and self.CARDS[i].replace("_evo", "") == "x_bow"
                        and self.COST[self.CARDS[i]] <= elixir + 1e-6), None)
            if bow is not None:
                return (1, bow, 0)
        return action

    def test_full_elixir_quiet_wait_becomes_the_bow(self):
        got = self._convert((0, 0, 0), na=False, elixir=9.8)
        self.assertEqual(1, got[0], "the leak was left to happen")
        self.assertEqual("x_bow", self.CARDS[got[1]])

    def test_a_threatened_board_is_never_converted(self):
        """Defence outranks pressure: needs_answer suppresses the wheel entirely."""
        self.assertEqual((0, 0, 0), self._convert((0, 0, 0), na=True, elixir=9.8))

    def test_below_the_guard_the_model_keeps_its_wait(self):
        """Banking IS doctrine (3.5 cycle deck): only the imminent LEAK is corrected."""
        self.assertEqual((0, 0, 0), self._convert((0, 0, 0), na=False, elixir=8.0))

    def test_a_real_play_is_never_overridden(self):
        self.assertEqual((1, 6, 42), self._convert((1, 6, 42), na=False, elixir=9.8))

    def test_no_bow_in_hand_means_no_conversion(self):
        got = self._convert((0, 0, 0), na=False, elixir=9.8,
                            hand=("knight", "the_log", "skeletons", "tornado"))
        self.assertEqual((0, 0, 0), got)


class SpellServingTests(unittest.TestCase):
    """Enemy spells are effects, not units (user rule, 2026-08-20): never served as targets --
    except the spawn-spells, which put units on the board and demand an answer."""

    def _tracker(self):
        return TeamTracker(own_cards=["knight"],
                           is_spell=lambda b: b in ("fireball", "graveyard", "the_log"))

    def _sight_twice(self, tr, base, y=0.62):
        tr.tag([_det(base, 0.50, y)], 0.0)
        d = _det(base, 0.50, y)
        tr.tag([d], 0.3)
        return d

    def test_an_enemy_spell_is_never_served(self):
        tr = self._tracker()
        d = self._sight_twice(tr, "fireball")             # deck veto -> enemy, corroborated
        self.assertEqual("enemy", d.team)
        self.assertEqual([], tr.enemy_tracks(0.4),
                         "their fireball was served as something to aim at")

    def test_a_spawn_spell_is_served(self):
        """Graveyard/barrel land units where they land -- the user's own exception."""
        tr = self._tracker()
        self._sight_twice(tr, "graveyard")
        self.assertTrue(tr.enemy_tracks(0.4), "an enemy graveyard was ignored")

    def test_spawn_spells_cover_the_wincon_spells(self):
        from clashrl.replay_mine import SPAWN_SPELLS
        self.assertIn("graveyard", SPAWN_SPELLS)
        self.assertIn("goblin_barrel", SPAWN_SPELLS)


class StaticPhantomTests(unittest.TestCase):
    """A misdetected static re-sights every pass, so min_hits never kills it. A REAL enemy deep
    in our half marches or takes tower fire; one that does neither for phantom_stale_s is not a
    unit (their side is exempt: enemy buildings legitimately stand still and unhurt)."""

    def _run(self, y=0.62, move=0.0, bars=False, seconds=7.0, own=("x_bow",)):
        tr = TeamTracker(own_cards=list(own))
        t, i = 0.0, 0
        while t <= seconds:
            d = _det("knight", 0.50, y + move * i)
            if bars:
                d.bar_vote = "enemy"
            tr.tag([d], t)
            t += 0.5
            i += 1
        return tr, t

    def test_a_never_moving_never_hit_deep_track_stops_being_served(self):
        tr, now = self._run()
        self.assertEqual([], tr.enemy_tracks(now),
                         "a 7-second stationary unhit 'enemy' deep in our half was still served")

    def test_it_is_served_before_the_staleness_clock_runs_out(self):
        tr = TeamTracker(own_cards=["x_bow"])
        tr.tag([_det("knight", 0.50, 0.62)], 0.0)
        tr.tag([_det("knight", 0.50, 0.62)], 0.4)
        self.assertTrue(tr.enemy_tracks(0.5),
                        "a young corroborated enemy was suppressed by the staleness rule")

    def test_a_marching_enemy_is_served_forever(self):
        tr, now = self._run(y=0.50, move=0.008)           # walking toward our towers
        self.assertTrue(tr.enemy_tracks(now), "a genuinely marching enemy was demoted")

    def test_an_enemy_taking_tower_fire_is_served_forever(self):
        """A tank whacking our princess stands still -- but the tower shoots it, its HP bar
        appears, and that bar evidence is exactly what keeps it real."""
        tr, now = self._run(bars=True)
        self.assertTrue(tr.enemy_tracks(now), "a stationary but BLEEDING enemy was demoted")

    def test_their_side_statics_are_exempt(self):
        """An enemy pump/tesla stands still and unhurt on their side for ages -- still real."""
        tr, now = self._run(y=0.30)
        self.assertTrue(tr.enemy_tracks(now), "their-side static (a building) was demoted")


class SituationSpellFilterTests(unittest.TestCase):
    """The advisor's situation string must skip 1-frame phantoms and non-spawn spells (mirrors
    _situation's enemy-det conditions -- the closure itself lives in train_rl)."""

    class _Kind:
        SPELLS = {"fireball", "the_log", "rocket", "graveyard", "goblin_barrel", "earthquake"}

        def kind(self, b):
            return "spell" if b in self.SPELLS else "troop"

    def _described(self, d):
        from clashrl.replay_mine import SPAWN_SPELLS
        _db = self._Kind()
        if int(getattr(d, "trk_hits", 2) or 2) < 2:
            return False
        if _db.kind(str(d.base)) == "spell" and str(d.base) not in SPAWN_SPELLS:
            return False
        return True

    def test_a_one_frame_phantom_is_not_described(self):
        d = _det("knight", 0.5, 0.6, team="enemy")
        d.trk_hits = 1
        self.assertFalse(self._described(d),
                         "a 1-frame phantom still reaches the advisor (tornado at mass 0.009)")

    def test_an_enemy_spell_is_not_described(self):
        d = _det("fireball", 0.5, 0.6, team="enemy")
        d.trk_hits = 3
        self.assertFalse(self._described(d), "the advisor is still told about enemy fireballs")

    def test_a_spawn_spell_is_described(self):
        d = _det("graveyard", 0.7, 0.6, team="enemy")
        d.trk_hits = 2
        self.assertTrue(self._described(d), "an enemy graveyard was hidden from the advisor")

    def test_a_corroborated_troop_is_described(self):
        d = _det("pekka", 0.5, 0.6, team="enemy")
        d.trk_hits = 2
        self.assertTrue(self._described(d))


if __name__ == "__main__":
    unittest.main(verbosity=1)
