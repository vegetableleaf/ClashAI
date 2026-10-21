"""W15 levers 2 + 3 (scratchpad/gauntlet/L74/nextround/LEVERS23.md): rl_royale ``ot_start_share`` / ``league_deck_weights``,
the env's mid-match start and the elixir counter's start.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_levers23.py

Absent / null = HEAD c7e56df (PRE): the same matchup rows AND rng state (tn_base_s74's league shape: PFSP + externals +
W7 exploiters + all16 levels), the same load_config dict and config hash. On: the opponent deck draw shifts to the
weighted share (census and exploiter pools; the learner deck unchanged); OT starts land on the share from a stream of
their own (every other matchup field identical to the key off); SelfPlayMatch maps learner / opp to sides; the env
starts at the drawn tick / tower hp / elixir and plays on to the tiebreak drain; the counter starts at the given elixir.
"""
from __future__ import annotations

import subprocess
import sys
import types
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import yaml                                                               # noqa: E402

from pipeline import rl_royale as RL                                      # noqa: E402

PRE = "c7e56df"                    # HEAD before W15: the absent-key reference
POOL = "scratchpad/gauntlet/L74/mix/decks_live_train.json"               # tracked; stands in for both pools
CK = "icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt"   # any existing file stands in for a checkpoint
W = yaml.safe_load((REPO / "scratchpad/gauntlet/L74/stepd/cfg/tn_tank3x_s74.yaml").read_text())["league_deck_weights"]
BASE = dict(league=True, init="init.pt", league_specialist="s1.pt", league_icebow_share=0.0, league_deck_alpha=1.0,
            league_deck_floor=0.0, league_mix={"latest": .5, "older": .25, "init": .25, "s1": 0.0},
            opp_elixir="counter", league_learner_icebow_share=1.0, league_pfsp="hard", league_external=["x1.pt", "x2.pt"],
            live_levels="all16")
EX = dict(BASE, league_exploiters={"ckpt": CK, "decks": POOL, "share": .3, "T": .1, "decide_every": 40})
SNAPS = [{"id": f"s{u}", "path": f"s{u}.pt"} for u in (5, 10, 15)]


def _pre_module():
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                         text=True, encoding="utf-8", timeout=60)
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_pre_w15")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_w15", "exec"), mod.__dict__)
    return mod


def _draw(mod, cfg, seed=3, updates=6, n=8):
    census = mod.league_decks(REPO / POOL)
    p = mod.deck_weights([d["sides"] for d in census], cfg["league_deck_alpha"], cfg["league_deck_floor"])
    rng = np.random.default_rng(seed)
    st = {"ratings": {"init": {"p": .8, "games": 3}}}
    rows = [mod.sample_matchups(rng, n, u, SNAPS[:u % 4], cfg, census, p, league_state=st,
                                exploiters=mod.exploiter_league(cfg)) for u in range(updates)]
    return [m for ms in rows for m in ms], rng.bit_generator.state


def _beat(deck):
    return any(str(c).split("@")[0] in W for c in deck)


class TestAbsentIsPre(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = _pre_module()

    def test_matchups_identical(self):
        for cfg in (BASE, EX):
            pre = _draw(self.P, cfg)
            self.assertEqual(_draw(RL, cfg), pre)
            self.assertEqual(_draw(RL, {**cfg, "league_deck_weights": None, "ot_start_share": None}), pre)

    def test_config_hash_and_load_identical(self):
        tmp = REPO / ".foreman" / "scratch" / "w15"
        tmp.mkdir(parents=True, exist_ok=True)
        cfg = {**yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text()), **EX, "init": CK}
        path = tmp / "absent_cfg.yaml"
        path.write_text(yaml.safe_dump(cfg))
        pre = self.P.load_config(path, [], False)
        self.assertEqual(RL.load_config(path, [], False), pre)
        self.assertEqual(RL.config_sha(pre), self.P.config_sha(pre))
        self.assertEqual(RL.config_sha({**pre, "league_deck_weights": None, "ot_start_share": None}), self.P.config_sha(pre))
        on = RL.load_config(path, ["league_deck_weights={Giant: 3}", "ot_start_share=0.25"], False)
        self.assertEqual((on["league_deck_weights"], on["ot_start_share"]), ({"Giant": 3}, 0.25))
        for k, v in (("league_deck_weights", {"Giant": 3}), ("ot_start_share", .25)):
            self.assertNotEqual(RL.config_sha({**pre, k: v}), self.P.config_sha(pre), k)


