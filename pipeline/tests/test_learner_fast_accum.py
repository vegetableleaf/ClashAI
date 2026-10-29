"""LEARNER-SCALE ``micro_batch`` (rl_royale.accum_backward via _ppo_steps): a minibatch computed in micro-batches with
gradient accumulation is the same update as one forward of the whole minibatch (fp32 summation order aside); off
(absent / null / >= minibatch) = byte-identical; kl_stop_prev fires at the same minibatch.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_learner_fast_accum -v

Real minibatch_loss on test_rl_royale's tiny S1Model and its sampler-made trajectories (no engine, no GPU), with and
without the clipped value loss.
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

import torch                                                    # noqa: E402

from pipeline import rl_royale as RL                            # noqa: E402
from pipeline.tests.test_rl_royale import TAU, T, _results, _tiny_model   # noqa: E402

torch.set_default_dtype(torch.float32)
BASE = {"minibatch": 16, "ppo_epochs": 3, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}
VF = {"coef": 0.5, "clip": 0.2, "policy": True, "trunk_grad": True}
MON = ("kl_gate", "kl_card", "kl_cell", "l_pg", "ratio_mean", "clip_frac", "grad_norm_mean")


class TestMicroBatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(1)
        res = _results(cls.model, [(0, 0, 40, "win"), (0, 1, 35, "loss"), (1, 0, 30, "draw"), (1, 1, 25, "win")], seed=3)
        Bn, _ = RL.collate(res)
        cls.B = RL.to_device(Bn, "cpu")
        g = torch.Generator().manual_seed(5)
        cls.B["v_old"] = torch.randn(len(cls.B["A"]), generator=g, dtype=torch.float64) * 0.1
        cls.B["ret"] = torch.randn(len(cls.B["A"]), generator=g, dtype=torch.float64) * 0.5
        ref = copy.deepcopy(cls.model).eval()
        for p in ref.parameters():
            p.requires_grad_(False)
        cls.R = RL.ref_terms(ref, cls.B, TAU, T)

    def run_update(self, cfg, vf=None, lr=1e-2, sgd=False):
        """sgd: the identity checks use SGD. Adam turns fp32-noise-sized gradients of parameters whose true gradient is 0
        (unused rows / heads of the tiny model) into steps of ~0.1 lr (m / (sqrt(v) + eps), eps 1e-8), so after a few
        steps Adam's weights differ by O(lr) on those parameters although every gradient agrees to ~1e-7 relative."""
        model = copy.deepcopy(self.model)
        opt = (torch.optim.SGD if sgd else torch.optim.Adam)(model.parameters(), lr=lr)
        out = RL.ppo_update(model, opt, self.B, self.R, cfg, 0.0, np.random.default_rng(0), vf=vf)
        return out, model

    @staticmethod
    def pbytes(m):
        return b"".join(p.detach().numpy().tobytes() for p in m.parameters())

    def test_off_is_byte_identical(self):
        for vf in (None, VF):
            off, m_off = self.run_update(dict(BASE), vf)
            for mi in (None, 16, 64):                         # null, = minibatch, > minibatch: the old path
                on, m_on = self.run_update({**BASE, "micro_batch": mi}, vf)
                self.assertEqual(self.pbytes(m_off), self.pbytes(m_on), msg=f"micro_batch {mi}")
                self.assertEqual(off, on)

    def test_accumulated_equals_whole_minibatch(self):
        for vf in (None, VF):
            for mb in (16, 64):                               # 64: one minibatch spans matches
                cfg = {**BASE, "minibatch": mb}
                off, m_off = self.run_update(cfg, vf, sgd=True)
                for mi in (1, 3, 4):
                    on, m_on = self.run_update({**cfg, "micro_batch": mi}, vf, sgd=True)
                    self.assertEqual(on["steps"], off["steps"])
                    for a, b in zip(m_off.parameters(), m_on.parameters()):
                        torch.testing.assert_close(b, a, rtol=1e-5, atol=1e-6, msg=f"mb {mb} micro {mi} vf {vf is not None}")
                    keys = MON + (("l_v", "l_v_first") if vf else ())
                    for k in keys:
                        self.assertAlmostEqual(on[k], off[k], delta=1e-5 * max(1.0, abs(off[k])), msg=k)
                    for h in ("gate", "card", "cell"):
                        self.assertAlmostEqual(on["ent"][h], off["ent"][h], delta=1e-6)
                    for k, v in off["first"].items():
                        if isinstance(v, float):
                            self.assertAlmostEqual(on["first"][k], v, delta=1e-6 * max(1.0, abs(v)), msg=k)

    def test_one_minibatch_gradient(self):
        idx = torch.arange(0, 48)
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.0, vf=VF, T_gate=None)
        grads = []
        for mi in (None, 5):
            m = copy.deepcopy(self.model)
            if mi is None:
                loss, st = RL.minibatch_loss(m, self.B, self.R, idx, n_total=len(self.B["A"]), **kw)
                loss.backward()
            else:
                loss, st = RL.accum_backward(m, self.B, self.R, idx, mi, len(self.B["A"]), kw)
            grads.append((float(loss.detach()), st, [torch.zeros_like(p) if p.grad is None else p.grad.clone() for p in m.parameters()]))
        (l0, s0, g0), (l1, s1, g1) = grads
        self.assertAlmostEqual(l1, l0, delta=1e-5 * abs(l0))
        for a, b in zip(g0, g1):
            torch.testing.assert_close(b, a, rtol=1e-5, atol=1e-7)
        for k in ("kl_gate", "kl_card", "kl_cell", "l_pg", "l_v", "ratio_mean", "ratio_maxdev", "clip_frac",
                  "ent_gate", "ent_card", "ent_cell"):
            self.assertAlmostEqual(s1[k], s0[k], delta=1e-6 * max(1.0, abs(s0[k])), msg=k)
        self.assertEqual(s1["n"], s0["n"])
        for h in s0["lp_maxdiff"]:
            self.assertAlmostEqual(s1["lp_maxdiff"][h], s0["lp_maxdiff"][h], delta=1e-9)

    def test_one_minibatch_gradient_with_kl_pull(self):
        """beta > 0 (OPP-LEARN-D fix): each micro-batch's KL means count by its row share, so the KL term's gradient is
        the whole minibatch's (before the fix it was summed per micro-batch = x the micro-batch count)."""
        m0 = copy.deepcopy(self.model)
        with torch.no_grad():                                 # off the ref: the KL term has a gradient
            for q in m0.parameters():
                q.add_(0.02 * torch.randn(q.shape, generator=torch.Generator().manual_seed(q.numel())))
        idx = torch.arange(0, 48)
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.5, vf=None, T_gate=None)
        grads = []
        for mi in (None, 5):
            m = copy.deepcopy(m0)
            if mi is None:
                loss, _ = RL.minibatch_loss(m, self.B, self.R, idx, n_total=len(self.B["A"]), **kw)
                loss.backward()
            else:
                loss, _ = RL.accum_backward(m, self.B, self.R, idx, mi, len(self.B["A"]), kw)
            grads.append([torch.zeros_like(p) if p.grad is None else p.grad.clone() for p in m.parameters()])
        for a, b in zip(*grads):
            torch.testing.assert_close(b, a, rtol=1e-5, atol=1e-7)

    def test_kl_stop_same_minibatch(self):
        cfg = {**BASE, "minibatch": 32}
        free, _ = self.run_update(cfg)
        lim = 0.5 * free["kl_gate"] + 0.5 * free["kl_card"] + 0.5 * free["kl_cell"]
        off, _ = self.run_update({**cfg, "kl_stop_prev": lim})
        on, _ = self.run_update({**cfg, "kl_stop_prev": lim, "micro_batch": 7})
        self.assertIsNotNone(off["kl_stop"])
        self.assertEqual((on["kl_stop"]["epoch"], on["kl_stop"]["minibatch"], on["steps"]),
                         (off["kl_stop"]["epoch"], off["kl_stop"]["minibatch"], off["steps"]))
        self.assertAlmostEqual(on["kl_stop"]["kl"], off["kl_stop"]["kl"], delta=1e-6)

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            self.assertEqual(RL.config_sha(load()), RL.config_sha(load(micro_batch=None)))
            self.assertNotEqual(RL.config_sha(load()), RL.config_sha(load(micro_batch=512)))
            for bad in (0, -1, 1.5, True, "512"):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(micro_batch=bad)


if __name__ == "__main__":
    unittest.main()
