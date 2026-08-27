"""RULING 18 -- Royal Delivery is own-half only, and every other spell is NOT.

Owner (2026-08-27): Royal Delivery "can only be cast on the caster's half of the map (and whatever
pocket presents itself)". It is a SPELL that DROPS A TROOP, so it should clamp like a troop rather
than be aimed like a spell.

VERIFIED INDEPENDENTLY on the wiki while implementing, and the page is more specific than the
ruling. Cards revid 437053, verbatim:

    "Generally, spells are temporary and can be cast anywhere in the battlefield (WITH THE
     EXCEPTION OF The Log, Barbarian Barrel, and Royal Delivery), including on top of buildings,
     while buildings ... and troops ... can only be spawned on the player's territory (with the
     exception of Miner and Goblin Drill)."

THREE exceptions, not one. Ruling 18 shipped Royal Delivery alone and recorded the other two in
conflicts.md, because The Log is in BOTH shipped decks and flagging it changes the agent's own
action space on a card it plays constantly.

RULING 20 (owner, 2026-08-27) then shipped them: "The Log's CAST POINT is restricted to the
caster's own half (plus pockets), but its CORRIDOR still rolls across the river." So the flagged
set is now the wiki's full three, and the assertions below moved from one card to three.
`test_log_own_half_r20.py` owns the Log's own measurements.

THE HALF OF THIS THAT IS A TRAP. An earlier fix (2026-08, recorded in the `anywhere_ids` comments)
had to undo exactly the opposite bug: `anywhere_ids` was the literal {rocket, miner}, so EVERY other
spell was forbidden from the enemy half -- the offensive Log, the Tornado river lock and hogeq's
whole Hog+Earthquake combo were actions the policy could not take at all. So the carve-out here is
by KB FLAG on one card, never by narrowing the spell rule, and
`test_every_OTHER_spell_still_goes_anywhere` asserts that explicitly so the old bug cannot come
back through this door.

MEASURED CLAMP DISTANCE (icebow's 18x24 action grid, board rows 0..23 with the deploy line at
row 13): a Royal Delivery aimed at the enemy back row lands 12 grid rows short of where it was
aimed -- see `test_a_royal_delivery_aimed_deep_in_the_enemy_half_clamps_back`, which prints and
pins the number.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.actions import ActionSpace                                # noqa: E402
from clashrl.cards import CardDB                                       # noqa: E402
from clashrl.config import Config                                      # noqa: E402
from clashrl.sim.engine import build_spec                              # noqa: E402

LVL = 11


def _cfg_db():
    cfg = Config.load(str(ROOT / "config" / "config.yaml"))
    return cfg, CardDB(cfg)


class RoyalDeliveryIsOwnHalfOnlyTests(unittest.TestCase):
    """The KB flag and the spec field it feeds."""

    def test_exactly_the_wikis_THREE_exceptions_carry_the_flag(self):
        """Cards revid 437053 names three and only three. Ruling 18 shipped one of them, ruling 20
        the other two; a FOURTH card appearing here would be the 2026-08 "every spell is forbidden
        from the enemy half" regression coming back through the DATA instead of the code."""
        _, db = _cfg_db()
        flagged = sorted(k for k in db.cards
                         if "own_half_only" in set((db.get(k) or {}).get("flags") or ()))
        self.assertEqual(["barbarian_barrel", "royal_delivery", "the_log"], flagged,
                         "the wiki names exactly The Log, Barbarian Barrel and Royal Delivery")

    def test_the_flag_reaches_the_spec(self):
        _, db = _cfg_db()
        for k in ("royal_delivery", "the_log", "barbarian_barrel"):
            with self.subTest(card=k):
                self.assertTrue(build_spec(db, k, LVL).own_half_only)
        for k in ("rocket", "tornado", "earthquake", "fireball", "arrows", "zap"):
            with self.subTest(card=k):
                self.assertFalse(build_spec(db, k, LVL).own_half_only)

    def test_it_is_still_a_SPELL_everywhere_else(self):
        """The flag changes WHERE it may be put, not WHAT it is. A Royal Delivery that stopped
        being a spell would lose its spell delay, its radius and its whole resolution path."""
        _, db = _cfg_db()
        s = build_spec(db, "royal_delivery", LVL)
        self.assertEqual("spell", s.kind)
        self.assertGreater(s.spell_radius, 0.0)
        self.assertGreater(s.spell_dmg, 0.0)


