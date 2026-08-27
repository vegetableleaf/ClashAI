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
                                replace, _dist, _TILES_X, _TILES_Y)

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


def _mute(spec):
    """The same body with its NORMAL attack silenced. Every test here measures ONE ability, and a
    champion's own swing lands in the same damage ledger -- so a Little Prince's 104-damage arrow
    or Goblinstein's Doctor putting 135 and a 0.5 s stun into a target reads as ability output.
    Muting the swing leaves the ability untouched: they are separate fields."""
    return replace(spec, hit_dmg=0.0, tower_hit_dmg=0.0, stuns=False, stun_dur=0.0,
                   splash=False, dmg_stages=())


def _shot(eng, base, lvl=LVL):
    """A hand-built projectile from `base`, for probing the reflection RULE without arranging a
    live firing line (several excluded cards are kamikaze, so "did the shooter survive" cannot
    tell a reflected shot from a normal one)."""
    from clashrl.sim.engine import Projectile
    s = build_spec(eng.db, base, lvl)
    return Projectile(label="%s_projectile" % base, team=1, x=0.5, y=0.5, tx=0.5, ty=0.6,
                      target=None, spec=s, dmg=s.hit_dmg, tower_dmg=s.tower_hit_dmg,
                      radius=0.0, speed=max(s.proj_speed, 20.0), left=1.0)


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


class ArcherQueenStealthTests(unittest.TestCase):
    """CLOAKING CAPE -- kind `stealth` (Archer_Queen.wikitext, revid 436755; decisions.md ruling 6).

    Wiki: "the Archer Queen activates her 'Cloaking Cape', becoming invisible (untargetable by
    enemy troops), having a 80% increase in attack speed, and a massive decrease in movement speed
    for the entire 3.5-second duration of the ability."

    THE ATTACK-SPEED BUFF IS STATED THREE WAYS ON THE SAME PAGE, and this is the resolution:
        prose    "a 80% increase in attack speed"                 -> x1.8   ACCEPTED
        table    Boost "+180%"                                    -> x2.8   rejected
        History  "attack speed buff to 180% (from 200%)"          -> x1.8   accepted
    Resolved by the page's OWN level table, which is the only machine-readable statement of the
    three: its "Damage per second (with Cloaking Cape)" column computes `Dps(dmg_11*1.80,
    atk_speed)` -- damage x1.80 at an UNCHANGED 1.2 s hit speed, i.e. 1.8x DPS. Two of the three
    prose statements land on the same number and the table's leading "+" is the outlier; read as
    +180% it would mean x2.8, which no other line on the page supports. Hit interval 1.2 / 1.8 =
    0.667 s.
    Neither reading reproduces the Strategy claim of "exactly 7 shots for the full duration"
    (1.8x gives ~5.25, 2.8x ~8.2, and 7 would need ~2.4x). That is an in-game count, queued in
    conflicts.md; it is not evidence for a third multiplier.

    The movement penalty is the table's Slow (45) = 0.75 tiles/s against her body's Medium (60).
    """

    def _cloaked(self, cloak=True):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        aq = _place(eng, "archer_queen", 0, 0.50, 0.60)
        if cloak:
            self.assertTrue(eng.champion_ability(0))
            for _ in range(11):                     # burn the 1 s activation delay
                eng.advance(0.1)
        return eng, aq

    def test_the_cloak_makes_her_untargetable_by_TROOPS(self):
        eng, aq = self._cloaked()
        self.assertGreater(aq.ability_active_s, 0.0)
        foe = _place(eng, "knight", 1, 0.50, 0.58)
        self.assertFalse(eng._valid_foe(foe, aq))

    def test_but_splash_and_spells_still_reach_her(self):
        """History 8/4/2022 FIXED an invisible Archer Queen to receive splash damage, and Strategy
        says "since it is a spell, the player can reliably hit the Archer Queen even while her
        ability is active". That is the Royal Ghost's invisibility class, not the Boss Bandit's
        untouchable one -- `ghost`, not `invis_left`."""
        eng, aq = self._cloaked()
        self.assertTrue(aq.ghost)
        self.assertEqual(0.0, aq.invis_left, "she is UNSEEN, not immune")
        before = aq.hp
        eng.elixir[1] = 10.0
        eng.deploy(1, build_spec(eng.db, "fireball", LVL), aq.x, aq.y)
        for _ in range(40):
            eng.advance(0.1)
        self.assertLess(aq.hp, before, "a spell must still land on a cloaked Archer Queen")

    def test_she_shoots_1_point_8_times_faster_while_it_runs(self):
        out = {}
        for cloak in (False, True):
            eng, aq = self._cloaked(cloak=cloak)
            t = build_spec(eng.db, "knight", LVL)
            foe = Unit(spec=t, team=1, x=0.50, y=0.60 - 3.0 / _TILES_Y, hp=t.hp * 500)
            foe.deploy_left = 0.0
            eng.units.append(foe)
            fx, fy = foe.x, foe.y
            h0 = foe.hp
            for _ in range(35):                      # 3.5 s, the published duration
                foe.x, foe.y, aq.x, aq.y = fx, fy, 0.50, 0.60
                eng.advance(0.1)
            out[cloak] = (h0 - foe.hp) / build_spec(eng.db, "archer_queen", LVL).hit_dmg
        self.assertGreater(out[True], out[False])
        self.assertAlmostEqual(1.8, out[True] / max(out[False], 1e-9), delta=0.35,
                               msg="shots in 3.5 s: %.2f cloaked vs %.2f plain" % (out[True], out[False]))

    def test_and_walks_at_Slow_45_while_it_runs(self):
        moved = {}
        for cloak in (False, True):
            eng, aq = self._cloaked(cloak=cloak)
            y0 = aq.y
            for _ in range(30):                      # 3 s, inside the 3.5 s window
                eng.advance(0.1)
            moved[cloak] = abs(aq.y - y0) * _TILES_Y
        self.assertAlmostEqual(0.75, moved[True] / max(moved[False], 1e-9), delta=0.12,
                               msg="tiles walked: %.2f cloaked vs %.2f plain"
                                   % (moved[True], moved[False]))

    def test_it_ends_after_the_published_3_point_5_seconds(self):
        eng, aq = self._cloaked()
        for _ in range(45):
            eng.advance(0.1)
        self.assertEqual(0.0, aq.ability_active_s)
        self.assertFalse(aq.ghost, "the cloak has to come off, or she is permanently unseen")

    def test_ruling_7_is_REACHABLE_for_a_deferred_kind(self):
        """The refund case that actually happens in a match: she is still targetable during the
        1 s cast, so a stun or a kill inside it takes the ability with it and returns the elixir.
        (The two at-once kinds cannot get here -- both go untargetable for that exact window.)"""
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        aq = _place(eng, "archer_queen", 0, 0.50, 0.60)
        self.assertTrue(eng.champion_ability(0))
        self.assertAlmostEqual(9.0, eng.elixir[0], places=6)
        aq.hp = 0.0
        eng.advance(0.1)
        self.assertAlmostEqual(10.0, eng.elixir[0], places=6)
        self.assertFalse(aq.ghost, "the cloak never went up")


