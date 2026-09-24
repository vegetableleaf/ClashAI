"""Generalist model / trainer / evaluator (pipeline.model_gen, train_gen, eval_gen) on toy rows, CPU, tiny model.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_model_gen -v

The toy rows are random (not game states) but carry BOTH encodings of one hand: S1's deck-slot one-hots in ``sc`` and
the generalist identity arrays with card id = slot + 1 and the deck = cards 1..8 (sorted, as dataset_gen stores it).
That makes the S1-equivalence test possible: an ``S1Model`` wrapped to the generalist call signature must get
IDENTICAL numbers from ``eval_gen.evaluate`` and ``train_s1.evaluate``.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import torch
import torch.nn as nn

from pipeline import eval_gen as EG
from pipeline import train_gen as TG
from pipeline import train_s1 as T1
from pipeline.dataset import PAST_K
from pipeline.model_gen import GenModel, mirror_gen
from pipeline.model_v3 import S1Model, hand_mask_from_sc
from pipeline.obs_contract import F as TOK_F, S as SC_S


def toy(n: int = 300, seed: int = 0, nt_max: int = 12) -> dict:
    rng = np.random.default_rng(seed)
    nt = rng.integers(1, nt_max, n)
    tok = rng.normal(size=(int(nt.sum()), TOK_F)).astype(np.float32)
    tok[:, 0] = rng.integers(0, 50, len(tok))
    tok[:, 4:6] = rng.uniform(0, 1, (len(tok), 2))
    sc = rng.normal(size=(n, SC_S)).astype(np.float32)
    sc[:, 7:52] = 0
    hand = np.stack([rng.choice(8, 4, replace=False) for _ in range(n)])       # deck slots, 4 distinct
    nxt = np.array([rng.choice(np.setdiff1d(np.arange(8), h)) for h in hand])
    for i in range(n):
        sc[i, 7 + np.arange(4) * 9 + hand[i]] = 1.0
        sc[i, 43 + nxt[i]] = 1.0
    gate = (rng.random(n) < 0.4).astype(np.int8)
    pos = rng.integers(0, 4, n)
    y_slot = np.where(gate == 1, hand[np.arange(n), pos], -1).astype(np.int8)
    wait = np.where(gate == 1, y_slot, rng.integers(0, 8, n)).astype(np.int8)
    y_xy = np.where(gate[:, None] == 1, rng.uniform(0, 1, (n, 2)), -1.0).astype(np.float32)
    past = rng.uniform(0, 1, (n, PAST_K, 4)).astype(np.float32)
    past[:, :, 0] = rng.integers(-1, 8, (n, PAST_K)); past[:, :, 3] *= 20
    past[past[:, :, 0] < 0] = -1.0
    deck_form = rng.integers(0, 3, (n, 8)).astype(np.int16)
    s1 = {"tok": tok, "off": np.concatenate([[0], np.cumsum(nt)]).astype(np.int64), "sc": sc, "past": past,
          "y_xy": y_xy, "y_slot": y_slot, "y_gate": gate, "y_wait_slot": wait,
          "y_crowns": rng.integers(0, 4, (n, 2)).astype(np.int8), "split": (rng.random(n) < 0.5).astype(np.int8)}
    gp = np.concatenate([past[..., :1] + 1, np.take_along_axis(deck_form, np.clip(past[..., 0], 0, 7).astype(int), 1)[..., None],
                         past[..., 1:]], -1).astype(np.float32)
    gp[..., 1] = np.where(gp[..., 0] > 0, gp[..., 1], 3)
    gen = dict(s1, past=gp, hand_card=(hand + 1).astype(np.int16),
               hand_form=np.take_along_axis(deck_form, hand, 1), next_card=(nxt + 1).astype(np.int16),
               next_form=deck_form[np.arange(n), nxt], deck_card=np.tile(np.arange(1, 9, dtype=np.int16), (n, 1)),
               deck_form=deck_form, y_card=(y_slot.astype(np.int16) + 1), y_hand_pos=np.where(gate == 1, pos, -1).astype(np.int8),
               y_wait_card=(wait.astype(np.int16) + 1), v3val=((rng.random(n) < 0.5) & (s1["split"] == 1)).astype(np.int8),
               deck_id=rng.integers(0, 3, n).astype(np.int32))
    for k in ("y_slot", "y_wait_slot"):
        gen.pop(k)
    return {"s1": s1, "gen": gen}


def tiny(seed: int = 0) -> GenModel:
    torch.manual_seed(seed)
    return GenModel(d=32, layers=1, heads=2, d_c=8, n_cards=9).eval()


class S1AsGen(nn.Module):
    """An S1Model behind the generalist call: hand positions / deck positions gathered from its slot logits."""

    def __init__(self, s1: S1Model):
        super().__init__()
        self.s1 = s1

    def forward(self, b, card=None, form=None):
        p4 = torch.cat([b["past"][..., :1] - 1, b["past"][..., 2:]], -1)
        out = self.s1(b["tok"], b["mask"], b["sc"], p4, card_slot=(card - 1).clamp(min=0),
                      hand_mask=hand_mask_from_sc(b["sc"]))
        out["card"] = out["card"].gather(1, b["hand_card"] - 1)
        out["wait"] = out["wait"].gather(1, b["deck_card"] - 1)
        return out


class TestModelGen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = toy()
        cls.rows = EG.GenRows(cls.t["gen"], np.arange(64), torch.device("cpu"))
        cls.b = cls.rows.batch(np.arange(64))

    def fwd(self, m, b):
        with torch.no_grad():
            return m(b, card=b["card"], form=b["form"])

    def test_shapes(self):
        o = self.fwd(tiny(), self.b)
        self.assertEqual(tuple(o["card"].shape), (64, 4))
        self.assertEqual(tuple(o["wait"].shape), (64, 8))
        self.assertEqual(tuple(o["cell"].shape), (64, 2304))
        self.assertEqual(tuple(o["gate"].shape), (64,))
        self.assertEqual(tuple(o["value"].shape), (64, 7))

    def test_pointer_never_selects_pad(self):
        b = dict(self.b)
        hc = b["hand_card"].clone()
        rng = np.random.default_rng(1)
        for i in range(len(hc)):                                 # 1-3 pad positions per row
            hc[i, rng.choice(4, rng.integers(1, 4), replace=False)] = 0
        b["hand_card"] = hc
        m = tiny()
        m.card_b.weight.data[0] = 1e6                            # even a huge pad bias must not win
        o = self.fwd(m, b)
        self.assertTrue(bool((hc.gather(1, o["card"].argmax(1, keepdim=True)) > 0).all()))
        self.assertTrue(bool(torch.isinf(o["card"][hc == 0]).all()))
        b["gate"] = torch.ones_like(b["gate"]); b["slot"] = (hc > 0).long().argmax(1)   # a real target position
        loss, _ = TG.losses(m.train(), b, mirror=True, grid="lattice")
        self.assertTrue(bool(torch.isfinite(loss)))

    def test_hand_permutation_equivariance(self):
        m = tiny()
        o = self.fwd(m, self.b)
        perm = torch.tensor([2, 0, 3, 1])
        b = dict(self.b, hand_card=self.b["hand_card"][:, perm], hand_form=self.b["hand_form"][:, perm])
        o2 = self.fwd(m, b)
        torch.testing.assert_close(o2["card"], o["card"][:, perm])
        for k in ("gate", "value", "wait", "cell"):
            torch.testing.assert_close(o2[k], o[k])

    def test_deck_order_invariance(self):
        m = tiny()
        o = self.fwd(m, self.b)
        perm = torch.tensor([5, 2, 7, 0, 1, 6, 3, 4])
        b = dict(self.b, deck_card=self.b["deck_card"][:, perm], deck_form=self.b["deck_form"][:, perm])
        o2 = self.fwd(m, b)
        for k in ("gate", "value", "card", "cell", "g"):
            torch.testing.assert_close(o2[k], o[k])
        torch.testing.assert_close(o2["wait"], o["wait"][:, perm])   # the deck pointer permutes with the deck

    def test_mirror_round_trip(self):
        b = self.b
        once = mirror_gen(b["tok"], b["sc"], b["past"], b["xy"])
        twice = mirror_gen(*once)
        for x, y in zip(twice, (b["tok"], b["sc"], b["past"], b["xy"])):
            torch.testing.assert_close(x, y)
        p, p1 = b["past"], once[2]
        real = p[..., 0] > 0
        torch.testing.assert_close(p1[..., 2][real], 1 - p[..., 2][real])      # x flips on real past plays
        torch.testing.assert_close(p1[..., 2][~real], p[..., 2][~real])        # none-rows keep -1
        torch.testing.assert_close(p1[..., [0, 1, 3, 4]], p[..., [0, 1, 3, 4]])  # card, form, y, dt untouched
        torch.testing.assert_close(once[1][:, [53, 54]], b["sc"][:, [54, 53]])   # tower hp L/R swapped

    def test_eval_matches_train_s1_evaluate(self):
        torch.manual_seed(0)
        s1 = S1Model(d=32, layers=1, heads=2)
        idx = np.arange(len(self.t["s1"]["sc"]))
        for grid in ("floor", "lattice"):
            r1 = T1.evaluate(s1, T1.Rows(self.t["s1"], idx, torch.device("cpu")), bs=64, grid=grid)
            rg = EG.evaluate(S1AsGen(s1), EG.GenRows(self.t["gen"], idx, torch.device("cpu")), bs=64, grid=grid)
            self.assertEqual(set(r1), set(rg))
            for k in r1:
                self.assertAlmostEqual(r1[k], rg[k], places=6, msg=(grid, k))
            self.assertGreater(r1["n_play"], 50)

    def test_batch_matches_train_s1_rows(self):
        t = toy(n=200, seed=3, nt_max=90)                       # rows longer than MAX_U = 64 are truncated alike
        self.assertGreater(int(np.diff(t["gen"]["off"]).max()), 64)
        rows = EG.GenRows(t["gen"], np.arange(200), torch.device("cpu"))
        ids = np.random.default_rng(0).permutation(200)[:77]
        b_new, b_old = rows.batch(ids), T1.Rows.batch(rows, ids)
        for k, v in b_old.items():
            self.assertTrue(torch.equal(b_new[k], v), k)

    def test_zero_valid_targets_give_zero_loss(self):
        b = dict(self.b, slot=torch.full_like(self.b["slot"], -1), wait=torch.full_like(self.b["wait"], -1))
        self.assertTrue(bool((b["gate"] > 0.5).any()) and bool((b["gate"] < 0.5).any()))
        loss, parts = TG.losses(tiny().train(), b, mirror=False, grid="lattice")
        self.assertEqual(parts["card"], 0.0)
        self.assertEqual(parts["wait"], 0.0)
        self.assertTrue(bool(torch.isfinite(loss)))
        loss.backward()                                          # the other heads still get a finite gradient

    def test_val_sample_is_fixed(self):
        g = self.t["gen"]
        a, b = EG.val_rows(g, 40), EG.val_rows(g, 40)
        self.assertEqual(a.tolist(), b.tolist())
        self.assertTrue(bool((g["split"][a] == 1).all()))
        self.assertEqual(len(EG.val_rows(g, 0)), int((g["split"] == 1).sum()))

    def test_checkpoint_roundtrip_and_eval_gen_reproduces(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            g = self.t["gen"]
            meta = {"card_vocab": ["<pad>"] + [f"c{i}" for i in range(1, 9)], "grid": "lattice"}
            np.savez(tmp / "toy.npz", meta=json.dumps(meta), tags=np.asarray(["t"]), **g)
            with mock.patch("torch.cuda.is_available", return_value=False):
                TG.main(["--data", str(tmp / "toy.npz"), "--seed", "0", "--epochs", "2", "--out-dir", str(tmp),
                         "--grid", "lattice", "--d", "32", "--layers", "1", "--d-c", "8", "--bs", "32",
                         "--val-sample", "50"])
                EG.main(["--ckpt", str(tmp / "gen_s0.pt"), "--data", str(tmp / "toy.npz"), "--out", str(tmp / "ev.json"),
                         "--val-sample", "50"])
            hist = json.loads((tmp / "hist_gen_s0.json").read_text())
            self.assertEqual(hist["val_rows"], EG.val_rows(g, 50).tolist())
            self.assertEqual(len(hist["val_rows"]), 50)
            st = torch.load(tmp / "gen_s0.pt")
            self.assertTrue(st["gen"]); self.assertEqual(st["d_c"], 8); self.assertEqual(st["card_vocab"], meta["card_vocab"])
            ev = json.loads((tmp / "ev.json").read_text())
            for k in ("cell_half_top1", "card_top1", "joint_top1", "cell_nll", "gate_acc", "gate_bal_acc", "place_dist"):
                self.assertAlmostEqual(ev["v3val"]["model"][k], st["val"]["v3val"][k], places=5, msg=k)
                self.assertAlmostEqual(ev["val_all"]["model"][k], st["val"][k], places=5, msg=k)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