class TestDeckWeights(unittest.TestCase):
    def test_pool_p_exact(self):
        census = RL.league_decks(REPO / POOL)
        p = RL.deck_weights([d["sides"] for d in census], 1.0, 0.0)
        b = np.array([_beat(d["engine"]) for d in census])
        q = RL.opp_deck_p(p, census, W)
        want = 3 * p[b].sum() / (3 * p[b].sum() + p[~b].sum())
        self.assertAlmostEqual(q[b].sum(), want, places=12)
        self.assertAlmostEqual(q.sum(), 1.0, places=12)
        np.testing.assert_allclose(q[~b] / q[~b].sum(), p[~b] / p[~b].sum())   # within a class: proportions kept
        self.assertIs(RL.opp_deck_p(p, census, None), p)
        exp = RL.exploiter_league({**EX, "league_deck_weights": W})["p"]
        self.assertAlmostEqual(exp[b].sum(), want, places=12)

    def test_sampled_mix_shifts(self):
        """The drawn opponent decks (census path + exploiter path) land on the weighted share; learner decks unchanged."""
        census = RL.league_decks(REPO / POOL)
        p = RL.deck_weights([d["sides"] for d in census], 1.0, 0.0)
        pb = p[np.array([_beat(d["engine"]) for d in census])].sum()
        want = 3 * pb / (3 * pb + 1 - pb)
        for cfg in (BASE, EX):
            off, _ = _draw(RL, cfg, updates=50, n=40)
            on, _ = _draw(RL, {**cfg, "league_deck_weights": W}, updates=50, n=40)
            for rows, share in ((off, pb), (on, want)):
                got = np.mean([_beat(m["opp_deck"]) for m in rows])
                sd = (share * (1 - share) / len(rows)) ** .5
                self.assertLess(abs(got - share), 4 * sd, (got, share))
                self.assertTrue(all(m["learner_deck_name"] == "icebow" for m in rows))

    def test_refusals(self):
        for bad in ({}, [], {"Giant": 0}, {"Giant": -1}, {"Giant": True}, {"Giant": "3"}, {3: 3.0}, {"Giant": float("inf")}):
            with self.assertRaisesRegex(SystemExit, "league_deck_weights must"):
                RL.check_deck_weights({**BASE, "league_deck_weights": bad})
        with self.assertRaisesRegex(SystemExit, "league true"):
            RL.check_deck_weights({**BASE, "league": False, "league_deck_weights": W})
        pool = RL.league_decks(REPO / POOL)
        RL.check_deck_weights({**BASE, "league_deck_weights": W}, pool)
        with self.assertRaisesRegex(SystemExit, "PEKKA"):
            RL.check_deck_weights({**BASE, "league_deck_weights": {"PEKKA": 3}}, pool)


