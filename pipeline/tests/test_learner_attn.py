"""LEARNER-SPEED ticket A (pipeline/learner_attn.py ``split_attn``): SplitMHA = nn.MultiheadAttention exactly.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_learner_attn -v

1. Both encoder shapes the models use (model_v3 trunk: d 16-128, 4 heads, ff 4d; model_gen memory: d 64, ff 2d, nested off),
   random padding (incl. a fully padded tail and a row with only the first token valid): forward bitwise equal, every
   parameter gradient and the input gradient bitwise equal; no_grad forward bitwise equal (it IS the original path).
2. A real minibatch_loss + backward on test_rl_royale's tiny S1Model with sampler-made trajectories (value loss on):
   loss and every gradient bitwise equal, the policy weights after 3 PPO updates bitwise equal.
3. use_split_attn keeps the state_dict keys / bytes and deepcopy keeps the class; config validation + historical hash.
On CUDA (if present) test 1 also runs on the GPU. ``--real`` records on a pod: lrn/../lspeed/attn_gate.py.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from pipeline import rl_royale as RL
from pipeline.learner_attn import SplitMHA, use_split_attn
from pipeline.tests.test_learner_fast_accum import BASE, REPO, VF, TestMicroBatch


def _encoder(d, ff, layers, nested, seed):
    torch.manual_seed(seed)
    layer = nn.TransformerEncoderLayer(d, 4, ff, dropout=0.0, batch_first=True, norm_first=True)
    return nn.TransformerEncoder(layer, layers, enable_nested_tensor=nested).eval()


def _pad(B, L, seed):
    g = torch.Generator().manual_seed(seed)
    n = torch.randint(1, L + 1, (B,), generator=g)
    n[0], n[-1] = 1, L
    return torch.arange(L)[None, :] >= n[:, None]               # True = padded


class TestSplitMHA(unittest.TestCase):
    def _cmp(self, dev):
        for d, ff, layers, nested, L in ((16, 64, 2, True, 9), (128, 512, 4, True, 40), (64, 128, 2, False, 17)):
            ref = _encoder(d, ff, layers, nested, 1).to(dev)
            new = copy.deepcopy(ref)
            self.assertEqual(use_split_attn(new), layers)
            x0 = torch.randn(7, L, d, generator=torch.Generator().manual_seed(2)).to(dev)
            pad = _pad(7, L, 3).to(dev)
            outs = []
            for m in (ref, new):
                x = x0.clone().requires_grad_(True)
                y = m(x, src_key_padding_mask=pad)
                (y.sin() * torch.linspace(-1, 1, d, device=dev)).sum().backward()
                outs.append((y.detach(), x.grad, [p.grad for p in m.parameters()]))
                with torch.no_grad():
                    outs[-1] += (m(x0, src_key_padding_mask=pad),)
            (y0, gx0, gp0, n0), (y1, gx1, gp1, n1) = outs
            msg = f"{dev} d {d}"
            self.assertTrue(torch.equal(y0, y1), msg)
            self.assertTrue(torch.equal(gx0, gx1), msg)
            for a, b in zip(gp0, gp1):
                self.assertTrue(torch.equal(a, b), msg)
            self.assertTrue(torch.equal(n0, n1), msg)

    def test_encoder_cpu(self):
        self._cmp("cpu")

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA")
    def test_encoder_cuda(self):                                # the learner's settings: deterministic, fp32 (TF32 off)
        old = (torch.are_deterministic_algorithms_enabled(), torch.backends.cuda.matmul.allow_tf32,
               torch.backends.cudnn.allow_tf32)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
        try:
            self._cmp("cuda")
        finally:
            torch.use_deterministic_algorithms(old[0])
            torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = old[1], old[2]

    def test_state_dict_and_deepcopy(self):
        ref = _encoder(16, 64, 2, True, 4)
        new = copy.deepcopy(ref)
        use_split_attn(new)
        a, b = ref.state_dict(), new.state_dict()
        self.assertEqual(list(a), list(b))
        self.assertTrue(all(torch.equal(a[k], b[k]) for k in a))
        self.assertIs(type(copy.deepcopy(new).layers[0].self_attn), SplitMHA)
        self.assertEqual(use_split_attn(new), 0)                # idempotent


class TestSplitMHALoss(unittest.TestCase):
    setUpClass = classmethod(TestMicroBatch.setUpClass.__func__)   # tiny S1Model + sampler-made trajectories
    pbytes = staticmethod(TestMicroBatch.pbytes)

    def test_minibatch_loss_gradients(self):
        new = copy.deepcopy(self.model)
        self.assertEqual(use_split_attn(new), 1)
        idx = torch.arange(0, len(self.B["A"]), 2)
        res = []
        for m in (self.model, new):
            m.zero_grad(set_to_none=True)
            loss, st = RL.minibatch_loss(m, self.B, self.R, idx, tau=BASE["tau"], T=BASE["T"], clip=0.2, beta=0.1,
                                         n_total=len(self.B["A"]), vf=VF)
            loss.backward()
            res.append((loss.detach(), [p.grad for p in m.parameters()], st))
        self.assertTrue(torch.equal(res[0][0], res[1][0]))
        for a, b in zip(res[0][1], res[1][1]):
            self.assertTrue((a is None and b is None) or torch.equal(a, b))
        self.assertEqual(res[0][2], res[1][2])
        self.model.zero_grad(set_to_none=True)

    def test_ppo_updates(self):
        outs = []
        for split in (False, True):
            m = copy.deepcopy(self.model)
            if split:
                use_split_attn(m)
            opt = torch.optim.Adam(m.parameters(), lr=1e-2)
            out = RL.ppo_update(m, opt, self.B, self.R, BASE, 0.1, np.random.default_rng(0), vf=VF)
            outs.append((out["steps"], self.pbytes(m)))
        self.assertEqual(outs[0], outs[1])

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            h = RL.config_sha(load())
            self.assertEqual(h, RL.config_sha(load(split_attn=None)))
            self.assertEqual(h, RL.config_sha(load(split_attn=False)))
            self.assertNotEqual(h, RL.config_sha(load(split_attn=True)))
            for bad in (1, "true", 0.5):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(split_attn=bad)


del TestMicroBatch                                            # imported for its fixtures; it runs in its own file

if __name__ == "__main__":
    unittest.main()
