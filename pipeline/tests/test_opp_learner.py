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


class TestDrift(unittest.TestCase):
    """OPP-LEARN-C: th_drift = the frozen heads' outputs, policy vs init, on fixed rows."""

    def test_zero_for_the_init_and_moves_with_the_trunk_only(self):
        model = _opp_model(5)
        B = _batch(_rollout(model, 1))
        rows = E.gen_batch(model, B, torch.arange(min(len(B["A"]), RL.TH_DRIFT_ROWS)))
        d0 = RL.th_drift(model, model, rows)
        self.assertEqual(d0["rows"], len(B["A"]))
        for k in ("hazard", "ab_hazard"):
            self.assertEqual((d0[k]["mad"], d0[k]["max"], d0[k]["tick_kl"]), (0.0, 0.0, 0.0), k)
        moved = copy.deepcopy(model)
        RL.freeze_heads(moved, {"freeze_heads": ["timing", "ability"]})
        with torch.no_grad():                                 # move the trunk only (what PPO on card / cell does)
            for n, q in moved.named_parameters():
                if q.requires_grad and not n.startswith(("card_q", "cell")):
                    q.add_(0.05 * torch.randn_like(q))
        d1 = RL.th_drift(moved, model, rows)
        self.assertTrue(torch.equal(moved.timing_head.weight, model.timing_head.weight))
        for k in ("hazard", "ab_hazard"):
            self.assertGreater(d1[k]["mad"], 0.0, k)
            self.assertGreater(d1[k]["tick_kl"], 0.0, k)
            self.assertGreaterEqual(d1[k]["max"], d1[k]["mad"])
            self.assertAlmostEqual(d1[k]["p_init"], d0[k]["p_now"], places=12)


class TestAnchor(unittest.TestCase):
    """OPP-LEARN-C th_anchor: lambda_t x KL(init || policy) of the frozen heads' outputs, gradient into the trunk only."""

    def test_pull_is_zero_at_the_init_and_reaches_only_the_trunk(self):
        model = _opp_model(7)
        B = _batch(_rollout(model, 1))
        idx = torch.arange(len(B["A"]))
        ref = copy.deepcopy(model).eval()
        frozen = RL.freeze_heads(model, {"freeze_heads": ["timing", "ability"]})
        with torch.no_grad():
            t0 = RL.policy_terms(ref, B, idx, 0.3, 1.0)
            self.assertEqual(float(RL.th_anchor_kl(RL.policy_terms(model, B, idx, 0.3, 1.0)["th"], t0["th"])), 0.0)
            for n, q in model.named_parameters():             # move the trunk off the init
                if q.requires_grad:
                    q.add_(0.05 * torch.randn_like(q))
        R = RL.ref_terms(ref, B, 0.3, 1.0)
        kw = dict(tau=0.3, T=1.0, clip=0.2, beta=0.1, n_total=len(idx))
        l0, st0 = RL.minibatch_loss(model, B, R, idx, **kw)
        l1, st1 = RL.minibatch_loss(model, B, R, idx, th_anchor=(2.0, ref), **kw)
        self.assertNotIn("kl_th", st0)
        self.assertGreater(st1["kl_th"], 0.0)
        self.assertAlmostEqual(float(l1 - l0), 2.0 * st1["kl_th"], places=6)
        model.zero_grad()
        (l1 - l0).backward()                                  # the pull's own gradient
        g = dict(model.named_parameters())
        for n in frozen:
            self.assertIsNone(g[n].grad, n)
        self.assertTrue(any(q.grad is not None and float(q.grad.abs().sum()) > 0 for n, q in g.items() if n not in frozen))
        cq = g["card_q.weight"].grad                          # the card head is not on the pull's path
        self.assertTrue(cq is None or float(cq.abs().sum()) == 0.0)

    def test_absent_hash_and_gate_models_unchanged(self):
        cfg = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", [], False)
        self.assertEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "th_anchor": None}))
        self.assertNotEqual(RL.config_sha(cfg), RL.config_sha({**cfg, "th_anchor": 1.0}))
        gm = _tiny_gen(3)
        B = _batch(_rollout(_opp_model(2), 1))
        self.assertIn("th", RL.policy_terms(_opp_model(2), B, torch.arange(4), 0.3, 1.0))
        res, _ = _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], E.GenPolicy(gm, VOCAB),
                      {"o": (E.GenPolicy(_tiny_gen(12), VOCAB), _cfg("sample", record=False))}, _cfg(T=1.0), n=1)
        with torch.no_grad():
            self.assertNotIn("th", RL.policy_terms(gm, _batch(res), torch.arange(4), 0.3, 1.0))


