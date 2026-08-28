"""RULING 31d -- the Hero Valkyrie's 5.5 is a TARGET-DETECTION BUBBLE, on ONE clock from activation.

WHAT THE SOURCES ACTUALLY SAY, in the order they were weighed.

  * `Valkyrie/Hero` revid 437412 (archived: `research/sim_parity/webcache/Valkyrie_Hero.live.wikitext`)
    publishes the number and nothing else about it. Its Wild Whirlwind attribute table reads
        Cost 3 | Hit Speed 0.25 sec | Crown Tower Damage -50% | Speed Medium (60) |
        Duration 3.5 sec | Radius 2.5 | Damage reduction 15% | Dash Distance 5.5
    the last column carrying `{{Icon|I=Dash Range}}`. NO prose on any Fandom page describes it --
    the Heroes master page (revid 437509) says only "Spins rapidly, dealing damage and increasing
    her movement speed while taking less damage".
  * An owner-supplied SECONDARY source (a web result, not Fandom and not an in-game observation)
    is the only account that explains the stat: "Target Detection: If an enemy troop or building is
    anywhere within a 5.5 tile radius, she will instantly lock onto them and enter her Ultra-Fast
    'Whirlwind Stage'. If no targets are within 5.5 tiles, she will run forward normally until an
    enemy enters that 5.5 tile bubble."
  * OWNER RULING on the clock, verbatim: "if she walks for 2 seconds before something enters the
    bubble, she only enters whirlwind state for 1.5 seconds. the timer counts down the moment the
    ability activates."

WHY THE SECONDARY SOURCE WINS DESPITE ITS PROVENANCE -- and this is the load-bearing measurement:
5.5 IS NOT A NEW NUMBER. `valkyrie`, `valkyrie_evo` and `valkyrie_hero` ALL already carry
sight 5.5, imported from the wiki into `card_mechanics.json` long before this ruling. A "5.5 tile
detection bubble" is therefore exactly the aggro radius the engine has always given her, which is
the kind of agreement a fabricated description does not produce. Three rival readings were
considered and are retired in conflicts.md: a 5.5-tile cumulative TRAVEL cap, a Bandit-style
dash-then-spin pre-phase, and a leap.

WHAT ACTUALLY CHANGED IN THE ENGINE: one thing. The whirlwind used to begin on the button and turn
in empty air; it now begins when something is in the bubble to spin at. Everything else the reading
needs -- the 5.5 acquisition, the lock-on, the pursuit -- the engine already did.

DELIBERATELY NOT IMPLEMENTED, with the reason:
  * THE SPEED BOOST. The prose claims one and the secondary source calls the stage "Ultra-Fast",
    but the ability table prints Speed Medium (60), IDENTICAL to her body, and "Ultra-Fast" is not
    one of the game's tiers (Slow 45 / Medium 60 / Fast 90 / Very Fast 120). No source publishes a
    number, so any multiplier would be invented. `test_no_speed_boost_is_invented` pins that.
  * THE 15% DAMAGE REDUCTION -- because it has NEVER BEEN WIRED, and that is a bug this ruling
    found rather than caused. Her KB row writes `ability_dmg_reduction` (the CardSpec FIELD name);
    `build_spec` reads `ability_damage_reduction` (the key the Monk's row uses, which is why his
    65% works). Hers silently resolves to 0.0. Pinned below, NOT fixed: an 8k PPO run is live and
    she is a hero candidate in 143 opponent meta decks, so the one-word fix is a behaviour change
    to sequence after it. See the HANDOFF bug ledger and conflicts.md "I8 / ruling 31d".

SHARED, byte-identical in both decks: every assertion is about the ENGINE and the KB, not a deck.
"""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clashrl.cards import CardDB                                            # noqa: E402
from clashrl.sim.engine import (SimEngine, Unit, build_spec, replace,       # noqa: E402
                                _seeking, _gap, _TILES_Y)
from clashrl.sim.opponents import ScriptedBot                               # noqa: E402
from test_sim_status_effects import DummyCfg                                # noqa: E402

LVL = 11
BUBBLE = 5.5                    # the ability table's "Dash Distance"
DB = CardDB(path=ROOT / "config" / "cards.yaml")

# A spot deep in team 1's half whose nearest ENEMY crown tower is ~15 tiles away, so the bubble is
# genuinely empty when no dummy is placed. Towers count as buildings (see `_seeking`), so a test
# that means "nothing in range" has to stand clear of them.
FAR_Y = 0.5 - 6.0 / _TILES_Y


