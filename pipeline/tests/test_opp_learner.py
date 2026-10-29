"""OPP-LEARN (REPORT_opponents 3 step 4.3): the P2 opponent model (timing-head GenModel) as the rl_royale LEARNER.

    icebow/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_opp_learner.py

Covers: a timing-head learner seat records rows (e1_eval.th_record) on test_league's fake self-play env, with the
frozen-head labels and the context ids; collate + policy_terms recompute its lp_card / lp_cell exactly (the update-0
on-policy check) and give lp_gate 0; freeze_heads -> the timing / ability heads get NO gradient and stay bit-identical
through Adam steps while the card / cell path trains; the fixed KL pull = beta0 = beta_min = beta_max; absent keys change
nothing (freeze_heads None, the config hash, actor_cfg, timing_cfg's record refusal for a frozen seat).
"""
from __future__ import annotations

import copy
import math
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
from pipeline.model_gen import GenModel                                   # noqa: E402
from pipeline.tests.test_league import _SPEnv, _cfg, _run, _spec, _tiny_gen, VOCAB   # noqa: E402

CTX = {"band": 6, "mode": 8, "era": 4}
SIM = {"ctx": {"band": 1, "mode": 1, "era": 1}, "deck_keys": []}


def _opp_model(seed=0, h=0.4):
    """A tiny timing + ability head GenModel (the P2 opponent architecture); hazard ~h so a fake match has plays."""
    torch.manual_seed(seed)
    m = GenModel(d=16, layers=1, heads=2, d_c=8, n_cards=len(VOCAB), timing=True, ability=True, deck_enc=True,
                 n_decks=2, ctx_tokens=CTX).eval()
    with torch.no_grad():
        m.timing_head.bias[0] = math.log(h / (1 - h))
    return m


class _AbEnv(_SPEnv):
    """+ what th_ability reads: a READY ability button for both sides, presses logged (the fake env has no heroes)."""

    def _scan(self, side, gate):
        return ["button"]

    def queue_abilities(self, side, cmds, delay):
        self.__dict__.setdefault("presses", []).append((self.tick, side, delay))


def _rollout(model, n_matches=2):
    learner = E.GenPolicy(model, VOCAB, SIM)
    jobs = [(i, _spec(i, "o", i % 2), 0, {"rollout_index": 0, "update": 0}) for i in range(n_matches)]
    res, _ = _run(jobs, learner, {"o": (E.GenPolicy(_tiny_gen(12), VOCAB), _cfg("sample", record=False))},
                  _cfg(T=1.0, th_learner=True), make_env=lambda: _AbEnv(tail=600), n=n_matches)
    return res


def _batch(res):
    B, _ = RL.collate(res)
    return RL.to_device(B, "cpu")


