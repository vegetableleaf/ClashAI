"""Offline tests for pipeline/rl_royale.py (the RoyaleSim RL trainer; design: scratchpad/gauntlet/L68/rl_plan.md,
scratchpad/gauntlet/L67/e1_engine_rl_design.md 3.2-3.6).

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_rl_royale -v

No engine, no GPU, no royalesim. Trajectories are SYNTHETIC but produced by the real behaviour sampler
(``e1_eval.sample_decide_batch``) on a tiny random S1Model with fake Match objects carrying ``rng_behave``, recorded
in ``Match.apply``'s row format and stacked by the real ``Match._traj_arrays`` -- so the learner's recomputation is
checked against exactly what an actor would hand it.
"""
from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                    # noqa: E402

from pipeline import e1_eval as E                               # noqa: E402
from pipeline import rl_royale as RL                            # noqa: E402
from pipeline.dataset import PAST_K                             # noqa: E402
from pipeline.obs_contract import F as TOK_F, S as SC_S         # noqa: E402

TAU, T = 0.27, 0.5
CFG = {"stop_consecutive": 2, "plays_lo": 0.6, "plays_hi": 1.6, "kl_cell_stop": 0.5, "kl_gate_stop": 0.1,
       "beta_max": 3.0, "tripwire_cell_pp": 1.0, "hard_cell_pp": 3.0, "hard_card_pp": 3.0, "hard_gate_bal": 0.05,
       "screen_stop_pp": -10.0, "outlived_pp": 15.0, "low_delivered_pp": 10.0, "ghost_refusal_x": 2.0,
       "entropy_floor_frac": 0.5}


def _tiny_model(seed: int):
    from pipeline.model_v3 import S1Model
    torch.manual_seed(seed)
    return S1Model(d=16, layers=1).eval()          # heads=4 default, so engine_play.load_model rebuilds it from args


class _FakeMatch:
    def __init__(self, seed: int):
        self.rng_behave = np.random.default_rng(seed)


def _synth_match(model, rng: np.random.Generator, n: int, seed: int, all_allowed: bool = False) -> dict:
    """``n`` decisions of one fake match through the real sampler -> ``Match._traj_arrays`` layout."""
    toks, masks, scs, pasts = [], [], [], []
    for _ in range(n):
        t = rng.normal(size=(E.MAX_U, TOK_F)).astype(np.float32)
        t[:, 0] = rng.integers(0, 50, size=E.MAX_U)
        t[:, 4:6] = rng.uniform(0, 1, size=(E.MAX_U, 2))
        toks.append(t)
        masks.append(rng.random(E.MAX_U) < 0.5)
        s = rng.normal(size=SC_S).astype(np.float32)
        s[7:43] = 0.0
        for g, slot in enumerate(rng.choice(E.N_SLOTS, size=4, replace=False)):
            s[7 + g * 9 + slot] = 1.0
        scs.append(s)
        p = np.full((PAST_K, 4), -1.0, np.float32)
        pasts.append(p)
    enc, heads, p, hand = E.model_forward_batch(model, toks, masks, scs, pasts)
    allowed = hand & (np.ones_like(hand) if all_allowed else (rng.random(hand.shape) < 0.7))
    if not all_allowed:
        allowed[rng.random(n) < 0.15] = False                  # some "nothing affordable" rows -> dropped by collate
    stalled = rng.random(n) < 0.1
    fm = _FakeMatch(seed)
    ds = E.sample_decide_batch(model, enc, heads, p, allowed, stalled, [fm] * n, {"tau": TAU, "T": T})
    rows = [{"tok": toks[r], "mask": masks[r], "sc": scs[r], "past": pasts[r], "allowed": d["allowed"],
             "stalled": d["stalled"], "gate_sampled": d["gate_sampled"], "played": d["play"], "slot": d["slot"],
             "cell": d["cell"], "lp_gate": d["lp_gate"], "lp_card": d["lp_card"], "lp_cell": d["lp_cell"],
             "p_gate": d["p_gate"], "T": d["T"]} for r, d in enumerate(ds)]
    return E.Match._traj_arrays(SimpleNamespace(traj=rows))


def _results(model, spec, seed=0, all_allowed=False) -> list[dict]:
    """spec: [(entry_index, g, n_decisions, outcome)] -> rollout result records with ``traj``."""
    rng = np.random.default_rng(seed)
    return [{"entry_index": i, "k": g, "outcome": o, "traj": _synth_match(model, rng, n, 100 * i + g, all_allowed)}
            for i, g, n, o in spec]