class GoldenKnightDashChainTests(unittest.TestCase):
    """DASHING DASH -- kind `dash_chain` (Golden_Knight.wikitext, revid 437147; owner ruling 10).

    Wiki, verbatim: "Once a unit is in range, he dashes to it quickly, then dashes towards the
    closest enemy unit within a 5.5-tile radius (even if the previous unit was not destroyed). His
    dashes have invulnerability and deal increased damage, like the Bandit. He cannot dash into
    the same troop per ability use. He will stop dashing after dashing 10 times, if no other valid
    targets are within range, or if the last target hit is a Crown Tower."

    THREE TERMINATORS, per ruling 10 as amended by that last clause (which the ruling omitted and
    wiki verification restored): the 10-dash cap, no valid target in range, and a Crown Tower hit.
    Ruling 10 also settles the page's most load-bearing ambiguity -- "no targets in range" ENDS
    the ability. There is no pause-and-resume and no return-to-origin: he stops AT THE LAST
    TARGET'S LOCATION and behaves as a normal troop from there.

    ⚠ DASH TRAVEL SPEED IS UNPUBLISHED and 8.33 tiles/s is the Bandit / Boss Bandit analog (their
    Dash Speed 500 at 60 units = 1 tile/s), marked untested in the KB. Every timing below is
    therefore a consequence of an unmeasured constant; the SHAPE tests are not.
    """

    def _chain(self, n_bodies=12, spacing=1.3, y=0.55, x0=0.06):
        # 1.3 tiles apart, so twelve of them span 15.6 tiles and FIT: the arena is 18 tiles wide,
        # and at the 3.0-tile spacing the first draft used, bodies 6-11 sat off the board and the
        # chain "ended early" for a reason that had nothing to do with the card.
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        gk = _place(eng, "golden_knight", 0, x0, y)
        t = build_spec(eng.db, "knight", LVL)
        bodies = []
        for i in range(n_bodies):
            b = Unit(spec=t, team=1, x=x0 + ((i + 1) * spacing) / _TILES_X, y=y, hp=t.hp * 50)
            b.deploy_left = 0.0
            bodies.append(b)
            eng.units.append(b)
        return eng, gk, bodies

    def _run(self, eng, gk, bodies, steps=200):
        """Damage dealt by the CHAIN, and by nothing else.

        The ledger is opened when the chain STARTS and closed the tick it ends. Both ends matter:
        before it starts he spends the 1 s activation delay walking up and swinging normally, and
        after it ends he swings at whatever he stopped beside -- MEASURED, both leak 161.1 per hit
        into a column that is supposed to read 335.
        """
        pos = [(b.x, b.y) for b in bodies]
        self.assertTrue(eng.champion_ability(0))
        start, started = None, False
        for _ in range(steps):
            for b, (px, py) in zip(bodies, pos):
                b.x, b.y = px, py                    # pinned: this is a CHAIN test, not a race
            eng.advance(0.05)
            if not started and gk.dash_left > 0:
                started = True
                start = [b.hp for b in bodies]       # the chain is armed: open the ledger here
            elif started and gk.dash_left <= 0:
                break
        self.assertTrue(started, "the chain never armed")
        return [h0 - b.hp for h0, b in zip(start, bodies)]

    def test_he_dashes_the_published_TEN_times_and_stops(self):
        eng, gk, bodies = self._chain(n_bodies=12)
        dmg = self._run(eng, gk, bodies)
        hit = [d for d in dmg if d > 0]
        self.assertEqual(10, len(hit), "table 'Maximum Dashes' = 10; got %s" % dmg)
        self.assertEqual(0, gk.dash_left)

    def test_each_dash_lands_the_published_dash_damage(self):
        eng, gk, bodies = self._chain(n_bodies=12)
        dmg = self._run(eng, gk, bodies)
        s = build_spec(eng.db, "golden_knight", LVL)
        self.assertAlmostEqual(335.0, s.ability_dmg, delta=0.5, msg="vardefine dash_11")
        for i, d in enumerate(dmg[:10]):
            with self.subTest(body=i):
                self.assertAlmostEqual(335.0, d, delta=1.0)

    def test_he_never_dashes_the_same_body_twice(self):
        """"He cannot dash into the same troop per ability use." Two bodies and a ten-dash budget:
        without the exclusion he would bounce between them until the cap."""
        eng, gk, bodies = self._chain(n_bodies=2)
        dmg = self._run(eng, gk, bodies)
        for i, d in enumerate(dmg):
            with self.subTest(body=i):
                self.assertAlmostEqual(335.0, d, delta=1.0, msg="exactly one dash each")

    def test_no_valid_target_in_range_ENDS_it(self):
        """Ruling 10's second terminator, and the answer to the page's biggest unknown: this is an
        END, not a pause. Two bodies inside 5.5 tiles and a third far outside it -- he takes the
        two and stops rather than waiting for the third to walk in."""
        eng, gk, bodies = self._chain(n_bodies=2)
        far = build_spec(eng.db, "knight", LVL)
        stray = Unit(spec=far, team=1, x=0.90, y=0.55, hp=far.hp * 50)
        stray.deploy_left = 0.0
        eng.units.append(stray)
        h0 = stray.hp
        self._run(eng, gk, bodies)
        self.assertEqual(0, gk.dash_left)
        self.assertAlmostEqual(h0, stray.hp, delta=1.0, msg="he must not have waited for it")

    def test_a_CROWN_TOWER_hit_ends_the_chain_even_with_dashes_left(self):
        """The third terminator, introduced 4/4/2022 and omitted by ruling 10 until wiki
        verification restored it: "or if the last target hit is a Crown Tower". The tower can
        still BE a dash target and take dash damage -- the chain simply always ends there."""
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        tw = eng.towers[1][0]
        gk = _place(eng, "golden_knight", 0, tw.x, tw.y + 4.0 / _TILES_Y)
        t = build_spec(eng.db, "knight", LVL)
        # A second body PAST the tower, still inside the 5.5-tile arc from it, so the only reason
        # it can survive is the terminator.
        behind = Unit(spec=t, team=1, x=tw.x + 3.0 / _TILES_X, y=tw.y - 2.0 / _TILES_Y,
                      hp=t.hp * 50)
        behind.deploy_left = 0.0
        eng.units.append(behind)
        hp0, bx, by = tw.hp, behind.x, behind.y
        self.assertTrue(eng.champion_ability(0))
        started, bh = False, None
        for _ in range(120):
            behind.x, behind.y = bx, by
            eng.advance(0.05)
            if not started and gk.dash_left > 0:
                started, bh = True, behind.hp
            elif started and gk.dash_left <= 0:
                break
        self.assertTrue(started)
        self.assertLess(tw.hp, hp0, "a crown tower IS a dash target")
        self.assertEqual(0, gk.dash_left, "and hitting one ends the chain")
        self.assertGreater(gk.spec.ability_max_hits, 2, "with dashes still on the clock")
        self.assertAlmostEqual(bh, behind.hp, delta=1.0,
                               msg="nothing after the tower may be dashed")

    def test_he_is_immune_to_damage_in_flight(self):
        """Wiki: "When dashing, he is immune to all forms of damage like the Bandit."""
        eng, gk, bodies = self._chain(n_bodies=12)
        self.assertTrue(eng.champion_ability(0))
        for _ in range(60):
            eng.advance(0.05)
            if gk.dash_go:
                break
        self.assertTrue(gk.dash_go, "he should be mid-dash by now")
        hp0 = gk.hp
        eng._hurt(gk, 5000.0)
        self.assertEqual(hp0, gk.hp)

    def test_he_stops_where_the_last_target_was_and_does_not_return(self):
        """Ruling 10: "he stops AT THE LAST TARGET'S LOCATION and then moves/attacks like a normal
        troop". No return-to-origin anywhere on the page or in the ruling. Wide spacing here so
        the three landing points are far apart and "where he stopped" is unambiguous."""
        eng, gk, bodies = self._chain(n_bodies=3, spacing=3.0)
        x0 = gk.x
        self._run(eng, gk, bodies)
        self.assertGreater(gk.x, x0 + 5.0 / _TILES_X,
                           "he ended back near where he started -- that is a return-to-origin")
        self.assertAlmostEqual(bodies[-1].x, gk.x, delta=2.5 / _TILES_X,
                               msg="he should be standing on the LAST body he dashed")

    def test_the_movement_boost_only_runs_while_the_chain_does(self):
        eng, gk, _bodies = self._chain(n_bodies=0)
        s = build_spec(eng.db, "golden_knight", LVL)
        self.assertAlmostEqual(2.0, s.ability_move_speed, places=6)   # Very Fast (120)
        self.assertAlmostEqual(1.0, s.speed, places=6)                # his body is Medium (60)
        self.assertEqual(0, gk.dash_left)


