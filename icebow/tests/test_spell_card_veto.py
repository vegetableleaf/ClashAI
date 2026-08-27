"""THE SPELL CARD VETO, IN ITS VALUE FORM (decisions.md ruling 30; spell_experiments.md §7.5/§8).

`spell_experiments.md` measured that this policy's spells are net-negative at the volume it casts
them, and that the lever is a state-conditioned CARD-level refusal: at a >=3-body clump test the
criterion is +0.233 tower fractions (3.58 sigma) over the baseline and +0.207 (2.98 sigma) over a
VOLUME-MATCHED random spell ban.

THE BODY-COUNT FORM WAS REJECTED BY THE OWNER, and the reason is a fact about the deck rather than
a preference: its highest-value casts are routinely SINGLE-body. The four drills below each have a
one-body reference line, and a K=3 count veto refuses every one of them:

    nado_king_activation      one Hog Rider     reference ("tornado", 0.472, 0.771, 3.6)
    nado_the_sneaky_lock      one Knight        reference ("tornado", 0.26,  0.40,  1.2)
    rocket_the_two_for_one    one Witch         reference ("rocket",  0.194, 0.229, 0.6)
    rocket_the_pump_on_sight  one pump          reference ("rocket",  0.30,  0.16,  1.2)

So the threshold is on VALUE in TOWER FRACTIONS -- `threat_value.catch_value_frac`, the project's
own triage model -- plus an exemption set for casts whose payoff is not the bodies at all.

This file is byte-identical in both decks: every case derives its cards from the DECK'S OWN specs
(`pulls` / `knockback` / `spell_tower_dmg` / `hits_hidden`) and skips when this deck has no spell
of that class. icebow has tornado+rocket+log; hogeq has earthquake+log and no pull spell at all.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config                       # noqa: E402
from clashrl import threat_value as TV                  # noqa: E402
from clashrl.sim.env import SimMatchEnv                 # noqa: E402
from clashrl.sim.engine import build_spec               # noqa: E402


def _env(seed=7):
    cfg = Config.load()
    e = SimMatchEnv(cfg, seed=seed)
    e.domain_rand.enabled = False
    e.domain_rand.resample()
    e.opponent_provider = None
    e.rng.seed(1)
    e.reset()
    return e


def _clear(e):
    """An empty board with the caches invalidated, so each case starts from a known state."""
    e.eng.units[:] = []
    e.eng.spells[:] = []
    return e


def _spell(e, anywhere=None, **want):
    """The first spell in THIS deck matching the wanted spec flags, or None.

    `anywhere=True` restricts to a spell that may be cast in THEIR half -- the tower cases need
    one, and hogeq's Log is `own_half_only` while its Earthquake is not.
    """
    for i, s in enumerate(e.specs):
        if getattr(s, "kind", "") != "spell":
            continue
        if anywhere is not None and (i in e.anywhere_ids) != bool(anywhere):
            continue
        if all(bool(getattr(s, k, False)) == v if isinstance(v, bool)
               else float(getattr(s, k, 0.0) or 0.0) > 0.0
               for k, v in want.items()):
            return i
    return None


def _put(e, base, x, y, team=1, level=11):
    sp = build_spec(e.db, base, level)
    e.eng.elixir[team] = 10.0                       # `deploy` refuses what the team cannot afford
    assert e.eng.deploy(team, sp, x, y, delay_s=0.0), base
    return e.eng.units[-1]


class CatchValueFracTests(unittest.TestCase):
    """`bodies_ignore_frac` alone could not price a caught set, and the numbers say why."""

    def setUp(self):
        self.db = _env().db

    def test_the_inf_holes_bodies_ignore_frac_leaves(self):
        # MEASURED 2026-08-27 on the sim's own ladder pool. `group_ignore_frac` turns a single
        # unmodellable body into `inf` for the WHOLE group, and a veto reading inf as "enormously
        # valuable" would wave through every cast on a board holding one Ice Spirit.
        for base, want in (("wall_breakers", 0.1415), ("fire_spirit", 0.0468),
                           ("ice_spirit", 0.0249)):
            self.assertEqual(TV.bodies_ignore_frac(self.db, [base]), float("inf"), base)
            self.assertAlmostEqual(TV.catch_value_frac(self.db, [base]), want, places=3)

    def test_genuinely_unresolvable_still_reads_inf(self):
        # A Mortar outranges the crown tower: the tower cannot answer it at all, so no threshold
        # should ever refuse the spell that can.
        self.assertEqual(TV.catch_value_frac(self.db, ["mortar"]), float("inf"))

    def test_one_expensive_body_outvalues_three_cheap_ones(self):
        """THE OWNER'S POINT, as a number. This is what a COUNT cannot express."""
        three_skeletons = TV.catch_value_frac(self.db, ["skeletons"] * 3)
        for heavy in ("mini_pekka", "hog_rider", "knight", "witch"):
            self.assertGreater(TV.catch_value_frac(self.db, [heavy]), three_skeletons, heavy)
        # ...and the gap is two orders of magnitude, not a rounding difference.
        self.assertLess(three_skeletons, 0.01)
        self.assertGreater(TV.catch_value_frac(self.db, ["mini_pekka"]), 0.5)

    def test_bodies_collapse_to_cards_not_multiplied(self):
        # Three skeleton BODIES are one Skeletons CARD, not three (cards_from_bodies).
        self.assertAlmostEqual(TV.catch_value_frac(self.db, ["skeletons"] * 3),
                               TV.catch_value_frac(self.db, ["skeletons"]), places=6)


