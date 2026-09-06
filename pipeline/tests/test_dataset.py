"""S1 dataset builder: invariants on the first corpus_v3 replays (skipped when the corpus is absent)."""
import unittest

import numpy as np

from pipeline import dataset as ds
from pipeline.obs_contract import load_deck

CORPUS = ds.CORPUS / "icebow"


@unittest.skipUnless(CORPUS.exists() and any(CORPUS.glob("replay_*.json")), "corpus_v3/icebow not on this box")
class TestDatasetInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.deck = load_deck("icebow")
        cls.rows = ds._Rows()
        cls.stats = {}
        cls.n_rep = 0
        for f in sorted(CORPUS.glob("replay_*.json"))[:4]:
            rec = json.loads(f.read_text(encoding="utf-8"))
            if ds.deck_sides(rec, cls.deck):
                ds.build_replay(rec, cls.deck, cls.rows, cls.n_rep, stats=cls.stats)
                cls.n_rep += 1
        cls.a = cls.rows.arrays()

    def test_shapes(self):
        a = self.a
        n = len(a["sc"])
        self.assertGreater(n, 0)
        self.assertEqual(a["off"].shape, (n + 1,))
        self.assertEqual(a["off"][-1], len(a["tok"]))
        self.assertEqual(a["past"].shape, (n, ds.PAST_K, 4))
        self.assertEqual(a["y_crowns"].shape, (n, 2))
        self.assertEqual(self.stats.get("unmapped", set()), set())

    def test_play_rows(self):
        a = self.a
        p = a["y_gate"] == 1
        self.assertTrue(((a["y_slot"][p] >= 0) & (a["y_slot"][p] < 8)).all())
        self.assertTrue(((a["y_xy"][p] >= 0) & (a["y_xy"][p] <= 1)).all())
        hand = a["sc"][:, 7:43].reshape(-1, 4, 9).argmax(-1)          # 4 hand slots one-hot over deck slot (8 = unknown)
        for i in np.where(p)[0]:
            self.assertIn(int(a["y_slot"][i]), hand[i].tolist(), "played card must be in the recorded hand")
        self.assertTrue((a["y_wait_dt"][p] == 0).all())

    def test_wait_rows(self):
        a = self.a
        w = a["y_gate"] == 0
        self.assertGreater(w.sum(), 0)
        self.assertTrue((a["y_slot"][w] == -1).all())
        self.assertTrue((a["y_wait_slot"][w] >= 0).all())
        self.assertTrue((a["y_wait_dt"][w] > 20 * 0.05).all(), "a wait row has no accepted play within play_window")
        hand = a["sc"][:, 7:43].reshape(-1, 4, 9).argmax(-1)
        self.assertTrue((hand[w] != 8).all(), "wait rows carry a fully reconstructed hand")

    def test_past_is_causal(self):
        a = self.a
        ok = a["past"][:, :, 3]
        self.assertTrue((ok[a["past"][:, :, 0] >= 0] > 0).all(), "seconds-ago strictly positive")
        # within one replay/side, play rows in tick order: past[0] of row k+1 is row k's own play
        for rep in np.unique(a["rep"]):
            for side in (0, 1):
                idx = np.where((a["rep"] == rep) & (a["side"] == side) & (a["y_gate"] == 1))[0]
                idx = idx[np.argsort(a["tick"][idx], kind="stable")]
                for k in range(1, len(idx)):
                    self.assertEqual(int(a["past"][idx[k], 0, 0]), int(a["y_slot"][idx[k - 1]]))


if __name__ == "__main__":
    unittest.main()
