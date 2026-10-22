"""L74 W18 R4: ``xbow_start_share`` (rl_royale.draw_xbow_start) + the forced opening act (e1_eval.SelfPlayMatch._force) +
``start["hand_first"]`` (royale_env.RoyaleSelfPlayEnv.reset). Opt-in; absent = the pre-change behaviour.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_xbow_start_w18.py

Covers: the states table (fields, frames, elixir >= 6); the draw (share, own stream, fields, the learner's elixir from another
row); sample_matchups (a start only against an X-Bow deck; the other draws unchanged); load_config validation and the config
hash (absent = HEAD's rl_royale); forced_name; a REAL engine reset with hand_first (the card is in the starting hand) and a real
SelfPlayMatch whose icebow side opens with the forced X-Bow at the live point (accepted, an X-Bow body on the board, counted
for the learner's opponent-elixir counter)."""
from __future__ import annotations

import json
import subprocess
import sys
import types
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402

YAML = REPO / "scratchpad/gauntlet/L74/opp_model/cfg/oppW18R1_redirect_s74.yaml"


def _head_rl():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", "HEAD:pipeline/rl_royale.py"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode or "def draw_xbow_start" in src.stdout:
        raise unittest.SkipTest("HEAD already holds W18 R4 (compare against the commit before it)")
    mod = types.ModuleType("rl_royale_pre_r4")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_r4", "exec"), mod.__dict__)
    return mod


class TestTable(unittest.TestCase):
    def test_states(self):
        d = json.loads(RL.XBOW_STATES.read_text(encoding="utf-8"))
        self.assertGreater(len(d["states"]), 500)
        for s in d["states"]:
            self.assertGreaterEqual(s["icebow_elixir"], 6.0)
            self.assertTrue(all(0 < f <= 1 for f in s["learner"] + s["icebow"]))
            x, y = s["xbow_board"]
            self.assertTrue(0 <= x <= 1 and 0.5 < y < 0.7, s)          # our half, at the bridge rows (18.5-20.5 / 32)


class TestDraw(unittest.TestCase):
    def test_share_and_stream(self):
        hits = [RL.draw_xbow_start(0.25, f"k{i}") for i in range(400)]
        n = sum(h is not None for h in hits)
        self.assertTrue(60 < n < 140, n)
        self.assertEqual(RL.draw_xbow_start(0.25, "k7"), RL.draw_xbow_start(0.25, "k7"))
        st = next(h for h in hits if h)
        self.assertEqual(set(st), {"tick", "row", "learner", "opp", "force"})
        self.assertEqual(st["force"]["card"], "Xbow")
        self.assertGreaterEqual(st["opp"]["elixir"], 6.0)
        self.assertGreaterEqual(st["learner"]["elixir"], 6.0)                # another row's icebow elixir
        self.assertIsNone(RL.draw_xbow_start(1e-9, "k7"))

    def test_sample_matchups_only_vs_xbow_decks(self):
        cfg = RL.load_config(YAML, [], False)
        census = RL.league_decks(REPO / cfg["league_decks"])
        p = RL.deck_weights([d["sides"] for d in census], cfg["league_deck_alpha"], cfg["league_deck_floor"])
        snaps = [{"id": "init", "cat": "init", "type": "init", "path": cfg["init"]}]
        base = RL.sample_matchups(np.random.default_rng(3), 32, 1, snaps, cfg, census, p)
        on = RL.sample_matchups(np.random.default_rng(3), 32, 1, snaps, {**cfg, "xbow_start_share": 1.0}, census, p)
        strip = lambda ms: [{k: v for k, v in m.items() if k != "start"} for m in ms]  # noqa: E731
        self.assertEqual(strip(base), strip(on))                               # no other draw moved
        for m in on:
            self.assertEqual("force" in (m.get("start") or {}), RL.has_xbow(m["opp_deck"]), m["opp_deck"])
        self.assertTrue(any("force" in (m.get("start") or {}) for m in on))


