"""LOOP-LRN ``lazy_refine`` (model_gen.GenModel.lazy_refine; rl_royale config key): the cell_refine / tower_refine cell
features are built inside cell_logits_gen, i.e. only for the rows whose cell logits are taken (policy_terms: the played
rows), instead of for every row in encode_gen. Owner 10-28: adopted, with a test that FAILS if those features are read
outside the played rows.

    icebow/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_lazy_refine.py

Tiny random GenModel with BOTH refine modules attached and non-zero outputs, rows from the real e1_eval sampler
(test_rl_gen's fake env). No engine, no GPU.
"""
from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_e1_eval_gen import VOCAB, _tiny_gen              # noqa: E402
from pipeline.tests.test_rl_gen import TAU, T, _batch, _rollouts, _wide_cells   # noqa: E402

TOL = 1e-5
OUT_KEYS = ("x", "card_lp", "cell_lp", "lp_gate", "lp_card", "lp_cell", "v")


def _refine_model(seed=3):
    m = _wide_cells(_tiny_gen(seed))
    m.add_cell_refine(c=8, layers=2)
    m.add_tower_refine(c=8, layers=2, hidden=16)
    g = torch.Generator().manual_seed(seed)
    with torch.no_grad():                                 # zero-initialised outputs would make the features irrelevant
        for lin in (m.cell_refine.out, m.tower_refine.cell.out):
            lin.weight.copy_(torch.randn(lin.weight.shape, generator=g))
            lin.bias.copy_(torch.randn(lin.bias.shape, generator=g))
    return m.eval()


def _frozen(m):
    r = copy.deepcopy(m).eval()
    for p in r.parameters():
        p.requires_grad_(False)
    return r


