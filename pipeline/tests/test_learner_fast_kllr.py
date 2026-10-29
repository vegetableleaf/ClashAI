"""LEARNER-SCALE ``kl_lr_target`` (rl_royale._ppo_steps): the policy step's lr is steered toward a per-step KL target
(lr x clamp(sqrt(min(target, cap - KL) / KL added by the last step), 0.5, 1.25), bounded to [lr / 16, 16 lr]); absent / null = byte-identical;
no effect in the critic warm-up (vf policy False).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_learner_fast_kllr -v
"""
from __future__ import annotations

import copy
import math
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
from pipeline.tests import test_learner_fast_accum as ACC   # noqa: E402

BASE, VF = ACC.BASE, ACC.VF

LR0 = 1e-2


class TestKlLr(unittest.TestCase):
    setUpClass = classmethod(ACC.TestMicroBatch.setUpClass.__func__)
    pbytes = staticmethod(ACC.TestMicroBatch.pbytes)

    def run_update(self, cfg, vf=None, record=False):
        model = copy.deepcopy(self.model)
        opt = torch.optim.Adam(model.parameters(), lr=LR0)
        seen = []
        if record:                                            # the lr of every step and the KL its minibatch measured
            real = opt.step

            def step(*a, **k):
                seen.append(opt.param_groups[0]["lr"])
                return real(*a, **k)
            opt.step = step
        out = RL.ppo_update(model, opt, self.B, self.R, {**cfg, "lr": LR0}, 0.0, np.random.default_rng(0), vf=vf)
        return out, model, opt, seen

    def test_off_is_byte_identical(self):
        for vf in (None, VF):
            off, m_off, _, _ = self.run_update(dict(BASE), vf)
            on, m_on, _, _ = self.run_update({**BASE, "kl_lr_target": None}, vf)
            self.assertEqual(self.pbytes(m_off), self.pbytes(m_on))
            self.assertEqual(off, on)

    def test_warmup_untouched(self):
        warm = {**VF, "policy": False}
        off, m_off, _, _ = self.run_update(dict(BASE), warm)
        on, m_on, opt, _ = self.run_update({**BASE, "kl_lr_target": 1e-9}, warm)
        self.assertEqual(self.pbytes(m_off), self.pbytes(m_on))
        self.assertEqual(opt.param_groups[0]["lr"], LR0)
        self.assertNotIn("lr_end", on)

    def test_steers_and_bounds(self):
        # the rule, replayed from the KLs the run measured: lr_t = clamp(lr_{t-1} x clamp(sqrt(ka / dKL), .5, 1.25))
        kls = []
        real = RL.minibatch_loss

        def spy(*a, **k):
            loss, st = real(*a, **k)
            kls.append(float(st["kl_gate"] + st["kl_card"] + st["kl_cell"]))
            return loss, st
        RL.minibatch_loss = spy
        try:
            for ka in (1e-9, 1e-4, 1e3):
                kls.clear()
                out, _, opt, seen = self.run_update({**BASE, "kl_lr_target": ka}, None, record=True)
                lr, want = LR0, []
                for t, kn in enumerate(kls):
                    if t:
                        g = min(1.25, max(0.5, math.sqrt(ka / max(kn - kls[t - 1], ka * 1e-2))))
                        lr = min(max(lr * g, LR0 / 16), LR0 * 16)
                    want.append(lr)
                self.assertEqual(seen, want, msg=f"ka {ka}")
                self.assertEqual(out["lr_end"], seen[-1])
                self.assertGreater(len(set(seen)), 1)
        finally:
            RL.minibatch_loss = real
        _, _, _, lo = self.run_update({**BASE, "kl_lr_target": 1e-12, "ppo_epochs": 30}, None, record=True)
        _, _, _, hi = self.run_update({**BASE, "kl_lr_target": 1e6, "ppo_epochs": 30}, None, record=True)
        self.assertTrue(all(LR0 / 16 <= x <= LR0 * 16 for x in lo + hi))
        self.assertAlmostEqual(min(lo), LR0 / 16)                # (a falling KL reads as a tiny step -> x2: lo oscillates)
        self.assertAlmostEqual(hi[-1], LR0 * 16)

    def test_cap_aware(self):
        # with kl_stop_prev ks: each step aims at min(ka, ks - KL) (floor ka / 10), so the last step does not overshoot
        kls, real = [], RL.minibatch_loss

        def spy(*a, **k):
            loss, st = real(*a, **k)
            kls.append(float(st["kl_gate"] + st["kl_card"] + st["kl_cell"]))
            return loss, st
        RL.minibatch_loss = spy
        try:
            self.run_update({**BASE, "kl_lr_target": 1.0}, None)        # the first step's KL sets the scale
            ka = kls[1]
            ks = 4 * ka
            kls.clear()
            out, _, _, seen = self.run_update({**BASE, "kl_lr_target": ka, "kl_stop_prev": ks, "ppo_epochs": 30}, None,
                                              record=True)
        finally:
            RL.minibatch_loss = real
        lr, want = LR0, []
        for t, kn in enumerate(kls[:len(seen)]):
            if t:
                tgt = min(ka, max(ks - kn, ka * 0.1))
                lr = min(max(lr * min(1.25, max(0.5, math.sqrt(tgt / max(kn - kls[t - 1], ka * 1e-2)))), LR0 / 16), LR0 * 16)
            want.append(lr)
        self.assertEqual(seen, want)
        self.assertGreater(len(seen), 1)

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            self.assertEqual(RL.config_sha(load()), RL.config_sha(load(kl_lr_target=None)))
            self.assertNotEqual(RL.config_sha(load()), RL.config_sha(load(kl_lr_target=0.005)))
            for bad in (0, -1.0, True, "0.005", float("inf")):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(kl_lr_target=bad)


if __name__ == "__main__":
    unittest.main()