class DeployClampTests(unittest.TestCase):
    """`Actions.deploy_clamp` is the rule; `anywhere_ids` is who is exempt from it."""

    def setUp(self):
        self.cfg, self.db = _cfg_db()
        self.actions = ActionSpace(self.cfg)
        self.gw = int(self.actions.gw)
        self.gh = int(self.actions.gh)

    def _cell(self, gx, gy):
        return gy * self.gw + gx

    def test_a_royal_delivery_aimed_deep_in_the_enemy_half_clamps_back(self):
        """THE RULING, measured. Aimed at the enemy back row, it comes back to the deploy line --
        the house style for this kind of fix is to report the tile distance, so this prints it."""
        gx = self.gw // 2
        moved = []
        for gy in range(0, self.actions.min_own_gy):          # every row in the ENEMY half
            out = self.actions.deploy_clamp(False, self._cell(gx, gy))
            out_gy = out // self.gw
            self.assertGreaterEqual(out_gy, self.actions.min_own_gy,
                                    "row %d stayed in the enemy half" % gy)
            self.assertEqual(gx, out % self.gw, "the clamp must not move the LANE")
            moved.append(out_gy - gy)
        deepest = moved[0]
        print("\n[R18] Royal Delivery aimed at the enemy BACK row (gy=0) clamps to gy=%d: "
              "%d grid rows / tiles moved. Deploy line is gy=%d of %d."
              % (self.actions.min_own_gy, deepest, self.actions.min_own_gy, self.gh))
        self.assertEqual(self.actions.min_own_gy, deepest,
                         "the deepest aim moves exactly as far as the deploy line is from row 0")
        self.assertGreater(deepest, 0)

    def test_a_pocket_placement_is_still_legal(self):
        """The pocket machinery is `deployable_mask(anywhere, pocket=...)`: taking an enemy
        princess grants deployment territory across the river on that side. A clamped card must
        still be placeable there, or the ruling would have deleted the pocket for it."""
        if "pocket" not in ActionSpace.deployable_mask.__code__.co_varnames:
            self.skipTest("this deck's Actions has no pocket parameter (deck-specific, icebow-only)")
        closed = self.actions.deployable_mask(False)
        left = self.actions.deployable_mask(False, pocket=(True, False))
        right = self.actions.deployable_mask(False, pocket=(False, True))
        self.assertGreater(sum(left), sum(closed), "an open LEFT pocket must add legal cells")
        self.assertGreater(sum(right), sum(closed), "an open RIGHT pocket must add legal cells")
        # ...and the cells it adds are in the ENEMY half, which is the whole point.
        added = [c for c in range(self.gw * self.gh) if left[c] and not closed[c]]
        self.assertTrue(added)
        for c in added:
            self.assertLess(c // self.gw, self.actions.min_own_gy,
                            "a pocket cell must be across the river")

    def test_an_anywhere_card_is_NOT_clamped(self):
        for gy in range(0, self.actions.min_own_gy):
            cell = self._cell(self.gw // 2, gy)
            self.assertEqual(cell, self.actions.deploy_clamp(True, cell),
                             "an anywhere card passes through untouched")


class AnywhereIdsTests(unittest.TestCase):
    """`sim/env.py` builds the id set. This is where the 2026-08 regression would come back."""

    @staticmethod
    def _ids(deck_keys, db):
        """The `anywhere_ids` rule, evaluated over an arbitrary deck.

        Mirrors sim/env.py exactly rather than constructing a whole SimEnv: the env needs a full
        config + observation stack, and what is under test is the RULE.
        """
        def _base(k):
            return k[:-4] if k.endswith("_evo") else k

        specs = [build_spec(db, k, LVL) for k in deck_keys]
        own_half = {i for i in range(len(deck_keys)) if specs[i].own_half_only}
        return {i for i, k in enumerate(deck_keys)
                if (specs[i].kind == "spell"
                    or _base(k) in ("miner", "goblin_drill"))} - own_half, own_half

    def test_royal_delivery_is_NOT_in_anywhere_ids(self):
        _, db = _cfg_db()
        deck = ["royal_delivery", "rocket", "knight", "x_bow",
                "tesla", "the_log", "skeletons", "tornado"]
        ids, own_half = self._ids(deck, db)
        self.assertEqual({0, 5}, own_half, "royal_delivery (0) and, since ruling 20, the_log (5)")
        self.assertNotIn(0, ids, "Royal Delivery must clamp like a troop")

    def test_every_OTHER_spell_still_goes_anywhere(self):
        """THE REGRESSION GUARD. The 2026-08 fix replaced the literal {rocket, miner} with
        `kind == spell` because the literal had confined Tornado, The Log and Earthquake to our own
        half -- deleting the offensive Log, the river Tornado lock and hogeq's Hog+Earthquake combo
        from the action space entirely. Ruling 18 removes ONE flagged card and must not touch a
        single other one."""
        _, db = _cfg_db()
        deck = ["rocket", "tornado", "earthquake", "fireball", "arrows", "zap",
                "royal_delivery", "the_log"]
        ids, _ = self._ids(deck, db)
        self.assertEqual(set(range(6)), ids,
                         "every spell but the FLAGGED ones goes anywhere; "
                         "got %r for %r" % (sorted(ids), deck))

    def test_the_deploy_anywhere_troops_are_untouched(self):
        _, db = _cfg_db()
        deck = ["miner", "goblin_drill", "knight", "x_bow",
                "tesla", "the_log", "skeletons", "royal_delivery"]
        ids, _ = self._ids(deck, db)
        self.assertIn(0, ids, "Miner tunnels anywhere")
        self.assertIn(1, ids, "Goblin Drill drills anywhere")
        self.assertNotIn(5, ids, "ruling 20: The Log's CAST POINT is own-half too")
        self.assertNotIn(7, ids)

    def test_the_shipped_deck_own_half_set_is_EXACTLY_the_flagged_cards(self):
        """Ruling 18 could claim "no behaviour change for the current checkpoints" because neither
        shipped deck held Royal Delivery. RULING 20 CANNOT: both decks play The Log, so this deck's
        own action space really does change -- and the honest test is that it changes by EXACTLY
        the flagged cards and by nothing else."""
        _, db = _cfg_db()
        deck = db.deck_names()
        ids, own_half = self._ids(deck, db)
        expect_own = {i for i, k in enumerate(deck)
                      if "own_half_only" in set((db.get(k) or {}).get("flags") or ())}
        self.assertEqual(expect_own, own_half)
        expect = {i for i, k in enumerate(deck)
                  if build_spec(db, k, LVL).kind == "spell"
                  or (k[:-4] if k.endswith("_evo") else k) in ("miner", "goblin_drill")} - own_half
        self.assertEqual(expect, ids)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
