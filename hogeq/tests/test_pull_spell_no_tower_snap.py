"""A PULL SPELL MUST NOT BE SNAPPED ONTO A CROWN TOWER (live aim assist, measured 2026-08-27).

`play.py` redirects a cast to the weaker enemy princess via `reward.weaker_princess_cell` whenever
the card is in `anywhere_ids`. That set is EVERY anywhere-spell, and for the icebow deck it is
{rocket, TORNADO}. A Tornado centred on a Crown Tower pulls nothing -- `engine._tick_vortex`
refuses to drag a building, "once a building is placed it holds that tile for its whole lifetime"
-- and its tower chip is a rounding error, so the snap turns a chosen cast into a guaranteed whiff.

MEASURED before the fix: 80 of 432 cells (18.5% of the board) lie inside the
+/- env.spell_tower_aim_radius box of an enemy princess, spanning board tile-y 0.7 .. 10.0 in both
lanes -- so roughly one tornado cast in five was being redirected onto a building.

The rule already existed in the sim and simply never reached live. `sim/env.py::spell_target_mask`:
"a live enemy princess is a valid chip target for a DAMAGE spell (never for a pull)".
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config                 # noqa: E402
from clashrl.actions import ActionSpace           # noqa: E402
from clashrl.cards import CardDB                  # noqa: E402
from clashrl import card_threat                   # noqa: E402
from clashrl.reward import weaker_princess_cell   # noqa: E402


def _pull_ids(deck_keys, db):
    """The rule `play.py` applies, evaluated over an arbitrary deck (mirrors the source, so this
    is a test of the RULE and not of one deck's happening to contain a Tornado)."""
    return {i for i, key in enumerate(deck_keys)
            if "pull" in set((db.get(card_threat.base_key(key)) or {}).get("flags") or ())}


class PullSpellTowerSnapTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.load()
        self.db = CardDB(self.cfg)
        self.acts = ActionSpace(self.cfg)

    def test_the_tornado_is_identified_as_a_pull_spell(self):
        deck = ["rocket", "tornado", "the_log", "x_bow", "tesla", "knight", "skeletons", "ice_wizard"]
        self.assertEqual({1}, _pull_ids(deck, self.db), "only the Tornado pulls")

    def test_a_damage_spell_is_NOT_excluded(self):
        deck = ["rocket", "fireball", "arrows", "earthquake", "zap", "the_log"]
        self.assertEqual(set(), _pull_ids(deck, self.db),
                         "the tower snap is exactly what a damage spell wants")

    def test_play_gates_the_tower_snap_on_the_pull_flag(self):
        """THE REGRESSION GUARD. The branch is inside `play.run`'s closure and needs a live screen
        to execute, so the gate itself is pinned here."""
        src = (ROOT / "src" / "clashrl" / "play.py").read_text(encoding="utf-8")
        self.assertIn("card_id in anywhere_ids and card_id not in _pull_ids", src,
                      "the weaker-princess snap must exclude pull spells")
        self.assertIn('"pull" in set(', src, "_pull_ids must come from the card DB flag")

    def test_the_snap_really_does_cover_a_fifth_of_the_board(self):
        """Pins the size of what was being redirected, so 'it hardly ever fires' cannot be assumed."""
        r = float(self.cfg.get("env", "spell_tower_aim_radius", default=0.12))
        anchors = [list(t) for t in self.cfg.get("env", "enemy_towers")][:2]
        gw, gh = int(self.acts.gw), int(self.acts.gh)
        n = sum(1 for c in range(gw * gh)
                if weaker_princess_cell(*self.acts.cell_center(c % gw, c // gw), r,
                                        anchors, [4000.0, 3000.0], [True, True], self.acts) is not None)
        self.assertGreater(n, 0.10 * gw * gh, f"only {n} cells snap; the measured figure was 80")


if __name__ == "__main__":
    unittest.main()
