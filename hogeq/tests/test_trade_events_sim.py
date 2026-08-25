"""Sim-side elixir-trade event ledger + threat-response timing port (2026-08-14). The sim grades
with engine ground truth (exact unit identities, exact crossing times), so these drive real
SimMatchEnv instances: deploy units, control the clock, and read the reward stream."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np                                  # noqa: E402
from clashrl.config import Config                   # noqa: E402
from clashrl.sim.env import SimMatchEnv             # noqa: E402
from clashrl.sim.engine import build_spec           # noqa: E402


def _quiet_env(seed=42):
    env = SimMatchEnv(Config.load(), seed=seed)
    env.reset()
    env.opponent.act = lambda eng: None              # deterministic board: the bot stays silent
    return env


def _total(env, name):
    t = env.rw_stats.run.get(name)
    return 0.0 if t is None else t.total


def _kill(env, unit):
    unit.hp = -1.0                                   # engine culls it on the next tick


class TradeLedgerTests(unittest.TestCase):
    def test_prompt_attributed_kill_credits(self):
        env = _quiet_env()
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.62)
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.52, 0.60)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        env.step((False, 0, 0))                      # both tracked; crossing stamped on first sight
        _kill(env, foe)
        env.step((False, 0, 0))                      # dies ~1 s after crossing: inside the grace
        self.assertGreater(_total(env, "elixir_trade"), 0.2,
                           "a 3-elixir kill next to our knight, answered promptly, must credit")

    def test_tower_kill_far_from_units_pays_nothing(self):
        env = _quiet_env(seed=43)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.80, 0.60)
        for _ in range(30):                          # no unit of ours ever fields; towers do the work
            env.step((False, 0, 0))
            if not any(u.team == 1 for u in env.eng.units):
                break
        env.step((False, 0, 0))
        self.assertEqual(_total(env, "elixir_trade"), 0.0,
                         "the towers' kill with nothing of ours nearby is not the policy's trade")

    def test_late_kill_decays_to_zero(self):
        env = _quiet_env(seed=44)
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.62)
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.52, 0.60)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        env.step((False, 0, 0))
        # rewrite the ledger so the crossing happened 15 s ago: the answer is ELEVEN+ seconds late
        env._ev_enemy = {uid: (sh, x, y, (tc - 15.0 if tc is not None else None), lh)
                         for uid, (sh, x, y, tc, lh) in env._ev_enemy.items()}
        base = _total(env, "elixir_trade")
        _kill(env, foe)
        env.step((False, 0, 0))
        self.assertAlmostEqual(_total(env, "elixir_trade") - base, 0.0, delta=1e-6,
                               msg="a kill >= trade_late_s after the crossing credits nothing")

    def test_own_troop_loss_debits(self):
        env = _quiet_env(seed=45)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "knight", 11), 0.50, 0.70)
        mine = [u for u in env.eng.units if u.team == 0][-1]
        env.step((False, 0, 0))
        _kill(env, mine)
        env.step((False, 0, 0))
        self.assertLess(_total(env, "elixir_trade"), -0.2,
                        "our dead knight = -0.3, whoever killed it")

    def test_spell_kill_credits_without_a_nearby_unit(self):
        env = _quiet_env(seed=46)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.70, 0.60)
        foe = [u for u in env.eng.units if u.team == 1][-1]
        env.step((False, 0, 0))
        env._ev_spells.append((0.70, 0.60, 2.0, env.eng.t))   # our rocket just landed here
        base = _total(env, "elixir_trade")
        _kill(env, foe)
        env.step((False, 0, 0))
        self.assertGreater(_total(env, "elixir_trade") - base, 0.2,
                           "a kill inside a recent damage-spell blast is OUR kill, no troop needed")

    def test_playing_a_damage_spell_records_a_cast(self):
        for seed in range(60):                       # find a seed whose opening hand holds a spell
            env = _quiet_env(seed=seed)
            spells = [ci for ci in env._hand_ids() if ci in env.damage_spell_ids]
            if spells:
                break
        self.assertTrue(spells, "no seed in 60 gave an opening damage spell (deck has 2)")
        env.eng.elixir[0] = 10.0
        for cell in (117, 153, 225, 315):            # first legal placement wins
            env.step((True, spells[0], cell))
            if env._ev_spells:
                break
        self.assertTrue(env._ev_spells, "a fielded damage spell must be recorded for attribution")


class RangedDefenderAttributionTests(unittest.TestCase):
    def test_lone_defensive_bow_kill_credits_at_range(self):
        """A defensive X-Bow kills from ~6 tiles -- far outside the 4-tile proximity radius.
        Before combat attribution this earned ZERO trade credit; the doctrine's defensive-bow
        value was invisible to the ledger."""
        env = SimMatchEnv(Config.load(), seed=31)
        env.reset()
        env.opponent.act = lambda eng: None
        for side in (0, 1):
            for tw in env.eng.towers[side]:
                tw.stun_left = 999.0
        env.eng.elixir[0] = env.eng.elixir[1] = 10.0
        assert env.eng.deploy(0, build_spec(env.eng.db, "x_bow", 11), 0.50, 0.73)
        assert env.eng.deploy(1, build_spec(env.eng.db, "dart_goblin", 11), 0.50, 0.55)
        for _ in range(12):
            env.step((False, 0, 0))
            if not any(u.team == 1 for u in env.eng.units):
                break
        env.step((False, 0, 0))
        t = env.rw_stats.run.get("elixir_trade")
        self.assertGreater(t.total if t else 0.0, 0.05,
                           "the bow FOUGHT it (combat stamp), so the kill credits at any range")


class ThreatPositionTests(unittest.TestCase):
    """`_threat_pos` must name the MOST DANGEROUS body, not the deepest one.

    THE BUG (fixed 2026-08-25): `_threat_response` grades the CARD against `_threat_id_true`, which
    ranks by `ignore_cost_frac`, and the PLACEMENT against `_threat_pos`, which ranked by DEPTH. A
    counter placed in front of a Pekka earned NOTHING while the same counter dropped in a lone
    Skeletons' lane earned full credit -- the reward PAID to defend the wrong lane, so training
    reinforced it and no amount of further training could unlearn it.
    """

    def _board(self, danger_x, danger_y, trickle_x, trickle_y, seed=7):
        env = _quiet_env(seed=seed)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "pekka", 11), danger_x, danger_y)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "skeletons", 11), trickle_x, trickle_y)
        env.step((False, 0, 0))
        return env

    def test_lane_follows_the_dangerous_body_not_the_deepest(self):
        """The owner's reported board: a tank shallow, a trickle DEEPER in the other lane."""
        env = self._board(0.25, 0.55, 0.75, 0.70)
        tx, _ = env._threat_pos()
        self.assertLess(abs(tx - 0.25), env.intercept_lane,
                        "the intercept lane must point at the PEKKA, not the deeper skeletons")
        self.assertGreater(abs(tx - 0.75), env.intercept_lane,
                           "the trickle's lane must NOT earn intercept credit")

    def test_identity_and_position_describe_the_SAME_body(self):
        """The property that was missing. The 2026-08-20 fix corrected the identity half only, and
        nothing asserted the two halves agreed -- which is why the symptom survived it."""
        env = self._board(0.25, 0.55, 0.75, 0.70)
        tid = env._threat_id_true
        tx, _ = env._threat_pos()
        self.assertGreaterEqual(tid[1], 0.5, "identity must recognise the tank")
        self.assertLess(abs(tx - 0.25), env.intercept_lane,
                        "identity says TANK, so the position must be the tank's")

    def test_depth_still_breaks_a_tie_between_equal_threats(self):
        """Depth was not wrong, it was only the wrong PRIMARY key. Among equally dangerous bodies
        the deepest is the most urgent, and that must survive the fix."""
        env = _quiet_env(seed=9)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.30, 0.55)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.70, 0.68)
        env.step((False, 0, 0))
        tx, ty = env._threat_pos()
        self.assertLess(abs(tx - 0.70), env.intercept_lane,
                        "equal danger -> the DEEPER knight is the one to intercept")

    def test_a_lone_trickle_is_still_named_when_it_is_all_there_is(self):
        """Negative control: the danger ranking must not make a board with only cheap bodies read
        as 'no threat'. Triage decides whether it is worth answering (bodies_ignore_frac); this
        function's job is only to say WHERE."""
        env = _quiet_env(seed=11)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "skeletons", 11), 0.72, 0.66)
        env.step((False, 0, 0))
        tx, ty = env._threat_pos()
        self.assertNotEqual((round(tx, 3), round(ty, 3)), (0.5, 0.5),
                            "a real body on our half must not report the centre-of-board default")
        self.assertLess(abs(tx - 0.72), 0.12, "it must name the trickle that IS there")


