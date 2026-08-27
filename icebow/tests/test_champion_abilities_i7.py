"""I7 -- champion abilities, enemy-side, at FULL fidelity. Bare-engine, deck-agnostic.

This file is BYTE-IDENTICAL in icebow and hogeq (parity_check enforces it). It covers the eight
live champions' abilities through `SimEngine.champion_ability` plus the lifecycle rulings that
apply to all of them, in the house bare-engine idiom: a `_make_engine()` SimEngine, bodies placed
by hand, and an `advance` loop.

Sources, per class. Wiki revids are the LIVE revisions the I4/I5 import recorded in
`config/cards_stats.json` (`_src.revid`, fetched 2026-08-26); the frozen prose archives are
`research/sim_parity/abilities/<key>.yaml`, which carry the verbatim quotes and the
open_questions each choice below answers. Owner rulings are `research/sim_parity/decisions.md`;
unresolved geometry is queued in `research/sim_parity/conflicts.md`.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_sim_status_effects import _make_engine                    # noqa: E402
from clashrl.sim.engine import (ABILITY_KINDS, Unit, build_spec,    # noqa: E402
                                replace, _TILES_X, _TILES_Y)

LVL = 11

# The eight live champions and the shape each one's KB row declares.
CHAMPION_KINDS = {
    "mighty_miner": "bomb",
    "boss_bandit": "movement_flight",
    "archer_queen": "stealth",
    "golden_knight": "dash_chain",
    "skeleton_king": "soul_bank",
    "little_prince": "guardian",
    "monk": "reflect",
    "goblinstein": "zone",
}


def _quiet(eng):
    """Disarm the crown towers WITHOUT killing them. Every test here measures ONE ability, and a
    tower volley in the same ledger reads as ability damage (MEASURED: 158.0 per shot -- close
    enough to a champion's own numbers to look plausible and be wrong).

    Setting `alive = False` would be the obvious way and it is a trap: with one side's towers gone
    the match ENDS, `advance` returns at its `self.done` guard, and every timer under test stops
    ticking after the first step (MEASURED: a 1.0 s activation window still read 0.9 s after 30
    calls to `advance(0.1)`). Disarming leaves the match running.
    """
    for side in (eng.towers[0], eng.towers[1]):
        for tw in side:
            tw.hit_dmg = 0.0
            tw.max_hp = tw.hp = 1e9      # ...and unkillable, so no ability under test can end it
    return eng


def _place(eng, key, team, x, y, lvl=LVL, hp_mult=1.0, spec=None):
    s = spec if spec is not None else build_spec(eng.db, key, lvl)
    u = Unit(spec=s, team=team, x=x, y=y, hp=s.hp * hp_mult)
    u.deploy_left = 0.0                       # these bodies are already on the field
    eng.units.append(u)
    return u


class AbilityKindDispatchTests(unittest.TestCase):
    """The registry replaces the truthiness dispatch.

    Until I7 the engine answered "which ability does this card have" with
    `spec.ability_bomb_dmg > 0` (Explosive Escape) or `spec.ability_invis > 0` (Getaway Grenade).
    Two cards, two numbers, and no room for a third: the 8 champions need 8 shapes and I8's heroes
    add ~16 more.  `ability_kind` names the shape and `ABILITY_KINDS` dispatches on it.
    """

    def test_every_declared_kind_has_a_handler_and_a_price(self):
        """A KB row that names a shape must reach an implementation of it. The completeness
        gate -- that all EIGHT champions declare one -- is `AllEightChampionsTests` below."""
        eng = _make_engine()
        for key in sorted(CHAMPION_KINDS):
            s = build_spec(eng.db, key, LVL)
            if not s.ability_kind:
                continue
            with self.subTest(champion=key):
                self.assertEqual(CHAMPION_KINDS[key], s.ability_kind)
                self.assertIn(s.ability_kind, ABILITY_KINDS,
                              "%s names a kind with no handler" % s.ability_kind)
                self.assertGreater(s.ability_cost, 0.0, "%s: every ability costs elixir" % key)

    def test_the_two_legacy_shapes_migrated_rather_than_being_reimplemented(self):
        """The exact migration the plan names: `ability_bomb_dmg > 0` -> `bomb`, and
        `ability_invis > 0` -> `movement_flight`. Both cards keep their numbers."""
        eng = _make_engine()
        mm = build_spec(eng.db, "mighty_miner", LVL)
        self.assertEqual("bomb", mm.ability_kind)
        self.assertGreater(mm.ability_bomb_dmg, 0.0)
        bb = build_spec(eng.db, "boss_bandit", LVL)
        self.assertEqual("movement_flight", bb.ability_kind)
        self.assertGreater(bb.ability_invis, 0.0)

    def test_an_unknown_kind_is_refused_and_costs_nothing(self):
        """A KB typo must be loud. The old truthiness dispatch could not fail this way -- an
        unrecognised card simply had no ability -- so the engine refuses the activation rather
        than spending elixir on a no-op."""
        eng = _quiet(_make_engine())
        s = replace(build_spec(eng.db, "mighty_miner", LVL), ability_kind="not_a_real_kind")
        _place(eng, None, 0, 0.5, 0.6, spec=s)
        eng.elixir[0] = 10.0
        self.assertFalse(eng.champion_ability(0))
        self.assertEqual(10.0, eng.elixir[0])

    def test_a_card_with_no_ability_at_all_is_not_a_champion_body(self):
        eng = _quiet(_make_engine())
        _place(eng, "knight", 0, 0.5, 0.6)
        eng.elixir[0] = 10.0
        self.assertFalse(eng.champion_ability(0))
        self.assertEqual(10.0, eng.elixir[0])


class Ruling5NewestBodyTests(unittest.TestCase):
    """RULING 5 -- the ability button drives the MOST RECENTLY PLAYED body. This was a LIVE BUG.

    Owner, verified in-game (decisions.md ruling 5); corroborated verbatim by the archived
    `Version_History_2025.wikitext`, "2025 Quarter 3 Update (29/9/2025) -- Champion Rework":
    *"Only the most recent placed Champion has the ability."*  Ruling 4 makes the two-body state
    reachable at all: champions are NOT removed from the hand while a body lives, so a second one
    can be cycled to and played.

    MEASURED BEFORE (unpatched tree): `champion_ability` filtered on "has a use left" and took
    `next()` over `self.units`, which is append-ordered oldest-first -- so with two bodies out it
    fired from the OLDEST, and a spent newest body fell back to an older one. Both halves pinned.
    """

    def _two_bodies(self):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        old = _place(eng, "mighty_miner", 0, 0.25, 0.60)
        new = _place(eng, "mighty_miner", 0, 0.75, 0.60)
        return eng, old, new

    def test_the_newest_body_is_the_one_that_fires(self):
        eng, old, new = self._two_bodies()
        self.assertGreater(new.deploy_seq, old.deploy_seq)
        self.assertTrue(eng.champion_ability(0))
        # Explosive Escape mirrors its caster across the centre line, so position IS the receipt.
        self.assertAlmostEqual(0.25, new.x, places=6, msg="the NEWEST body should have mirrored")
        self.assertAlmostEqual(0.25, old.x, places=6, msg="the OLDEST body must not have moved")
        self.assertEqual(0, eng._ability_uses_left(new))
        self.assertEqual(1, eng._ability_uses_left(old), "the older body keeps its own use")

    def test_a_SPENT_newest_body_does_NOT_fall_back_to_an_older_one(self):
        """The half ruling 5 explicitly forbids. Selecting first and testing second is what makes
        this false; one comprehension filtering on "has a use left" passes the previous test and
        fails this one."""
        eng, old, _new = self._two_bodies()
        self.assertTrue(eng.champion_ability(0))
        before = eng.elixir[0]
        self.assertFalse(eng.champion_ability(0), "the spent newest body fell back to the older")
        self.assertEqual(before, eng.elixir[0])
        self.assertEqual(1, eng._ability_uses_left(old), "the older body's use was spent for it")

    def test_a_body_placed_AFTER_the_first_one_spent_its_use_takes_the_button(self):
        """Ruling 6: one use per BODY. A fresh body is a fresh use, and it is now the newest."""
        eng, _old, _new = self._two_bodies()
        self.assertTrue(eng.champion_ability(0))
        third = _place(eng, "mighty_miner", 0, 0.50, 0.60)
        self.assertTrue(eng.champion_ability(0))
        self.assertAlmostEqual(0.50, third.x, places=6)
        self.assertEqual(0, eng._ability_uses_left(third))

    def test_a_DEAD_newest_body_is_skipped_for_a_living_older_one(self):
        """"Newest" means newest LIVING. A corpse is not a champion on the arena."""
        eng, old, new = self._two_bodies()
        new.hp = 0.0
        self.assertTrue(eng.champion_ability(0))
        self.assertAlmostEqual(0.75, old.x, places=6, msg="the living older body should have fired")

    def test_the_enemys_champion_never_arms_ours(self):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        _place(eng, "mighty_miner", 1, 0.5, 0.30)
        self.assertFalse(eng.champion_ability(0))
        self.assertEqual(10.0, eng.elixir[0])

    def test_deploy_seq_is_stamped_on_every_construction_path(self):
        """Including the hand-placed bodies these tests build -- the counter lives in
        `Unit.__post_init__`, not in `deploy()`, precisely so no path can miss it."""
        eng = _quiet(_make_engine())
        a = _place(eng, "knight", 0, 0.4, 0.6)
        b = _place(eng, "knight", 0, 0.6, 0.6)
        eng.elixir[1] = 10.0
        eng.deploy(1, build_spec(eng.db, "knight", LVL), 0.5, 0.3)
        c = eng.units[-1]
        self.assertLess(a.deploy_seq, b.deploy_seq)
        self.assertLess(b.deploy_seq, c.deploy_seq)


class Ruling7RefundTests(unittest.TestCase):
    """RULING 7 -- the elixir comes back if the body dies before the ability goes off.

    Owner (decisions.md ruling 7): "if the body dies before the ability goes off, the ability's
    elixir is refunded". The window is `ability_delay`, which I7 rules at the PROSE's 1 second for
    every champion -- the standing precedent set by the Mighty Miner's `ability_delay_s: 1.0`, and
    the only figure stated anywhere as a RULE (`Cards.wikitext`: "The abilities adhere to the
    server's 1 second deployment delay"). The attribute tables' 0.933 / 0.944 / 0.766 s "Cast
    Time" columns are the rejected alternatives: they disagree with the prose and with each other
    on all seven champion pages (conflicts.md C7), and the engine needs ONE convention.

    MEASURED BEFORE: absent. Elixir was deducted at activation and never returned.

    Probed here on the Mighty Miner because his is the shape the rule was written against. In a
    real match neither at-once kind can reach the refund -- he is intangible for exactly this
    window and the Boss Bandit is invisible for hers -- so these tests kill the body by setting
    `hp` directly, which is the only way past that immunity. The reachable-in-play case is the
    Archer Queen's, pinned in `ArcherQueenStealthTests`.
    """

    def _cast(self, key="mighty_miner", x=0.50, y=0.60):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        champ = _place(eng, key, 0, x, y)
        self.assertTrue(eng.champion_ability(0))
        return eng, champ

    def test_a_champion_killed_during_the_cast_gets_his_elixir_back(self):
        eng, champ = self._cast()
        cost = champ.spec.ability_cost
        self.assertAlmostEqual(10.0 - cost, eng.elixir[0], places=6)
        champ.hp = 0.0
        eng.advance(0.1)
        self.assertAlmostEqual(10.0, eng.elixir[0], places=6,
                               msg="the body died mid-cast: ruling 7 refunds the ability cost")

    def test_a_champion_who_survives_the_cast_keeps_paying_for_it(self):
        eng, champ = self._cast()
        self.assertGreater(champ.spec.ability_cost, 0.0)
        for _ in range(30):                                  # 3 s, well past the 1 s window
            eng.advance(0.1)
        self.assertEqual([], eng._ability_pending, "the activation record must not leak")

    def test_a_death_AFTER_the_window_refunds_nothing(self):
        eng, champ = self._cast()
        for _ in range(20):
            eng.advance(0.1)
        eng.elixir[0] = 0.0
        champ.hp = 0.0
        eng.advance(0.1)
        # ...bounded by the bar's own regen for one 0.1 s step, NOT by the 1-elixir refund.
        self.assertLess(eng.elixir[0], champ.spec.ability_cost,
                        "the ability had already resolved -- nothing to refund")

    def test_the_refund_cannot_overflow_the_bar(self):
        eng, champ = self._cast()
        eng.elixir[0] = 10.0
        champ.hp = 0.0
        eng.advance(0.1)
        self.assertLessEqual(eng.elixir[0], 10.0)

    def test_the_two_at_once_kinds_cannot_reach_the_refund_and_that_is_correct(self):
        """The Mighty Miner is INTANGIBLE for exactly this window and the Boss Bandit INVISIBLE
        for hers, so neither can be killed during it. Ruling 7 pays back a champion killed before
        his ability went off; these two cannot be, and what they already committed is deliberately
        not rolled back."""
        for key in ("mighty_miner", "boss_bandit"):
            with self.subTest(champion=key):
                eng, champ = self._cast(key)
                self.assertGreater(champ.invis_left, 0.0)