class ShippedDefaultIsInertTests(unittest.TestCase):
    """⚠ THE DEFAULT IS 0.0 AND THAT IS DELIBERATE -- verified by BEHAVIOUR, not by the banner.

    HANDOFF §3n: a knob can look set and not be (`--drill-frac 0.0` printed its banner and every
    worker still trained at 0.3). The mirror risk here is the opposite -- a non-zero default
    propagating into a RESPAWNED worker of a run that never opted in -- so the test asserts that
    with config as shipped, a cast the veto WOULD refuse is still castable.
    """

    def test_config_default_is_off(self):
        self.assertEqual(
            float(Config.load().get("sim", "ppo_spell_min_value", default=0.0)), 0.0)

    def test_a_refused_cast_is_still_castable_at_the_shipped_default(self):
        e = _env()
        shipped = float(Config.load().get("sim", "ppo_spell_min_value", default=0.0))
        spells = [i for i, s in enumerate(e.specs) if getattr(s, "kind", "") == "spell"]
        refused = 0
        for _ in range(400):
            e.step((0, 0, 0))
            for i in spells:
                hi, _w = e.spell_card_ok(i, 5.0)      # nothing FINITE clears 5 tower fractions
                if not hi:
                    refused += 1
                    lo, _w2 = e.spell_card_ok(i, shipped)
                    self.assertTrue(lo, "the shipped default refused a cast -- it is not inert")
            if refused >= 10:
                break
        self.assertGreaterEqual(refused, 10, "nothing was ever refused, so nothing was checked")


class FootprintTests(unittest.TestCase):
    """The hit test MIRRORS THE ENGINE. §4v retracted a finding for treating a roll as a disc."""

    def test_a_rolling_spell_is_a_corridor_not_a_disc(self):
        e = _clear(_env())
        log = _spell(e, rolls=True)
        if log is None:
            self.skipTest("this deck has no rolling spell")
        spec = e.specs[log]
        u = _put(e, "knight", 0.5, 0.55)
        hit, us = e._spell_footprint(log)
        self.assertEqual(len(us), 1)
        cx, cy = e._clamped_xy(log in e.anywhere_ids)
        far = lat = 0
        for c in range(hit.shape[0]):
            dyf = (u.y - cy[c]) * -1.0 * 32.0        # forward is decreasing y for team 0
            dxx = abs(u.x - cx[c]) * 18.0
            want = (dyf >= -e._ROLL_BACK_SLOP and dyf <= float(spec.roll_len)
                    and dxx <= float(spec.spell_radius))
            self.assertEqual(bool(hit[c, 0]), want, f"cell {c} dy={dyf:.2f} dx={dxx:.2f}")
            if want and (dxx ** 2 + dyf ** 2) ** 0.5 > float(spec.spell_radius):
                far += 1                            # a DISC of spell_radius would miss this cell
            if dxx > float(spec.spell_radius) and abs(dyf) < 1.0:
                lat += int(bool(hit[c, 0]))
        self.assertGreater(far, 0, "no cell outside a spell_radius disc hits -- this is not a roll")
        self.assertEqual(lat, 0, "a body BESIDE the corridor was caught")

    def test_a_hidden_building_is_not_a_target_for_a_spell_that_cannot_reach_it(self):
        """engine._hurt: `if u.hidden and not hits_hidden: return`. A Rocket 'catching' a retracted
        Tesla it deals zero damage to would let the veto wave that cast through."""
        e = _clear(_env())
        blast = _spell(e, spell_dmg=True, rolls=False, pulls=False)
        if blast is None:
            self.skipTest("this deck has no point-blast spell")
        u = _put(e, "tesla", 0.5, 0.30)
        u.hidden = True
        _hit, us = e._spell_footprint(blast)
        if not getattr(e.specs[blast], "hits_hidden", False):
            self.assertNotIn(id(u), {id(x) for x in us})
        else:
            self.assertIn(id(u), {id(x) for x in us})