class SkeletonKingSoulBankTests(unittest.TestCase):
    """SOUL SUMMONING -- kind `soul_bank` (Skeleton_King.wikitext, revid 436753; owner ruling 8).

    Wiki: "The number of Skeletons spawned is based on how many troops die (either from the player
    or the opponent) while he is deployed... With no souls, the Skeleton King will spawn 6
    Skeletons, but with a maximum of 10 souls, he can summon 16." The Skeletons "behave identically
    to cloned Skeletons... they only have 1 hitpoint" -- a curated `soul_skeleton` row, not the
    Skeletons card. Spawn radius 3.5 (History 24/10/2025; the ability prose's 4 was never
    updated), one every 0.25 s.

    RULING 8 (owner): a body that has spent its use stops banking souls.
    """

    def _king(self, souls=0):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        sk = _place(eng, "skeleton_king", 0, 0.50, 0.60)
        sk.souls = souls
        return eng, sk

    def _summon(self, eng, sk, steps=120):
        self.assertTrue(eng.champion_ability(0))
        for _ in range(steps):
            eng.advance(0.05)
        return [u for u in eng.units
                if u.team == 0 and u.hp > 0 and u.spec.base == "soul_skeleton"]

    def test_no_souls_summons_the_published_floor_of_six(self):
        eng, sk = self._king(souls=0)
        self.assertEqual(6, len(self._summon(eng, sk)))

    def test_a_full_bar_summons_the_published_sixteen(self):
        eng, sk = self._king(souls=10)
        self.assertEqual(16, len(self._summon(eng, sk)))

    def test_they_are_ONE_hitpoint_clone_variant_skeletons(self):
        eng, sk = self._king()
        for u in self._summon(eng, sk):
            self.assertAlmostEqual(1.0, u.spec.hp, places=6)
            self.assertAlmostEqual(81.0, u.spec.hit_dmg, delta=1.0)   # vardefine skel_dmg_11
        self.assertNotEqual("skeletons", build_spec(eng.db, "skeleton_king", LVL).ability_spawn.base)

    def test_they_land_inside_the_published_radius_one_at_a_time(self):
        """Positions are read the tick each Skeleton APPEARS. They are Fast (90) and march off
        immediately, so measuring at the end of the run measures where they walked to -- MEASURED,
        6.45 tiles from him after 6 s, against a 3.5-tile spawn radius."""
        eng, sk = self._king(souls=10)
        self.assertTrue(eng.champion_ability(0))
        seen, first_at, counts, cx, cy = set(), [], [], None, None
        for _ in range(120):
            eng.advance(0.05)
            if cx is None and eng._late_spawns:
                cx, cy = sk.x, sk.y                  # where he stood when the summon queued
            for u in eng.units:
                if u.spec.base == "soul_skeleton" and id(u) not in seen:
                    seen.add(id(u))
                    first_at.append(_dist(u.x, u.y, cx, cy))
            counts.append(len(seen))
        self.assertEqual(16, len(first_at))
        self.assertLess(counts[4], 16, "0.25 s apart -- they cannot all be out immediately")
        # Sixteen 0.5-radius bodies inside a 3.5-tile disc overlap heavily, so soft collision has
        # already shoved them by the tick after each one appears -- MEASURED, up to 0.6 tiles.
        # The ABILITY's own choice is asserted strictly below, off the queued points; this bound
        # is on where physics leaves them.
        for i, d in enumerate(first_at):
            with self.subTest(skeleton=i):
                self.assertLessEqual(d, 3.5 + 1.0)

    def test_the_summon_points_themselves_are_inside_the_published_radius(self):
        """The ability's own geometry, read off the spawn queue before any physics touches it.
        History 24/10/2025: "decreased Soul Summoning's skeleton spawn radius to 3.5 tiles (from
        4 tiles)" -- the later edit, against an ability prose paragraph still saying 4.

        Measured from where he stood when the ability RESOLVED, not from where he was placed: he
        walks during the 1 s activation delay, and reading from the placement point instead put
        the queued points up to 4.09 tiles out -- a full tile of his own movement, not spread.
        """
        eng, sk = self._king(souls=10)
        self.assertTrue(eng.champion_ability(0))
        cx = cy = None
        for _ in range(21):                          # burn the 1 s activation delay
            eng.advance(0.05)
            if cx is None and eng._late_spawns:
                cx, cy = sk.x, sk.y
        pts = [(q[3], q[4]) for q in eng._late_spawns]
        self.assertEqual(16, len(pts) + sum(1 for u in eng.units
                                            if u.spec.base == "soul_skeleton"))
        for i, (px, py) in enumerate(pts):
            with self.subTest(point=i):
                self.assertLessEqual(_dist(px, py, cx, cy), 3.5 + 1e-6)

    def test_a_troop_death_on_EITHER_side_banks_a_soul(self):
        eng, sk = self._king()
        mine = _place(eng, "knight", 0, 0.40, 0.60)
        theirs = _place(eng, "knight", 1, 0.60, 0.60)
        mine.hp = 0.0
        theirs.hp = 0.0
        eng.advance(0.05)
        self.assertEqual(2, sk.souls, 'wiki: "either from the player or the opponent"')

    def test_a_BUILDING_death_banks_nothing(self):
        """Wiki: "Buildings also do not count as souls when vanquished."""
        eng, sk = self._king()
        b = _place(eng, "cannon", 1, 0.60, 0.60)
        self.assertEqual("building", b.spec.kind)
        b.hp = 0.0
        eng.advance(0.05)
        self.assertEqual(0, sk.souls)

    def test_the_bar_stops_at_the_published_cap_of_ten(self):
        eng, sk = self._king(souls=10)
        v = _place(eng, "knight", 1, 0.60, 0.60)
        v.hp = 0.0
        eng.advance(0.05)
        self.assertEqual(10, sk.souls)

    def test_RULING_8_a_spent_body_stops_accruing(self):
        eng, sk = self._king(souls=2)
        self._summon(eng, sk, steps=40)
        self.assertEqual(0, eng._ability_uses_left(sk))
        before = sk.souls
        v = _place(eng, "knight", 1, 0.60, 0.60)
        v.hp = 0.0
        eng.advance(0.05)
        self.assertEqual(before, sk.souls, "ruling 8: a spent body banks nothing more")

    def test_his_own_summoned_skeletons_do_not_bank_souls(self):
        """"neither do the Skeletons summoned from the ability" -- and without the exclusion a
        Skeleton King on a swarm board would feed his own bar off his own bodies."""
        eng, sk = self._king()
        skels = self._summon(eng, sk, steps=40)
        sk.ability_left = 1                       # re-arm ONLY the accrual gate, not a second use
        before = sk.souls
        for u in skels:
            u.hp = 0.0
        eng.advance(0.05)
        self.assertEqual(before, sk.souls)

    def test_the_summon_finishes_even_if_he_dies_mid_sequence(self):
        """"It continues, even if the Skeleton King dies." Queued into the engine's timed-spawn
        list, which holds positions rather than a reference to him, so his death cannot cancel
        it -- and History 30/3/2022 had to FIX a case where it could."""
        eng, sk = self._king(souls=10)
        self.assertTrue(eng.champion_ability(0))
        for _ in range(30):                        # 1.5 s: past the cast, mid-sequence
            eng.advance(0.05)
        out = sum(1 for u in eng.units if u.spec.base == "soul_skeleton")
        self.assertGreater(out, 0)
        self.assertLess(out, 16, "still summoning")
        sk.hp = 0.0
        for _ in range(120):
            eng.advance(0.05)
        self.assertEqual(16, sum(1 for u in eng.units if u.spec.base == "soul_skeleton"))