# ------------------------------------------------------------------------------------------------------
class TestLooAdvantage(unittest.TestCase):
    def test_values(self):
        A = RL.loo_advantage([1, -1, 1, 1])
        np.testing.assert_allclose(A, [1 - 1 / 3, -1 - 1, 1 - 1 / 3, 1 - 1 / 3])

    def test_all_same_group_is_zero(self):
        for R in ([1, 1, 1, 1], [-1, -1], [0, 0, 0]):
            np.testing.assert_array_equal(RL.loo_advantage(R), np.zeros(len(R)))

    def test_clamp(self):
        np.testing.assert_allclose(RL.loo_advantage([1, -1]), [2, -2])        # G=2 extreme is exactly the clamp
        np.testing.assert_allclose(RL.loo_advantage([1, -1], clip=1.5), [1.5, -1.5])

    def test_single_rollout_no_signal(self):
        np.testing.assert_array_equal(RL.loo_advantage([1]), [0.0])

    def test_collate_assigns_group_advantage(self):
        model = _tiny_model(0)
        res = _results(model, [(0, 0, 6, "win"), (0, 1, 7, "loss"), (3, 0, 5, "win"), (3, 1, 4, "win")])
        B, st = RL.collate(res)
        for j, r in enumerate(res):
            a = B["A"][B["match"] == j]
            want = {0: 2.0, 1: -2.0, 2: 0.0, 3: 0.0}[j]
            self.assertTrue(np.all(a == want), (j, a))
        self.assertEqual(st["mixed_groups"], 1)
        self.assertEqual(st["groups"], 2)
        keep = sum(int((r["traj"]["gate_sampled"] | r["traj"]["played"]).sum()) for r in res)
        self.assertEqual(len(B["A"]), keep)                    # rows that sampled nothing are dropped
        self.assertLess(keep, st["decisions"])


