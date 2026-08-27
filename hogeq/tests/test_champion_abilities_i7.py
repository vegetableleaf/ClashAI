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


class BossBanditIsAButtonNowTests(unittest.TestCase):
    """Getaway Grenade -- the engine's HP auto-trigger DELETED (owner ruling, conflicts.md C5).

    Boss_Bandit.wikitext (revid 437146) describes the ability ONLY as a button "accessible from
    the rightmost side of the screen just above the player's card slots", and its History
    8/7/2025 says it "can be activated a total of 2 times INDEPENDENT ON Boss Bandit's
    hitpoints" -- i.e. an HP-gated model was REMOVED from the game. The sim fired it
    automatically below a rolled `ability_hp_frac`, so it modelled a rule that no longer exists.

    MEASURED BEFORE: a Boss Bandit chipped below her rolled threshold vanished on her own, with
    no decision anywhere. AFTER: she sits at 1 HP forever unless somebody presses the button.

    She is also the ONE champion exempt from the 4/8/2026 single-use change ("Champions and
    Heroes (minus Boss Bandit)"), so 2 uses and the 3 s cooldown between them stay.
    """

    def _bandit(self, hp_mult=1.0, y=0.45):
        # y=0.45 on purpose: 6 tiles back from 0.30 lands her on top of her own King Tower, and
        # the collision shove then hides the teleport under a footprint push.
        eng = _quiet(_make_engine())
        eng.elixir[1] = 10.0
        bb = _place(eng, "boss_bandit", 1, 0.50, y, hp_mult=hp_mult)
        return eng, bb

    def test_the_engine_no_longer_fires_it_on_its_own(self):
        eng, bb = self._bandit(hp_mult=0.02)             # far below any old rolled threshold
        before = eng.elixir[1]
        for _ in range(200):                             # 20 s
            eng.advance(0.1)
        self.assertEqual(2, eng._ability_uses_left(bb), "nothing pressed the button")
        self.assertLessEqual(bb.invis_left, 0.0)
        self.assertGreaterEqual(eng.elixir[1], before - 1e-9, "no elixir was spent on her behalf")

    def test_the_hp_threshold_field_is_gone_entirely(self):
        """Left behind, it would be dead state that a later pass could revive by accident."""
        _eng, bb = self._bandit()
        self.assertFalse(hasattr(bb, "ability_hp_frac"))

    def test_the_button_still_does_the_whole_grenade(self):
        eng, bb = self._bandit()
        y0 = bb.y
        self.assertTrue(eng.champion_ability(1))
        self.assertAlmostEqual(bb.spec.ability_invis, bb.invis_left, places=6)
        for _ in range(40):
            eng.advance(0.05)
            if bb.invis_left <= 0.0:
                break                                   # she has just reappeared; read it now,
        # ...before she walks the distance back. "teleports 6 tiles behind her original position",
        # and team 1 attacks toward larger y, so back is up the board.
        self.assertLessEqual(bb.invis_left, 0.0)
        self.assertAlmostEqual(y0 - bb.spec.ability_back / _TILES_Y, bb.y, delta=0.01)

    def test_she_keeps_TWO_uses_and_the_three_second_cooldown(self):
        eng, bb = self._bandit()
        s = build_spec(eng.db, "boss_bandit", LVL)
        self.assertEqual(2, s.ability_uses)
        self.assertAlmostEqual(3.0, s.ability_cd, places=6)
        self.assertTrue(eng.champion_ability(1))
        self.assertFalse(eng.champion_ability(1), "the 3 s cooldown gates the second grenade")
        for _ in range(60):
            eng.advance(0.1)
        eng.elixir[1] = 10.0
        self.assertTrue(eng.champion_ability(1), "the second use is hers once the cooldown ends")
        self.assertEqual(0, eng._ability_uses_left(bb))

    def test_she_is_untargetable_while_the_grenade_runs(self):
        eng, bb = self._bandit()
        eng.champion_ability(1)
        mine = _place(eng, "knight", 0, 0.50, 0.30)
        self.assertFalse(eng._valid_foe(mine, bb), "invisible = not merely unseen")