class LittlePrinceGuardianTests(unittest.TestCase):
    """ROYAL RESCUE -- kind `guardian` (Little_Prince.wikitext, revid 437347; decisions.md #13).

    Wiki: "causing Guardienne to charge directly in front of the Little Prince and knock opposing
    ground troops away by 0-2 tiles (depends on how close the unit is to the sweet spot) while
    also doing moderate damage. After the charge is completed, Guardienne stays in the arena until
    she's taken out."

    GUARDIENNE IS FULLY SPECIFIED and PERMANENT: 1600 hp (guard_hp_11), 1.2 s hit speed, 0.5 s
    first hit, Medium (60), 0.3 s deploy, Melee: Medium (1.2), GROUND ONLY, 0.8-tile collision.
    Her damage is 232, NOT the 217 vardefine: 217 is byte-identical at revid 436758 and live, so
    it predates the 4/8/2026 "Guardian Melee Damage +7%" (217 x 1.07 -> 232). I5 applied it with
    an explicit warning that I7 must not revert it, and this test is that warning's enforcement.

    PUSHBACK 2.5 TILES, FLAT -- the little_prince half of conflicts.md C8. The page states it
    twice and disagrees with itself: prose "0-2 tiles (depends on how close the unit is to the
    sweet spot)" vs History 1/9/2025 "increased the Royal Rescue's pushback to 2.5 tiles (from 2
    tiles)". The History entry is later and its chain is complete and monotone (3.5 -> 2.5 -> 2 ->
    2.5). The graded version is unimplementable regardless: the "sweet spot" is never located and
    no falloff curve is given.
    """

    def _rescue(self, foes=(), y=0.60):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        lp = _place(eng, None, 0, 0.50, y, spec=_mute(build_spec(eng.db, "little_prince", LVL)))
        bodies = [_place(eng, key, 1, 0.50, y - d / _TILES_Y, hp_mult=40.0) for key, d in foes]
        self.assertTrue(eng.champion_ability(0))
        for _ in range(22):                       # burn the 1 s activation delay + the charge
            eng.advance(0.05)
        return eng, lp, bodies

    def _guardienne(self, eng):
        return [u for u in eng.units if u.hp > 0 and u.spec.base == "guardienne"]

    def test_she_arrives_with_her_published_body(self):
        eng, _lp, _ = self._rescue()
        g = self._guardienne(eng)
        self.assertEqual(1, len(g))
        s = g[0].spec
        self.assertAlmostEqual(1600.0, s.hp, delta=1.0)
        self.assertAlmostEqual(232.0, s.hit_dmg, delta=1.0,
                               msg="232, not the stale 217 vardefine -- I5 warned about this one")
        self.assertAlmostEqual(1.2, s.hit_speed, places=6)
        self.assertAlmostEqual(1.2, s.reach, places=6)
        self.assertAlmostEqual(0.3, s.deploy_time, places=6)
        self.assertAlmostEqual(0.8, s.radius, places=6)
        self.assertAlmostEqual(1.0, s.speed, places=6, msg="Medium (60)")

    def test_she_is_GROUND_only(self):
        """Attributes table Target = Ground, and Strategy proves it: "Minions can also work even
        if he activates his ability, as they are immune to Guardienne's damage and cannot be
        targeted by Guardienne."
        """
        eng, _lp, _ = self._rescue()
        self.assertFalse(self._guardienne(eng)[0].spec.attacks_air)

    def test_she_is_PERMANENT_and_outlives_the_prince(self):
        """"stays in the arena until she's taken out" -- no lifetime, and the page's Strategy
        describes killing him and then dealing with her separately."""
        eng, lp, _ = self._rescue()
        lp.hp = 0.0
        for _ in range(400):                      # 20 s
            eng.advance(0.05)
        self.assertEqual(1, len(self._guardienne(eng)), "she must not despawn with him")

    def test_the_charge_damages_ground_bodies_in_front_of_him(self):
        eng, _lp, bodies = self._rescue(foes=(("knight", 2.0),))
        self.assertLess(bodies[0].hp, bodies[0].spec.hp * 40.0)

    def test_the_charge_hits_EVERY_body_in_the_corridor(self):
        """"The Little Prince can be used as a situational counter to the Goblin Barrel as
        activating his ability at the proper time and position will allow Guardienne to take out
        all three Goblins at once due to her charge." Multi-target, once each."""
        eng, _lp, bodies = self._rescue(foes=(("knight", 1.5), ("knight", 3.0), ("knight", 4.2)))
        for i, b in enumerate(bodies):
            with self.subTest(body=i):
                self.assertLess(b.hp, b.spec.hp * 40.0)

    def test_but_not_past_its_published_reach(self):
        """4 tiles of dash range plus her 0.8-tile collision radius -- the page's own Strategy
        adds them: "Although the Royal Rescue's range is 4 tiles, the Guardienne has an extra 0.8
        tile collision radius, allowing her to reach slightly further"."""
        eng, _lp, bodies = self._rescue(foes=(("knight", 7.5),))
        self.assertAlmostEqual(bodies[0].spec.hp * 40.0, bodies[0].hp, delta=1.0)

    def test_it_knocks_ground_bodies_BACK(self):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        _place(eng, None, 0, 0.50, 0.60, spec=_mute(build_spec(eng.db, "little_prince", LVL)))
        foe = _place(eng, "knight", 1, 0.50, 0.60 - 2.0 / _TILES_Y, hp_mult=40.0)
        y0 = foe.y
        self.assertTrue(eng.champion_ability(0))
        for _ in range(22):
            eng.advance(0.05)
        self.assertLess(foe.y, y0, "pushed AWAY from the Little Prince, i.e. further up the board")
        self.assertAlmostEqual(2.5, build_spec(eng.db, "little_prince", LVL).ability_knock,
                               places=6, msg="History 1/9/2025, not the prose 0-2")

    def test_AIR_is_untouched_by_the_charge(self):
        """His own arrows DO reach air (Target: Air & Ground) -- MEASURED, an unmuted Little
        Prince put 104.4 into this Minion, which is his body damage, not the charge's 256."""
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        _place(eng, None, 0, 0.50, 0.60, spec=_mute(build_spec(eng.db, "little_prince", LVL)))
        bat = _place(eng, "minions", 1, 0.50, 0.60 - 2.0 / _TILES_Y, hp_mult=40.0)
        self.assertTrue(bat.spec.flying)
        h0 = bat.hp
        self.assertTrue(eng.champion_ability(0))
        for _ in range(12):
            eng.advance(0.05)
        self.assertAlmostEqual(h0, bat.hp, delta=1.0)


