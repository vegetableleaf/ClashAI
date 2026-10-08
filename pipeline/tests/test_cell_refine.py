"""CellRefine (L73 centre-column fix): opt-in by checkpoint content, byte-identical when absent or zero-initialised,
card head untouched, and loadable by every consumer (model_gen / eval_gen loaders, the sim's e1_eval.load_policy,
rl_royale actors' load_state_dict, live GenPilot).

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_cell_refine.py
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
from pipeline.model_v3 import cell_label
from pipeline.tests.test_model_gen import toy


def _model(seed=0):
    torch.manual_seed(seed)
    return GenModel(d=32, layers=1, d_c=8, n_cards=9).eval()          # heads=4: what load_model constructs


def _save(model, path, **extra):
    torch.save({"model": model.state_dict(), "gen": True, "d_c": 8, "card_vocab": [f"c{i}" for i in range(9)],
                "args": {"d": 32, "layers": 1, "feature_version": 1, "grid": "lattice"}, "epoch": 1, "n_params": 0,
                "deck": "generalist", **extra}, path)


def _fwd(m, b):
    with torch.no_grad():
        return m(b, card=b["card"], form=b["form"])


class TestCellRefine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        t = toy()
        cls.b = EG.GenRows(t["gen"], np.arange(64), torch.device("cpu")).batch(np.arange(64))
        cls.tmp = Path(tempfile.mkdtemp())

    def test_zero_init_is_byte_identical(self):
        m = _model()
        before = _fwd(m, self.b)
        m.add_cell_refine()
        after = _fwd(m, self.b)
        for k in ("cell", "card", "gate", "wait", "value"):
            self.assertTrue(torch.equal(before[k], after[k]), k)

    def test_old_checkpoint_loads_unchanged(self):
        m = _model()
        _save(m, self.tmp / "old.pt")
        m2, _ = load_model(self.tmp / "old.pt", torch.device("cpu"))
        self.assertIsNone(getattr(m2, "cell_refine", None))
        a, b = _fwd(m, self.b), _fwd(m2.eval(), self.b)
        for k in ("cell", "card", "gate", "wait", "value"):
            self.assertTrue(torch.equal(a[k], b[k]), k)

    def test_refine_checkpoint_loads_everywhere(self):
        m = _model()
        m.add_cell_refine()
        torch.manual_seed(1)
        torch.nn.init.normal_(m.cell_refine.out.weight, std=0.5)
        ref = _fwd(m, self.b)
        base = _fwd(_model(), self.b)
        self.assertFalse(torch.equal(ref["cell"], base["cell"]))      # the module does act on the cell head
        for k in ("card", "gate", "wait", "value"):                    # and on nothing else
            self.assertTrue(torch.equal(ref[k], base[k]), k)
        p = self.tmp / "ref.pt"
        _save(m, p, cell_refine=True)
        # model_gen.load_model (sim e1_eval, search_s0, live) and eval_gen.load_model (rl_royale learner)
        for loader in (load_model, EG.load_model):
            m2, _ = loader(p, torch.device("cpu"))
            self.assertIsNotNone(m2.cell_refine)
            self.assertTrue(torch.equal(_fwd(m2.eval(), self.b)["cell"], ref["cell"]))
        # rl_royale actor: constructs a plain GenModel, then load_state_dict(torch.load(bytes))
        buf = io.BytesIO(); torch.save(m.state_dict(), buf)
        net = GenModel(d=32, layers=1, d_c=8, n_cards=9).eval()
        net.load_state_dict(torch.load(io.BytesIO(buf.getvalue())))
        self.assertTrue(torch.equal(_fwd(net.eval(), self.b)["cell"], ref["cell"]))
        # sim: e1_eval.load_policy -> GenPolicy; its cell_logits route through cell_logits_gen with the refinement
        from pipeline import e1_eval as E
        pol, info = E.load_policy(p, "cpu")
        self.assertTrue(info["gen"])
        enc = pol.model.encode_gen(self.b)
        self.assertIn("cell_feat", enc)
        enc = {**enc, "slot_card": self.b["hand_card"].new_zeros(64, 9), "slot_form": self.b["hand_card"].new_zeros(64, 9)}
        enc["slot_card"][:, 0] = self.b["card"]; enc["slot_form"][:, 0] = self.b["form"]
        with torch.no_grad():
            sub = {k: v[:10] for k, v in enc.items()}                  # rl_royale.policy_terms row-subsets enc
            cl = pol.cell_logits(sub, torch.zeros(10, dtype=torch.long))
        self.assertTrue(torch.allclose(cl, ref["cell"][:10], atol=1e-5))
        # live: GenPilot builds its model from the checkpoint path
        from pipeline.live_gen import GenPilot
        pilot = GenPilot(p, device="cpu", use_counter=False)
        self.assertIsNotNone(pilot.model.cell_refine)
        self.assertTrue(torch.equal(_fwd(pilot.model, self.b)["cell"], ref["cell"]))

    def test_composes_with_fv6_barrel_branch(self):
        """fv6 projectile-target branch (barrel add-on) + CellRefine in one checkpoint: both load, both act, and the
        branch-only part is unchanged by the zero-init refinement."""
        from pipeline.tests.test_spatial_projectiles import batch
        b = batch()
        torch.manual_seed(0)
        m = GenModel(d=32, layers=1, d_c=16, n_cards=124, feature_version=6).eval()
        torch.nn.init.normal_(m.projectile_target_spread.weight, std=0.5)       # a "trained" barrel branch
        before = _fwd(m, b)
        m.add_cell_refine(16, 5)
        self.assertTrue(torch.equal(_fwd(m, b)["cell"], before["cell"]))
        torch.nn.init.normal_(m.cell_refine.out.weight, std=0.5)
        ref = _fwd(m, b)
        p = self.tmp / "fv6_ref.pt"
        torch.save({"model": m.state_dict(), "gen": True, "d_c": 16, "card_vocab": list(range(124)),
                    "args": {"d": 32, "layers": 1, "feature_version": 6, "grid": "lattice"}, "cell_refine": True}, p)
        m2, _ = load_model(p, torch.device("cpu"))
        self.assertEqual((m2.cell_refine.C, len(m2.cell_refine.convs)), (16, 5))
        self.assertTrue(torch.equal(_fwd(m2.eval(), b)["cell"], ref["cell"]))
        no_branch = m2.state_dict()
        no_branch["projectile_target_spread.weight"] = torch.zeros_like(no_branch["projectile_target_spread.weight"])
        m2.load_state_dict(no_branch)
        self.assertFalse(torch.equal(_fwd(m2.eval(), b)["cell"], ref["cell"]))     # the branch still acts

    def test_saved_shape_is_enforced_on_load(self):
        """The module is built from the stored (width, depth): a state dict missing its last conv layer must FAIL a
        strict load instead of loading silently as a shallower module; pre-cfg files still load by key inference."""
        m = _model()
        m.add_cell_refine(16, 5)
        torch.nn.init.normal_(m.cell_refine.out.weight, std=0.5)
        sd = m.state_dict()
        self.assertEqual(sd["cell_refine.cfg"].tolist(), [16, 5])
        truncated = {k: v for k, v in sd.items() if not k.startswith("cell_refine.convs.4.")}
        with self.assertRaises(RuntimeError):
            _model().load_state_dict(truncated)
        legacy = {k: v for k, v in sd.items() if k != "cell_refine.cfg"}         # written before the cfg buffer
        m2 = _model()
        m2.load_state_dict(legacy)
        self.assertEqual((m2.cell_refine.C, len(m2.cell_refine.convs)), (16, 5))
        self.assertTrue(torch.equal(_fwd(m2, self.b)["cell"], _fwd(m, self.b)["cell"]))

    def test_unit_scatter_mirrors_like_labels(self):
        x = torch.tensor([[17 / 36, 0.7], [19 / 36, 0.7], [3.4 / 36, 0.2]])
        mx = x.clone(); mx[:, 0] = 1 - mx[:, 0]
        c, mc = cell_label(x, "lattice"), cell_label(mx, "lattice")
        self.assertTrue(torch.equal(c // 36, mc // 36))
        self.assertTrue(torch.equal(c % 36 + mc % 36, torch.full_like(c, 36)))


if __name__ == "__main__":
    unittest.main()
