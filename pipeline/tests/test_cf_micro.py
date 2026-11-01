"""
(``B["cf"]`` True: no KL, no entropy monitor, no value target in minibatch_loss), the accumulated micro-batches give the same
loss, gradient and monitors as one forward of the whole minibatch. Without cf rows nothing changed (test_learner_fast_accum).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_cf_micro -v
"""
from __future__ import annotations

import copy
import unittest

import numpy as np
import torch

from pipeline import rl_royale as RL
from pipeline.tests import test_learner_fast_accum as ACC
from pipeline.tests.test_rl_royale import TAU, T


class TestCfMicro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ACC.TestMicroBatch.setUpClass()
        cls.model, cls.R = ACC.TestMicroBatch.model, ACC.TestMicroBatch.R
        cls.B = dict(ACC.TestMicroBatch.B)
        n = len(cls.B["A"])
        cf = torch.zeros(n, dtype=torch.bool)
        cf[n - n // 3:] = True                                # the last third play the alternative rows
        cls.B["cf"] = cf

    def grads(self, m0, idx, kw, micro):
        m = copy.deepcopy(m0)
        if micro is None:
            loss, st = RL.minibatch_loss(m, self.B, self.R, idx, n_total=len(self.B["A"]), **kw)
            loss.backward()
        else:
            loss, st = RL.accum_backward(m, self.B, self.R, idx, micro, len(self.B["A"]), kw)
        return float(loss.detach()), st, [torch.zeros_like(p) if p.grad is None else p.grad.clone() for p in m.parameters()]

    def test_accumulated_equals_whole_minibatch_with_cf_rows(self):
        m0 = copy.deepcopy(self.model)
        with torch.no_grad():                                 # off the ref: the KL term has a gradient
            for q in m0.parameters():
                q.add_(0.02 * torch.randn(q.shape, generator=torch.Generator().manual_seed(q.numel())))
        n = len(self.B["A"])
        idx = torch.from_numpy(np.random.default_rng(1).permutation(n)[:60])   # real and cf rows mixed
        self.assertTrue(bool(self.B["cf"][idx].any()) and bool((~self.B["cf"][idx]).any()))
        for vf in (None, ACC.VF):
            kw = dict(tau=TAU, T=T, clip=0.2, beta=0.5, vf=vf, T_gate=None)
            l0, s0, g0 = self.grads(m0, idx, kw, None)
            for micro in (5, 7):
                l1, s1, g1 = self.grads(m0, idx, kw, micro)
                self.assertAlmostEqual(l1, l0, delta=1e-5 * abs(l0))
                for a, b in zip(g0, g1):
                    torch.testing.assert_close(b, a, rtol=1e-5, atol=1e-7)
                for k in ("kl_gate", "kl_card", "kl_cell", "l_pg", "ratio_mean", "clip_frac", "ent_gate", "ent_card",
                          "ent_cell") + (("l_v",) if vf else ()):
                    self.assertAlmostEqual(s1[k], s0[k], delta=1e-6 * max(1.0, abs(s0[k])), msg=f"{k} micro {micro}")

    def test_ppo_update_accepts_cf_rows_with_micro_batch(self):
        cfg = {"minibatch": 32, "micro_batch": 8, "ppo_epochs": 1, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}
        m = copy.deepcopy(self.model)
        out = RL.ppo_update(m, torch.optim.SGD(m.parameters(), lr=1e-2), self.B, self.R, cfg, 0.0, np.random.default_rng(0))
        self.assertIsNone(out["nonfinite"])
        self.assertGreater(out["steps"], 0)


if __name__ == "__main__":
    unittest.main()