class SecondaryLaneTests(unittest.TestCase):
    """FIX 6: prioritising the greater threat must not mean IGNORING the lesser one.

    Owner's board: Golem + support one side, Mini Pekka the other. The golem is the bigger threat
    and fix 5 correctly points the primary lane at it -- but the mini pekka still needs a cheap
    answer. MEASURED before fix 6: the correct Skeletons scored `threat_response` +0.000 while
    saving ~2266 tower HP, so the only incentive was the delayed outcome term.
    """

    def _two_lane(self, second="mini_pekka", seed=21):
        env = _quiet_env(seed=seed)
        for name, x, y in (("golem", 0.25, 0.56), ("mega_minion", 0.27, 0.54), (second, 0.75, 0.58)):
            env.eng.elixir[1] = 10.0
            assert env.eng.deploy(1, build_spec(env.eng.db, name, 11), x, y)
        env.step((False, 0, 0))
        return env, {c: i for i, c in enumerate(env.deck_keys)}

    def test_cheap_answer_in_the_other_lane_is_paid(self):
        env, ix = self._two_lane()
        env._threat_credits = 0
        self.assertGreater(env._secondary_lane_response(ix["skeletons"], 0.75, 0.62), 0.5,
                           "a correct answer to the mini pekka must be worth something")

    def test_primary_lane_is_left_to_threat_response(self):
        """No double-paying: the primary lane is _threat_response's job, not this term's."""
        env, ix = self._two_lane()
        env._threat_credits = 0
        self.assertEqual(env._secondary_lane_response(ix["skeletons"], 0.25, 0.62), 0.0)

    def test_a_lane_with_nothing_in_it_pays_nothing(self):
        env, ix = self._two_lane()
        env._threat_credits = 0
        self.assertEqual(env._secondary_lane_response(ix["skeletons"], 0.50, 0.62), 0.0)

    def test_triage_refuses_a_second_lane_not_worth_a_card(self):
        """The doctrine's tier above every counter rule. A trickle in the other lane is not a
        second threat, and paying for answering it would teach exactly the over-answering that
        `min(threat_credit_budget, n_cards)` was added to stop."""
        env = _quiet_env(seed=31)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "pekka", 11), 0.25, 0.56)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "skeletons", 11), 0.75, 0.60)
        env.step((False, 0, 0))
        ix = {c: i for i, c in enumerate(env.deck_keys)}
        env._threat_credits = 0
        self.assertEqual(env._secondary_lane_response(ix["skeletons"], 0.75, 0.62), 0.0)

    def test_credit_scales_with_the_lane_s_own_danger(self):
        """A near-equal threat pays near-full; the price IS the doctrine, not a flat bonus."""
        big, ixb = self._two_lane("mini_pekka")
        big._threat_credits = 0
        v_big = big._secondary_lane_response(ixb["skeletons"], 0.75, 0.62)
        small, ixs = self._two_lane("spear_goblins", seed=23)
        small._threat_credits = 0
        v_small = small._secondary_lane_response(ixs["skeletons"], 0.75, 0.62)
        self.assertGreater(v_big, v_small,
                           "a mini pekka must be worth more to answer than spear goblins")

    def test_an_offensive_placement_earns_nothing(self):
        """This is a DEFENSIVE term. A play on the enemy half is graded by wincon_exec."""
        env, ix = self._two_lane()
        env._threat_credits = 0
        self.assertEqual(env._secondary_lane_response(ix["skeletons"], 0.75, 0.30), 0.0)