def _engine() -> SimEngine:
    """Crown towers DISARMED but alive -- the I8 house idiom. Killing them ends the match and
    freezes every timer under test at `advance`'s `self.done` guard."""
    eng = SimEngine(DummyCfg(), DB, random.Random(0))
    for side in (eng.towers[0], eng.towers[1]):
        for tw in side:
            tw.hit_dmg = 0.0
            tw.max_hp = tw.hp = 1e9
    return eng


def _valk(eng, x, y):
    """Her body, planted (`speed=0`) and with its normal swing muted, so the only thing that can
    move the ledger is the whirlwind. Planting her is what makes "nothing enters the bubble" hold
    still: a walking Valkyrie finds a crown tower on her own and arms the stance."""
    s = build_spec(DB, "valkyrie_hero", LVL)
    s = replace(s, hit_dmg=0.0, tower_hit_dmg=0.0, splash=False, dmg_stages=(), speed=0.0)
    u = Unit(s, 1, x, y, s.hp)
    u.deploy_left = 0.0
    eng.units.append(u)
    eng.elixir[1] = 10.0
    return u


def _body(eng, x, y, base="knight", team=0):
    s = replace(build_spec(DB, base, LVL), hit_dmg=0.0, tower_hit_dmg=0.0, hp=1e7,
                dmg_stages=(), speed=0.0)
    u = Unit(s, team, x, y, 1e7)
    u.deploy_left = 0.0
    eng.units.append(u)
    return u


def _run(eng, seconds, dt=0.1):
    for _ in range(int(round(seconds / dt))):
        eng.advance(dt)


class SeekKBTests(unittest.TestCase):
    def test_the_kb_carries_the_published_5_5(self):
        s = build_spec(DB, "valkyrie_hero", LVL)
        self.assertAlmostEqual(s.ability_seek_tiles, BUBBLE, places=6)
        # geometry never scales with level
        self.assertAlmostEqual(build_spec(DB, "valkyrie_hero", 15).ability_seek_tiles, BUBBLE, 6)

    def test_the_bubble_is_the_sight_radius_she_already_had(self):
        """THE CORROBORATION THAT DECIDED THE RULING. The secondary source's 5.5 lands exactly on a
        number the KB has held since the card was imported -- so the reading costs no new
        constant."""
        for key in ("valkyrie", "valkyrie_evo", "valkyrie_hero"):
            with self.subTest(card=key):
                self.assertAlmostEqual(build_spec(DB, key, LVL).sight, BUBBLE, places=6)

    def test_she_is_the_only_card_with_a_detection_bubble(self):
        """The field is generic but she is its only owner today. A second card appearing here
        silently would change that card's ability, so it has to be deliberate."""
        owners = [k for k in DB.cards
                  if getattr(build_spec(DB, k, LVL), "ability_seek_tiles", 0.0) > 0.0]
        self.assertEqual(owners, ["valkyrie_hero"])

    def test_no_speed_boost_is_invented(self):
        """The blurb says "increasing her movement speed" and the secondary source says
        "Ultra-Fast". The ability table prints Speed Medium (60) -- her body's own speed -- and
        "Ultra-Fast" is not one of the game's tiers, so no number exists to curate."""
        s = build_spec(DB, "valkyrie_hero", LVL)
        self.assertAlmostEqual(s.ability_move_speed, 0.0, places=9)
        self.assertAlmostEqual(s.speed, 1.0, places=6)              # Medium (60)


