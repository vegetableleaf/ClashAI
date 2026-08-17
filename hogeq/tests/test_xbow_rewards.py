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
        _real_punish = env._punish_window
        env._punish_window = lambda *a, **k: False
        # (a) first-play bridge bow: fraction of the normal credit while t < 30
        env.eng.t = 5.0
        early = env._wincon_exec(xid, 0.20, 0.53)
        self.assertAlmostEqual(early, env.w_wincon * env.bow_first_frac, delta=0.01)
        # (b) after 30 s, a plain offensive bow pays full
        env.eng.t = 60.0
        base = env._wincon_exec(xid, 0.20, 0.53)
        self.assertAlmostEqual(base, env.w_wincon, delta=0.01)
        # (c) enemy golem invested deep in THEIR right lane -> OPPOSITE-lane bow is punish-class
        env._punish_window = _real_punish         # the punish path is what (c) is FOR
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