class ExemptionTests(unittest.TestCase):
    """Each exemption is a play whose value is NOT the bodies. Sources are in ruling 30."""

    def test_king_activation_exempts_a_single_attacker(self):
        """drill `nado_king_activation`: ONE Hog Rider, and it is the deck's highest-value cast."""
        e = _clear(_env())
        nado = _spell(e, pulls=True)
        if nado is None:
            self.skipTest("this deck has no pull spell")
        _put(e, "hog_rider", 0.25, 0.80)
        self.assertFalse(e.eng.towers[0][2].active, "the drill's premise is a SLEEPING king")
        self.assertEqual(e.spell_veto_exempt(nado), "king_activation")
        ok, _w = e.spell_card_ok(nado, 5.0)          # a threshold nothing could ever clear
        self.assertTrue(ok, "the king activation was vetoed")

    def test_king_activation_does_not_fire_once_the_king_is_awake(self):
        e = _clear(_env())
        nado = _spell(e, pulls=True)
        if nado is None:
            self.skipTest("this deck has no pull spell")
        _put(e, "hog_rider", 0.25, 0.80)
        e.eng.towers[0][2].active = True
        self.assertNotEqual(e.spell_veto_exempt(nado), "king_activation")

    def test_a_building_is_one_body_and_killing_it_is_the_play(self):
        """drills `rocket_the_pump_on_sight` / `eq_the_pump_on_sight` / `eq_clears_the_hogs_building`."""
        e = _clear(_env())
        blast = _spell(e, spell_dmg=True, pulls=False)
        if blast is None:
            self.skipTest("this deck has no damage spell")
        _put(e, "elixir_collector", 0.30, 0.16 if blast in e.anywhere_ids else 0.60)
        self.assertEqual(e.spell_veto_exempt(blast), "building")

    def test_a_pull_gets_no_building_exemption(self):
        """engine._tick_vortex refuses to drag a building, so there is nothing to exempt."""
        e = _clear(_env())
        nado = _spell(e, pulls=True)
        if nado is None:
            self.skipTest("this deck has no pull spell")
        _put(e, "elixir_collector", 0.5, 0.60)
        self.assertNotEqual(e.spell_veto_exempt(nado), "building")

    def test_a_knockback_spell_is_exempt_on_an_armed_charge(self):
        """drill `log_resets_the_charge` is scored in TOWER HITS TAKEN, never in bodies."""
        e = _clear(_env())
        log = _spell(e, knockback=True, rolls=True)
        if log is None:
            self.skipTest("this deck has no knockback roll")
        u = _put(e, "battle_ram", 0.5, 0.62)
        u.charge_dist = 99.0
        self.assertEqual(e.spell_veto_exempt(log), "charge_reset")

    def test_the_charge_reset_exemption_is_guarded_by_trade_sane(self):
        """⚠ MEASURED BUG, FIXED HERE. The Rocket also carries 1.0 tiles of knockback and
        `_knock` disarms a charge for it too, so an unguarded reset exemption made a SIX-elixir
        cast unrefusable on any charging body. Doctrine names the LOG for charge resets, never the
        Rocket (DOCTRINE.md rows 4/28/67), and `trade_sane` is the project's own rule for it."""
        e = _clear(_env())
        rocket = next((i for i, s in enumerate(e.specs)
                       if getattr(s, "kind", "") == "spell" and float(s.elixir) >= 6.0), None)
        if rocket is None:
            self.skipTest("this deck has no 6-elixir spell")
        u = _put(e, "bandit", 0.5, 0.30)             # 3 elixir: 6 - 3 >= SPELL_OVERKILL_MARGIN
        u.charge_dist = 99.0
        self.assertFalse(TV.trade_sane(e.db, e.specs[rocket].base, ["bandit"]))
        self.assertNotEqual(e.spell_veto_exempt(rocket), "charge_reset")

    def test_lock_break_exempts_dragging_one_defender_off_our_building(self):
        """drill `nado_the_sneaky_lock`: ONE Knight on our X-Bow. env._nado_catch says it in its
        own words -- "most wincons pulled this way are worth less than one" rocket."""
        e = _clear(_env())
        nado = _spell(e, pulls=True)
        if nado is None:
            self.skipTest("this deck has no pull spell")
        mine = _put(e, "x_bow" if "x_bow" in e.deck_keys else "tesla", 0.26, 0.53, team=0)
        foe = _put(e, "knight", 0.26, 0.50)
        foe.target, foe.locked = mine, True
        self.assertEqual(e.spell_veto_exempt(nado), "lock_break")

    def test_lock_break_does_NOT_fire_on_an_ordinary_scrap_with_our_troops(self):
        """⚠ MEASURED BUG, FIXED HERE. A first version asked only "is this body locked onto
        something of ours" and fired on 21% of every veto evaluation -- an enemy is nearly always
        chewing on something -- which on its own turned the value form into a null (casts/match
        7.83 -> 6.15 against the count form's 4.25)."""
        e = _clear(_env())
        nado = _spell(e, pulls=True)
        if nado is None:
            self.skipTest("this deck has no pull spell")
        e.eng.towers[0][2].active = True
        mine = _put(e, "knight", 0.30, 0.60, team=0)          # OUR TROOP, not a building
        foe = _put(e, "knight", 0.30, 0.58)
        foe.target, foe.locked = mine, True
        self.assertNotEqual(e.spell_veto_exempt(nado), "lock_break")

    def test_the_retarget_branch_needs_a_building_only_body_worth_the_bar(self):
        """env._nado_catch gates `targeters` at nado_retarget_min_worth (2.0) and requires
        `building_only` -- "most wincons pulled this way are worth less than one" rocket."""
        e = _clear(_env())
        nado = _spell(e, pulls=True)
        if nado is None:
            self.skipTest("this deck has no pull spell")
        e.eng.towers[0][2].active = True
        tower = e.eng.towers[0][0]
        cheap = _put(e, "skeletons", tower.x, tower.y + 0.01)  # 0.25 elixir/body, not building_only
        cheap.target, cheap.locked = tower, True
        self.assertNotEqual(e.spell_veto_exempt(nado), "lock_break")
        _clear(e)
        e.eng.towers[0][2].active = True
        hog = _put(e, "hog_rider", tower.x, tower.y + 0.01)    # building_only, 4 elixir
        hog.target, hog.locked = tower, True
        self.assertTrue(hog.spec.building_only)
        self.assertEqual(e.spell_veto_exempt(nado), "lock_break")

    def test_a_tower_lethal_cast_catches_zero_bodies_and_is_exempt(self):
        e = _clear(_env())
        blast = _spell(e, anywhere=True, spell_tower_dmg=True, pulls=False)
        if blast is None:
            self.skipTest("this deck has no tower-damaging spell castable in their half")
        for t in e.eng.towers[1][:2]:
            t.hp = 1.0
        self.assertEqual(e.spell_veto_exempt(blast), "tower_lethal")

    def test_a_live_princess_alone_is_NOT_a_licence_to_cast(self):
        """⚠ MEASURED BUG, FIXED HERE. An anywhere-spell can always reach a live princess, so an
        ungated tower exemption exempted the Rocket on 300 of 300 sampled steps and the veto could
        never refuse it at all. `_rocket_value` prices a regulation chip at rocket_chip_early 0.25
        against rocket_chip_behind 1.2 once late and level-or-behind: only the branches that pay
        are exempt."""
        e = _clear(_env())
        blast = _spell(e, anywhere=True, spell_tower_dmg=True, pulls=False)
        if blast is None:
            self.skipTest("this deck has no tower-damaging spell castable in their half")
        e._defensive = False
        e.eng.t = 0.0
        for t in e.eng.towers[1][:2]:
            self.assertTrue(t.alive)
            self.assertGreater(float(t.hp), float(e.specs[blast].spell_tower_dmg))
        self.assertIsNone(e.spell_veto_exempt(blast))
        ok, why = e.spell_card_ok(blast, 5.0)
        self.assertFalse(ok, why)

    def test_the_tiebreak_chip_IS_exempt_once_late_and_behind(self):
        e = _clear(_env())
        blast = _spell(e, anywhere=True, spell_tower_dmg=True, pulls=False)
        if blast is None:
            self.skipTest("this deck has no tower-damaging spell castable in their half")
        # ⚠ NOT `_defensive`, WHICH IS ALREADY TRUE AT t=0 (measured, see the code comment).
        # OVERTIME is the gate the doctrine research actually states.
        e._defensive = True
        e.eng.t = 0.0
        self.assertIsNone(e.spell_veto_exempt(blast), "_defensive alone must not exempt a chip")
        e.eng.t = float(e._double_time) + 1.0
        for t in e.eng.towers[0][:2]:                 # OUR towers lower -> losing the tiebreak
            t.hp = t.hp * 0.3
        self.assertEqual(e.spell_veto_exempt(blast), "tower_chip")

    def test_a_finishable_tower_is_exempt_even_in_regulation(self):
        """DOCTRINE_RESEARCH §3.4: "3-4 EQ casts finish a low tower in x2"; the deck page's own
        switch point is an enemy tower at <=773 HP. An endgame chip catches ZERO bodies."""
        e = _clear(_env())
        blast = _spell(e, anywhere=True, spell_tower_dmg=True, pulls=False)
        if blast is None:
            self.skipTest("this deck has no tower-damaging spell castable in their half")
        e.eng.t = 0.0
        dmg = float(e.specs[blast].spell_tower_dmg)
        for t in e.eng.towers[1][:2]:
            t.hp = dmg * 2.5                          # inside 3 casts, outside 1
        self.assertEqual(e.spell_veto_exempt(blast), "tower_finish")

    def test_an_incoming_troop_spawning_spell_exempts_the_preemptive_cast(self):
        """"Pre-log beats post-log" (DOCTRINE.md row 19/21); drill `log_the_barrel_on_landing`
        spawns its barrel at t=4.0, so the cast-time footprint is empty BY CONSTRUCTION."""
        e = _clear(_env())
        log = _spell(e, rolls=True)
        if log is None:
            self.skipTest("this deck has no rolling spell")
        from clashrl.sim.engine import _Spell
        barrel = build_spec(e.db, "goblin_barrel", 11)
        if getattr(barrel, "spawn_spec", None) is None:
            self.skipTest("goblin_barrel does not resolve to a spawning spell in this KB")
        e.eng.spells.append(_Spell(1, 0.2, 0.85, barrel, 1.0))
        self.assertEqual(e.spell_veto_exempt(log), "incoming_spawn")