class TestBotPartner(unittest.TestCase):
    """OPP-LEARN-C: a league_exploiters entry = the bot partner on our deck with its own decode (T, T_gate, tau,
    tau_phase); a frozen human-model partner keeps the run's T (the init / snapshot path, unchanged)."""
    BASE = {"league": True, "league_deck_alpha": 1.0, "league_deck_floor": 0.0}
    CK = "pipeline/rl_royale.yaml"                            # any repo file (exploiter_league checks it exists)

    def test_icebow_pool_and_own_decode(self):
        x = RL.exploiter_league({**self.BASE, "league_exploiters": {
            "ckpt": self.CK, "decks": "icebow", "share": 0.6, "T": 0.5, "T_gate": 0.1, "tau": 0.35,
            "tau_phase": [0.35, 0.45, 0.55]}})
        self.assertEqual(x["decks"], [RL.ICEBOW_DECK])
        self.assertEqual(list(x["p"]), [1.0])
        self.assertEqual(x["opp"]["cfg"], {"T": 0.5, "T_gate": 0.1, "tau": 0.35, "tau_phase": [0.35, 0.45, 0.55]})
        oc = {"T": 1.0, "T_gate": None, "tau": 0.35, "decide_every": 10}
        got = RL.own_opp_cfg(oc, x["opp"], {})
        self.assertEqual((got["T"], got["T_gate"], got["tau"], got["tau_phase"]), (0.5, 0.1, 0.35, [0.35, 0.45, 0.55]))
        # list form: two bots on icebow, matchups draw ICEBOW_DECK for them
        xl = RL.exploiter_league({**self.BASE, "league_exploiters": [
            {"ckpt": self.CK, "decks": "icebow", "share": 0.3, "T_gate": 0.1},
            {"ckpt": "pipeline/rl_royale.py", "decks": "icebow", "share": 0.3}]})
        self.assertAlmostEqual(xl["share"], 0.6)
        ms = RL.sample_matchups(np.random.default_rng(0), 200, 0, [], {"league_icebow_share": 0.0, "league_mix":
                                {"init": 1.0}, "init": "i.pt", "league_specialist": "s.pt"},
                                [{"name": "r1", "engine": ["Knight"], "sides": 1, "bucket": "head"}], np.ones(1), None, xl)
        bots = [m for m in ms if m["opp"]["type"] == "exploiter_league"]
        self.assertTrue(40 < len(bots) < 160)
        self.assertTrue(all(m["opp_deck_name"] == "icebow" for m in bots))
        self.assertTrue(all(m["opp"]["type"] == "init" and m["opp_deck_name"] == "r1" for m in ms if m not in bots))

    def test_absent_keys_unchanged_and_refusals(self):
        x = RL.exploiter_league({**self.BASE, "league_exploiters": {"ckpt": self.CK, "decks": "icebow", "share": 0.5}})
        self.assertNotIn("cfg", x["opp"])
        oc = {"T": 1.0, "T_gate": None, "tau": 0.35, "decide_every": 10}
        self.assertEqual(RL.own_opp_cfg(oc, x["opp"], {}), RL.own_opp_cfg(oc, {"type": "init"}, {}))
        y = RL.exploiter_league({**self.BASE, "league_exploiters": {"ckpt": self.CK, "decks": "icebow", "share": 0.5,
                                                                    "T": 0.5}})
        self.assertNotIn("tau_phase", RL.own_opp_cfg(oc, y["opp"], {}))
        self.assertIsNone(RL.own_opp_cfg(oc, y["opp"], {})["T_gate"])
        for bad in ({"T_gate": 0}, {"T_gate": True}, {"tau_phase": [0.3, 0.4]}, {"tau_phase": [0.3, 0.4, 1.0]},
                    {"tau_phase": 0.3}, {"decks": "icebow2"}):
            with self.assertRaises(SystemExit, msg=str(bad)):
                RL.exploiter_league({**self.BASE, "league_exploiters": {"ckpt": self.CK, "decks": "icebow", "share": 0.5,
                                                                        **bad}})


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
