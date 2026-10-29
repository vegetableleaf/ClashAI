"""OPP-LEARN-D ``timing_pg``: the P2 opponent learner's timing head (slot hazard + tick) gets a policy gradient.

    icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_opp_timing_pg.py

On test_league's fake self-play env (test_opp_learner's tiny timing + ability GenModel): (0) without the key the timing
head gets NO gradient from the loss even when it is not frozen (what the calibration arms ran); the rollout with th_pg
is the same rollout (every other traj key byte-identical) + lp_th = the taken slot decision's log-prob; collate keeps
the slot-start rows with their own w_th while the play rows keep the play-only batch's weights; policy_terms recomputes
lp_th (the update-0 on-policy check); the loss = the off loss + l_th, card / cell monitors unchanged, the timing head
now trains; ppo_update takes the play-only batch's step count; absent key = config hash / actor cfg unchanged.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_league import _cfg, _run, _spec, _tiny_gen, VOCAB   # noqa: E402
from pipeline.tests.test_opp_learner import SIM, _AbEnv, _opp_model       # noqa: E402

KW = dict(tau=0.3, T=1.0, clip=0.2, beta=0.1)


def _rollout(model, th_pg, n=2):
    jobs = [(i, _spec(i, "o", i % 2), 0, {"rollout_index": 0, "update": 0}) for i in range(n)]
    res, _ = _run(jobs, E.GenPolicy(model, VOCAB, SIM), {"o": (E.GenPolicy(_tiny_gen(12), VOCAB), _cfg("sample", record=False))},
                  _cfg(T=1.0, th_learner=True, **({"th_pg": True} if th_pg else {})), make_env=lambda: _AbEnv(tail=600), n=n)
    return res


def _B(res):
    return RL.to_device(RL.collate(res)[0], "cpu")


class TestTimingPG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _opp_model(3)
        cls.off, cls.on = _rollout(cls.model, False), _rollout(cls.model, True)
        cls.Boff, cls.Bon = _B(cls.off), _B(cls.on)

    def test_off_the_timing_head_gets_no_gradient(self):
        """(a) the calibration arms' loss: lp_gate 0, PPO on card / cell only -> no gradient on timing_head even unfrozen."""
        model = copy.deepcopy(self.model)
        B = dict(self.Boff, A=torch.linspace(-1.0, 1.0, len(self.Boff["A"]), dtype=torch.float64))
        with torch.no_grad():
            for q in model.parameters():
                q.add_(0.01 * torch.randn_like(q))
        R = RL.ref_terms(self.model, B, 0.3, 1.0)
        loss, _ = RL.minibatch_loss(model, B, R, torch.arange(len(B["A"])), n_total=len(B["A"]), **KW)
        loss.backward()
        for n, q in model.named_parameters():
            if n.startswith("timing_head."):
                self.assertTrue(q.grad is None or float(q.grad.abs().sum()) == 0.0, n)
        self.assertGreater(float(model.card_q.weight.grad.abs().sum()), 0.0)

    def test_rollout_unchanged_plus_lp_th(self):
        for a, b in zip(self.off, self.on):
            ta, tb = a["traj"], b["traj"]
            self.assertEqual(set(tb) - set(ta), {"lp_th"})
            self.assertEqual(a["outcome"], b["outcome"])
            for k in ta:
                self.assertEqual(np.asarray(ta[k]).tobytes(), np.asarray(tb[k]).tobytes(), k)
            j, lt = tb["th_j"], tb["lp_th"]
            self.assertTrue((lt[j < -1] == 0).all())
            self.assertTrue((lt[j >= -1] < 0).all())
            self.assertGreater(int((j == -1).sum()), int((j >= 0).sum()))      # waits outnumber plays (h ~ .4)

    def test_collate_weights_and_recompute(self):
        Boff, Bon = self.Boff, self.Bon
        pl, sl = Bon["played"], Bon["th_j"] >= -1
        self.assertTrue(bool((pl | sl).all()))
        self.assertEqual(int(pl.sum()), len(Boff["A"]))
        for k in ("w", "lp_old", "lp_card", "lp_cell", "slot", "cell", "A"):     # the play rows = the off batch's, bitwise
            self.assertTrue(torch.equal(Bon[k][pl], Boff[k]), k)
        self.assertTrue(bool((Bon["w"][~pl] == 0).all()) and bool((Bon["w_th"][~sl] == 0).all()))
        M = len(set(Bon["match"].tolist()))
        for m in set(Bon["match"].tolist()):
            r = Bon["match"] == m
            self.assertAlmostEqual(float(Bon["w_th"][r].sum()), 1.0 / M, places=12)
        with torch.no_grad():
            t = RL.policy_terms(self.model, Bon, torch.arange(len(Bon["A"])), 0.3, 1.0)
        self.assertLess(float((t["lp_th"] - Bon["lp_th"]).abs().max()), 1e-5)
        self.assertEqual(float(t["lp_th"][~sl].abs().max()), 0.0)
        for k in ("lp_card", "lp_cell"):
            self.assertLess(float((t[k] - Bon[k]).abs().max()), 1e-5, k)

    def test_k_rows_per_match(self):
        """timing_pg K: K slot rows per match (uniform, fixed by the row key), w_th 1 / (K M); play rows unchanged."""
        B1, B2 = (RL.to_device(RL.collate(self.on, timing_rows=5)[0], "cpu") for _ in range(2))
        for k in B1:
            if torch.is_tensor(B1[k]):
                self.assertTrue(torch.equal(B1[k], B2[k]), k)
        pl, ts = B1["played"], B1["w_th"] > 0
        self.assertTrue(bool((pl | ts).all()))
        for k in ("w", "lp_old", "A"):
            self.assertTrue(torch.equal(B1[k][pl], self.Boff[k]), k)
        M = len(set(B1["match"].tolist()))
        for m in set(B1["match"].tolist()):
            r = B1["match"] == m
            self.assertEqual(int(ts[r].sum()), 5)
            self.assertAlmostEqual(float(B1["w_th"][r].sum()), 1.0 / M, places=12)
        self.assertTrue(bool((B1["th_j"][ts] >= -1).all()))
        self.assertLess(len(B1["A"]), len(self.Bon["A"]))
        R = RL.ref_terms(self.model, B1, 0.3, 1.0)
        _, st = RL.minibatch_loss(self.model, B1, R, torch.arange(len(B1["A"])), n_total=len(B1["A"]), **KW)
        self.assertEqual(st["th_n"], 5 * M)
        self.assertLess(st["th_ratio_maxdev"], 1e-4)
        cfg = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", ["timing_pg=32"], False)
        self.assertEqual(cfg["timing_pg"], 32)
        self.assertNotEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "timing_pg": True}))

    def test_loss_adds_l_th_and_trains_the_timing_head(self):
        model = copy.deepcopy(self.model)
        with torch.no_grad():
            for q in model.parameters():
                q.add_(0.01 * torch.randn_like(q))
        g = torch.Generator().manual_seed(1)
        Aoff = torch.randn(len(self.Boff["A"]), generator=g, dtype=torch.float64)
        Bon = dict(self.Bon)
        Bon["A"] = self.Bon["A"].clone()
        Bon["A"][self.Bon["played"]] = Aoff                  # the same A on the play rows; random on the timing rows
        Bon["A"][~self.Bon["played"]] = torch.randn(int((~self.Bon["played"]).sum()), generator=g, dtype=torch.float64)
        Boff = dict(self.Boff, A=Aoff)
        Ron, Roff = RL.ref_terms(self.model, Bon, 0.3, 1.0), RL.ref_terms(self.model, Boff, 0.3, 1.0)
        on = RL.minibatch_loss(model, Bon, Ron, torch.arange(len(Bon["A"])), n_total=len(Bon["A"]), **KW)
        off = RL.minibatch_loss(model, Boff, Roff, torch.arange(len(Boff["A"])), n_total=len(Boff["A"]), **KW)
        for k in ("l_pg", "kl_card", "kl_cell", "ratio_mean", "ratio_maxdev", "clip_frac"):
            self.assertAlmostEqual(on[1][k], off[1][k], places=10, msg=k)
        self.assertAlmostEqual(float(on[0] - off[0]), on[1]["l_th"], places=10)
        self.assertNotIn("l_th", off[1])
        self.assertGreater(on[1]["th_ratio_maxdev"], 0.0)
        self.assertEqual(on[1]["th_n"], int((Bon["w_th"] > 0).sum()))
        model.zero_grad()
        on[0].backward()
        self.assertGreater(float(model.timing_head.weight.grad.abs().sum()), 0.0)

    def test_on_policy_at_init_and_step_count(self):
        R = RL.ref_terms(self.model, self.Bon, 0.3, 1.0)
        _, st = RL.minibatch_loss(self.model, self.Bon, R, torch.arange(len(self.Bon["A"])), n_total=len(self.Bon["A"]), **KW)
        self.assertLess(st["th_ratio_maxdev"], 1e-4)
        self.assertLess(st["lp_maxdiff"]["lp_th"], 1e-5)
        cfg = {"minibatch": 16, "ppo_epochs": 2, "tau": 0.3, "T": 1.0, "clip": 0.2, "grad_clip": 0.5, "lr": 1e-3}
        steps = []
        for B in (self.Boff, self.Bon):
            m = copy.deepcopy(self.model)
            out = RL.ppo_update(m, torch.optim.Adam(m.parameters(), lr=1e-3), B, RL.ref_terms(self.model, B, 0.3, 1.0),
                                cfg, 0.1, np.random.default_rng(0))
            steps.append(out["steps"])
        self.assertEqual(steps[0], steps[1])
        self.assertEqual(out["th_n"], int((self.Bon["th_j"] >= -1).sum()))
        self.assertIsNotNone(out["l_th"])

    def test_micro_batch_equals_whole_minibatch_with_kl_pulls(self):
        """accum_backward weights each micro-batch's KL / th_anchor means by its row share (beta > 0): the same update."""
        cfg = {"minibatch": 1000, "ppo_epochs": 1, "tau": 0.3, "T": 1.0, "clip": 0.2, "grad_clip": 1e9, "lr": 1e-2,
               "th_anchor": 10.0}
        out = []
        for mi in (None, 37):
            m = copy.deepcopy(self.model)
            with torch.no_grad():
                for q in m.parameters():
                    q.add_(0.01 * torch.randn(q.shape, generator=torch.Generator().manual_seed(q.numel())))
            st = RL.ppo_update(m, torch.optim.SGD(m.parameters(), lr=1e-2), self.Bon, RL.ref_terms(self.model, self.Bon, 0.3, 1.0),
                               {**cfg, "micro_batch": mi}, 0.3, np.random.default_rng(0), th_ref=self.model)
            out.append((m, st))
        self.assertEqual(out[0][1]["steps"], out[1][1]["steps"])
        for a, b in zip(out[0][0].parameters(), out[1][0].parameters()):
            torch.testing.assert_close(b, a, rtol=1e-5, atol=1e-7)

    def test_absent_key_unchanged(self):
        cfg = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", [], False)
        self.assertEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "timing_pg": None}))
        self.assertNotEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "timing_pg": True}))
        base = {"tau": 0.3, "afford_mask": True, "stall_elixir": 9.0, "stall_seconds": 12.0, "obs": "clean",
                "grid": "lattice", "decide_every": 10, "T": 1.0, "opp_init": "x.pt"}
        self.assertNotIn("th_pg", RL.actor_cfg(base, "rollout", 0, "cpu"))
        self.assertTrue(RL.actor_cfg({**base, "timing_pg": True}, "rollout", 0, "cpu")["th_pg"])
        self.assertNotIn("th_pg", RL.actor_cfg({**base, "timing_pg": True}, "screen", 0, "cpu"))
        self.assertTrue(E.timing_cfg(_cfg("sample", record=True, th_learner=True, th_pg=True))["th_pg"])
        cfg2 = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", ["timing_pg=true"], False)
        self.assertIs(cfg2["timing_pg"], True)


if __name__ == "__main__":
    unittest.main()
