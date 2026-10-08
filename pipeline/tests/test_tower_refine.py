"""TowerRefine (L73 chip Rocket): opt-in by checkpoint content, byte-identical when absent or zero-initialised,
composes with CellRefine, and loads through model_gen / eval_gen loaders and a plain load_state_dict.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_tower_refine.py
"""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from pipeline import eval_gen as EG
from pipeline.model_gen import GenModel, load_model
from pipeline.tests.test_cell_refine import _fwd, _model, _save
from pipeline.tests.test_model_gen import toy

HEADS = ("cell", "card", "gate", "wait", "value")


class TestTowerRefine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = EG.GenRows(toy()["gen"], np.arange(64), torch.device("cpu")).batch(np.arange(64))
        cls.tmp = Path(tempfile.mkdtemp())

    def test_zero_init_is_byte_identical(self):
        m = _model(); m.add_cell_refine()
        before = _fwd(m, self.b)
        m.add_tower_refine(); m.eval()
        after = _fwd(m, self.b)
        for k in HEADS:
            self.assertTrue(torch.equal(before[k], after[k]), k)

    def test_plain_checkpoint_has_no_module(self):
        m = _model(); _save(m, self.tmp / "plain.pt")
        m2, _ = load_model(self.tmp / "plain.pt", torch.device("cpu"))
        self.assertIsNone(getattr(m2, "tower_refine", None))

    def test_trained_module_round_trips_with_cell_refine(self):
        m = _model(); m.add_cell_refine(); m.add_tower_refine(); m.eval()
        torch.manual_seed(2)
        torch.nn.init.normal_(m.cell_refine.out.weight, std=0.5)
        torch.nn.init.normal_(m.tower_refine.cell.out.weight, std=0.5)
        torch.nn.init.normal_(m.tower_refine.card[2].weight, std=0.5)
        ref = _fwd(m, self.b)
        base = _model(); base.add_cell_refine(); base.load_state_dict({k: v for k, v in m.state_dict().items() if not k.startswith("tower_refine.")})
        plain = _fwd(base.eval(), self.b)
        self.assertFalse(torch.equal(ref["cell"], plain["cell"]))
        self.assertFalse(torch.equal(ref["card"], plain["card"]))
        for k in ("gate", "wait", "value"):                             # the module never touches these heads
            self.assertTrue(torch.equal(ref[k], plain[k]), k)
        p = self.tmp / "tr.pt"; _save(m, p)
        for loader in (load_model, EG.load_model):
            m2, _ = loader(p, torch.device("cpu"))
            out = _fwd(m2.eval(), self.b)
            for k in HEADS:
                self.assertTrue(torch.equal(out[k], ref[k]), k)
        buf = io.BytesIO(); torch.save(m.state_dict(), buf); buf.seek(0)    # rl_royale actor path
        m3 = GenModel(d=32, layers=1, d_c=8, n_cards=9); m3.load_state_dict(torch.load(buf)); m3.eval()
        self.assertTrue(torch.equal(_fwd(m3, self.b)["card"], ref["card"]))


if __name__ == "__main__":
    unittest.main()
