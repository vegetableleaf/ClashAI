"""Step d builders (cue_drive / cue_sidecar) + the trainer's cue path (eval_gen.GenRows, train_gen.losses). CPU, no SIM:
    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider scratchpad/gauntlet/L74/stepd/test_stepd.py
The SIM-side parity (imitation builder vs RL builder on the same RoyaleSim states) is parity_rows.py (needs the runtime).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import eval_gen as EG, train_gen as TG                       # noqa: E402
from pipeline.model_gen import CUE_N                                       # noqa: E402
from pipeline.obs_contract import F as TOK_F                               # noqa: E402
from scratchpad.gauntlet.L74.stepd import cue_drive as CD                  # noqa: E402
from scratchpad.gauntlet.L74.stepd.cue_sidecar import CUE_SCALE, replay_cue   # noqa: E402


def ent(side, x, y, hp, mhp, cid):
    return [side, x, y, "n", hp, mhp, 0, cid, 1]


class TestFidelity(unittest.TestCase):
    def test_body_fid(self):
        nat = [ent(0, 9000, 24000, 100, 100, 26000000), ent(1, 3000, 6000, 50, 100, 26000001), ent(0, 0, 0, 999, 999, -1)]
        self.assertEqual(CD.body_fid(nat, [ent(0, 9400, 24300, 100, 100, 26000000), ent(1, 3000, 6000, 52, 100, 26000001)]),
                         (1.0, 1.0))                                     # within 1 tile, hp within 15%; towers ignored
        d, h = CD.body_fid(nat, [ent(0, 11000, 24000, 100, 100, 26000000), ent(1, 3000, 6000, 90, 100, 26000001)])
        self.assertEqual((d, h), (0.5, 0.0))                             # 2 tiles off = unmatched; hp 40% off = not ok
        self.assertEqual(CD.body_fid(nat, [ent(0, 9000, 24000, 100, 100, 26000099)])[0], 0.0)   # other card id
        d, h = CD.body_fid([], [])
        self.assertEqual(d, 1.0)
        self.assertTrue(np.isnan(h))

    def test_source_from_crawl_rotation_and_abilities(self):
        battle = {"opponent_deck": "x-bow,knight-ev1", "team_deck": "hog-rider,zap", "opponent_crowns": "1", "team_crowns": "0"}
        rows = [dict(play_index="1", tick="40", attr_s="blue", attr_card="zap", attr_ability="0", x_units="1000",
                     y_units="2000", attr_i="1"),
                dict(play_index="0", tick="20", attr_s="red", attr_card="knight", attr_ability="0", x_units="9500",
                     y_units="31500", attr_i="0"),
                dict(play_index="2", tick="60", attr_s="red", attr_card="_invalid", attr_ability="1", x_units="",
                     y_units="", attr_i="0")]
        s = CD.source_from_crawl("t", battle, rows)
        self.assertEqual([p["play_index"] for p in s["plays"]], [0, 1, 2])
        self.assertEqual((s["plays"][1]["side"], s["plays"][1]["x"], s["plays"][1]["y"]), (1, 17.0, 30.0))   # rotated
        self.assertEqual((s["plays"][2]["ability"], s["plays"][2]["x"]), (1, None))
        self.assertEqual(s["decks"]["0"], ["x-bow", "knight-ev1"])
        self.assertEqual(s["expected"]["crowns_by_side"], {"0": 1, "1": 0})
        self.assertEqual(s["blocks"], [])


class TestSidecar(unittest.TestCase):
    def setUp(self):
        # one MY unit token at board (0.5, 0.25) = engine tiles (9, 24) for side 0; one ENEMY token at (0.25, 0.75)
        tk = np.zeros((2, TOK_F), np.float32)
        tk[0, [1, 4, 5]] = (1, 0.5, 0.25)
        tk[1, [2, 4, 5]] = (1, 0.25, 0.75)
        self.tok = np.concatenate([tk] * 4)
        self.n_tok = np.array([2, 2, 2, 2])
        c_mine, c_enemy, c_play = (np.zeros(CUE_N, np.float32) for _ in range(3))
        c_mine[[0, 3, 10, 13]] = 1; c_mine[15] = 0.5
        c_enemy[[0, 2]] = 1
        c_play[[0, 1]] = 1
        body = lambda team, x, y, c: [team, x, y, 0.0, *c]               # hp_frac 0 = the tokens hold no hp (hp_known 0)  # noqa: E731
        frames = [(100, -1, 0.95, [body(0, 9.2, 24.1, c_mine), body(1, 4.5, 8.0, c_enemy)]),
                  (100, 7, 0.95, [body(0, 9.0, 24.0, c_play)]),
                  (110, -1, 0.50, [body(0, 9.0, 24.0, c_mine)])]
        off, bodies = [0], []
        for f in frames:
            bodies += f[3]; off.append(len(bodies))
        self.cz = dict(tick=np.array([f[0] for f in frames]), pidx=np.array([f[1] for f in frames]),
                       fid=np.array([f[2] for f in frames], np.float32), off=np.array(off),
                       bodies=np.asarray(bodies, np.float32))
        self.c = dict(mine=c_mine, enemy=c_enemy, play=c_play)

    def test_status_alignment_and_quantisation(self):
        q = lambda c: np.rint(c * CUE_SCALE).astype(np.uint8)            # noqa: E731
        cue, st, fid, tfid = replay_cue(self.tok, self.n_tok, np.array([100, 110, 120, 100]), np.zeros(4, int),
                                  np.array([0, 0, 0, 1]), self.cz, 0.9)
        self.assertEqual(st.tolist(), [4, 2, 1, 4])
        np.testing.assert_array_equal(cue[0], q(self.c["mine"]))         # nearest same-side body within 3 tiles
        np.testing.assert_array_equal(cue[1], q(self.c["enemy"]))        # the enemy token: board (0.25, 0.75) = (4.5, 8)
        self.assertFalse(cue[2:6].any())                                 # fid below the bar / no frame: unknown (0)
        np.testing.assert_array_equal(cue[6], q(self.c["play"]))         # a play row reads the pre-act PLAY frame
        self.assertFalse(cue[7].any())                                   # ... which has no enemy body: unmatched = 0
        self.assertAlmostEqual(float(fid[1]), 0.5, places=5)
        _, st0, _, _ = replay_cue(self.tok, self.n_tok, np.array([100, 110, 120, 100]), np.zeros(4, int),
                               np.array([0, 0, 0, 1]), None, 0.9)
        self.assertEqual(st0.tolist(), [0, 0, 0, 0])

    def test_pod_mode_token_fid_and_gate(self):
        # no native fid (NaN): the bar reads the token Dice; a token with no 1-tile / hp match keeps 0 cues
        tok = self.tok[:2].copy()
        tok[:, 7] = 1; tok[:, 6] = 0.5                                   # both tokens know their hp: 50%
        bodies = np.asarray([[0, 9.0, 24.0, 0.52, *self.c["mine"]],     # mine: on the token, hp within 15%
                             [1, 6.5, 8.0, 0.50, *self.c["enemy"]]], np.float32)   # enemy: 2 tiles off (align would take it)
        cz = dict(tick=np.array([100]), pidx=np.array([-1]), fid=np.array([np.nan], np.float32), off=np.array([0, 2]),
                  bodies=bodies)
        args = (tok, np.array([2]), np.array([100]), np.zeros(1, int), np.array([0]), cz)
        cue, st, fid, tfid = replay_cue(*args, 0.9)
        self.assertEqual((st.tolist(), float(tfid[0])), ([2], 0.5))       # Dice 2 * 1 / (2 + 2) < 0.9
        self.assertTrue(np.isnan(fid[0]))
        cue, st, _, _ = replay_cue(*args, 0.4)
        self.assertEqual(st.tolist(), [4])
        self.assertEqual(int(cue[0, 0]), 255)
        self.assertFalse(cue[1].any())                                   # token gate
        cue, _, _, _ = replay_cue(*args, 0.4, token_gate=False)
        self.assertEqual(int(cue[1, 0]), 255)                            # ... without it align's 3-tile match stands
        b2 = bodies.copy(); b2[0, 3] = 0.9                               # hp 90% vs the token's 50%: no match
        _, _, _, tf2 = replay_cue(tok, np.array([2]), np.array([100]), np.zeros(1, int), np.array([0]), dict(cz, bodies=b2), 0.9)
        self.assertEqual(float(tf2[0]), 0.0)

    def test_side1_mirror(self):
        # side 1 sees the board mirrored: its token (0.5, 0.25) is engine (9, 8)
        tok = np.zeros((1, TOK_F), np.float32); tok[0, [1, 4, 5]] = (1, 0.5, 0.25)
        cz = dict(self.cz, tick=np.array([100]), pidx=np.array([-1]), fid=np.array([1.0], np.float32),
                  off=np.array([0, 1]), bodies=np.asarray([[1, 9.0, 8.0, 0.0, *self.c["mine"]]], np.float32))
        cue, st, _, _ = replay_cue(tok, np.array([1]), np.array([100]), np.array([1]), np.array([0]), cz, 0.9)
        self.assertEqual(st.tolist(), [4])
        self.assertEqual(int(cue[0, 0]), 255)


class TestTrainerCuePath(unittest.TestCase):
    def test_batch_gather_identity_and_gradient(self):
        from pipeline.tests.test_model_gen import tiny, toy
        g = toy()["gen"]
        rng = np.random.default_rng(1)
        cue = rng.integers(0, 256, (len(g["tok"]), CUE_N)).astype(np.uint8)
        ids = np.arange(40)
        dev = torch.device("cpu")
        b0 = EG.GenRows(g, ids, dev).batch(ids)
        b1 = EG.GenRows(dict(g, cue=cue), ids, dev).batch(ids)
        self.assertNotIn("cue", b0)
        for k in b0:                                                     # the cue array changes nothing else
            self.assertTrue(torch.equal(b0[k], b1[k]), k)
        off = g["off"]
        for k, i in enumerate(ids):
            a, m = off[i], min(off[i + 1] - off[i], 64)
            np.testing.assert_allclose(b1["cue"][k, :m].numpy(), cue[a:a + m] / 255.0, rtol=0, atol=1e-6)
            self.assertEqual(float(b1["cue"][k, m:].abs().sum()), 0.0)
        m = tiny()
        l0, _ = TG.losses(m, b0, mirror=False, grid="floor")
        l1, _ = TG.losses(m, b1, mirror=False, grid="floor")
        self.assertEqual(float(l0), float(l1))                           # no cue layer: b["cue"] is ignored
        m.add_cue_in()
        l2, _ = TG.losses(m, b1, mirror=True, grid="floor")
        l3, _ = TG.losses(m, b0, mirror=True, grid="floor")
        self.assertAlmostEqual(float(l2), float(l3), places=5)           # zero-init layer: same loss at step 0
        l2.backward()
        self.assertGreater(float(m.cue_in.weight.grad.abs().sum()), 0.0)  # ... and it trains


if __name__ == "__main__":
    unittest.main()