class MonkReflectTests(unittest.TestCase):
    """PENSIVE PROTECTION -- kind `reflect` (Monk.wikitext, revid 437140).

    Wiki: "reducing all incoming damage he takes by 65% and reflect all incoming projectile-based
    ranged attacks back to the said offender. Spells are always reflected to the closest opposing
    Crown Tower. He cannot protect nearby allies from melee attacks, non-projectile ranged attacks
    and non-projectile spells."

    ⚠ THE CONTRADICTION, and the choice. The ability prose says he reflects ALL projectile-based
    ranged attacks. Strategy then exempts Spirit cards "DESPITE BEING PROJECTILES when attacking"
    -- the same sentence concedes they are projectiles and excludes them anyway. Both are
    recorded in research/sim_parity/abilities/monk.yaml; the SPECIFIC list is implemented, for
    three reasons: it is dated (the Heal Spirit exemption is History 12/12/2022, i.e. a change TO
    the blanket rule), it is enumerated card by card rather than asserted in general, and reading
    the prose literally would hand the Monk four matchups the same page says he loses. The list
    lives in engine.py's `_NO_REFLECT_BASES` with each quote beside it, because the exclusions are
    stated by CARD NAME and nothing in a card's stats separates an instant electric hit from a
    fired one.

    The "Invulnerability Duration 4 sec" column is a misnomer -- he is not invulnerable, and the
    same table publishes "Damage Reduced -65%" beside it.
    """

    def _monk(self, active=True):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        mk = _place(eng, "monk", 0, 0.50, 0.60)
        if active:
            self.assertTrue(eng.champion_ability(0))
            for _ in range(21):                   # burn the 1 s activation delay
                eng.advance(0.05)
            self.assertGreater(mk.ability_active_s, 0.0)
        return eng, mk

    def test_he_takes_65_percent_less_from_EVERY_source(self):
        """"reducing ALL incoming damage he takes by 65%" -- not only the projectiles he
        reflects, which is why this lives in `_hurt` and not in the reflection path."""
        taken = {}
        for active in (False, True):
            eng, mk = self._monk(active=active)
            h0 = mk.hp
            eng._hurt(mk, 1000.0)
            taken[active] = h0 - mk.hp
        self.assertAlmostEqual(1000.0, taken[False], delta=1.0)
        self.assertAlmostEqual(350.0, taken[True], delta=1.0, msg="Damage Reduced -65%")

    def test_a_projectile_aimed_at_him_goes_BACK_at_the_shooter(self):
        """Measured strictly INSIDE the 4 s window: it is a duration, and MEASURED past it the
        musketeer's next two shots land on him normally, which is the ability working."""
        eng, mk = self._monk()
        shooter = _place(eng, "musketeer", 1, 0.50, 0.60 - 5.0 / _TILES_Y, hp_mult=20.0)
        sx, sy, h0, mh0 = shooter.x, shooter.y, shooter.hp, mk.hp
        for _ in range(60):                       # 3 s, inside the published 4
            shooter.x, shooter.y, mk.x, mk.y = sx, sy, 0.50, 0.60
            eng.advance(0.05)
        self.assertGreater(mk.ability_active_s, 0.0, "still inside the window")
        self.assertLess(shooter.hp, h0, "the shooter must take her own shot")
        self.assertAlmostEqual(mh0, mk.hp, delta=1.0, msg="and the Monk must take none of it")

    def test_the_reflected_shot_keeps_the_SOURCE_damage(self):
        """"Any projectile the Monk reflects with Pensive Protection will have the same damage as
        the initial source of the projectile, and will not scale up nor down to the Monk's
        level."
        """
        eng, mk = self._monk()
        shooter = _place(eng, "musketeer", 1, 0.50, 0.60 - 5.0 / _TILES_Y, hp_mult=20.0)
        sx, sy, h0 = shooter.x, shooter.y, shooter.hp
        for _ in range(60):
            shooter.x, shooter.y, mk.x, mk.y = sx, sy, 0.50, 0.60
            eng.advance(0.05)
            if shooter.hp < h0:
                break
        self.assertAlmostEqual(build_spec(eng.db, "musketeer", LVL).hit_dmg, h0 - shooter.hp,
                               delta=1.0)

    def test_an_INFERNO_BEAM_is_not_a_projectile_and_is_not_reflected(self):
        """"Both the Inferno Dragon and Inferno Tower can counter a Monk for positive or neutral
        trade, as neither their beams count as projectiles."
        """
        eng, mk = self._monk()
        inf = _place(eng, "inferno_dragon", 1, 0.50, 0.60 - 3.0 / _TILES_Y, hp_mult=20.0)
        sx, sy, h0 = inf.x, inf.y, inf.hp
        for _ in range(120):
            inf.x, inf.y, mk.x, mk.y = sx, sy, 0.50, 0.60
            eng.advance(0.05)
        self.assertAlmostEqual(h0, inf.hp, delta=1.0, msg="its beam must not bounce")
        self.assertLess(mk.hp, mk.spec.hp, "...and it must still be hurting him")

    def test_an_INSTANT_electric_attack_is_not_reflected(self):
        """"Cards such as Tesla, Zappies, Electro Dragon and Electro Wizard will not take
        reflected damage, since their attacks are instant and not counted as projectiles."
        """
        eng, mk = self._monk()
        ew = _place(eng, "electro_wizard", 1, 0.50, 0.60 - 4.0 / _TILES_Y, hp_mult=20.0)
        sx, sy, h0 = ew.x, ew.y, ew.hp
        for _ in range(120):
            ew.x, ew.y, mk.x, mk.y = sx, sy, 0.50, 0.60
            eng.advance(0.05)
        self.assertAlmostEqual(h0, ew.hp, delta=1.0)

    def test_a_SPIRIT_is_not_reflected_even_though_it_is_a_projectile(self):
        """The contradiction, implemented: "Spirit cards cannot be reflected by the Monk, despite
        being projectiles when attacking." The specific list beats the general claim.

        Probed on the reflection TEST rather than by live fire, because a Spirit is kamikaze --
        it dies of its own attack, so "did the shooter survive" cannot distinguish a reflected
        shot from a normal one for this class of card.
        """
        eng, mk = self._monk()
        for base in ("ice_spirit", "fire_spirit", "electro_spirit", "heal_spirit"):
            with self.subTest(card=base):
                p = _shot(eng, base)
                self.assertFalse(eng._reflects(mk, p))
        self.assertTrue(eng._reflects(mk, _shot(eng, "musketeer")),
                        "...while an ordinary fired projectile still bounces")

    def test_the_reflection_list_is_the_pages_own_enumeration(self):
        import clashrl.sim.engine as E
        for base in ("inferno_dragon", "inferno_tower", "tesla", "zappies", "electro_dragon",
                     "electro_wizard", "ice_spirit", "fire_spirit", "electro_spirit",
                     "heal_spirit", "fisherman"):
            with self.subTest(card=base):
                self.assertIn(base, E._NO_REFLECT_BASES)

    def test_the_FISHERMAN_hook_is_stifled_rather_than_reflected(self):
        """"The Fisherman's hook is fully stifled until the ability ends, forcing him to
        repeatedly charge his hook." Nullified, which is a different outcome from reflected, and
        the page is explicit about which one it is."""
        eng, mk = self._monk()
        self.assertTrue(eng._hook_blocked(mk))
        eng2, mk2 = self._monk(active=False)
        self.assertFalse(eng2._hook_blocked(mk2))

    def test_it_ends_after_the_published_four_seconds(self):
        eng, mk = self._monk()
        for _ in range(120):
            eng.advance(0.05)
        self.assertEqual(0.0, mk.ability_active_s)
        h0 = mk.hp
        eng._hurt(mk, 1000.0)
        self.assertAlmostEqual(1000.0, h0 - mk.hp, delta=1.0, msg="the reduction has to lapse")


