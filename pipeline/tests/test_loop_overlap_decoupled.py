"""LOOP-ASYNC ``ppo_decoupled`` (rl_royale.minibatch_loss: Hilton et al. 2021 decoupled PPO for the one-version-stale
fastloop --overlap 1 rows), on test_rl_royale's tiny S1Model and its sampler-made trajectories (no engine, no GPU).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_loop_overlap_decoupled -v

absent / null = byte-identical updates and the historical config hash; on-policy rows (lp_old = the update-start
policy's own lps) = today's loss exactly (bitwise, every step, any c); prox_lp = policy_terms of the anchor bit for bit;
stale rows = the decoupled formula with the importance weight truncated at c; micro_batch merges its monitors."""
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


class TestDecoupled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(1)
        res = _results(cls.model, [(0, 0, 40, "win"), (0, 1, 35, "loss"), (1, 0, 30, "draw"), (1, 1, 25, "win")], seed=3)
        Bn, _ = RL.collate(res)
        cls.B = RL.to_device(Bn, "cpu")
        g = torch.Generator().manual_seed(5)
        cls.B["v_old"] = torch.randn(len(cls.B["A"]), generator=g, dtype=torch.float64) * 0.1
        cls.B["ret"] = torch.randn(len(cls.B["A"]), generator=g, dtype=torch.float64) * 0.5
        cls.ref = copy.deepcopy(cls.model).eval()
        for p in cls.ref.parameters():
            p.requires_grad_(False)
        cls.R = RL.ref_terms(cls.ref, cls.B, TAU, T)
        cls.N = len(cls.B["A"])
        cls.lpp = RL.prox_lp(cls.R, cls.B, torch.arange(cls.N))
        cls.B_on = {**cls.B, "lp_old": cls.lpp.clone()}      # rows played by the update-start policy itself
        noise = torch.randn(cls.N, generator=g, dtype=torch.float64) * 0.6
        cls.B_st = {**cls.B, "lp_old": cls.lpp + noise}      # one version stale: behaviour != update-start

    def run_update(self, cfg, B, vf=None):
        model = copy.deepcopy(self.model)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        out = RL.ppo_update(model, opt, B, self.R, cfg, 0.0, np.random.default_rng(0), vf=vf)
        return out, b"".join(p.detach().numpy().tobytes() for p in model.parameters())

    def test_prox_lp_is_policy_terms(self):
        t = RL.policy_terms(self.ref, self.B, torch.arange(self.N), TAU, T)
        self.assertTrue(torch.equal(self.lpp, t["lp_gate"] + t["lp_card"] + t["lp_cell"]))
        idx = torch.tensor([5, 0, 17, 3, 40])                  # any row order / subset
        self.assertTrue(torch.equal(RL.prox_lp(self.R, self.B, idx), self.lpp[idx]))

    def test_absent_and_null_byte_identical(self):
        for vf in (None, VF):
            off, b_off = self.run_update(dict(BASE), self.B, vf)
            on, b_on = self.run_update({**BASE, "ppo_decoupled": None}, self.B, vf)
            self.assertEqual(b_off, b_on)
            self.assertEqual(off, on)

    def test_on_policy_rows_are_todays_loss(self):
        for vf in (None, VF):
            for c in (1.0, 2.0):
                off, b_off = self.run_update(dict(BASE), self.B_on, vf)
                on, b_on = self.run_update({**BASE, "ppo_decoupled": c}, self.B_on, vf)
                self.assertEqual(b_off, b_on, msg=f"c {c} vf {vf is not None}")
                d = on.pop("decoupled")
                extra = {k: on["first"].pop(k) for k in ("is_maxdev", "is_trunc_frac")}
                self.assertEqual(off, on)                     # every monitor of today's loss, exactly
                self.assertEqual(extra, {"is_maxdev": 0.0, "is_trunc_frac": 0.0})
                self.assertEqual((d["c"], d["is_maxdev_first"], d["is_trunc_frac_ep0"]), (c, 0.0, 0.0))

    def test_stale_formula_and_truncation(self):
        idx = torch.arange(0, 48)
        c = 1.5
        m = copy.deepcopy(self.model)
        loss, st = RL.minibatch_loss(m, self.B_st, self.R, idx, tau=TAU, T=T, clip=0.2, beta=0.0, n_total=self.N,
                                     decoupled=c)
        t = RL.policy_terms(self.model, self.B_st, idx, TAU, T)
        lp = t["lp_gate"] + t["lp_card"] + t["lp_cell"]
        r = torch.exp(lp - self.lpp[idx])
        w_is = torch.exp(self.lpp[idx] - self.B_st["lp_old"][idx])
        A, w = self.B_st["A"][idx], self.B_st["w"][idx]
        ref = (w * -(w_is.clamp(max=c) * torch.min(r * A, r.clamp(0.8, 1.2) * A))).sum() * (self.N / len(idx))
        torch.testing.assert_close(loss.detach(), ref.detach(), rtol=1e-12, atol=1e-12)
        self.assertGreater(float(w_is.max()), c)              # the cap binds on this batch
        self.assertAlmostEqual(st["is_trunc_frac"], float((w_is > c).double().mean()))
        self.assertAlmostEqual(st["is_maxdev"], float((w_is - 1).abs().max()))
        self.assertAlmostEqual(st["ratio_maxdev"], float((r - 1).abs().max()))
        loss_off, _ = RL.minibatch_loss(copy.deepcopy(self.model), self.B_st, self.R, idx, tau=TAU, T=T, clip=0.2,
                                        beta=0.0, n_total=self.N)
        self.assertNotAlmostEqual(float(loss_off), float(loss), places=6)   # the key does act on stale rows

    def test_micro_batch_merges(self):
        cfg = {**BASE, "ppo_decoupled": 2.0}
        a, _ = self.run_update(cfg, self.B_st)
        b, _ = self.run_update({**cfg, "micro_batch": 5}, self.B_st)
        self.assertEqual(a["steps"], b["steps"])
        self.assertAlmostEqual(a["decoupled"]["is_maxdev_first"], b["decoupled"]["is_maxdev_first"], delta=1e-9)
        self.assertAlmostEqual(a["decoupled"]["is_trunc_frac_ep0"], b["decoupled"]["is_trunc_frac_ep0"], delta=1e-9)

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            self.assertEqual(RL.config_sha(load()), RL.config_sha(load(ppo_decoupled=None)))
            ok = load(ppo_decoupled=2.0, kl_ref_refresh_every=1)
            self.assertNotEqual(RL.config_sha(load(kl_ref_refresh_every=1)), RL.config_sha(ok))
            for bad in (0.5, 0, -1, True, "2", float("inf")):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(ppo_decoupled=bad, kl_ref_refresh_every=1)
            with self.assertRaises(SystemExit):
                load(ppo_decoupled=2.0)                         # the anchor must be the update-start policy
            with self.assertRaises(SystemExit):
                load(ppo_decoupled=2.0, kl_ref_refresh_every=2)


if __name__ == "__main__":
    unittest.main()