class AbilityAIFrameworkTests(unittest.TestCase):
    """`ScriptedBot._try_ability` -- the decision the engine used to make for the Boss Bandit.

    Deliberately built as a FRAMEWORK, keyed on the ability's SHAPE rather than on the card,
    because I8 adds ~16 hero kinds on top of these 8. Three families, each a different question
    about the board: `escape` (this body is in trouble or too deep), `defensive` (it is about to
    be swarmed), `offensive` (it is deep enough that the ability buys tower damage). Every knob
    is a CHOICE -- no page states when to press the button -- so they sit in one named table and
    a KB `ability_ai:` dict overrides them per card.
    """

    def _bot(self, cards=("boss_bandit", "knight", "archers", "fireball",
                          "musketeer", "minions", "zap", "hog_rider")):
        from clashrl.config import Config
        from clashrl.sim.opponents import ScriptedBot
        import random
        eng = _quiet(_make_engine())
        bot = ScriptedBot(Config.load(), eng.db, random.Random(7), list(cards), "control")
        bot.reaction_s = 0.0                    # the delay has its own test
        return eng, bot

    def test_a_healthy_bandit_in_her_own_half_does_not_burn_the_grenade(self):
        eng, bot = self._bot()
        eng.elixir[1] = 10.0
        _place(eng, "boss_bandit", 1, 0.50, 0.30)
        self.assertFalse(bot._try_ability(eng))

    def test_a_LOW_bandit_escapes(self):
        eng, bot = self._bot()
        eng.elixir[1] = 10.0
        bb = _place(eng, "boss_bandit", 1, 0.50, 0.30, hp_mult=0.20)
        self.assertTrue(bot._try_ability(eng))
        self.assertGreater(bb.invis_left, 0.0)

    def test_an_OVEREXTENDED_bandit_escapes_at_full_health(self):
        """"escape" is not only about hitpoints. Past the river she is inside the defender's
        answer range with no way back, which is the other half of what the ability is for."""
        eng, bot = self._bot()
        eng.elixir[1] = 10.0
        bb = _place(eng, "boss_bandit", 1, 0.50, 0.72)     # team 1 attacks DOWNWARD
        self.assertTrue(bot._try_ability(eng))
        self.assertGreater(bb.invis_left, 0.0)

    def test_a_DEFENSIVE_kind_waits_for_the_swarm(self):
        eng, bot = self._bot(cards=("mighty_miner", "knight", "archers", "fireball",
                                    "musketeer", "minions", "zap", "hog_rider"))
        eng.elixir[1] = 10.0
        mm = _place(eng, "mighty_miner", 1, 0.50, 0.30)
        self.assertFalse(bot._try_ability(eng), "two bodies is not a swarm")
        for i in range(2):
            _place(eng, "skeletons", 0, 0.50 + 0.004 * i, 0.30)
        self.assertFalse(bot._try_ability(eng))
        _place(eng, "skeletons", 0, 0.51, 0.30)
        self.assertTrue(bot._try_ability(eng), "3 enemies within 4 tiles is the default threshold")
        self.assertEqual(0, eng._ability_uses_left(mm))

    def test_an_OFFENSIVE_kind_waits_until_it_is_near_a_TOWER(self):
        """Driven through `ability_ai` rather than through one of the offensive CARDS, so the
        family predicate is tested on its own -- the cards that declare it (`dash_chain`, `zone`)
        each have their own end-to-end test."""
        eng, bot = self._bot()
        eng.elixir[1] = 10.0
        s = replace(build_spec(eng.db, "boss_bandit", LVL),
                    ability_ai=(("family", "offensive"), ("tower_tiles", 7.0)))
        u = _place(eng, None, 1, 0.50, 0.40, spec=s)      # mid-board: no tower within 7 tiles
        self.assertFalse(bot._try_ability(eng))
        u.x, u.y = eng.towers[0][0].x, eng.towers[0][0].y - 4.0 / _TILES_Y
        self.assertTrue(bot._try_ability(eng))

    def test_the_KB_can_override_the_family_and_the_knobs(self):
        """`ability_ai:` is the escape hatch: a card whose shape says one thing and whose page
        says another does not need engine or bot code to say so."""
        eng, bot = self._bot()
        eng.elixir[1] = 10.0
        s = replace(build_spec(eng.db, "boss_bandit", LVL),
                    ability_ai=(("family", "escape"), ("hp_frac", 0.95), ("over_river", False)))
        bb = _place(eng, None, 1, 0.50, 0.30, spec=s, hp_mult=0.90)
        self.assertTrue(bot._try_ability(eng), "the KB raised her escape threshold to 95%")
        self.assertGreater(bb.invis_left, 0.0)

    def test_a_reaction_delay_stops_the_bot_firing_on_the_exact_tick(self):
        """Without it the ability lands the instant the condition flips -- inhuman, and
        unlearnable: the policy would face perfect timing every match."""
        eng, bot = self._bot()
        bot.reaction_s = 0.8
        eng.elixir[1] = 10.0
        _place(eng, "boss_bandit", 1, 0.50, 0.30, hp_mult=0.20)
        self.assertFalse(bot._try_ability(eng), "the window only just opened")
        for _ in range(12):
            eng.advance(0.1)
        self.assertTrue(bot._try_ability(eng))

    def test_the_bot_asks_the_NEWEST_body_not_any_body(self):
        """Ruling 5 again, on the bot side. Scanning for "a body that wants to fire" would press
        the button because an OLDER, cornered body wanted it -- and the engine would then fire
        the newest one, which did not."""
        eng, bot = self._bot()
        eng.elixir[1] = 10.0
        old = _place(eng, "boss_bandit", 1, 0.50, 0.30, hp_mult=0.05)   # desperate
        new = _place(eng, "boss_bandit", 1, 0.20, 0.30, hp_mult=1.00)   # fine
        self.assertFalse(bot._try_ability(eng))
        self.assertLessEqual(old.invis_left, 0.0)
        self.assertLessEqual(new.invis_left, 0.0)

    def test_it_never_fires_without_the_elixir(self):
        eng, bot = self._bot()
        eng.elixir[1] = 0.0
        _place(eng, "boss_bandit", 1, 0.50, 0.30, hp_mult=0.20)
        self.assertFalse(bot._try_ability(eng))

    def test_a_body_still_landing_does_not_fire(self):
        eng, bot = self._bot()
        eng.elixir[1] = 10.0
        bb = _place(eng, "boss_bandit", 1, 0.50, 0.72)
        bb.deploy_left = 1.0
        self.assertFalse(bot._try_ability(eng))

    def test_every_implemented_kind_has_a_family(self):
        """A new `ability_kind` with no family silently never fires. Cheap to pin, and I8 adds
        sixteen more."""
        from clashrl.sim.opponents import _ABILITY_FAMILY, _ABILITY_AI_DEFAULTS
        for kind in sorted(ABILITY_KINDS):
            with self.subTest(kind=kind):
                self.assertIn(kind, _ABILITY_FAMILY)
                self.assertIn(_ABILITY_FAMILY[kind], _ABILITY_AI_DEFAULTS)


if __name__ == "__main__":
    unittest.main()
