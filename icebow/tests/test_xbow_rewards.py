"""X-Bow reward-ledger repair (2026-08-14): uptime ticks, overcommit credit, linear chip lane,
and the doctrine context modifiers on wincon_exec. Design rationale in log.txt + DOCTRINE."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim.engine import build_spec


def _quiet_env(seed=42):
    env = SimMatchEnv(Config.load(), seed=seed)
    env.reset()
    env.opponent.act = lambda eng: None          # deterministic board: the bot stays silent
    return env


def _total(env, name):
    t = env.rw_stats.run.get(name)
    return 0.0 if t is None else t.total


class XbowRewardTests(unittest.TestCase):
    def test_lock_ticks_accumulate_and_cap(self):
        env = _quiet_env()
        bow = build_spec(env.eng.db, "x_bow", 11)
        env.eng.elixir[0] = 10.0
        # bridge-lock spot: in siege range of the enemy princess, nothing contesting
        assert env.eng.deploy(0, bow, 0.20, 0.53)
        for _ in range(40):                       # 40 s of siege
            env.eng.elixir[0] = 5.0
            env.step((False, 0, 0))
        lock = _total(env, "xbow_lock")
        self.assertGreater(lock, 0.1, "a tower-locked bow must earn uptime ticks")
        self.assertLessEqual(lock, env.bow_lock_cap + 1e-6, "per-bow cap must hold")

    def test_linear_chip_lane_pays_while_bow_stands(self):
        env = _quiet_env(seed=43)
        bow = build_spec(env.eng.db, "x_bow", 11)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, bow, 0.20, 0.53)
        for _ in range(25):
            env.eng.elixir[0] = 5.0
            env.step((False, 0, 0))
        self.assertGreater(_total(env, "chip_linear"), 0.01,
                           "the bow's DoT must flow through the linear lane")

    def test_overcommit_credit_on_bow_death(self):
        env = _quiet_env(seed=44)
        bow = build_spec(env.eng.db, "x_bow", 11)
        env.eng.elixir[0] = 10.0
        assert env.eng.deploy(0, bow, 0.50, 0.60)
        bow_u = [u for u in env.eng.units if u.team == 0 and u.spec.base == "x_bow"][-1]
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "pekka", 11), 0.50, 0.575)   # 7 elixir
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.52, 0.575)  # +3 = 10
        env.step((False, 0, 0))                   # they lock onto the bow -> ledger records them
        env.step((False, 0, 0))
        bow_u.hp = 0.0                            # the bow is thwarted...
        env.step((False, 0, 0))
        got = _total(env, "xbow_overcommit")
        self.assertGreater(got, 0.2, "10 elixir spent on a 6-elixir bow must credit the draw")
        self.assertLessEqual(got, env.bow_over_cap + 1e-6)

    def test_wincon_context_modifiers(self):
        env = _quiet_env(seed=45)
        xid = next(iter(env.xbow_ids))
        env._defensive = False
        # PIN THE PUNISH BRANCH OFF for parts (a) and (b), which are about the first-play discount
        # and the plain offensive bow -- not the punish multiplier. Whether _punish_window fires
        # depends on the OPPONENT'S DECK (its cheapest blocker and whether one is in hand), and the
        # deck is sampled from the meta pool by seed. So re-weighting that pool -- sim.meta_deck_boost
        # / meta_deck_top_n -- silently changed which opponent seed 45 draws and this test started
        # reading 4.5 (= w_wincon x xbow_punish_mult) instead of the discounted 0.75. The assertions
        # were right; their setup was quietly depending on pool sampling. Part (c) restores it and
        # tests the punish path deliberately.
        # STUB THE LICENCE GATE, NOT ONE OF ITS CLAUSES. Until 2026-08-23 the offensive bow was
        # licensed by _punish_window alone, so stubbing that isolated (a) and (b). It is now licensed
        # by _bow_window, which ORs EIGHT windows (DOCTRINE_RESEARCH.md S3A) -- stubbing only the
        # elixir clause left W4/W6/W7 free to fire and (b) read 3.6 (= w_wincon x xbow_window_mult)
        # instead of 3.0. The assertions were right; the stub had gone stale against the thing it
        # was meant to switch off.
        _real_window = env._bow_window
        env._bow_window = lambda *a, **k: None
        # (a) first-play bridge bow: fraction of the normal credit while t < 30
        env.eng.t = 5.0
        early = env._wincon_exec(xid, 0.20, 0.53)
        self.assertAlmostEqual(early, env.w_wincon * env.bow_first_frac, delta=0.01)
        # (b) after 30 s, a plain offensive bow pays full
        env.eng.t = 60.0
        base = env._wincon_exec(xid, 0.20, 0.53)
        self.assertAlmostEqual(base, env.w_wincon, delta=0.01)
        # (c) enemy golem invested deep in THEIR right lane -> OPPOSITE-lane bow is punish-class
        # (c) isolates the SPLIT-PUNISH branch specifically, which lives past the window gate, so
        # the gate stays stubbed off -- otherwise W1 would hand back xbow_punish_mult on its own and
        # this would pass without _bow_split_punish ever being consulted.
        env._bow_window = lambda *a, **k: None
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "golem", 11), 0.75, 0.10)
        env.eng.elixir[1] = 10.0                  # restore their bar: NOT an elixir-race window,
        env.eng.t = 60.0                          # so this isolates the split-punish branch
        split = env._wincon_exec(xid, 0.20, 0.53)
        self.assertAlmostEqual(split, env.w_wincon * env.xbow_punish_mult, delta=0.01,
                               msg="back-tank investment makes the opposite-lane bow punish-class")
        # (d) a bow-hostile card seen tempers offensive credit
        env._enemy_seen.add("little_prince")
        tempered = env._wincon_exec(xid, 0.20, 0.53)
        self.assertAlmostEqual(tempered, env.w_wincon * env.xbow_punish_mult * env.bow_hostile_frac,
                               delta=0.01)


class BowWindowTests(unittest.TestCase):
    """The eight offensive-bow windows (DOCTRINE_RESEARCH.md S3A)."""

    def test_opening_ban_outranks_every_window_except_the_pump(self):
        """"Never X-Bow the bridge first play" -- unless they pumped, which is the named exception."""
        env = _quiet_env(seed=45)
        xid = next(iter(env.xbow_ids))
        env._defensive = False
        env.eng.t = 5.0
        env._bow_window = lambda *a, **k: ("W1_elixir", True)
        self.assertAlmostEqual(env._wincon_exec(xid, 0.20, 0.53),
                               env.w_wincon * env.bow_first_frac, delta=0.01,
                               msg="an elixir window must NOT license an opening bridge bow")
        env._bow_window = lambda *a, **k: ("W5_pump", True)
        self.assertAlmostEqual(env._wincon_exec(xid, 0.20, 0.53),
                               env.w_wincon * env.xbow_punish_mult, delta=0.01,
                               msg="a pump IS the exception: Theria's 'unless the opponent pumps up first'")

    def test_favourable_window_pays_less_than_a_punish_window(self):
        env = _quiet_env(seed=45)
        xid = next(iter(env.xbow_ids))
        env._defensive = False
        env.eng.t = 60.0
        env._bow_window = lambda *a, **k: ("W6_no_big_spell", False)
        fav = env._wincon_exec(xid, 0.20, 0.53)
        env._bow_window = lambda *a, **k: ("W1_elixir", True)
        pun = env._wincon_exec(xid, 0.20, 0.53)
        self.assertLess(fav, pun, "a standing matchup property must not pay the punish rate")
        self.assertAlmostEqual(fav, env.w_wincon * env.xbow_window_mult, delta=0.01)

    def test_cycle_depth_counts_from_the_hand(self):
        """W2: the first FOUR cycle entries are the hand, so an in-hand blocker is depth 0."""
        env = _quiet_env(seed=45)
        specs = getattr(env.opponent, "specs", None)
        cyc = list(getattr(env.opponent, "cycle", None) or ())
        if not specs or len(cyc) < 6:
            self.skipTest("opponent does not expose a cycle")
        base = str(getattr(specs[int(cyc[0])], "base", "") or "")
        self.assertEqual(env._opp_cycle_depth({base}), 0, "cycle[0] is in hand -> depth 0")
        deep = str(getattr(specs[int(cyc[5])], "base", "") or "")
        if deep != base:
            self.assertEqual(env._opp_cycle_depth({deep}), 2, "cycle[5] is two plays away")
        self.assertEqual(env._opp_cycle_depth({"__nonexistent__"}), 99,
                         "a card they do not hold reads as unavailable, not as in hand")

    def test_pump_rocket_defers_to_the_bow_when_the_bow_can_punish(self):
        """W5: rocketing a pump keeps full credit ONLY while the bow is not in cycle to punish."""
        env = _quiet_env(seed=45)
        env.eng.elixir[1] = 10.0
        assert env.eng.deploy(1, build_spec(env.eng.db, "elixir_collector", 11), 0.30, 0.16)
        pump = next(u for u in env.eng.units if u.spec.base == "elixir_collector")
        env.eng.elixir[0] = 10.0
        xid = next(iter(env.xbow_ids))
        env._hand_ids = lambda: [xid]                       # bow in hand and affordable
        with_bow = env._pump_rocket(pump.x, pump.y)
        env._hand_ids = lambda: []                          # bow not in cycle to punish
        without_bow = env._pump_rocket(pump.x, pump.y)
        self.assertGreater(without_bow, 0.0, "rocket-on-sight still stands without the bow")
        self.assertAlmostEqual(with_bow, without_bow * env.pump_rocket_bow_frac, delta=0.01)


class PunishWindowTests(unittest.TestCase):
    """W1 after the 2026-08-23 repricing: a DEPLOY LEAD and a POST-SPEND reserve."""

    def test_deploy_lead_is_the_bow_s_own_deploy_time_times_the_live_rate(self):
        env = _quiet_env(seed=45)
        dep = max(float(getattr(env.specs[c], "deploy_time", 0.0) or 0.0) for c in env.xbow_ids)
        self.assertGreater(dep, 0.0, "the bow must carry a deploy_time or the lead is silently 0")
        self.assertAlmostEqual(env._opp_deploy_lead(), dep * env.eng.elixir_rate(), delta=1e-6)

    def test_deploy_lead_grows_in_double_elixir(self):
        """The same 3.5 s buys them twice the answer, so the window must tighten by itself."""
        env = _quiet_env(seed=45)
        env.eng.t = 0.0
        single = env._opp_deploy_lead()
        env.eng.t = env.eng.regulation - 30.0          # last minute of regulation = double
        self.assertGreater(env._opp_deploy_lead(), single * 1.5)

    def test_clause_A_asks_whether_they_are_broke_AFTER_the_deploy(self):
        """The old test read their bar at the instant of casting; the bow is not firing yet."""
        env = _quiet_env(seed=45)
        env._opp_can_block_now = lambda: False
        env._opp_block_cost = 4.0
        lead = env._opp_deploy_lead()
        # Broke now, but they out-regen the deploy and can afford the blocker when it matters.
        env.eng.elixir[1] = 4.0 - lead + 0.25
        env.eng.elixir[0] = 6.0
        self.assertFalse(env._punish_window(spend=0.0, cost=6.0),
                         "regenerating into a blocker during the deploy is NOT a punish window")
        # Broke now AND still broke after the deploy -- the real window.
        env.eng.elixir[1] = 4.0 - lead - 0.25
        self.assertTrue(env._punish_window(spend=0.0, cost=6.0))

    def test_clause_B_is_the_RESERVE_not_the_bar_you_are_about_to_empty(self):
        """The bug this replaced: affording the bow and being 4 ahead were the same event."""
        env = _quiet_env(seed=45)
        env._opp_can_block_now = lambda: False
        env._opp_block_cost = 0.0                     # clause A can never fire -> isolates B
        env.eng.elixir[1] = 2.0
        # Exactly affordable: paying leaves 0, which does not lead them. The OLD test passed here.
        env.eng.elixir[0] = 6.0
        self.assertFalse(env._punish_window(spend=0.0, cost=6.0),
                         "emptying the bar for a bow is not an elixir advantage")
        # A real reserve: the guides' "around 10 elixir" leaves 4 against their 2.
        env.eng.elixir[0] = 10.0
        self.assertTrue(env._punish_window(spend=0.0, cost=6.0))

    def test_post_spend_caller_and_pre_spend_caller_agree(self):
        """_wincon_exec is billed already; _wincon_reach is not. Same board, same verdict."""
        env = _quiet_env(seed=45)
        env._opp_can_block_now = lambda: False
        env._opp_block_cost = 0.0
        env.eng.elixir[1] = 2.0
        env.eng.elixir[0] = 10.0
        pre = env._punish_window(spend=0.0, cost=6.0)      # about to pay
        env.eng.elixir[0] = 4.0                            # same board, already debited
        post = env._punish_window(spend=6.0, cost=6.0)
        self.assertEqual(pre, post, "the two call conventions must describe the same reserve")


if __name__ == "__main__":
    unittest.main(verbosity=1)

class BowOvercommitAttributionTests(unittest.TestCase):
    """Only elixir the opponent SPENT to answer the bow counts as drawn."""

    def test_troops_already_committed_do_not_count(self):
        """Planting a bow on top of an existing push must not book that push as 'drawn'.

        The ledger counted any enemy whose current target was the bow. Drop a bow into a push that
        is already committed and every body retargets it, so the whole push booked as drawn, the
        bow died, and the overcommit credit paid out -- rewarding exactly the habit seen in sim
        view (user, 2026-08-16). Troops on the board before the bow existed were paid for before
        the bow existed.
        """
        env = _quiet_env(seed=5)
        env.eng.elixir[1] = 10.0
        env.eng.deploy(1, build_spec(env.eng.db, "knight", 11), 0.30, 0.45)
        early = env.eng.units[-1]
        for _ in range(30):
            env.eng.advance(0.1)
        env.eng.elixir[0] = 10.0
        env.eng.deploy(0, build_spec(env.eng.db, "x_bow", 11), 0.31, 0.56)
        bow = env.eng.units[-1]
        for _ in range(10):
            env.eng.advance(0.1)
        env.eng.elixir[1] = 10.0
        env.eng.deploy(1, build_spec(env.eng.db, "musketeer", 11), 0.31, 0.42)
        late = env.eng.units[-1]
        for _ in range(10):
            env.eng.advance(0.1)
        self.assertGreater(early.age, bow.age,
                           "the pre-existing pusher must be OLDER than the bow")
        self.assertLess(late.age, bow.age,
                        "the answer played after the bow must be YOUNGER than it")
        # the predicate the ledger uses
        # the predicate the ledger uses: STRICTLY older than the bow is excluded
        self.assertFalse(early.age <= bow.age, "an already-committed troop must not count as drawn")
        self.assertTrue(late.age <= bow.age, "a troop spent to answer the bow must count as drawn")