class VetoBitesTests(unittest.TestCase):
    """It has to REFUSE things, or it is not a veto."""

    def test_an_empty_board_refuses_every_spell(self):
        e = _clear(_env())
        e.eng.towers[1][0].alive = False
        e.eng.towers[1][1].alive = False
        for i, s in enumerate(e.specs):
            if getattr(s, "kind", "") != "spell":
                continue
            ok, why = e.spell_card_ok(i, 0.05)
            self.assertFalse(ok, f"{s.base} allowed on an empty board: {why}")

    def test_a_lone_skeleton_swarm_is_refused_and_a_mini_pekka_is_not(self):
        """The whole point of the value form, on one board each."""
        e = _clear(_env())
        nado = _spell(e, pulls=True)
        card = nado if nado is not None else _spell(e, rolls=True)
        if card is None:
            self.skipTest("this deck has no spell to test")
        e.eng.towers[0][2].active = True             # rule out the king-activation exemption
        _put(e, "skeletons", 0.48, 0.60)             # ONE card, four bodies
        self.assertGreaterEqual(len(e.eng.units), 3, "the Skeletons card should field a squad")
        ok, why = e.spell_card_ok(card, 0.05)
        self.assertFalse(ok, f"one Skeletons card ({len(e.eng.units)} bodies) cleared 0.05: {why}")
        _clear(e)
        e.eng.towers[0][2].active = True
        _put(e, "mini_pekka", 0.48, 0.60)
        ok, why = e.spell_card_ok(card, 0.05)
        self.assertTrue(ok, f"a Mini P.E.K.K.A. was refused: {why}")

    def test_not_a_spell_is_never_vetoed(self):
        e = _clear(_env())
        for i, s in enumerate(e.specs):
            if getattr(s, "kind", "") == "spell":
                continue
            self.assertEqual(e.spell_card_ok(i, 5.0), (True, "not_a_spell"))