class MissPenaltyScaleTests(unittest.TestCase):
    """FIX 7: the missed-defence penalty is priced by what the ignored group COSTS.

    It used to be a step function -- free below IGNORE_FRAC, a flat -1.0 above -- so ignoring two
    trickles (0.107 of a tower) charged exactly what ignoring a golem push (2.074) charged, a 19x
    difference in real threat priced identically.
    """

    def _miss(self, bases, seed=41):
        env = _quiet_env(seed=seed)
        for i, b in enumerate(bases):
            env.eng.elixir[1] = 10.0
            assert env.eng.deploy(1, build_spec(env.eng.db, b, 11), 0.30 + 0.03 * i, 0.58)
        env.step((False, 0, 0))
        env._threat_miss_last = -1e9          # arm the rate limiter
        env.eng.elixir[0] = 10.0              # a counter must be affordable or the term waives
        return env._threat_miss_idle()

    def test_a_bigger_threat_costs_more_to_ignore(self):
        knight = self._miss(["knight"])
        mini = self._miss(["mini_pekka"])
        self.assertLess(knight, 0.0, "an answerable knight must still charge")
        self.assertLess(mini, knight, "a mini pekka must cost MORE to ignore than a knight")

    def test_two_trickles_no_longer_cost_what_a_golem_push_costs(self):
        """The owner's case, and the reason for the fix."""
        trickles = self._miss(["spear_goblins", "skeletons"])
        push = self._miss(["golem", "mega_minion"])
        self.assertLess(trickles, 0.0, "two trickles together ARE a real threat -- still charge")
        self.assertGreater(trickles, push / 2.0,
                           "...but nothing like a golem push: it must cost far less")

    def test_the_penalty_is_capped_at_the_full_weight(self):
        """This term is a PROXY for delayed tower damage, not a replacement for it. A two-tower
        push must not out-shout the outcome terms it stands in for."""
        huge = self._miss(["golem", "mega_minion", "mini_pekka", "mini_pekka"])
        self.assertGreaterEqual(huge, -1.0 - 1e-9, "must not exceed w_threat_miss")

    def test_a_lone_trickle_is_still_waived_entirely(self):
        """The IGNORE_FRAC early return is KEPT on purpose: the term is rate-limited, and a 0.004
        fire would arm the limiter and mask a real push arriving a second later."""
        self.assertEqual(self._miss(["skeletons"]), 0.0)