class GoblinsteinZoneTests(unittest.TestCase):
    """LIGHTNING LINK -- kind `zone` (Goblinstein.wikitext, revid 437348).

    Wiki: "creating an electric link between him and Monster. It damages by shocking nearby
    targets every 0.5 seconds up to 2 tiles away. This ability deals reduced damage to the Crown
    Tower. If the Monster has already been defeated, it will drop an antenna on the ground which
    is what the Goblinstein's electric link will target when the ability is activated."

    ⚠ LINK GEOMETRY IS UNDEFINED ON THE PAGE, and this is the choice, queued for an in-game check
    in conflicts.md. Three readings were available: 2 tiles from the SEGMENT joining Doctor and
    Monster (a capsule), 2 tiles from each endpoint (two circles), or 2 tiles from the Monster end
    alone. THE CAPSULE IS TAKEN, because the prose makes the LINK the damaging object -- "creating
    an electric link between him and Monster. It damages by shocking nearby targets ... up to 2
    tiles away" -- and the Strategy line that sounds like a circle ("will hit everything within a
    2 tile radius") never names a centre, so it cannot decide it. Two circles would leave a hole
    in the middle of a tether drawn as one continuous arc, and the Monster-only reading
    contradicts "between him and Monster".

    Numbers are I5's: 107 per shock (vardefine link_11), 23 against a Crown Tower (crown_11), 2
    tiles, 4 s, every 0.5 s. NO STUN, per Trivia: "The Goblinstein's Lightning Link does not
    inflict a stun on the enemies despite being an attack involving electricity."
    """

    def _link(self):
        """Doctor and Monster hand-placed 6 tiles apart, so the capsule's MIDDLE is far from both
        ends and the three readings give visibly different answers."""
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        card = build_spec(eng.db, "goblinstein", LVL)
        doc, mon = (_mute(c) for c in card.components)
        d = _place(eng, None, 0, 0.50, 0.60, spec=doc)
        m = _place(eng, None, 0, 0.50 + 6.0 / _TILES_X, 0.60, spec=mon)
        return eng, d, m

    def _run(self, eng, pinned, steps=120):
        pos = [(u.x, u.y) for u in pinned]
        for _ in range(steps):
            for u, (px, py) in zip(pinned, pos):
                u.x, u.y = px, py
            eng.advance(0.05)

    def test_the_link_carries_the_ability_even_with_the_bodies_muted(self):
        """`_mute` is what makes every measurement in this class about the LINK. The Doctor is a
        5.5-tile air-and-ground attacker whose own swing STUNS for 0.5 s and the Monster is a
        building-targeting melee body; unmuted, MEASURED, their normal attacks put 647 extra
        damage and a stun into a ledger that is supposed to read 8 x 107 and no stun."""
        eng, doc, _mon = self._link()
        self.assertEqual(0.0, doc.spec.hit_dmg)
        self.assertGreater(doc.spec.ability_dmg, 0.0)

    def test_the_doctor_owns_the_ability_and_the_monster_does_not(self):
        """Both bodies come from one `replace` in build_spec, so without the component-0 rule the
        Monster inherits `ability_kind` and becomes a second champion body -- which would then win
        ruling 5's newest-body selection about half the time."""
        eng, doc, mon = self._link()
        self.assertEqual("zone", doc.spec.ability_kind)
        self.assertEqual("", mon.spec.ability_kind)
        self.assertTrue(mon.spec.building_only, "the Monster is the building-targeting half")

    def test_it_shocks_everything_along_the_LINK_not_just_around_the_doctor(self):
        """The capsule reading, made falsifiable: a body at the MIDPOINT is 3 tiles from each
        endpoint, so under the two-circles reading it would take nothing at all."""
        eng, doc, mon = self._link()
        mid = _place(eng, "knight", 1, 0.50 + 3.0 / _TILES_X, 0.60, hp_mult=40.0)
        h0 = mid.hp
        self.assertTrue(eng.champion_ability(0))
        self._run(eng, [doc, mon, mid])
        self.assertLess(mid.hp, h0, "a body on the tether must be shocked")

    def test_it_ticks_eight_times_for_the_published_damage(self):
        """4 s / 0.5 s, first shock AT activation. The page publishes the duration and the
        interval and never says whether t=0 fires; 8 is the reading in which the published
        duration IS the ability rather than the duration plus a free tick."""
        eng, doc, mon = self._link()
        v = _place(eng, "knight", 1, 0.50 + 3.0 / _TILES_X, 0.60, hp_mult=400.0)
        h0 = v.hp
        self.assertTrue(eng.champion_ability(0))
        self._run(eng, [doc, mon, v], steps=140)
        s = build_spec(eng.db, "goblinstein", LVL)
        self.assertAlmostEqual(107.0, s.ability_dmg, delta=0.5, msg="vardefine link_11")
        self.assertAlmostEqual(8 * 107.0, h0 - v.hp, delta=2.0)

    def test_nothing_outside_two_tiles_of_the_link_is_touched(self):
        eng, doc, mon = self._link()
        far = _place(eng, "knight", 1, 0.50 + 3.0 / _TILES_X, 0.60 - 4.0 / _TILES_Y, hp_mult=40.0)
        h0 = far.hp
        self.assertTrue(eng.champion_ability(0))
        self._run(eng, [doc, mon, far])
        self.assertAlmostEqual(h0, far.hp, delta=1.0)

    def test_it_reaches_AIR_as_well_as_ground(self):
        """Lightning Link Attributes Target = "Air & Ground", unlike the Doctor's own attack
        having to pick one."""
        eng, doc, mon = self._link()
        air = _place(eng, "minions", 1, 0.50 + 3.0 / _TILES_X, 0.60, hp_mult=40.0)
        self.assertTrue(air.spec.flying)
        h0 = air.hp
        self.assertTrue(eng.champion_ability(0))
        self._run(eng, [doc, mon, air])
        self.assertLess(air.hp, h0)

    def test_it_does_NOT_stun(self):
        """Trivia: "The Goblinstein's Lightning Link does not inflict a stun on the enemies
        despite being an attack involving electricity. However, his regular attack is able to
        stun." The Doctor's own 0.5 s stun is a separate mechanic and stays."""
        eng, doc, mon = self._link()
        v = _place(eng, "knight", 1, 0.50 + 3.0 / _TILES_X, 0.60, hp_mult=400.0)
        self.assertTrue(eng.champion_ability(0))
        stunned = False
        pos = [(u.x, u.y) for u in (doc, mon, v)]
        for _ in range(60):
            for u, (px, py) in zip((doc, mon, v), pos):
                u.x, u.y = px, py
            eng.advance(0.05)
            stunned = stunned or v.stun_left > 0.0
        self.assertLess(v.hp, v.spec.hp * 400.0, "it was being shocked")
        self.assertFalse(stunned)

    def test_a_crown_tower_takes_the_REDUCED_published_value(self):
        eng = _quiet(_make_engine())
        eng.elixir[0] = 10.0
        card = build_spec(eng.db, "goblinstein", LVL)
        doc, mon = (_mute(c) for c in card.components)
        tw = eng.towers[1][0]
        d = _place(eng, None, 0, tw.x, tw.y + 2.0 / _TILES_Y, spec=doc)
        m = _place(eng, None, 0, tw.x + 2.0 / _TILES_X, tw.y + 2.0 / _TILES_Y, spec=mon)
        hp0 = tw.hp
        self.assertTrue(eng.champion_ability(0))
        self._run(eng, [d, m], steps=140)
        s = build_spec(eng.db, "goblinstein", LVL)
        self.assertAlmostEqual(23.0, s.ability_crown_dmg, delta=0.5, msg="vardefine crown_11")
        self.assertAlmostEqual(8 * 23.0, hp0 - tw.hp, delta=2.0,
                               msg="the crown value, not the 107 it deals to troops")

    def test_the_ANTENNA_anchors_the_link_once_the_monster_is_dead(self):
        """"If the Monster has already been defeated, it will drop an antenna on the ground which
        is what the Goblinstein's electric link will target when the ability is activated." The
        antenna has no hitpoints, no lifetime and no way to remove it anywhere on the page, so it
        is held as a position and nothing more."""
        eng, doc, mon = self._link()
        mx, my = mon.x, mon.y
        mon.hp = 0.0
        eng.advance(0.05)
        self.assertEqual((mx, my), eng._antenna.get(0))
        mid = _place(eng, "knight", 1, 0.50 + 3.0 / _TILES_X, 0.60, hp_mult=40.0)
        h0 = mid.hp
        self.assertTrue(eng.champion_ability(0))
        self._run(eng, [doc, mid])
        self.assertLess(mid.hp, h0, "the link still reaches down the dead Monster's tether")


