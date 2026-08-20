"""The champion ability is a BUTTON, and train-rl's live env only knew about hand slots.

Owner's report: the model had never once played the Mighty Miner ability in live training. It was
not a preference -- the action could not be executed. `LiveMatchEnv._execute` starts with

    slot = next((s for s, c in enumerate(self.hand_ids) if c == card_id), -1)
    if slot < 0:
        return

and the ability is a PSEUDO-CARD in the action space, never a tray slot, so `hand_ids` could never
contain it: every selection was discarded before it could even misfire. `play.py` has always done
this correctly (one tap on the calibrated button, gated on the champion being on the arena) and
train-rl simply never got the same treatment -- which is exactly the kind of divergence between the
playing path and the training path that a test should hold shut.

These exercise `_execute` and the availability rule directly on a bare instance, because a real
LiveMatchEnv wants a screen capture and a detector.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from clashrl.env import LiveMatchEnv          # noqa: E402


class _Det:
    def __init__(self, base, team):
        self.base, self.team = base, team


class _Controller:
    """Records the gesture used, so the test can tell a TAP from a select-then-place."""

    def __init__(self):
        self.taps = []
        self.plays = []

    def tap(self, x, y):
        self.taps.append((round(float(x), 4), round(float(y), 4)))

    def play_card(self, *a):
        self.plays.append(tuple(a))


def _env(on_board=True, spent=False):
    e = object.__new__(LiveMatchEnv)
    e.ability_id = 7
    e.ability_xy = (0.963, 0.758)
    e._champ_base = "mighty_miner"
    e._ability_spent = spent
    e.hand_ids = [0, 1, 2, 3]                  # the ability is NEVER one of these
    e._last_dets_all = [_Det("mighty_miner", "mine")] if on_board else [_Det("hog_rider", "mine")]
    e.controller = _Controller()
    return e


class ChampionAbilityExecutionTests(unittest.TestCase):

    def test_the_ability_is_ONE_TAP_on_the_button(self):
        """No slot select, no placement: it acts on the champion wherever he stands."""
        e = _env()
        e._execute((1, e.ability_id, 123))
        self.assertEqual(e.controller.taps, [(0.963, 0.758)])
        self.assertEqual(e.controller.plays, [], "the ability must not go through play_card")

    def test_the_cell_is_ignored(self):
        """Whatever cell the policy produced is irrelevant -- same as in the sim."""
        for cell in (0, 57, 431):
            e = _env()
            e._execute((1, e.ability_id, cell))
            self.assertEqual(e.controller.taps, [(0.963, 0.758)])

    def test_THE_REPORTED_BUG_it_is_not_dropped_for_having_no_slot(self):
        """The whole failure: `hand_ids` cannot contain a button, so the slot lookup returned -1
        and the play was discarded silently."""
        e = _env()
        self.assertNotIn(e.ability_id, e.hand_ids)
        e._execute((1, e.ability_id, 0))
        self.assertTrue(e.controller.taps, "a selection with no hand slot must still fire the button")

    def test_not_tapped_when_the_champion_is_not_on_the_board(self):
        """He can die between the decision and the tap; the button is dead without him."""
        e = _env(on_board=False)
        e._execute((1, e.ability_id, 0))
        self.assertEqual(e.controller.taps, [])

    def test_an_ordinary_card_does_NOT_take_the_ability_branch(self):
        """A normal card must fall through to the slot path. The bare instance has no grid, so it
        raises once it gets there -- which is itself the proof that it took the other branch, and
        stubbing the whole env to watch it finish would test the stub rather than the split."""
        e = _env()
        with self.assertRaises(AttributeError):
            e._execute((1, 2, 100))
        self.assertEqual(e.controller.taps, [], "an ordinary card must never tap the ability button")

    def test_a_play_of_zero_does_nothing(self):
        e = _env()
        e._execute((0, e.ability_id, 0))
        self.assertEqual(e.controller.taps, [])


class ChampionAbilityAvailabilityTests(unittest.TestCase):

    def test_on_board_is_read_from_the_detector(self):
        self.assertTrue(_env(on_board=True)._champion_on_board())
        self.assertFalse(_env(on_board=False)._champion_on_board())

    def test_an_enemy_champion_does_not_light_the_button(self):
        e = _env()
        e._last_dets_all = [_Det("mighty_miner", "enemy")]
        self.assertFalse(e._champion_on_board())

    def test_spent_is_per_body(self):
        """4/8/2026 removed the cooldown, so availability is a spent flag cleared when he leaves --
        the next Mighty Miner is a NEW body with his own activation."""
        e = _env()
        e._execute((1, e.ability_id, 0))
        self.assertTrue(e._ability_spent)


if __name__ == "__main__":
    unittest.main()
