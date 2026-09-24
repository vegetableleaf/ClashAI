"""Generalist dataset builder (pipeline.dataset_gen) on 3 real corpus_v6 replays (skipped when the corpus is absent).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_dataset_gen -v

Fixtures: an icebow replay (opponent deck carries @evolution and @hero cards), a v3-VAL icebow replay where icebow
is engine side 1 (the mirrored frame), a hogeq replay, and an icebow MIRROR match (both sides icebow, the two
engine deck lists in different orders -- the case that first decoded side 1 with the wrong slot order).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline import dataset as ds
from pipeline import dataset_gen as G
from pipeline.obs_contract import SCALAR_FEATURES, load_deck

V6 = G.REPO / "scratchpad" / "gauntlet" / "ext" / "corpus_v6"
FIXTURES = [V6 / "icebow" / "replay_000YL9U0U8JL.json", V6 / "icebow" / "replay_000YLY2VQ92P.json",
            V6 / "hogeq" / "replay_000YLL09YQ0V.json", V6 / "icebow" / "replay_082Y8Q0CRU92.json"]


@unittest.skipUnless(all(f.is_file() for f in FIXTURES), "corpus_v6 fixtures not on this box")
class TestDatasetGen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        for f in FIXTURES:
            shutil.copy(f, cls.tmp / f.name)
        cls.out = cls.tmp / "gen.npz"
        cls.summary = G.build([cls.tmp], cls.out, grid="lattice", workers=1, log=None)
        z = np.load(cls.out, allow_pickle=False)
        cls.a = {k: z[k] for k in z.files if k != "meta"}
        cls.meta = json.loads(str(z["meta"]))
        cls.vocab = cls.meta["card_vocab"]
        cls.recs = {str(r["tag"]): r for r in (json.loads(f.read_text(encoding="utf-8")) for f in FIXTURES)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def key(self, cid):
        return self.vocab[int(cid)]

    def rows(self, tag, side, gate):
        a = self.a
        rep = list(a["tags"]).index(tag)
        return np.where((a["rep"] == rep) & (a["side"] == side) & (a["y_gate"] == gate))[0]

    def test_both_sides_every_replay(self):
        self.assertEqual(self.summary["failed"], 0)
        for tag in self.recs:
            for side in (0, 1):
                self.assertGreater(len(self.rows(tag, side, 1)), 0, (tag, side, "play"))
                self.assertGreater(len(self.rows(tag, side, 0)), 0, (tag, side, "wait"))

    def test_identity_matches_engine_on_play_frames(self):
        """Every play row: hand / next / deck / played card and hand position equal the engine record."""
        a, n_checked = self.a, 0
        for tag, rec in self.recs.items():
            pframes = {int(p["play_index"]): p for p in rec["play_frames"]}
            for side in (0, 1):
                names = rec["final_decks"][str(side)]
                forms = {G.card_key(n): G.card_form(n) for n in names}
                plays = sorted((e for e in rec["log"] if int(e.get("side", -1)) == side and e.get("accepted")
                                and int(e["play_index"]) in pframes), key=lambda e: (int(e["tick"]), int(e["play_index"])))
                idx = self.rows(tag, side, 1)
                self.assertEqual(len(idx), len(plays))
                for i, e in zip(idx, plays):
                    pf = pframes[int(e["play_index"])]
                    me = next(p for p in pf["players"] if int(p["side"]) == side)
                    self.assertEqual(int(a["tick"][i]), int(pf["tick"]))
                    self.assertEqual([self.key(c) for c in a["hand_card"][i]], [G.card_key(h) for h in me["hand"]])
                    self.assertEqual([self.key(c) for c in a["hand_card"][i]], [G.card_key(h) for h in e["hand_before"]])
                    self.assertEqual(a["hand_form"][i].tolist(), [forms[G.card_key(h)] for h in me["hand"]])
                    self.assertEqual(self.key(a["next_card"][i]), G.card_key(names[int(me["next"])]))
                    self.assertEqual(sorted(self.key(c) for c in a["deck_card"][i]), sorted(forms))
                    self.assertEqual([forms[self.key(c)] for c in a["deck_card"][i]], a["deck_form"][i].tolist())
                    # y_card = the card actually played (log slug), at the engine's hand position
                    self.assertEqual(self.key(a["y_card"][i]), str(e["card"]))
                    self.assertEqual(int(a["y_hand_pos"][i]), int(e["hand_index"]))
                    self.assertEqual(self.key(a["y_wait_card"][i]), str(e["card"]))
                    n_checked += 1
        self.assertGreater(n_checked, 50)
        # the fixture's opponent deck has both forms, so they are really read
        self.assertTrue({1, 2} <= set(a["deck_form"].ravel().tolist()))

    def test_wait_rows(self):
        a = self.a
        w = a["y_gate"] == 0
        self.assertTrue((a["y_card"][w] == G.CARD_PAD).all() and (a["y_hand_pos"][w] == -1).all())
        self.assertTrue((a["y_cell"][w] == -1).all() and (a["y_cell"][~w] >= 0).all())
        self.assertTrue((a["y_wait_card"][w] != G.CARD_PAD).all())
        self.assertTrue((a["y_wait_dt"][w] > 20 * 0.05).all())
        # the card waited for is in the hand the row carries (hand only changes on an own accepted play)
        self.assertTrue((a["hand_card"][w] == a["y_wait_card"][w, None]).any(1).all())

    def test_no_deck_slot_information_in_sc(self):
        sc = self.a["sc"]
        self.assertEqual(sc.shape[1], G.S)
        i = 0                                            # locate the slot one-hots from the contract's own layout
        for name, width in SCALAR_FEATURES:
            if name in ("hand_slot_onehot_4x9", "next_slot_onehot_9"):
                self.assertTrue((sc[:, i:i + width] == 0).all(), name)
            i += width
        self.assertTrue((sc[:, 3] > 0).any(), "the rest of sc is still filled (my_elixir)")

    def test_icebow_side_matches_s1(self):
        """On the icebow side, tokens, non-slot sc, labels and past positions equal S1's own builder."""
        deck = load_deck("icebow")
        for tag, side in [(t, sd) for t in self.recs for sd in ds.deck_sides(self.recs[t], deck)]:
            rows = ds._Rows()
            ds.build_replay(self.recs[tag], deck, rows, 0)
            s1 = rows.arrays()
            m1 = s1["side"] == side
            s1 = {k: (v[m1] if k not in ("tok", "off") else v) for k, v in s1.items()}
            j1 = np.where(m1)[0]
            rep = list(self.a["tags"]).index(tag)
            m = (self.a["rep"] == rep) & (self.a["side"] == side)
            idx = np.where(m)[0]
            self.assertEqual(len(idx), len(s1["sc"]))
            keep = np.ones(G.S, bool)
            keep[G.SC_SLOT_COLS] = False
            np.testing.assert_array_equal(self.a["sc"][idx][:, keep], s1["sc"][:, keep])
            np.testing.assert_array_equal(self.a["y_xy"][idx], s1["y_xy"])
            np.testing.assert_array_equal(self.a["y_gate"][idx], s1["y_gate"])
            np.testing.assert_array_equal(self.a["past"][idx][:, :, 2:], s1["past"][:, :, 1:])
            s1_card = [ds.vocab.base_key(deck.cards[s]).replace("_", "-") if s >= 0 else "<pad>" for s in s1["y_slot"]]
            self.assertEqual([self.key(c) for c in self.a["y_card"][idx]], s1_card)
            for j, i in zip(j1, idx):
                np.testing.assert_array_equal(self.a["tok"][self.a["off"][i]:self.a["off"][i + 1]],
                                              s1["tok"][s1["off"][j]:s1["off"][j + 1]])
            s1_hand = [[ds.vocab.base_key(deck.cards[x]).replace("_", "-") if x < 8 else "<pad>" for x in h]
                       for h in s1["sc"][:, 7:43].reshape(-1, 4, 9).argmax(-1)]
            self.assertEqual([[self.key(c) for c in h] for h in self.a["hand_card"][idx]], s1_hand)

    def test_no_row_type_leak(self):
        """§5cs.61: play and wait rows share one format. Every array has the same trailing shape for both row
        types by construction; here: no FORMAT column (token cols 6-13: hp/deploying/age/conf/is_spell and their
        'known' flags) differs between row types, no input column is constant-per-row-type, and no single input
        column separates the row types by a threshold as well as the leaked format did (0.98)."""
        a = self.a
        play = a["y_gate"] == 1
        row_of_tok = np.repeat(np.arange(len(play)), np.diff(a["off"]))
        tp = play[row_of_tok]
        for c in range(6, 14):
            if c == 6:                                   # hp_frac is state (damage), only its range is format
                continue
            self.assertEqual(set(np.unique(a["tok"][tp, c])), set(np.unique(a["tok"][~tp, c])), f"tok col {c}")
        # per-row inputs the model sees (token column means, sc, identity arrays, past)
        ntok = np.maximum(np.diff(a["off"]), 1)
        tok_mean = np.stack([np.bincount(row_of_tok, a["tok"][:, c], len(play)) / ntok for c in range(1, 14)], 1)
        X = np.concatenate([tok_mean, np.diff(a["off"])[:, None], a["sc"], a["hand_card"], a["hand_form"],
                            a["next_card"][:, None], a["next_form"][:, None], a["deck_card"], a["deck_form"],
                            a["past"].reshape(len(play), -1)], 1).astype(np.float64)
        worst = 0.0
        for j in range(X.shape[1]):
            x = X[:, j]
            up, uw = np.unique(x[play]), np.unique(x[~play])
            if len(up) == 1 and len(uw) == 1:
                self.assertEqual(up[0], uw[0], f"column {j} is a row-type constant")
            order = np.argsort(x, kind="stable")          # best single-threshold balanced accuracy
            xs, p = x[order], play[order]
            tpr = np.concatenate([[0], np.cumsum(p)]) / p.sum()
            fpr = np.concatenate([[0], np.cumsum(~p)]) / (~p).sum()
            cut = np.concatenate([[True], xs[1:] != xs[:-1], [True]])    # thresholds only between distinct values
            worst = max(worst, float(np.max(np.abs(tpr - fpr)[cut])) / 2 + 0.5)
        self.assertLess(worst, 0.9, f"a single column separates play/wait at bal-acc {worst:.3f}")


if __name__ == "__main__":
    unittest.main()
