"""OPP-LEARN-A: the fast loop's timing-head opponent seat (plan1026/pilot/loop producer.ThEnv + msg_p2.py). The exactness
check against production is compare.py on a pod (cmp_p2.sh); these pin the Python glue production's decode runs on.

    icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_loop_timing_seat.py

Covers: ThEnv answers production's th_ability (the ready list in, the press out with its tick), refuses a second press in one
decision, delegates every other attribute to the capture env; on a pod (royalegym) th_decided / timing_decide_batch read
its game-over flag; msg_p2 puts the timing checkpoint on every n-th job and turns opp_style off.
"""
from __future__ import annotations

import pickle
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
LOOP = REPO / "scratchpad/gauntlet/L74/plan1026/pilot/loop"
for p in (REPO, LOOP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pipeline import e1_eval as E                                         # noqa: E402
import msg_p2                                                             # noqa: E402
from producer import ThEnv                                                # noqa: E402

try:
    import royalegym.protocol  # noqa: F401
    HAS_RG = True
except ImportError:            # the laptop venv: the game-over test runs on a pod
    HAS_RG = False
DECK = ["Knight", "Archers", "Giant", "Musketeer", "Arrows", "Fireball", "Valkyrie", "Mirror"]


def _seat(env, oa=None):
    return NS(env=env, engine_deck=list(DECK), deck_index_of_slot=list(range(8)), costs=[3.0] * 8, done_plays=[],
              _cur=(1000, None, NS(my_elixir=10.0)), _th_slot=None, side=1, tag="t", rng_behave=np.random.default_rng(0),
              _gen_row=None if oa is None else {"own_ability": oa})


class TestThEnv(unittest.TestCase):
    def test_ability_press_goes_back_with_its_tick(self):
        pmf = np.log(np.maximum(np.array([0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0]), 1e-30))
        heads = {"ab_hazard": torch.full((1,), 20.0), "ab_tick": torch.tensor(pmf)[None]}
        vis = np.zeros((2, 7), np.float32)
        vis[0, 0] = 1
        env = ThEnv(NS(engine_delay_ticks=20))
        env.ready = [(0, 5, 77), (1, 6, 78)]
        m = _seat(env, vis)
        E.th_ability(m, heads, 0)
        self.assertEqual(env.queued, ([(0, 5, 77)], 3))                 # production queues ready[0], j ticks on
        with self.assertRaises(RuntimeError):
            env.queue_abilities(1, [(1, 6, 78)], 0)
        env2 = ThEnv(NS(engine_delay_ticks=20))                           # nothing ready: drawn, never queued
        m2 = _seat(env2, vis)
        E.th_ability(m2, heads, 0)
        self.assertIsNone(env2.queued)
        self.assertEqual(m2.th_ab, {"slots": 1, "draws": 1, "queued": 0})

    def test_delegates_to_the_capture_env(self):
        inner = NS(engine_delay_ticks=20, learned_sides=set())
        env = ThEnv(inner)
        self.assertEqual(env.engine_delay_ticks, 20)
        env.learned_sides.add(1)
        self.assertEqual(inner.learned_sides, {1})
        self.assertIs(env.core, env)

    @unittest.skipUnless(HAS_RG, "royalegym (pod runtime) not importable")
    def test_game_over_flag_is_th_decided(self):
        heads = {"hazard": torch.full((1,), 20.0), "tick": torch.zeros(1, 10), "card": torch.zeros(1, 8)}
        env = ThEnv(NS(engine_delay_ticks=20))
        self.assertFalse(E.th_decided(_seat(env)))
        env.over = True
        m = _seat(env)
        state = m.rng_behave.bit_generator.state
        out = E.timing_decide_batch(None, {}, heads, np.ones((1, 8), bool), [m], {"T": 1.0})
        self.assertEqual(out[0]["why"], "game_over")
        self.assertEqual(m.rng_behave.bit_generator.state, state)


class TestMsgP2(unittest.TestCase):
    def test_every_nth_job_gets_the_timing_opponent(self):
        jobs = [(i, {"tag": f"m{i}", "opp": {"id": "x", "path": "a.pt"}}, i, {"rollout_index": i}) for i in range(6)]
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / "m.pkl", Path(d) / "o.pkl"
            src.write_bytes(pickle.dumps(({"opp_style": "on", "T": 0.5}, 3, b"sd", jobs)))
            msg_p2.main([str(src), str(out), "--ckpt", str(Path(d) / "p2.pt"), "--jobs", "5", "--every", "2"])
            base, update, sd, got = pickle.loads(out.read_bytes())
        self.assertEqual((base["opp_style"], base["T"], update, sd, len(got)), ("off", 0.5, 3, b"sd", 5))
        self.assertEqual([j[1]["opp"]["id"] for j in got], ["p2_timing", "x", "p2_timing", "x", "p2_timing"])
        self.assertEqual(got[1], jobs[1])
        self.assertEqual(got[2][3], {"rollout_index": 2})


if __name__ == "__main__":
    unittest.main()