class AllEightChampionsTests(unittest.TestCase):
    """THE I7 COMPLETION GATE, plus the two invariants that make the stage safe to merge."""

    def test_all_EIGHT_live_champions_declare_a_kind_and_reach_a_handler(self):
        eng = _make_engine()
        for key, kind in sorted(CHAMPION_KINDS.items()):
            with self.subTest(champion=key):
                s = build_spec(eng.db, key, LVL)
                self.assertEqual(kind, s.ability_kind,
                                 "%s must declare its shape in the KB, not imply it" % key)
                self.assertIn(kind, ABILITY_KINDS, "%s names a kind with no handler" % kind)
                self.assertGreater(s.ability_cost, 0.0, "%s: every ability costs elixir" % key)
                self.assertGreater(s.ability_uses, 0, "%s: and has at least one use" % key)

    def test_all_EIGHT_fire_in_ENEMY_hands_through_the_bot(self):
        """The stage gate. Every champion has to work for the OPPONENT -- that is the whole point
        of I7 (decisions.md ruling 1: enemy-side only) -- and the route is `_try_ability`, not a
        direct engine call."""
        from clashrl.config import Config
        from clashrl.sim.opponents import ScriptedBot
        import random
        for key in sorted(CHAMPION_KINDS):
            with self.subTest(champion=key):
                eng = _quiet(_make_engine())
                deck = [key, "knight", "archers", "fireball", "musketeer", "minions",
                        "zap", "hog_rider"]
                bot = ScriptedBot(Config.load(), eng.db, random.Random(3), deck, "control")
                bot.reaction_s = 0.0
                eng.elixir[1] = 10.0
                # A board that satisfies every family at once: the champion is low, deep in our
                # half, beside a crown tower, and surrounded.
                tw = eng.towers[0][0]
                u = _place(eng, key, 1, tw.x, tw.y - 3.0 / _TILES_Y, hp_mult=0.25)
                for i in range(4):
                    _place(eng, "skeletons", 0, tw.x + 0.004 * i, tw.y - 3.0 / _TILES_Y)
                self.assertTrue(bot._try_ability(eng), "%s never fired in enemy hands" % key)
                self.assertEqual(0, eng._ability_uses_left(u)
                                 if u.spec.ability_uses == 1 else 0,
                                 "%s: the use has to be spent" % key)

    def test_the_policy_head_shapes_are_UNCHANGED(self):
        """decisions.md ruling 1: champions are ENEMY-SIDE ONLY, so no I7 work may widen the
        action space. icebow's deck holds no champion (10 identities); hogeq's holds the Mighty
        Miner, whose ability slot predates this stage (10 cards + 1 ability = 11). A checkpoint
        refuses to load against a different width, so this is the assertion that keeps every
        existing one loadable."""
        from clashrl.cards import CardDB
        from clashrl.config import Config
        db = CardDB(Config.load())
        ids = db.policy_identities()
        self.assertIn(len(ids), (10, 11), "head width moved: %d identities %s" % (len(ids), ids))
        champs = [k for k in db.deck_identities()
                  if (db.get(k) or {}).get("rarity") == "champion"]
        self.assertEqual(len(ids), len(db.deck_identities()) + (1 if champs else 0),
                         "the action space grows if and ONLY if the deck holds a champion")
        for key in CHAMPION_KINDS:
            if key not in db.deck_identities():
                self.assertNotIn(key + "_ability", ids,
                                 "%s is enemy-side: it must not reach the action space" % key)


if __name__ == "__main__":
    unittest.main()