class SeekBranchTests(unittest.TestCase):
    """The substance: with something in the bubble she spins, without it she does not."""

    def test_an_enemy_inside_the_bubble_arms_the_spin_at_once(self):
        """MEASURED: a troop 3.5 tiles away -- inside the 5.5 bubble, OUTSIDE the 2.5 damage
        radius -- gets the stance turning on the first tick after the 1 s activation delay, all
        14 turns."""
        eng = _engine()
        v = _valk(eng, 0.5, 0.6)
        d = _body(eng, 0.5, 0.6 - 4.0 / _TILES_Y)
        self.assertGreater(_gap(v.x, v.y, d), v.spec.ability_radius_tiles,
                           "the target must start OUTSIDE the damage radius, or this only proves "
                           "that something in reach gets hit")
        self.assertLess(_gap(v.x, v.y, d), BUBBLE)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 6.0)
        self.assertEqual(v.ability_hits, 14, "3.5 s at 0.25 s is 14 turns")

    def test_an_empty_bubble_means_she_walks_and_does_NOT_spin(self):
        """The half of the reading that changes engine behaviour. MEASURED: nearest enemy troop
        8.5 tiles, nearest enemy crown tower 14.95 -- zero turns, zero damage, and the 3.5 s
        window expires anyway."""
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        d = _body(eng, 0.5, FAR_Y - 12.0 / _TILES_Y)
        self.assertGreater(_gap(v.x, v.y, d), BUBBLE)
        self.assertGreater(min(_gap(v.x, v.y, tw) for tw in eng._enemy_towers(1)), BUBBLE)
        hp0 = d.hp
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 6.0)
        self.assertEqual(v.ability_hits, 0, "nothing to lock onto -> no Whirlwind Stage")
        self.assertAlmostEqual(hp0 - d.hp, 0.0, places=3)
        self.assertAlmostEqual(v.ability_active_s, 0.0, places=6, msg="...and the window still ran")

    def test_the_spin_begins_the_moment_an_enemy_CROSSES_INTO_the_bubble(self):
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        d = _body(eng, 0.5, FAR_Y - 12.0 / _TILES_Y)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 2.0)
        self.assertEqual(v.ability_hits, 0)
        d.y = FAR_Y - 3.0 / _TILES_Y                       # placed INTO the bubble
        _run(eng, 0.3)
        self.assertGreater(v.ability_hits, 0, "entering the bubble has to arm the stance")

    def test_a_BUILDING_arms_it_too_not_only_a_troop(self):
        """"an enemy troop OR BUILDING" is the source's own wording."""
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        b = _body(eng, 0.5, FAR_Y - 3.4 / _TILES_Y, base="cannon")
        self.assertEqual(b.spec.kind, "building")
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 6.0)
        self.assertEqual(v.ability_hits, 14)

    def test_an_AIR_body_does_not_arm_it(self):
        """She cannot lock onto or damage what she cannot reach -- her Target is Ground, and the
        spin already skips flyers. Arming on one would burn the window against a target the
        stance can never hit."""
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        a = _body(eng, 0.5, FAR_Y - 2.5 / _TILES_Y, base="minions")
        self.assertTrue(a.spec.flying)
        self.assertLess(_gap(v.x, v.y, a), BUBBLE)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 6.0)
        self.assertEqual(v.ability_hits, 0)

    def test_an_enemy_CROWN_TOWER_arms_it(self):
        eng = _engine()
        tw = eng.towers[0][0]
        v = _valk(eng, tw.x, tw.y - 4.0 / _TILES_Y)
        self.assertLess(min(_gap(v.x, v.y, t) for t in eng._enemy_towers(1)), BUBBLE)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 6.0)
        self.assertGreater(v.ability_hits, 0, "a crown tower is a building by every reading")


class SeekClockTests(unittest.TestCase):
    """OWNER RULING: one clock, started at activation, and the walk phase burns it."""

    def test_two_seconds_of_walking_leaves_exactly_one_and_a_half_of_whirlwind(self):
        """The owner's own worked example. MEASURED: 6 turns, not 14 -- 1.5 s / 0.25 s. Modelling
        the clock as starting at whirlwind entry would give 14 and make a bad activation free."""
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        d = _body(eng, 0.5, FAR_Y - 12.0 / _TILES_Y)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.1)                                     # `ability_delay_s` 1.0, resolved on the
                                                           # NEXT tick; the window opens showing 3.4
                                                           # because the tick that opens it also
                                                           # spends one dt of it
        self.assertAlmostEqual(v.ability_active_s, 3.4, places=6, msg="the window opens here")
        _run(eng, 2.0)                                     # ...and 2 s of it burns while she walks
        self.assertEqual(v.ability_hits, 0, "she is walking, not spinning")
        self.assertAlmostEqual(v.ability_active_s, 1.4, places=6)
        d.y = FAR_Y - 3.0 / _TILES_Y                       # NOW something enters the bubble
        _run(eng, 3.0)
        self.assertEqual(v.ability_hits, 6,
                         "~1.5 s of window at 0.25 s is SIX turns, not the fourteen a clock "
                         "started at whirlwind entry would give")

    def test_an_enemy_that_arrives_after_the_window_gets_nothing(self):
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        d = _body(eng, 0.5, FAR_Y - 12.0 / _TILES_Y)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 4.6)                                     # 1.0 delay + 3.5 window, expired
        self.assertAlmostEqual(v.ability_active_s, 0.0, places=6)
        hp0 = d.hp
        d.y = FAR_Y - 2.0 / _TILES_Y
        _run(eng, 3.0)
        self.assertEqual(v.ability_hits, 0)
        self.assertAlmostEqual(hp0 - d.hp, 0.0, places=3)

    def test_the_stage_LATCHES_once_it_has_turned(self):
        """"enter her Whirlwind Stage" is a state she ENTERS, not a condition re-tested every tick.
        MEASURED: the target dies after 2 turns and she still spends all 14 -- she does not revert
        to walking and go looking again. Consistent with the one-clock ruling, under which
        re-seeking could only ever hand back time the clock has already spent."""
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        d = _body(eng, 0.5, FAR_Y - 2.0 / _TILES_Y)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.3)
        self.assertGreater(v.ability_hits, 0)
        d.hp = 0.0                                         # the bubble is now empty again
        _run(eng, 4.0)
        self.assertEqual(v.ability_hits, 14)

    def test_seeking_is_false_once_the_stage_has_turned(self):
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.1)
        self.assertTrue(_seeking(eng, v), "empty bubble, nothing spun yet")
        v.ability_hits = 1
        self.assertFalse(_seeking(eng, v), "the latch is `ability_hits`")