class ThreatTimingTests(unittest.TestCase):
    def _lit_env(self, seed=50):
        env = _quiet_env(seed=seed)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.30, 0.58)
        env.step((False, 0, 0))                      # _observe refreshes the true threat vector
        assert env._threat_id_true[0] >= 0.5, "an enemy knight on our half must light the threat"
        return env

    def _troop_counter(self, env):
        ci = next(i for i, k in enumerate(env.deck_keys) if "knight" in k)
        tid = env._threat_id_true
        tx, _ = env._threat_pos()
        return ci, tid, tx

    def test_depth_window_gates_positives(self):
        env = self._lit_env()
        ci, tid, tx = self._troop_counter(env)
        tid[7] = 0.40
        mid = env._threat_response(ci, tx, 0.60)
        self.assertGreater(mid, 0.0, "counter + intercept + mid depth must pay")
        env._threat_credits = 0
        tid[7] = 0.05
        self.assertEqual(env._threat_response(ci, tx, 0.60), 0.0,
                         "below min depth = premature: the push is still building")
        tid[7] = 0.90
        self.assertEqual(env._threat_response(ci, tx, 0.60), 0.0,
                         "above max depth = too late: the threat is already on our tower")

    def test_budget_caps_and_hysteresis_refills(self):
        env = self._lit_env(seed=51)
        ci, tid, tx = self._troop_counter(env)
        tid[7] = 0.40
        self.assertGreater(env._threat_response(ci, tx, 0.60), 0.0)
        self.assertGreater(env._threat_response(ci, tx, 0.60), 0.0)
        self.assertEqual(env._threat_response(ci, tx, 0.60), 0.0,
                         "third credit for the same push: the budget is spent")
        for u in list(env.eng.units):                # the push dies; the board goes quiet
            if u.team == 1:
                _kill(env, u)
        # TIME-BASED, not step-based: the refill needs >= 3 s of engine time, and `range(5)` only
        # delivered that while a decision was 1.0 s. Lowering the period to 0.6 s put this exactly
        # on the boundary (5 x 0.6 = 3.0) -- the same latent assumption _tick carried.
        _dt = float(getattr(env, "agent_dt", 1.0)) or 1.0
        for _ in range(int(round(5.0 / _dt))):       # >= 3 s of sustained engine-time quiet
            env.step((False, 0, 0))
        self.assertEqual(env._threat_credits, 0, "sustained quiet must refill the budget")
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.30, 0.58)
        env.step((False, 0, 0))
        env._threat_id_true[7] = 0.40
        _, _, tx = self._troop_counter(env)
        self.assertGreater(env._threat_response(ci, tx, 0.60), 0.0,
                           "a fresh push after the reset earns fresh credit")

    def test_building_defensive_geometry(self):
        env = self._lit_env(seed=52)
        bi = next(i for i, k in enumerate(env.deck_keys) if "tesla" in k)
        env._threat_id_true[7] = 0.40
        self.assertGreater(env._threat_response(bi, 0.50, 0.65), 0.0,
                           "central tesla in the defensive band pays")
        env._threat_credits = 0
        self.assertEqual(env._threat_response(bi, 0.50, 0.30), 0.0,
                         "a building on the OFFENSIVE half is not a defense")
        self.assertEqual(env._threat_response(bi, 0.50, 0.92), 0.0,
                         "a building jammed at the king is past the pull geometry")


if __name__ == "__main__":
    unittest.main(verbosity=1)