class TestOtStart(unittest.TestCase):
    def test_share_own_stream_and_frames(self):
        import json
        S = json.loads(RL.OT_STATES.read_text())
        by = {s["key"]: s for s in S["states"]}
        off, st_off = _draw(RL, EX, updates=60, n=40)
        on, st_on = _draw(RL, {**EX, "ot_start_share": .25}, updates=60, n=40)
        self.assertEqual(st_on, st_off)                                    # the learner's stream does not move
        self.assertEqual([{k: v for k, v in m.items() if k != "start"} for m in on], off)
        got = np.mean(["start" in m for m in on])
        self.assertLess(abs(got - .25), 4 * (.25 * .75 / len(on)) ** .5, got)
        els = {s["elixir"] for s in S["states"]}
        for m in on:
            if "start" in m:
                s, row = m["start"], by[m["start"]["row"]]
                self.assertEqual(s["tick"], 3590)
                self.assertEqual(s["learner"]["princess"], row["own"])
                self.assertEqual(s["opp"]["princess"], row["opp"][::-1])        # our screen frame -> the opponent's own
                self.assertEqual(s["learner"]["elixir"], row["elixir"])
                self.assertIn(s["opp"]["elixir"], els)
        self.assertTrue(all(0 < f <= 1 for s in S["states"] for f in s["own"] + s["opp"]))

    def test_refusals(self):
        for bad in (0, 1.5, -.1, True, "x"):
            with self.assertRaisesRegex(SystemExit, "ot_start_share must"):
                RL.ot_start_share({**BASE, "ot_start_share": bad})
        with self.assertRaisesRegex(SystemExit, "league true"):
            RL.ot_start_share({**BASE, "league": False, "ot_start_share": .25})
        self.assertIsNone(RL.ot_start_share(BASE))

    def test_selfplay_match_maps_sides(self):
        from pipeline import e1_eval as E

        class Got(Exception):
            pass

        class Env:
            def reset(self, d0, d1, seed, **kw):
                raise Got(kw)

        start = {"tick": 3590, "row": "r", "learner": {"princess": [.2, .9], "elixir": 3.0},
                 "opp": {"princess": [.7, .6], "elixir": 8.0}}
        for L in (0, 1):
            spec = {"learner_side": L, "learner_deck": ["Knight"] * 8, "opp_deck": ["Giant"] * 8, "seed": 1, "start": start}
            with self.assertRaises(Got) as c:
                E.SelfPlayMatch(Env(), spec, 0, {}, {})
            kw = c.exception.args[0]["start"]
            sides = (start["learner"], start["opp"]) if L == 0 else (start["opp"], start["learner"])
            self.assertEqual(kw, {"tick": 3590, "princess": [sides[0]["princess"], sides[1]["princess"]],
                                  "elixir": [sides[0]["elixir"], sides[1]["elixir"]]})
            spec.pop("start")
            with self.assertRaises(Got) as c:
                E.SelfPlayMatch(Env(), spec, 0, {}, {})
            self.assertEqual(c.exception.args[0], {})                      # absent: no start kwarg at all

    def test_observer_counter_start(self):
        from pipeline.public_observation import PublicObserver
        from pipeline.opp_elixir_count import regen_between
        sched = ((0, 1 / 56), (2400, 1 / 28), (4800, 1 / 18.6), (6000, 0.0))
        o = PublicObserver(0, schedule=sched)
        self.assertEqual(o.estimate_at(3590), 10.0)                        # unseeded: tick 0, 6 elixir, capped by 3590
        o.start_at(3590, 2.5)
        self.assertEqual(o.estimate_at(3590), 2.5)
        self.assertAlmostEqual(o.estimate_at(3630), 2.5 + regen_between(3590, 3630, sched))
        self.assertEqual((o.counter.tick, o.counter.est), (3590, 2.5))


class TestEnvStart(unittest.TestCase):
    """The engine starts mid-match: tick, tower hp (fraction x max, TowerSlot order) and elixir; it plays on into
    overtime and, with no plays, the tiebreak drain ends it against the side with the lowest tower."""

    @classmethod
    def setUpClass(cls):
        try:
            from pipeline.royale_env import RoyaleSelfPlayEnv
        except Exception as exc:                                          # no runtime on this machine
            raise unittest.SkipTest(f"royale_env: {exc}")
        cls.env = RoyaleSelfPlayEnv(tail_cap=7200)

    DECKS = (["Knight", "Archer", "Giant", "Fireball", "Arrows", "Musketeer", "MiniPekka", "Valkyrie"],
             ["Knight", "Archer", "Giant", "Fireball", "Arrows", "Musketeer", "MiniPekka", "HogRider"])

    def test_start_state_and_drain(self):
        env = self.env
        plain = env.reset(*self.DECKS, seed=4)
        self.assertEqual(env.reset(*self.DECKS, seed=4, start=None), plain)
        self.assertIsNone(env.scenario_start)
        mx = [list(env.core.state().players[s].tower_max_hp) for s in (0, 1)]
        start = {"tick": 3590, "princess": [[.5, .9], [.8, .3]], "elixir": [4.0, 7.5]}
        env.reset(*self.DECKS, seed=4, start=start)
        st = env.core.state()
        self.assertEqual(int(st.tick), 3590)
        self.assertIs(env.scenario_start, start)
        for s in (0, 1):
            self.assertEqual(list(st.players[s].tower_hp), [mx[s][0]] + [round(f * mx[s][k + 1]) for k, f in
                                                                       enumerate(start["princess"][s])])
            self.assertEqual(int(st.players[s].crowns), 0)
        self.assertEqual([int(st.players[s].elixir_milli) for s in (0, 1)], [4000, 7500])
        env.advance_to(env.tail_cap)
        self.assertTrue(env.terminated, int(env.tick))
        self.assertGreater(int(env.tick), 6000)                          # overtime ran out, then the drain
        self.assertEqual(env.outcome(0)[0], "win")                        # Red's 0.3 tower is the lowest
        env.reset(*self.DECKS, seed=4)
        self.assertIsNone(env.scenario_start)


if __name__ == "__main__":
    unittest.main()
