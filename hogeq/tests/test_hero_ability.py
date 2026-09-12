"""L67ag D1 + H3 (HANDOFF 5cs.99 AM): the hero Ice Wizard's ability button state, the button-region detector mask,
and the Frosty Fella press rule."""
from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from clashrl.hero_ability import (TILE_X, TILE_Y, UIMaskedDetector, ability_button_state,   # noqa: E402
                                  frosty_fella_decision, tiles_between)

PLAY = os.path.join(os.path.dirname(__file__), "..", "src", "clashrl", "play.py")
BTN = (0.909, 0.765)


def _frame(color=None):
    fr = np.zeros((1198, 656, 3), np.uint8)
    fr[:] = (60, 150, 70)                                    # arena grass (BGR)
    if color is not None:
        cv2.circle(fr, (int(BTN[0] * 656), int(BTN[1] * 1198)), 36, color, -1)
    return fr


WINCON = {"hog_rider", "balloon", "giant", "ram_rider"}.__contains__


class ButtonState(unittest.TestCase):
    def test_blue_disc_is_ready(self):
        self.assertEqual(ability_button_state(_frame((255, 160, 20)), BTN)[0], "ready")

    def test_grey_disc_is_grey(self):
        self.assertEqual(ability_button_state(_frame((205, 205, 205)), BTN)[0], "grey")

    def test_no_disc_is_absent(self):
        self.assertEqual(ability_button_state(_frame(None), BTN)[0], "absent")
        self.assertEqual(ability_button_state(None, BTN)[0], "absent")


class _Det:
    def __init__(self, dets):
        self.dets, self.available = dets, True

    def detect(self, frame, conf=0.3):
        return list(self.dets)


def _d(cls, cx, cy):
    return SimpleNamespace(cls=cls, cx=cx, cy=cy, team="enemy")


class ButtonMask(unittest.TestCase):
    def setUp(self):
        self.inner = _Det([_d("earthquake", 0.905, 0.768), _d("hog_rider", 0.745, 0.60)])
        self.det = UIMaskedDetector(self.inner, [(BTN[0], BTN[1], 0.062)])

    def test_the_phantom_on_a_showing_button_is_dropped(self):
        out = self.det.detect(_frame((205, 205, 205)))
        self.assertEqual([d.cls for d in out], ["hog_rider"])
        self.assertEqual(self.det.masked, 1)

    def test_nothing_is_dropped_while_the_button_is_absent(self):
        self.assertEqual(len(self.det.detect(_frame(None))), 2)

    def test_the_wrapper_passes_attributes_through(self):
        self.assertTrue(self.det.available)


class FrostyRule(unittest.TestCase):
    TOWERS = [(0.245, 0.615), (0.745, 0.615), (0.495, 0.72)]

    def test_tile_scales_match_the_tower_anchors(self):
        self.assertAlmostEqual(tiles_between((0.245, 0.615), (0.745, 0.615)), 11.0, places=6)
        self.assertAlmostEqual(tiles_between((0.745, 0.205), (0.745, 0.615)), 19.0, places=6)

    def test_a_hog_at_our_tower_is_frozen(self):
        r = frosty_fella_decision([(0.745, 0.57, "hog_rider"), (0.76, 0.56, "skeletons")], [], self.TOWERS,
                                  (0.70, 0.66), elixir=5, is_wincon=WINCON)
        self.assertEqual(r["reason"], "wincon_at_building")
        self.assertEqual(r["wincon"], "hog_rider")
        self.assertEqual(r["n"], 2)

    def test_not_affordable_never_presses(self):
        self.assertIsNone(frosty_fella_decision([(0.745, 0.57, "hog_rider")], [], self.TOWERS, None,
                                                elixir=1, is_wincon=WINCON))

    def test_a_lone_cheap_unit_never_presses(self):
        self.assertIsNone(frosty_fella_decision([(0.5, 0.55, "knight")], [], self.TOWERS, None,
                                                elixir=9, is_wincon=WINCON))

    def test_a_win_condition_still_on_their_half_waits(self):
        self.assertIsNone(frosty_fella_decision([(0.745, 0.30, "hog_rider")], [], self.TOWERS, None,
                                                elixir=9, is_wincon=WINCON))

    def test_a_stacked_push_inside_the_radius(self):
        ens = [(0.50, 0.55, "knight"), (0.52, 0.56, "musketeer"), (0.49, 0.57, "skeletons")]
        r = frosty_fella_decision(ens, [], [], None, elixir=4, is_wincon=WINCON)
        self.assertEqual((r["reason"], r["n"]), ("stacked_push", 3))

    def test_a_spread_push_is_not_stacked(self):
        ens = [(0.20, 0.55, "knight"), (0.50, 0.60, "musketeer"), (0.80, 0.70, "skeletons")]
        self.assertIsNone(frosty_fella_decision(ens, [], [], None, elixir=4, is_wincon=WINCON))

    def test_troops_on_our_xbow(self):
        xb = (0.745, 0.47)
        ens = [(0.745 + TILE_X, 0.47, "knight"), (0.745, 0.47 + TILE_Y, "valkyrie")]
        r = frosty_fella_decision(ens, [xb], [], None, elixir=3, is_wincon=WINCON, xbows=[xb])
        self.assertEqual(r["reason"], "xbow_guard")

    def test_a_hero_out_of_reach_does_not_press(self):
        r = frosty_fella_decision([(0.745, 0.57, "hog_rider")], [], self.TOWERS, (0.20, 0.25),
                                  elixir=9, is_wincon=WINCON)
        self.assertIsNone(r)


class PlayWiring(unittest.TestCase):
    def test_play_masks_the_button_and_checks_the_ability_after_the_elixir_read(self):
        with open(PLAY, encoding="utf-8") as fh:
            src = fh.read()
        if "frosty_fella_decision" not in src:
            self.skipTest("this deck's play.py has no hero ability")
        self.assertLess(src.index("UIMaskedDetector(_detector"), src.index("PerceptionLoop(cfg, _detector"))
        self.assertLess(src.index("elixir = vision.read_elixir(frame)"), src.index("if _hero_on and _frosty_check(frame"))
        self.assertLess(src.index("def _frosty_check(frame"), src.index("def act_in_match(frame)"))
        self.assertLess(src.index("controller.ensure_focus()  # L67ag"), src.index("controller.tap(*_hero_btn)"))
        self.assertIn('_hero.update(t=None, xy=None, press=None)', src)


if __name__ == "__main__":
    unittest.main()