class TestConfig(unittest.TestCase):
    def test_hash_absent_is_pre(self):
        P = _head_rl()
        for y in (REPO / "pipeline/rl_royale.yaml", YAML):
            cfg = RL.load_config(y, [], False)
            self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg), y.name)
            self.assertEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "xbow_start_share": None}))
            self.assertNotEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "xbow_start_share": 0.25}))

    def test_validation(self):
        for bad in (0, 1.5, True, "0.2"):
            with self.assertRaises(SystemExit):
                RL.xbow_start_share({"league": True, "xbow_start_share": bad})
        with self.assertRaises(SystemExit):
            RL.xbow_start_share({"league": False, "xbow_start_share": 0.2})
        self.assertEqual(RL.xbow_start_share({"league": True, "xbow_start_share": 0.2}), 0.2)
        self.assertIsNone(RL.xbow_start_share({"league": True}))

    def test_forced_name(self):
        self.assertEqual(E.forced_name(E.ICEBOW_ENGINE_DECK, "Xbow"), "Xbow")
        self.assertEqual(E.forced_name(["Knight@evolution", "X-Bow"], "xbow"), "X-Bow")
        with self.assertRaises(ValueError):
            E.forced_name(["Knight"], "Xbow")


class TestRealEngine(unittest.TestCase):
    def setUp(self):
        try:
            from pipeline.royale_env import RoyaleSelfPlayEnv
        except ImportError as exc:
            raise unittest.SkipTest(str(exc))
        self.Env = RoyaleSelfPlayEnv
        self.opp = ["Giant", "Musketeer", "MiniPekka", "Valkyrie", "Fireball", "Zap", "Skeletons", "Arrows"]

    def test_hand_first(self):
        env = self.Env(decision_ticks=10, tail_cap=7200)
        for seed in range(6):
            raw = env.reset(self.opp, list(E.ICEBOW_ENGINE_DECK), seed,
                            start={"tick": 2000, "princess": [[1.0, 1.0], [0.8, 1.0]], "elixir": [7.0, 8.0],
                                   "hand_first": {1: "Xbow"}})
            self.assertEqual(env.deal[1][0], "Xbow")
            self.assertEqual(env.tick, raw["tick"])
        env.reset(self.opp, list(E.ICEBOW_ENGINE_DECK), 0)                   # absent = the seeded deal as before
        self.assertEqual(env.deal[1], [env.decks[1][i] for i in self._order(0)])

    @staticmethod
    def _order(seed):
        import random
        o = list(range(8))
        random.Random(f"deal:{seed}:1").shuffle(o)
        return o

    def test_forced_xbow(self):
        env = self.Env(decision_ticks=10, tail_cap=7200)
        st = RL.draw_xbow_start(1.0, "real")
        spec = {"tag": "x", "learner_side": 0, "seed": 5, "learner_deck": self.opp, "opp_deck": list(E.ICEBOW_ENGINE_DECK),
                "start": st}
        cfg = {"policy": "live", "tau": 0.35, "afford_mask": True, "stall_elixir": None, "stall_seconds": 12.0, "obs": "clean",
               "noise": E.Noise(), "p_random": 0.0, "random_hand_only": False, "grid": "lattice", "device": "cpu",
               "decide_every": 10, "slot": 0, "port": 0, "T": 0.5, "record": False, "entry_index": 0,
               "action_delay_ticks": 26}
        m = E.SelfPlayMatch(env, spec, 0, cfg, dict(cfg), None, None)
        self.assertTrue(m.forced)
        self.assertEqual(m.opp.accepted[0][0], int(env.tick))
        env._advance_to(int(env.tick) + 10)                                 # the X-Bow body exists once the engine steps
        xid = env.card_id("Xbow")
        xb = [e for e in env.raw()["entities"] if int(e["side"]) == 1 and int(e.get("card_id", -1)) == xid]
        self.assertEqual(len(xb), 1, [(e.get("side"), e.get("card_id")) for e in env.raw()["entities"]])
        x, y = st["force"]["board"]                                        # at the live point (icebow = Red: rotated frame)
        self.assertAlmostEqual(xb[0]["x"], (1 - x) * 18000, delta=600)
        self.assertAlmostEqual(xb[0]["y"], y * 32000, delta=600)


if __name__ == "__main__":
    unittest.main()