class SeekOpponentAITests(unittest.TestCase):
    """The bot must not throw the ability away on an empty board -- under the one-clock ruling that
    wastes all 3.5 s. It cannot, and the reason is arithmetic rather than a sampled winrate."""

    def test_the_bots_own_trigger_is_strictly_inside_the_bubble(self):
        """`ability_ai` is family `defensive` with crowd_n 2 / crowd_tiles 2.5, so `_ability_wants`
        needs TWO enemy bodies within 2.5 tiles -- well inside 5.5. No new precondition is needed
        for this kind, and adding one would be dead code."""
        s = build_spec(DB, "valkyrie_hero", LVL)
        ai = dict(s.ability_ai)
        self.assertEqual(ai.get("family"), "defensive")
        self.assertLessEqual(float(ai["crowd_tiles"]), s.ability_seek_tiles)
        self.assertGreaterEqual(int(ai["crowd_n"]), 1)

    def test_wanting_the_button_implies_a_non_empty_bubble(self):
        """The property stated directly, on a board the bot would actually fire on."""
        eng = _engine()
        v = _valk(eng, 0.5, FAR_Y)
        bot = ScriptedBot.__new__(ScriptedBot)
        ai = dict(v.spec.ability_ai)
        knobs = {"crowd_n": int(ai["crowd_n"]), "crowd_tiles": float(ai["crowd_tiles"])}
        self.assertFalse(bot._ability_wants(eng, v, "defensive", knobs),
                         "empty board -> the bot must not want it")
        for i in range(int(ai["crowd_n"])):
            _body(eng, 0.5 + (i - 0.5) * 0.4 / 18.0, FAR_Y - 1.5 / _TILES_Y)
        self.assertTrue(bot._ability_wants(eng, v, "defensive", knobs))
        self.assertFalse(_seeking(eng, v),
                         "...and whenever it wants it, the bubble is already occupied")


class SeekKnownBugTests(unittest.TestCase):
    def test_the_published_15pct_damage_reduction_is_NOT_wired_KB_KEY_TYPO(self):
        """PINS A LIVE BUG so fixing it is a deliberate, sequenced flip and not a surprise.

        Her KB row writes `ability_dmg_reduction: 15.0` -- the CardSpec FIELD name. `build_spec`
        reads `ability_damage_reduction`, the key the Monk's row uses and the reason his 65% works.
        Hers resolves to 0.0, so she has taken FULL damage through Wild Whirlwind since I8.

        MEASURED: 1000 damage mid-ability costs her 1000.0 hitpoints; the published 15% would cost
        850.0. NOT FIXED HERE -- an 8k PPO run is live and she is a hero candidate in 143 opponent
        meta decks. When it is fixed, this test flips.
        """
        s = build_spec(DB, "valkyrie_hero", LVL)
        self.assertAlmostEqual(s.ability_dmg_reduction, 0.0, places=9)
        self.assertAlmostEqual(build_spec(DB, "monk", LVL).ability_dmg_reduction, 0.65, places=9,
                               msg="the CONTROL: the Monk's row spells the key the way build_spec "
                                   "reads it, which is what makes this a typo and not a design")
        eng = _engine()
        v = _valk(eng, 0.5, 0.4)
        self.assertTrue(eng.champion_ability(1))
        _run(eng, 1.5)
        self.assertGreater(v.ability_active_s, 0.0)
        hp0 = v.hp
        eng._hurt(v, 1000.0)
        self.assertAlmostEqual(hp0 - v.hp, 1000.0, places=3)


if __name__ == "__main__":
    unittest.main()