class TestRecord(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = _opp_model(3)
        cls.res = _rollout(cls.model)

    def test_rows_carry_labels_and_context(self):
        for r in self.res:
            t = r["traj"]
            for k in ("deck_gid", "ctx_band", "ctx_mode", "ctx_era", "th_j", "th_ab"):
                self.assertIn(k, t)
            pl, j = t["played"], t["th_j"]
            self.assertGreater(int(pl.sum()), 5)
            self.assertFalse(t["gate_sampled"].any())
            self.assertTrue((t["lp_gate"] == 0).all())
            self.assertTrue(((j[pl] >= 0) | (j[pl] == -2)).all())            # a play: at a slot start (j=0) or drawn tick
            self.assertTrue(set(np.unique(j)) <= set(range(-3, 10)))
            self.assertTrue((t["lp_card"][pl] <= 0).all() and (t["lp_cell"][pl] < 0).all())
            self.assertTrue((t["lp_card"][~pl] == 0).all())
            # every drawn tick j > 0 at a slot start is followed by that slot's play / no_affordable row (-2)
            self.assertEqual(int((j > 0).sum()), int((j == -2).sum()))
            ab = t["th_ab"]
            self.assertTrue(((ab == -1) | ((ab >= 0) & (ab < 10))).all() and (ab >= 0).any())
            self.assertTrue((ab[j == -2] == -1).all())                      # presses are drawn at slot starts only

    def test_recompute_matches_the_behaviour_logprobs(self):
        B = _batch(self.res)
        self.assertEqual(int(B["played"].sum()), len(B["A"]))                # only the play rows contribute
        idx = torch.arange(len(B["A"]))
        with torch.no_grad():
            t = RL.policy_terms(self.model, B, idx, tau=0.3, T=1.0)
        self.assertEqual(float(t["lp_gate"].abs().max()), 0.0)
        for k in ("lp_card", "lp_cell"):
            self.assertLess(float((t[k] - B[k]).abs().max()), 1e-5, k)

    def test_frozen_heads_get_no_gradient_and_stay_bit_identical(self):
        B = _batch(self.res)
        B["A"] = torch.linspace(-1.0, 1.0, len(B["A"]), dtype=torch.float64)   # a non-trivial advantage
        model = copy.deepcopy(self.model)
        ref = copy.deepcopy(self.model).eval()
        frozen = RL.freeze_heads(model, {"freeze_heads": ["timing", "ability"]})
        self.assertEqual(set(frozen), {"timing_head.weight", "timing_head.bias", "ability_head.weight", "ability_head.bias"})
        with torch.no_grad():                                 # move the policy off the ref so the KL term has a gradient
            for n, q in model.named_parameters():
                if q.requires_grad:
                    q.add_(0.01 * torch.randn_like(q))
        R = RL.ref_terms(ref, B, 0.3, 1.0)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        idx = torch.arange(len(B["A"]))
        for _ in range(3):
            opt.zero_grad()
            loss, st = RL.minibatch_loss(model, B, R, idx, tau=0.3, T=1.0, clip=0.2, beta=0.1, n_total=len(idx))
            loss.backward()
            g = dict(model.named_parameters())
            for n in frozen:
                self.assertIsNone(g[n].grad, n)
            self.assertGreater(float(g["card_q.weight"].grad.abs().sum()), 0.0)
            self.assertGreater(st["kl_card"] + st["kl_cell"], 0.0)
            self.assertEqual(st["kl_gate"], 0.0)
            opt.step()
        sd = dict(model.named_parameters())
        for n, v in frozen.items():
            self.assertTrue(torch.equal(sd[n].detach(), v), n)
        self.assertFalse(torch.equal(sd["card_q.weight"].detach(), self.model.card_q.weight))


class TestKeys(unittest.TestCase):
    def test_fixed_kl_pull_is_beta0_min_max(self):
        lam = 0.2
        for kl in (0.0, 1e-9, 0.01, 100.0):
            self.assertEqual(RL.adapt_beta(lam, kl, 0.03, lam, lam), lam)

    def test_freeze_heads_absent_and_refusals(self):
        m = _opp_model(1)
        before = {n: q.detach().clone() for n, q in m.named_parameters()}
        self.assertIsNone(RL.freeze_heads(m, {}))
        self.assertIsNone(RL.freeze_heads(m, {"freeze_heads": None}))
        self.assertTrue(all(q.requires_grad and torch.equal(q, before[n]) for n, q in m.named_parameters()))
        for bad in (["timing", "timing"], [], ["gate"], "timing"):
            with self.assertRaises(SystemExit, msg=str(bad)):
                RL.freeze_heads(m, {"freeze_heads": bad})
        with self.assertRaises(SystemExit):                   # a legacy GenModel has no timing head
            RL.freeze_heads(_tiny_gen(0), {"freeze_heads": ["timing"]})

    def test_absent_keys_leave_hash_and_cfgs_unchanged(self):
        cfg = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", [], False)
        self.assertEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "freeze_heads": None}))
        self.assertNotEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "freeze_heads": ["timing"]}))
        base = {"tau": 0.3, "afford_mask": True, "stall_elixir": 9.0, "stall_seconds": 12.0, "obs": "clean",
                "grid": "lattice", "decide_every": 10, "T": 1.0}
        self.assertNotIn("th_learner", RL.actor_cfg(base, "rollout", 0, "cpu"))
        self.assertTrue(RL.actor_cfg({**base, "opp_init": "x.pt"}, "rollout", 0, "cpu")["th_learner"])
        self.assertNotIn("th_learner", RL.actor_cfg({**base, "opp_init": "x.pt"}, "screen", 0, "cpu"))
        with self.assertRaises(ValueError):                   # a frozen timing seat still never records
            E.timing_cfg(_cfg("sample", record=True))
        self.assertTrue(E.timing_cfg(_cfg("sample", record=True, th_learner=True))["record"])
        self.assertEqual(E.opp_row_keys({"tok": 0, "ctx": 1, "deck_gid": 2, "ctx_band": 3}), ("deck_gid", "ctx_band"))


if __name__ == "__main__":
    unittest.main()