# ------------------------------------------------------------------------------------------------------
class TestOnPolicy(unittest.TestCase):
    """policy == ref == behaviour: recomputed log-probs == recorded, ratio == 1, KL == 0 (rl_plan.md 'Learner')."""

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(1)
        # widen cell_bias so cell log-probs are not a near-uniform 1/2304 (a stricter recompute check)
        with torch.no_grad():
            cls.model.cell_bias.copy_(torch.from_numpy(np.random.default_rng(5).normal(size=E.N_CELLS).astype("float32")))
        res = _results(cls.model, [(0, 0, 40, "win"), (0, 1, 35, "loss"), (1, 0, 30, "draw"), (1, 1, 25, "win")], seed=3)
        Bn, cls.st = RL.collate(res)
        cls.B = RL.to_device(Bn, "cpu")

    def test_recomputed_logprobs_equal_recorded(self):
        with torch.no_grad():
            t = RL.policy_terms(self.model, self.B, torch.arange(len(self.B["A"])), TAU, T)
        self.assertGreater(int(self.B["played"].sum()), 5)
        self.assertGreater(int(self.B["gate_sampled"].sum()), 5)
        for k in ("lp_gate", "lp_card", "lp_cell"):
            d = float((t[k] - self.B[k]).abs().max())
            self.assertLess(d, 1e-5, k)

    def test_ratio_one_and_kl_zero(self):
        ref = copy.deepcopy(self.model).eval()
        for p in ref.parameters():
            p.requires_grad_(False)
        R = RL.ref_terms(ref, self.B, TAU, T)
        N = len(self.B["A"])
        loss, st = RL.minibatch_loss(self.model, self.B, R, torch.arange(N), tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
        self.assertLess(st["ratio_maxdev"], 1e-4)
        for k in ("kl_gate", "kl_card", "kl_cell"):
            self.assertLess(abs(st[k]), 1e-8, k)
        self.assertTrue(torch.isfinite(loss))
        loss.backward()                                        # gradients flow, and are finite (no -inf/NaN traps)
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in self.model.parameters() if p.grad is not None))
        self.model.zero_grad(set_to_none=True)

    def test_ppo_update_first_minibatch_is_on_policy(self):
        model = copy.deepcopy(self.model)
        ref = copy.deepcopy(self.model).eval()
        R = RL.ref_terms(ref, self.B, TAU, T)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        cfg = {"minibatch": 32, "ppo_epochs": 2, "tau": TAU, "T": T, "clip": 0.2, "grad_clip": 0.5}
        out = RL.ppo_update(model, opt, self.B, R, cfg, 0.3, np.random.default_rng(0))
        self.assertIsNone(out["nonfinite"])
        self.assertLess(out["first"]["ratio_maxdev"], 1e-4)
        self.assertLess(out["first"]["kl_cell"], 1e-8)
        self.assertGreater(out["kl_cell"], 0.0)               # it moved after steps at lr 1e-3
        self.assertEqual(out["steps"], 2 * -(-len(self.B["A"]) // 32))


# ------------------------------------------------------------------------------------------------------
class TestPerMatchWeighting(unittest.TestCase):
    """E1 3.2: loss averaged per match, then over the batch -- a 60-decision match does not outweigh a 5-decision one."""

    def test_weights_sum_per_match(self):
        W = RL.match_weights([5, 60, 0, 12])
        self.assertEqual([len(w) for w in W], [5, 60, 0, 12])
        for w in (W[0], W[1], W[3]):
            self.assertAlmostEqual(float(w.sum()), 1 / 3, places=12)

    def test_long_loss_does_not_outweigh_short_win(self):
        model = _tiny_model(2)
        res = _results(model, [(0, 0, 5, "win"), (0, 1, 60, "loss")], seed=9, all_allowed=True)
        Bn, _ = RL.collate(res)
        self.assertEqual(len(Bn["A"]), 65)                     # all_allowed: every row sampled something
        B = RL.to_device(Bn, "cpu")
        R = RL.ref_terms(copy.deepcopy(model).eval(), B, TAU, T)
        N = len(B["A"])
        _, st = RL.minibatch_loss(model, B, R, torch.arange(N), tau=TAU, T=T, clip=0.2, beta=0.0, n_total=N)
        # on-policy ratio 1: L_pg = -(1/2)(+2) - (1/2)(-2) = 0 per match; per-decision averaging would give
        # -(5 * 2 - 60 * 2) / 65 = +1.69
        self.assertAlmostEqual(st["l_pg"], 0.0, places=4)


# ------------------------------------------------------------------------------------------------------
class TestBeta(unittest.TestCase):
    def test_rule(self):
        self.assertEqual(RL.adapt_beta(0.3, 0.2, 0.1), 0.6)          # > 1.5 kappa -> x2
        self.assertEqual(RL.adapt_beta(0.3, 0.05, 0.1), 0.15)        # < kappa / 1.5 -> /2
        self.assertEqual(RL.adapt_beta(0.3, 0.1, 0.1), 0.3)          # in the band -> unchanged
        self.assertEqual(RL.adapt_beta(0.3, 0.149, 0.1), 0.3)
        self.assertEqual(RL.adapt_beta(3.0, 1.0, 0.1), 3.0)          # clamp high
        self.assertEqual(RL.adapt_beta(0.03, 0.0, 0.1), 0.03)        # clamp low
        self.assertEqual(RL.adapt_beta(2.0, 1.0, 0.1, hi=3.0), 3.0)


# ------------------------------------------------------------------------------------------------------
class TestStopRules(unittest.TestCase):
    INIT = {"cell_half_top1": 0.2073, "card_top1": 0.6394, "gate_bal_acc": 0.7636}

    def pa(self, dc=0.0, dk=0.0, dg=0.0):
        i = self.INIT
        return {"cell_half_top1": i["cell_half_top1"] + dc, "card_top1": i["card_top1"] + dk,
                "gate_bal_acc": i["gate_bal_acc"] + dg}

    def test_tripwire_needs_both(self):
        self.assertIsNotNone(RL.tripwire_reason(self.pa(dc=-0.011), self.INIT, 0.0, CFG))     # both
        self.assertIsNotNone(RL.tripwire_reason(self.pa(dc=-0.02), self.INIT, -3.0, CFG))
        self.assertIsNone(RL.tripwire_reason(self.pa(dc=-0.011), self.INIT, 0.5, CFG))        # winrate gain
        self.assertIsNone(RL.tripwire_reason(self.pa(dc=-0.009), self.INIT, -5.0, CFG))       # cell within 1 pp
        self.assertIsNone(RL.tripwire_reason(self.pa(dc=-0.02), self.INIT, None, CFG))        # no screen yet

    def test_hard_stop(self):
        self.assertIsNone(RL.hard_stop_reason(self.pa(dc=-0.029, dk=-0.029, dg=-0.049), self.INIT, CFG))
        self.assertIn("cell", RL.hard_stop_reason(self.pa(dc=-0.031), self.INIT, CFG))
        self.assertIn("card", RL.hard_stop_reason(self.pa(dk=-0.031), self.INIT, CFG))
        self.assertIn("gate_bal_acc", RL.hard_stop_reason(self.pa(dg=-0.051), self.INIT, CFG))

    def test_plays_rule_needs_two_consecutive(self):
        g = RL.Guards(CFG)
        g.set_baselines({"plays_per_min": 10.0})
        self.assertEqual(g.after_update({"plays_per_min": 5.0}, 0.3, 0.0, 0.0), [])
        self.assertEqual(g.after_update({"plays_per_min": 10.0}, 0.3, 0.0, 0.0), [])        # counter resets
        self.assertEqual(g.after_update({"plays_per_min": 17.0}, 0.3, 0.0, 0.0), [])
        self.assertEqual(len(g.after_update({"plays_per_min": 17.0}, 0.3, 0.0, 0.0)), 1)

    def test_kl_rule_only_at_beta_clamp(self):
        g = RL.Guards(CFG)
        g.set_baselines({})
        for _ in range(3):
            self.assertEqual(g.after_update({}, 1.5, 0.9, 0.0), [])                           # beta below clamp
        g.after_update({}, 3.0, 0.9, 0.0)
        self.assertEqual(len(g.after_update({}, 3.0, 0.1, 0.2)), 1)                           # KL_gate leg

    def test_train_batch_share_rise_no_longer_stops(self):
        """rl30 false alarm: the train batch's <=10-delivered / outlived / refused values moving vs update 0 (different
        ghosts sampled) is a monitor only -- after_update never stops on it."""
        g = RL.Guards(CFG)
        g.set_baselines({"plays_per_min": 11.0, "outlived_win_share": 0.265, "low_delivered_win_share": 0.0,
                         "ghost_refused_per_match": 0.64})
        self.assertEqual(g.s["base"], {"plays_per_min": 11.0})
        for _ in range(8):                                   # the rl30 u4-shaped batch, repeated
            out = g.after_update({"plays_per_min": 11.0, "outlived_win_share": 0.6, "low_delivered_win_share": 0.241,
                                  "ghost_refused_per_match": 9.0}, 0.3, 0.0, 0.0)
            self.assertEqual(out, [])

    def test_screen_needs_delta_and_ci(self):
        g = RL.Guards(CFG)
        self.assertIsNone(g.screen(-9.9, -1.0))                  # delta not low enough
        self.assertIsNone(g.screen(-25.0, 0.0))                  # CI reaches 0: could be noise
        self.assertIsNotNone(g.screen(-10.0, -0.1))              # both
        self.assertEqual(g.s["latest_screen_delta_pp"], -10.0)

    def test_ghost_refused_limit(self):
        self.assertAlmostEqual(RL.ghost_refused_limit(0.64), 1.64)          # +1.0 floor binds (rl_gate's bound)
        self.assertAlmostEqual(RL.ghost_refused_limit(3.0), 6.0)            # 2x binds
        self.assertEqual(RL.ghost_refused_limit(0.0), 1.0)
        self.assertIsNone(RL.ghost_refused_limit(None))

    def test_old_guard_state_loads(self):
        """--resume of a checkpoint written before the lead's screen-guard ruling (rl30_20260924_latest.pt's shape):
        the obsolete EMA / exploit-baseline / ghost_refused_limit keys are dropped, the live counters kept."""
        old = {"base": {"plays_per_min": 11.89, "outlived_win_share": 0.2647, "low_delivered_win_share": 0.0,
                        "ghost_refused_per_match": 0.64},
               "consec": {"plays": 1, "kl": 0, "entropy_gate": 0, "entropy_card": 0, "entropy_cell": 0,
                          "outlived_win_share": 0, "low_delivered_win_share": 1, "ghost_refusal": 0},
               "ema": {"outlived_win_share": 0.344, "low_delivered_win_share": 0.11, "ghost_refused_per_match": 0.8},
               "latest_screen_delta_pp": 1.1, "ghost_refused_limit": 1.64}
        g = RL.Guards(CFG, RL._py(old))
        self.assertEqual(g.s["base"], {"plays_per_min": 11.89})
        self.assertEqual(g.s["consec"], {"plays": 1, "kl": 0, "entropy_gate": 0, "entropy_card": 0, "entropy_cell": 0})
        self.assertEqual(g.s["latest_screen_delta_pp"], 1.1)
        self.assertNotIn("ema", g.s)
        self.assertNotIn("ghost_refused_limit", g.s)
        out = g.after_update({"plays_per_min": 3.0, "low_delivered_win_share": 0.5}, 0.3, 0.0, 0.0)
        self.assertEqual(len(out), 1)                        # plays counter continued (1 -> 2), no exploit stop
        self.assertIn("plays/min", out[0])


def _screen_res(tags, k_seeds, *, loss=(), after_script=(), low_dlv=(), refused=0):
    """Synthetic screen records (e1_eval.Match.result keys screen_record reads)."""
    return [{"tag": t, "k": k, "outcome": "loss" if (t, k) in loss else "win", "plays_attempted": 10, "seconds": 120.0,
             "won_after_script": (t, k) in after_script and (t, k) not in loss,
             "ghost_delivered": 5 if (t, k) in low_dlv else 40, "ghost_refused": refused} for t in tags for k in k_seeds]


class TestScreenExploitGuards(unittest.TestCase):
    """E1 4.2.1-3 on the held-out screen, candidate vs init on the SAME matches (single occurrence)."""

    TAGS = [f"H{i:02d}" for i in range(20)]
    KEYS = [(t, k) for t in TAGS for k in range(3)]

    def _init(self):
        sc = RL.screen_score(_screen_res(self.TAGS, range(3), after_script=set(self.KEYS[:15]),
                                         low_dlv=set(self.KEYS[:3]), refused=0), None)
        return sc["per_key"]

    def test_identical_screen_does_not_fire(self):
        init = self._init()
        sc = RL.screen_score(_screen_res(self.TAGS, range(3), after_script=set(self.KEYS[:15]),
                                         low_dlv=set(self.KEYS[:3])), init)
        self.assertEqual(sc["exploit_init"], sc["exploit_cand"])
        self.assertAlmostEqual(sc["exploit_init"]["outlived_win_share"], 0.25)
        self.assertEqual(RL.exploit_reasons(sc["exploit_init"], sc["exploit_cand"], CFG), [])

    def test_each_guard_fires(self):
        init = self._init()
        outl = RL.screen_score(_screen_res(self.TAGS, range(3), after_script=set(self.KEYS[:25]),      # 0.25 -> 0.417
                                           low_dlv=set(self.KEYS[:3])), init)
        r = RL.exploit_reasons(outl["exploit_init"], outl["exploit_cand"], CFG)
        self.assertEqual(len(r), 1); self.assertIn("outlived", r[0])
        low = RL.screen_score(_screen_res(self.TAGS, range(3), after_script=set(self.KEYS[:15]),
                                          low_dlv=set(self.KEYS[:10])), init)                         # 0.05 -> 0.167
        r = RL.exploit_reasons(low["exploit_init"], low["exploit_cand"], CFG)
        self.assertEqual(len(r), 1); self.assertIn("<=10-delivered", r[0])
        ref = RL.screen_score(_screen_res(self.TAGS, range(3), after_script=set(self.KEYS[:15]),
                                          low_dlv=set(self.KEYS[:3]), refused=2), init)               # 0 -> 2 > 1.0
        r = RL.exploit_reasons(ref["exploit_init"], ref["exploit_cand"], CFG)
        self.assertEqual(len(r), 1); self.assertIn("refused", r[0])

    def test_margins_are_inclusive_of_noise(self):
        init = self._init()                                                                           # refused 0/match
        sc = RL.screen_score(_screen_res(self.TAGS, range(3), after_script=set(self.KEYS[:23]),       # +13.3 pp < 15
                                         low_dlv=set(self.KEYS[:8]), refused=1), init)                # +8.3 pp; 1.0 = limit
        self.assertEqual(RL.exploit_reasons(sc["exploit_init"], sc["exploit_cand"], CFG), [])

    def test_compared_on_paired_matches_only(self):
        init = self._init()
        # the candidate screen misses 10 tags; the init side is recomputed on the SAME 10 tags x 3 seeds
        sc = RL.screen_score(_screen_res(self.TAGS[:10], range(3), after_script=set(self.KEYS[:15]),
                                         low_dlv=set(self.KEYS[:3])), init)
        self.assertEqual(sc["paired"], 30)
        self.assertEqual(sc["exploit_init"], sc["exploit_cand"])
        self.assertAlmostEqual(sc["exploit_init"]["outlived_win_share"], 0.5)

    def test_old_float_init_has_delta_but_no_guard(self):
        init = {f"{t}:{k}": 1.0 for t, k in self.KEYS}
        sc = RL.screen_score(_screen_res(self.TAGS, range(3)), init)
        self.assertEqual(sc["delta_pp"], 0.0)
        self.assertIsNone(sc["exploit_init"]); self.assertIsNone(sc["exploit_cand"])


    # ------------------------------------------------------------------------------------------------------
class _Skip(Exception):
    pass


class TestRolloutJobsSeeds(unittest.TestCase):
    """The real ``run_batch`` applies each job's 4th-element cfg overrides to THAT match only (explicit per-job seeds),
    and 3-element jobs (e1_eval's own CLI, the screen) still work."""

    def _run(self, jobs):
        seen = []

        class StubMatch:
            def __init__(self, env, deck, entry, k, cfg):
                seen.append((entry["tag"], k, cfg.get("rollout_index"), cfg.get("update"), cfg.get("obs_seed"),
                             cfg["entry_index"]))
                raise _Skip()

        cfg = {"policy": "sample", "device": "cpu", "tau": TAU}
        orig = E.Match
        E.Match = StubMatch
        try:
            E.run_batch(lambda: object(), None, None, jobs, cfg, 3,
                        on_result=lambda r: None, on_skip=lambda e, exc: None, skip=(_Skip,))
        finally:
            E.Match = orig
        self.assertEqual(cfg, {"policy": "sample", "device": "cpu", "tau": TAU})    # shared cfg never mutated
        return seen

    def test_per_job_overrides(self):
        jobs = [(i, {"tag": f"t{i}"}, g) for i in (4, 7) for g in range(3)]
        seen = self._run(RL.rollout_jobs(jobs, 5))
        self.assertEqual(len(seen), 6)
        for (i, e, g), (tag, k, ri, up, os_, ei) in zip(jobs, seen):
            self.assertEqual((tag, k, ri, up, ei), (e["tag"], g, g, 5, i))
            self.assertEqual(os_, RL.rl_obs_seed(e["tag"], g, 5))
        self.assertEqual(len({s[4] for s in seen}), 6)         # distinct obs seeds per (entry, g)

    def test_three_element_jobs(self):
        seen = self._run([(0, {"tag": "a"}, 0), (1, {"tag": "b"}, 2)])
        self.assertEqual(seen, [("a", 0, None, None, None, 0), ("b", 2, None, None, None, 1)])


class TestEmptyTraj(unittest.TestCase):
    def test_empty_traj_keeps_trailing_shapes(self):
        t = E.Match._traj_arrays(SimpleNamespace(traj=[]))
        want = {"tok": (0, E.MAX_U, TOK_F), "mask": (0, E.MAX_U), "sc": (0, SC_S), "past": (0, PAST_K, 4),
                "allowed": (0, E.N_SLOTS), "played": (0,), "lp_cell": (0,)}
        for k, shape in want.items():
            self.assertEqual(t[k].shape, shape, k)


class TestScreenScore(unittest.TestCase):
    """Entry-clustered paired delta + bootstrap CI over (tag, k), as rl_gate grades it."""

    def test_clustered_delta_and_ci(self):
        tags = [f"T{i:02d}" for i in range(20)]
        init = {f"{t}:{k}": 1.0 for t in tags for k in range(3)}
        res = _screen_res(tags, range(3), loss={(t, k) for t in tags[:4] for k in range(2)})
        sc = RL.screen_score(res, init)
        self.assertEqual((sc["paired"], sc["paired_entries"], sc["worse"], sc["better"]), (60, 20, 8, 0))
        self.assertAlmostEqual(sc["delta_pp"], -100 * (4 * (2 / 3)) / 20, places=6)          # -13.33 pp
        self.assertLess(sc["ci_lo_pp"], sc["delta_pp"])
        self.assertLessEqual(sc["ci_hi_pp"], 0.0)
        same = RL.screen_score([dict(r, outcome="win") for r in res], init)
        self.assertEqual((same["delta_pp"], same["ci_lo_pp"], same["ci_hi_pp"]), (0.0, 0.0, 0.0))


# ------------------------------------------------------------------------------------------------------
class TestCheckpointRoundTrip(unittest.TestCase):
    """Checkpoint layout: engine_play.load_model and torch.load(weights_only=True) load it; _restore gets it back."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_royale_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _learner(self, model):
        L = RL.Learner.__new__(RL.Learner)
        L.cfg = dict(CFG, init="icebow/data/pipeline/x.pt", lr=1e-3)
        L.run, L.dev, L.model, L.pool_sha = "unit", torch.device("cpu"), model, "sha"
        L.init_meta = {"args": {"d": 16, "layers": 1, "grid": "lattice"}, "deck": "icebow", "epoch": 12, "n_params": 1}
        L.opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        L.update, L.beta, L.rng, L.visits = 0, 0.3, np.random.default_rng(0), [0, 0, 0]
        L.train = [None] * 3
        L.base = {"init_proagree": {"cell_half_top1": np.float64(0.2)}, "init_screen": {"a": 1.0, "b": 0.5}}
        L.guards = RL.Guards(L.cfg)
        L.log = lambda m: None
        return L

    def test_restore_old_format_checkpoint(self):
        """A checkpoint written by the pre-screen-guard code (old guards dict, outcome-only init screen) restores."""
        L = self._learner(_tiny_model(5))
        L.guards.s = {"base": {"plays_per_min": 11.9, "outlived_win_share": 0.26, "low_delivered_win_share": 0.0,
                               "ghost_refused_per_match": 0.64},
                      "consec": {"plays": 0, "kl": 0, "low_delivered_win_share": 2, "ghost_refusal": 0},
                      "ema": {"low_delivered_win_share": 0.11}, "latest_screen_delta_pp": None, "ghost_refused_limit": 1.64}
        L.update = 6
        path = self.tmp / "old_latest.pt"
        torch.save(L._payload(None), path)
        L2 = self._learner(_tiny_model(9))
        L2._restore(path)
        self.assertEqual(L2.update, 6)
        self.assertEqual(L2.guards.s["base"], {"plays_per_min": 11.9})
        self.assertEqual(L2.guards.s["consec"], {"plays": 0, "kl": 0})
        self.assertEqual(L2.base["init_screen"], {"a": 1.0, "b": 0.5})      # outcome-only: main() rebuilds it on resume

    def test_round_trip(self):
        from pipeline import engine_play as ep
        model = _tiny_model(4)
        L = self._learner(model)
        loss = sum(p.float().pow(2).sum() for p in model.parameters())
        loss.backward()
        L.opt.step()                                          # non-empty Adam state
        L.update, L.beta, L.visits = 7, 0.6, [2, 0, 5]
        L.rng.random(5)
        L.guards.set_baselines({"plays_per_min": np.float64(9.5)})
        path = self.tmp / "unit_latest.pt"
        torch.save(L._payload({"cell_half_top1": np.float64(0.21)}), path)
        ck = torch.load(path, map_location="cpu", weights_only=True)          # eval_s1 / load_model's torch.load
        for k in ("model", "args", "deck", "epoch", "val", "n_params", "rl"):
            self.assertIn(k, ck)
        m2, info = ep.load_model(path, "cpu")
        self.assertEqual(info["grid"], "lattice")
        for a, b in zip(model.state_dict().values(), m2.state_dict().values()):
            self.assertTrue(torch.equal(a, b))
        L2 = self._learner(_tiny_model(99))
        L2._restore(path)
        self.assertEqual((L2.update, L2.beta, L2.visits), (7, 0.6, [2, 0, 5]))
        self.assertEqual(L2.rng.bit_generator.state, L.rng.bit_generator.state)
        self.assertEqual(L2.guards.s["base"]["plays_per_min"], 9.5)
        self.assertEqual(L2.base["init_screen"], {"a": 1.0, "b": 0.5})
        s1, s2 = L.opt.state_dict()["state"], L2.opt.state_dict()["state"]
        for k in s1:
            self.assertEqual(float(s1[k]["step"]), float(s2[k]["step"]))
            self.assertTrue(torch.equal(s1[k]["exp_avg"], s2[k]["exp_avg"]))
        for a, b in zip(model.state_dict().values(), L2.model.state_dict().values()):
            self.assertTrue(torch.equal(a, b))


# ------------------------------------------------------------------------------------------------------
class TestEntropyStop(unittest.TestCase):
    """E1 3.4: a head's entropy < entropy_floor_frac x the init's on the same rows, stop_consecutive updates."""

    INIT = {"gate": 0.27, "card": 0.11, "cell": 1.8}

    def test_fires_on_second_consecutive_for_that_head_only(self):
        g = RL.Guards(CFG)
        g.set_baselines({})
        low_gate = {"gate": 0.10, "card": 0.10, "cell": 1.0}          # gate 0.10 < 0.135; card, cell above half
        self.assertEqual(g.after_update({}, 0.3, 0.0, 0.0, ent=low_gate, ent_init=self.INIT), [])
        out = g.after_update({}, 0.3, 0.0, 0.0, ent=low_gate, ent_init=self.INIT)
        self.assertEqual(len(out), 1)
        self.assertIn("gate entropy", out[0])

    def test_recovery_resets_and_none_is_skipped(self):
        g = RL.Guards(CFG)
        g.set_baselines({})
        low = {"gate": 0.27, "card": 0.11, "cell": 0.5}
        g.after_update({}, 0.3, 0.0, 0.0, ent=low, ent_init=self.INIT)
        self.assertEqual(g.after_update({}, 0.3, 0.0, 0.0, ent=self.INIT, ent_init=self.INIT), [])     # reset
        self.assertEqual(g.after_update({}, 0.3, 0.0, 0.0, ent=low, ent_init=self.INIT), [])
        none = {"gate": None, "card": None, "cell": None}
        for _ in range(3):
            self.assertEqual(g.after_update({}, 0.3, 0.0, 0.0, ent=none, ent_init=self.INIT), [])


class TestScreenNoPairs(unittest.TestCase):
    def test_no_pairs_is_none_and_not_a_screen(self):
        res = _screen_res(["X"], [0], loss={("X", 0)})
        sc = RL.screen_score(res, {"Y:0": 1.0})
        self.assertEqual(sc["paired"], 0)
        self.assertIsNone(sc["delta_pp"]); self.assertIsNone(sc["ci_hi_pp"]); self.assertIsNone(sc["ci_lo_pp"])
        g = RL.Guards(CFG)
        g.screen(-3.0, 9.0)
        self.assertIsNone(g.screen(sc["delta_pp"], sc["ci_hi_pp"]))
        self.assertIsNone(g.s["latest_screen_delta_pp"])            # the stale -3.0 is dropped, not carried forward
        pa = {"cell_half_top1": 0.10, "card_top1": 0.64, "gate_bal_acc": 0.76}
        init = {"cell_half_top1": 0.2073, "card_top1": 0.6394, "gate_bal_acc": 0.7636}
        self.assertIsNotNone(RL.tripwire_reason(pa, init, -3.0, CFG))    # the stale delta WOULD have tripped it
        self.assertIsNone(RL.tripwire_reason(pa, init, g.s["latest_screen_delta_pp"], CFG))


# ------------------------------------------------------------------------------------------------------
class _Log:
    def __init__(self):
        self.lines, self.recs = [], []

    def __call__(self, m):
        self.lines.append(m)

    def json(self, r):
        self.recs.append(r)


def _monitor_fields(res: list[dict]) -> list[dict]:
    """The result keys rollout_monitors reads, on the synthetic trajectories."""
    for r in res:
        n = int(r["traj"]["played"].sum())
        r.update({"tag": f"t{r['entry_index']}", "seconds": 120.0, "plays_attempted": n, "plays_accepted": n,
                  "card_mix_attempted": {}, "refuse_reasons": {}, "play_elixir": [], "stall_fired": 0,
                  "ghost_delivered": 20, "ghost_refused": 0, "ghost_undelivered": 0, "won_after_script": False})
    return res


class TestOneUpdate(unittest.TestCase):
    """``Learner.one_update`` offline (rollout stubbed with synthetic sampler trajectories): a normal update, the
    non-finite path (stop reason, crash save, _latest untouched) and resume's already-existing numbered checkpoint."""

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, [(0, 0, 30, "win"), (0, 1, 25, "loss"), (1, 0, 20, "win"),
                                                           (1, 1, 28, "draw")], seed=13))

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_royale_upd_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        orig_root, orig_mbl = RL.CKPT_ROOT, RL.minibatch_loss
        RL.CKPT_ROOT = self.tmp / "ck"
        self.addCleanup(setattr, RL, "CKPT_ROOT", orig_root)
        self.addCleanup(setattr, RL, "minibatch_loss", orig_mbl)

    def _learner(self) -> "RL.Learner":
        model = copy.deepcopy(self.model)
        L = RL.Learner.__new__(RL.Learner)
        L.cfg = dict(CFG, init="x.pt", lr=1e-4, tau=TAU, T=T, adv_clip=2.0, minibatch=64, ppo_epochs=2, clip=0.2,
                     grad_clip=0.5, kl_target=0.1, beta_min=0.03, beta_max=3.0, screen_every=1000,
                     proagree_every=1000, save_every=1, max_updates=1)
        L.run, L.dev, L.model, L.pool_sha = "unit", torch.device("cpu"), model, "sha"
        L.ref = copy.deepcopy(model).eval()
        for p in L.ref.parameters():
            p.requires_grad_(False)
        L.init_meta = {"args": {"d": 16, "layers": 1, "grid": "lattice"}, "deck": "icebow", "epoch": 12, "n_params": 1}
        L.opt = torch.optim.Adam(model.parameters(), lr=1e-4)
        L.update, L.beta, L.rng, L.visits, L.train = 0, 0.3, np.random.default_rng(0), [0, 0], [None, None]
        L.base, L.guards, L.latest_pa = {"init_screen": {}}, RL.Guards(L.cfg), None
        L.run_dir, L.ck_dir = self.tmp / "run", self.tmp / "ck" / "unit"
        L.run_dir.mkdir(parents=True); L.ck_dir.mkdir(parents=True)
        L.log = _Log()
        L.rollout = lambda u: (list(self.results), {"picked": [0, 1], "actors": {}, "skipped": 0})
        return L

    def test_normal_update(self):
        L = self._learner()
        rec, reasons, crash = L.one_update(0)                   # includes the update-0 on-policy assertion (1e-4/1e-6)
        self.assertFalse(crash)
        self.assertEqual(L.update, 1)
        self.assertLess(rec["first_minibatch"]["ratio_maxdev"], RL.ASSERT_RATIO)
        self.assertTrue((L.ck_dir / "unit_latest.pt").exists())
        self.assertTrue((L.ck_dir / "unit_u0001.pt").exists())

    def test_nonfinite_stops_and_keeps_latest(self):
        L = self._learner()
        latest = L.ck_dir / "unit_latest.pt"
        latest.write_bytes(b"LAST-GOOD")
        real = RL.minibatch_loss
        RL.minibatch_loss = (lambda *a, **k: (lambda ls: (ls[0] * float("nan"), ls[1]))(real(*a, **k)))
        code, why = L.loop()
        self.assertEqual(code, 0)
        self.assertIn("non-finite loss", why)
        self.assertEqual(latest.read_bytes(), b"LAST-GOOD")        # _latest untouched
        self.assertEqual(len(list(L.ck_dir.glob("unit_crash_u0000_*.pt"))), 1)
        self.assertFalse((L.ck_dir / "unit_u0001.pt").exists())
        self.assertEqual(L.update, 0)                               # the crashed update is not counted
        self.assertTrue(any(m.startswith("STOP after update 0: non-finite loss") for m in L.log.lines), L.log.lines)
        self.assertIn("non-finite loss", L.log.recs[-1]["stop"][0])

    def test_existing_numbered_checkpoint_is_kept(self):
        L = self._learner()
        numbered = L.ck_dir / "unit_u0001.pt"
        numbered.write_bytes(b"FIRST-ATTEMPT")                      # crash after it, before _latest; resume re-runs
        rec, reasons, crash = L.one_update(0)
        self.assertFalse(crash)
        self.assertEqual(numbered.read_bytes(), b"FIRST-ATTEMPT")
        self.assertTrue((L.ck_dir / "unit_latest.pt").exists())
        self.assertTrue(any("already exists" in m for m in L.log.lines))