class GreedyParityTests(unittest.TestCase):
    """⚠ `choose_greedy` applied NO spell restriction of any kind before this change, so eval and
    live cast spells unmasked while sampling ran masked (spell_experiments.md §7.5). All three
    greedy paths now take the same veto: the trainer's benchmark, and the drill report's own."""

    def test_the_trainer_greedy_takes_an_envs_argument(self):
        import inspect
        from clashrl import train_sim_ppo
        src = inspect.getsource(train_sim_ppo)
        self.assertIn("def choose_greedy(obs_b, hand_b, nxt_b, elx_b, thr_b, envs=None):", src)
        self.assertIn("choose_greedy(eo, eh, en, ee, et, envs=eval_pool)", src)
        self.assertEqual(src.count("def _apply_veto("), 1)
        self.assertEqual(src.count("_apply_veto(cq_m, gq_m, playable, i,"), 3,
                         "expected the definition plus ONE call in choose_sample and ONE in "
                         "choose_greedy -- the veto must be applied in both")

    def test_the_drill_report_greedy_applies_the_veto_too(self):
        import inspect
        from clashrl import cli
        src = inspect.getsource(cli._drill_policy_from_checkpoint)
        self.assertIn("spell_card_ok", src)
        self.assertIn("spell_min_value", src)