class TestLazyRefine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _refine_model()
        cls.B, st = _batch(_rollouts(E.GenPolicy(cls.model, VOCAB), n_matches=8))
        cls.N = len(cls.B["A"])
        cls.played = cls.B["played"]
        assert 10 < int(cls.played.sum()) < cls.N         # both kinds of rows exist
        cls.R = RL.ref_terms(_frozen(cls.model), cls.B, TAU, T)

    def _copy(self, lazy):
        m = copy.deepcopy(self.model)
        m.lazy_refine = lazy
        return m

    def _terms_loss_grads(self, m, idx=None):
        """policy_terms outputs (value on), the PPO minibatch loss and every parameter gradient, rows ``idx``."""
        idx = torch.arange(self.N) if idx is None else idx
        m.zero_grad(set_to_none=True)
        t = RL.policy_terms(m, self.B, idx, TAU, T, value=True)
        out = {k: t[k].detach().clone() for k in OUT_KEYS}
        loss, _ = RL.minibatch_loss(m, self.B, self.R, idx, tau=TAU, T=T, clip=0.2, beta=0.3, n_total=self.N)
        loss.backward()
        grads = {n: p.grad.detach().clone() for n, p in m.named_parameters() if p.grad is not None}
        return out, float(loss.detach()), grads

    def test_refine_acts_on_the_cell_head(self):          # the fixture is not vacuous
        m = self._copy(False)
        with torch.no_grad():
            m.cell_refine.out.weight.zero_(); m.cell_refine.out.bias.zero_()
            m.tower_refine.cell.out.weight.zero_(); m.tower_refine.cell.out.bias.zero_()
        a, _, _ = self._terms_loss_grads(self._copy(False))
        b, _, _ = self._terms_loss_grads(m)
        self.assertGreater(float((a["cell_lp"] - b["cell_lp"]).abs().max()), 1e-3)

    def test_lazy_equals_eager(self):
        e_out, e_loss, e_g = self._terms_loss_grads(self._copy(False))
        z_out, z_loss, z_g = self._terms_loss_grads(self._copy(True))
        for k in OUT_KEYS:
            self.assertLess(float((e_out[k] - z_out[k]).abs().max()), TOL, k)
        self.assertLess(abs(e_loss - z_loss), TOL)
        self.assertEqual(set(e_g), set(z_g))
        self.assertTrue(any(n.startswith("cell_refine.") for n in z_g) and any(n.startswith("tower_refine.cell.")
                                                                              for n in z_g))
        for n in e_g:
            self.assertLess(float((e_g[n] - z_g[n]).abs().max()), TOL, n)
        # a few PPO steps from the same start: the weights stay together. Plain SGD: Adam divides by sqrt(v), so on a
        # near-zero gradient component a 1e-9 float difference can flip the step's sign (+-lr) -- not a lazy effect
        ws = []
        for lazy in (False, True):
            m = self._copy(lazy)
            opt = torch.optim.SGD(m.parameters(), lr=1e-2)
            cfg = {"minibatch": 32, "ppo_epochs": 2, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}
            out = RL.ppo_update(m, opt, self.B, self.R, cfg, 0.3, np.random.default_rng(0))
            self.assertIsNone(out["nonfinite"])
            ws.append({n: p.detach().clone() for n, p in m.named_parameters()})
        for n in ws[0]:
            self.assertLess(float((ws[0][n] - ws[1][n]).abs().max()), TOL, n)

    def test_lazy_builds_features_for_played_rows_only(self):
        m = self._copy(True)
        sizes = []
        for mod, name in ((m.cell_refine, "features"), (m.tower_refine, "cell_feat")):
            real = getattr(mod, name)

            def spy(*a, _real=real):
                sizes.append(len(a[0]))
                return _real(*a)
            setattr(mod, name, spy)
        idx = torch.from_numpy(np.random.default_rng(1).choice(self.N, self.N // 2, replace=False))
        for rows in (torch.arange(self.N), idx):
            sizes.clear()
            RL.policy_terms(m, self.B, rows, TAU, T, value=True)
            self.assertEqual(sizes, [int(self.played[rows].sum())] * 2)

    def test_lazy_poisoned_non_played_refine_inputs_change_nothing(self):
        """NaN in every refine input (unit states u, unit xy, tower scalars) of the NON-played rows: outputs, loss and
        gradients are bit-identical and finite -> nothing reads those rows' refine features."""
        clean = self._terms_loss_grads(self._copy(True))
        m = self._copy(True)
        enc_real, bad = m.encode_gen, ~self.played

        def poisoned(b):
            enc = enc_real(b)
            assert len(enc["u"]) == self.N                # policy_terms over every row: b's rows are B's rows
            out = dict(enc)
            for k in ("u", "refine_xy", "refine_sc"):
                v = enc[k]
                out[k] = torch.where(bad.view(-1, *([1] * (v.dim() - 1))), torch.full_like(v, float("nan")), v)
            return out
        m.encode_gen = poisoned
        out, loss, grads = self._terms_loss_grads(m)
        for k in OUT_KEYS:
            self.assertTrue(torch.isfinite(out[k]).all(), k)
            self.assertTrue(torch.equal(out[k], clean[0][k]), k)
        self.assertEqual(loss, clean[1])
        self.assertEqual(set(grads), set(clean[2]))
        for n in grads:
            self.assertTrue(torch.equal(grads[n], clean[2][n]), n)

    def test_eager_poisoned_non_played_features_change_nothing(self):
        """The premise of lazy_refine, on the EAGER model: the cell / tower-cell features of the non-played rows set to
        NaN after they are built -> outputs, loss and gradients bit-identical (a reader of those rows would turn NaN)."""
        clean = self._terms_loss_grads(self._copy(False))
        m = self._copy(False)
        bad = ~self.played
        for mod, name in ((m.cell_refine, "features"), (m.tower_refine, "cell_feat")):
            real = getattr(mod, name)

            def poisoned(*a, _real=real):
                f = _real(*a)
                assert len(f) == self.N
                return torch.where(bad.view(-1, 1, 1), torch.full_like(f, float("nan")), f)
            setattr(mod, name, poisoned)
        out, loss, grads = self._terms_loss_grads(m)
        for k in OUT_KEYS:
            self.assertTrue(torch.isfinite(out[k]).all(), k)
            self.assertTrue(torch.equal(out[k], clean[0][k]), k)
        self.assertEqual(loss, clean[1])
        for n in grads:
            self.assertTrue(torch.equal(grads[n], clean[2][n]), n)

    def test_config_key_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            base = RL.config_sha(load())
            self.assertEqual(base, RL.config_sha(load(lazy_refine=None)))     # absent == null == false: historical
            self.assertEqual(base, RL.config_sha(load(lazy_refine=False)))
            self.assertNotEqual(base, RL.config_sha(load(lazy_refine=True)))
            for bad in (1, "yes", 0.5):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(lazy_refine=bad)
            p = Path(d) / "c.yaml"
            p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
            self.assertTrue(RL.load_config(p, ["lazy_refine=true"], smoke=False)["lazy_refine"])   # an override


if __name__ == "__main__":
    unittest.main()