# ------------------------------------------------------------------------------------------------------
def _big_put_child(q, ev, nbytes):
    """An actor-like spawn child: the actor's queue setup (``rl_royale.actor_sender``), one large put that nobody will
    ever read, then return -- the process must still exit promptly."""
    send = RL.actor_sender(q)
    send(("done", 0, 0, b"x" * nbytes))
    ev.set()


class TestActorExitWithUnreadPut(unittest.TestCase):
    """Verifier F1: a spawn child that put a multi-MB payload on an mp.Queue nobody reads must not hang at exit."""

    def test_exits_promptly(self):
        import multiprocessing as mp
        try:
            ctx = mp.get_context("spawn")
        except ValueError:
            self.skipTest("no spawn start method")
        q, ev = ctx.Queue(), ctx.Event()
        p = ctx.Process(target=_big_put_child, args=(q, ev, 5_000_000), daemon=True)
        p.start()
        try:
            self.assertTrue(ev.wait(120), "child never reached its put (import too slow?)")
            t0 = time.perf_counter()
            p.join(10)
            exit_s = time.perf_counter() - t0
            self.assertFalse(p.is_alive(), "actor-like child hung at exit after an unread 5 MB put")
            self.assertLess(exit_s, 10.0)
            self.assertEqual(p.exitcode, 0)
        finally:
            if p.is_alive():
                p.kill()
                p.join(5)


if __name__ == "__main__":
    unittest.main()