class RemoteWorkerPathTests(unittest.TestCase):
    """⚠ THE VETO HAS TO SURVIVE `--workers 12`, WHICH IS EVERY REAL RUN OF THIS PROJECT.

    MEASURED DEFECT, fixed here. `train_sim_ppo` sets `remote = workers > 1` and then keeps its
    own env list EMPTY in that mode (`for e in (pool if not remote else [])`). The first version
    of this veto guarded the sampling path with `and not remote`, so with the shipped training
    command it would have been applied at EVAL and in the drill report and NOWHERE in training --
    ruling 30's own asymmetry, inverted, and invisible: the banner would still print.

    That seam is not new. `remote_pool.py` records the identical failure for deck PFSP ("a worker
    has its OWN cfg copy that the parent's record never reaches -- so deck exploiters silently did
    nothing whenever --workers > 0, which is every real run"), and HANDOFF §3n records it for
    `--drill-frac 0.0`, which printed its banner while every worker trained at 0.3.
    """

    def test_the_sampler_no_longer_switches_itself_off_under_workers(self):
        import inspect
        from clashrl import train_sim_ppo
        src = inspect.getsource(train_sim_ppo)
        self.assertNotIn("spell_min_value > 0.0 and not remote", src,
                         "the sampling-path veto is disabled for every --workers > 1 run")
        self.assertIn("rpool.spell_veto(i) if remote else _spell_veto(", src)

    def test_the_worker_ships_the_refusal_in_its_payload(self):
        import inspect
        from clashrl.sim import remote_pool
        src = inspect.getsource(remote_pool)
        self.assertIn('"veto": spell_veto_ids(env, spell_min_value)', src)
        self.assertIn("def spell_veto(self, i: int):", src)

    def test_the_worker_side_helper_agrees_with_spell_card_ok(self):
        """Same env, same answer -- the worker must not be a second, drifting implementation."""
        from clashrl.sim.remote_pool import spell_veto_ids
        e = _clear(_env())
        e.eng.towers[0][2].active = True                  # no king-activation exemption
        e.eng.towers[1][0].alive = False                  # ...and no tower exemption either
        e.eng.towers[1][1].alive = False
        hand = [int(c) for c in e._hand_ids()]
        self.assertTrue(hand, "the env dealt no hand")
        want = [c for c in hand
                if getattr(e.specs[c], "kind", "") == "spell" and not e.spell_card_ok(c, 5.0)[0]]
        self.assertEqual(list(spell_veto_ids(e, 5.0)), want)
        self.assertTrue(want, "no spell in hand was refused, so nothing was compared")

    def test_the_worker_helper_is_inert_at_the_shipped_default(self):
        """0.0 must not even LOOK at the env: an un-opted run pays nothing and behaves as before."""
        from clashrl.sim.remote_pool import spell_veto_ids

        class Exploding:
            def __getattr__(self, name):
                raise AssertionError("the veto touched the env at min_value 0.0")

        self.assertEqual(spell_veto_ids(Exploding(), 0.0), [])
        e = _clear(_env())
        _put(e, "skeletons", 0.48, 0.60)
        self.assertEqual(spell_veto_ids(e, 0.0), [])


if __name__ == "__main__":
    unittest.main()
