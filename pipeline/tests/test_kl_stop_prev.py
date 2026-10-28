"""LOOP-LRN ``kl_stop_prev`` (rl_royale._ppo_steps): the epoch loop stops BEFORE a step whose minibatch KL to the anchor
(kl_gate + kl_card + kl_cell, minibatch_loss's monitors) exceeds the limit; off (absent / null) = the loop unchanged.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_kl_stop_prev -v

Real minibatch_loss on test_rl_royale's tiny S1Model and its sampler-made trajectories (no engine, no GPU).
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

BASE = {"minibatch": 16, "ppo_epochs": 3, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}


class TestKlStopPrev(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(1)
        res = _results(cls.model, [(0, 0, 40, "win"), (0, 1, 35, "loss"), (1, 0, 30, "draw"), (1, 1, 25, "win")], seed=3)
        Bn, _ = RL.collate(res)
        cls.B = RL.to_device(Bn, "cpu")
        ref = copy.deepcopy(cls.model).eval()
        for p in ref.parameters():
            p.requires_grad_(False)
        cls.R = RL.ref_terms(ref, cls.B, TAU, T)              # the anchor = the policy at the update's start

    def run_update(self, cfg, lr=1e-2):
        """-> (monitors, params bytes, the KL sum of every minibatch_loss call in order)."""
        model = copy.deepcopy(self.model)
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        kls, real = [], RL.minibatch_loss

        def spy(*a, **k):
            loss, st = real(*a, **k)
            kls.append(st["kl_gate"] + st["kl_card"] + st["kl_cell"])
            return loss, st
        RL.minibatch_loss = spy
        try:
            out = RL.ppo_update(model, opt, self.B, self.R, cfg, 0.0, np.random.default_rng(0))
        finally:
            RL.minibatch_loss = real
        return out, b"".join(p.detach().numpy().tobytes() for p in model.parameters()), kls

    def test_off_and_never_firing_are_byte_identical(self):
        off, p_off, kl_off = self.run_update(dict(BASE))
        null, p_null, _ = self.run_update({**BASE, "kl_stop_prev": None})
        big, p_big, _ = self.run_update({**BASE, "kl_stop_prev": 1e9})
        self.assertNotIn("kl_stop", off)                      # off: the summary keys unchanged
        self.assertNotIn("kl_stop", null)
        self.assertIsNone(big["kl_stop"])                     # on but never over: every step ran
        n_steps = BASE["ppo_epochs"] * -(-len(self.B["A"]) // BASE["minibatch"])
        self.assertEqual(off["steps"], n_steps)
        self.assertEqual(big["steps"], n_steps)
        self.assertEqual(p_off, p_null)
        self.assertEqual(p_off, p_big)
        self.assertGreater(max(kl_off), 0.0)                  # the policy really moved (a KL to stop on exists)

    def test_stops_exactly_at_the_first_minibatch_over_the_limit(self):
        _, _, kl_off = self.run_update(dict(BASE))
        lim = float(np.quantile(kl_off[1:], 0.5))             # fires mid-run: the first call is 0 (policy == anchor)
        out, p, kls = self.run_update({**BASE, "kl_stop_prev": lim})
        first = next(i for i, x in enumerate(kl_off) if x > lim)
        st = out["kl_stop"]
        self.assertIsNotNone(st)
        self.assertEqual(len(kls), first + 1)                 # same trajectory up to the stop, then no more calls
        self.assertEqual(kls, kl_off[:first + 1])
        self.assertTrue(all(x <= lim for x in kls[:-1]))      # never fired on a minibatch at or under the limit
        self.assertGreater(kls[-1], lim)
        self.assertEqual(out["steps"], first)                 # the over-limit minibatch took no step
        self.assertEqual(st["steps"], first)
        self.assertAlmostEqual(st["kl"], kls[-1], places=12)
        mb = -(-len(self.B["A"]) // BASE["minibatch"])
        self.assertEqual((st["epoch"], st["minibatch"]), divmod(first, mb))
        self.assertIsNotNone(out["kl_gate"])                  # epoch monitors = the steps that ran, never empty
        # the stopped run == a run that never saw the over-limit minibatch: params equal the off run's after `first`
        model = copy.deepcopy(self.model)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        calls = []
        real = RL.minibatch_loss

        def cut(*a, **k):
            calls.append(1)
            if len(calls) > first:
                raise _Cut
            return real(*a, **k)
        RL.minibatch_loss = cut
        try:
            RL.ppo_update(model, opt, self.B, self.R, dict(BASE), 0.0, np.random.default_rng(0))
        except _Cut:
            pass
        finally:
            RL.minibatch_loss = real
        self.assertEqual(p, b"".join(q.detach().numpy().tobytes() for q in model.parameters()))

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            base = load()
            self.assertEqual(RL.config_sha(base), RL.config_sha(load(kl_stop_prev=None)))   # absent == null hash
            on = load(kl_stop_prev=0.02, kl_ref_refresh_every=1)
            self.assertNotEqual(RL.config_sha(on), RL.config_sha(load(kl_ref_refresh_every=1)))
            for bad in ({"kl_stop_prev": 0.02}, {"kl_stop_prev": 0.02, "kl_ref_refresh_every": 50},
                        {"kl_stop_prev": 0, "kl_ref_refresh_every": 1}, {"kl_stop_prev": True, "kl_ref_refresh_every": 1}):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(**bad)


class _Cut(Exception):
    pass


if __name__ == "__main__":
    unittest.main()
