"""
the R2 residual critic V_eff = Phi + s v_net and the time-based discount ``gae_gamma_unit: tick``.

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_rl_gamma_tick.py

Covers: defaults bit-identical to commit 85966cb (collate arrays with phi_state/tick recorded but unread, whole updates
in match_loo AND gae mode, weights compared with torch.equal); the residual critic (= the shaped-critic method;
differs from R1 when v_net is not exact; = the true-value advantage when the residual is exact; gae_batch target and
monitors; adv_cfg rejects shaping without warm-up or with too small a scale); tick-gamma GAE
hand-computed on irregular ticks; the shaping telescoping identity with a per-step gamma; equal gaps with
gamma_tick^gap = gamma_row reproduce the row unit; e1_eval records ``tick`` only under record_tick; config checks.
No engine, no GPU.
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

import torch                                                              # noqa: E402

from pipeline import reward_shaping as RS                                 # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_rl_gae import SPEC, _learner, _strip, _Tmp       # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402
from pipeline.tests.test_rl_shaping import SHP, _module_at, _with_phi    # noqa: E402

HEAD = "85966cb"            # the last commit before the 7b fixes
NEW_KEYS = ("gae_gamma_unit", "gae_gamma_tick")


def _with_tick(results, seed=0, gap=None):
    """Attach a strictly increasing decision ``tick`` per row (irregular gaps 10..60, or a constant ``gap``)."""
    rng = np.random.default_rng(seed)
    out = copy.deepcopy(results)
    for r in out:
        n = len(r["traj"]["played"])
        d = np.full(n, gap) if gap else rng.integers(1, 7, n) * 10
        r["traj"]["tick"] = (90 + np.cumsum(d) - d[:1].sum()).astype(np.int64)
    return out


# ------------------------------------------------------------------------------------------------------
class TestDefaultIsHead(_Tmp):
    """gae_gamma_unit row (absent or explicit) = commit 85966cb, in match_loo and gae mode (shaping none)."""

    @classmethod
    def setUpClass(cls):
        cls.P = _module_at(HEAD)
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_collate_arrays_identical(self):
        for res in (self.results, _with_tick(_with_phi(self.results))):   # recorded phi_state / tick never read
            for adv in ("match_loo", "gae"):
                Bp, sp = self.P.collate(copy.deepcopy(res), 2.0, advantage=adv)
                Bn, sn = RL.collate(copy.deepcopy(res), 2.0, advantage=adv)
                self.assertEqual(sorted(Bn), sorted(Bp))
                for k in Bp:
                    self.assertEqual(Bn[k].dtype, Bp[k].dtype, k)
                    self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), (adv, k))
                self.assertEqual(sn, sp)

    def test_gae_scalar_identical(self):
        rng = np.random.default_rng(5)
        r, v, m = rng.normal(size=50), rng.uniform(-1, 1, 50), np.repeat([0, 1, 2], [20, 25, 5])
        for g, lam in ((0.999, 0.95), (0.9, 0.8), (1.0, 1.0)):
            for a, b in zip(self.P.gae(r, v, m, g, lam), RL.gae(r, v, m, g, lam)):
                self.assertEqual(a.tobytes(), b.tobytes())

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        res = _with_tick(self.results)
        explicit = {"gae_gamma_unit": "row", "gae_gamma_tick": 0.5}
        for label, base in (("match_loo", {}), ("gae", {"advantage": "gae", "critic_warmup_updates": 1}),
                            ("gae_detached", {"advantage": "gae", "vf_trunk_grad": False})):
            runs = {}
            for name, mod, extra in (("head", self.P, {}), ("absent", RL, {}), ("explicit", RL, explicit)):
                L = _learner(mod, self.model, res, self.tmp / f"{label}_{name}")
                L.cfg.update(base)
                L.cfg.update(extra)
                recs = [L.one_update(u)[0] for u in range(2)]
                runs[name] = ([_strip(r) for r in recs], L.beta,
                              {k: v.clone() for k, v in L.model.state_dict().items()}, L.rng.bit_generator.state,
                              L.log.lines)
            recs_p, beta_p, sd_p, rng_p, _ = runs["head"]
            for name in ("absent", "explicit"):
                recs, beta, sd, rng, lines = runs[name]
                self.assertEqual(recs, recs_p, (label, name))
                self.assertEqual(beta, beta_p, (label, name))
                self.assertEqual(rng, rng_p, (label, name))
                for k in sd_p:
                    self.assertTrue(torch.equal(sd[k], sd_p[k]), (label, name, k))

    def test_actor_cfg_unchanged(self):
        import yaml
        base = {**yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8")), "grid": "lattice"}
        old = {k: v for k, v in base.items() if k not in NEW_KEYS}
        for kind in ("rollout", "screen"):
            self.assertEqual(RL.actor_cfg(base, kind, 0, "cpu"), self.P.actor_cfg(old, kind, 0, "cpu"))
            self.assertNotIn("record_tick", RL.actor_cfg(base, kind, 0, "cpu"))


# ------------------------------------------------------------------------------------------------------
class TestResidualCritic(unittest.TestCase):
    """R2 residual critic V_eff = Phi + s v_net, A = GAE(r, V_eff). Two matches (boundary reset), scalar and per-step
    gamma, general (not only terminal) rewards."""
    S = 1.5

    def setUp(self):
        rng = np.random.default_rng(11)
        self.n = (9, 14)
        self.m = np.repeat([0, 1], self.n)
        self.r = rng.normal(0, 0.3, sum(self.n))
        self.phi = rng.uniform(-0.5, 0.5, sum(self.n))
        self.gs = (0.97, np.concatenate([np.append(rng.uniform(0.8, 1.0, n - 1), 1.0) for n in self.n]))
        self.rng = rng

    def _F(self, gamma):
        F = []
        for j, n in enumerate(self.n):
            sl = self.m == j
            g = gamma if np.ndim(gamma) == 0 else gamma[sl]
            F.append(RS.shaping_from_parts(self.phi[sl].tolist(), [0.0] * n, g, (1.0, 0.0))["F"])
        return np.concatenate(F)

    def test_is_the_shaped_critic_method(self):
        """GAE(r, Phi + s v) = GAE(r + F, s v): a critic s v on the shaped reward; ret - Phi = the shaped return."""
        for g in self.gs:
            F = self._F(g)
            for _ in range(3):
                v = self.rng.uniform(-1, 1, len(self.r))
                for lam in (0.0, 0.95, 1.0):
                    A, ret = RL.gae(self.r, self.phi + self.S * v, self.m, g, lam)
                    A2, ret2 = RL.gae(self.r + F, self.S * v, self.m, g, lam)
                    np.testing.assert_allclose(A, A2, atol=1e-12)
                    np.testing.assert_allclose(ret - self.phi, ret2, atol=1e-12)

    def test_differs_from_r1_when_v_net_not_exact(self):
        for g in self.gs:
            for _ in range(3):
                v = self.rng.uniform(-1, 1, len(self.r))
                for lam in (0.0, 0.95):
                    d = np.abs(RL.gae(self.r, self.phi + self.S * v, self.m, g, lam)[0]
                               - RL.gae(self.r, v, self.m, g, lam)[0])
                    self.assertGreater(float(d.max()), 1e-2)

    def test_exact_residual_is_true_value_advantage(self):
        for g in self.gs:
            # any true value function (a stochastic game's V is not the realised return): s v* = V_true - Phi
            V_true = self.rng.uniform(-1, 1, len(self.r))
            v_star = (V_true - self.phi) / self.S
            for lam in (0.0, 0.5, 0.95, 1.0):
                np.testing.assert_allclose(RL.gae(self.r, self.phi + self.S * v_star, self.m, g, lam)[0],
                                           RL.gae(self.r, V_true, self.m, g, lam)[0], atol=1e-12)
            # deterministic trajectory: V_true = the return-to-go -> A = 0, and v*'s target (ret - Phi)/s = v*
            G = RL.gae(self.r, np.zeros(len(self.r)), self.m, g, 1.0)[1]
            v_star = (G - self.phi) / self.S
            for lam in (0.0, 0.95, 1.0):
                A, ret = RL.gae(self.r, self.phi + self.S * v_star, self.m, g, lam)
                np.testing.assert_allclose(A, 0.0, atol=1e-12)
                np.testing.assert_allclose((ret - self.phi) / self.S, v_star, atol=1e-12)

    def test_scale_bound_keeps_target_in_value_head_range(self):
        """|G| <= 1 and |Phi| < w_t + (2/3) w_c (= 0.5 at w 0.3): the exact residual (G - Phi) / s stays in [-1, 1]
        at the default s = 1.5."""
        s = RL.GAE_DEFAULTS["shaping_critic_scale"]
        bound = 1.0 + RL.GAE_DEFAULTS["shaping_w_tower"] + 2.0 / 3.0 * RL.GAE_DEFAULTS["shaping_w_crown"]
        self.assertGreaterEqual(s, bound)
        for G in (-1.0, 1.0):
            for ph in (-0.5, 0.5):
                self.assertLessEqual(abs(G - ph) / s, 1.0)

    def test_gae_batch(self):
        model = _tiny_model(6)
        res = _with_tick(_with_phi(_monitor_fields(_results(model, SPEC, seed=13)), seed=2), seed=3)
        cfg = {"advantage": "gae", "gae_gamma": 0.99, "gae_lambda": 0.9, "shaping": "tower_crown",
               "critic_warmup_updates": 1, "shaping_critic_scale": 1.7}
        for tick in (None, 0.9995):
            kw = {} if tick is None else {"gamma_tick": tick}
            Bn, _ = RL.collate(copy.deepcopy(res), 2.0, advantage="gae", shaping={**SHP, "gamma": 0.99}, **kw)
            B = RL.to_device(Bn, "cpu")
            st = RL.gae_batch(model, B, cfg)
            v = B["v_old"].numpy()                                           # v_net, the raw value head
            g = Bn["gamma_row"] if tick else 0.99
            veff = Bn["phi"] + 1.7 * v
            A, ret = RL.gae(Bn["r_step"], veff, Bn["match"], g, 0.9)
            self.assertEqual(B["ret"].numpy().tobytes(), ((ret - Bn["phi"]) / 1.7).tobytes())   # v_net's target
            np.testing.assert_array_equal(B["A"].numpy(), (A - A.mean()) / (A.std() + 1e-8))
            a_r1 = RL.gae(Bn["r_step"], v, Bn["match"], g, 0.9)[0]
            self.assertAlmostEqual(st["adv_r1_diff"], float(np.abs(A - a_r1).mean()), places=15)
            self.assertGreater(st["adv_r1_diff"], 1e-3)                       # shaping changes the advantages
            self.assertAlmostEqual(st["phi_share"], float(np.abs(Bn["phi"]).mean() / np.abs(veff).mean()), places=12)
            self.assertAlmostEqual(st["explained_var"], RL.explained_variance(veff, ret), places=12)
            self.assertEqual(st["critic_scale"], 1.7)
            self.assertGreater(float(np.abs(Bn["phi"]).max()), 0.01)          # shaping is not trivially zero here


# ------------------------------------------------------------------------------------------------------
class TestTickGamma(unittest.TestCase):

    def test_row_gammas(self):
        np.testing.assert_allclose(RL.row_gammas([90, 100, 125, 130], 0.9), [0.9 ** 10, 0.9 ** 25, 0.9 ** 5, 1.0])
        self.assertEqual(RL.row_gammas([90], 0.9).tolist(), [1.0])
        for bad in ([90, 90], [100, 90]):
            with self.assertRaises(ValueError):
                RL.row_gammas(bad, 0.9)

    def test_hand_computed_irregular_ticks(self):
        # ticks 0, 2, 5, 6 with gamma_tick 0.9 -> gamma_t = 0.81, 0.729, 0.9 (last unused); lambda 0.5
        r, v = [0.0, 0.0, 0.0, 1.0], [0.2, -0.1, 0.4, 0.5]
        g = RL.row_gammas([0, 2, 5, 6], 0.9)
        A, ret = RL.gae(r, v, [0] * 4, g, 0.5)
        d3 = 1.0 - 0.5                                                    # V after the last row = 0
        d2 = 0.0 + 0.9 * 0.5 - 0.4
        d1 = 0.0 + 0.729 * 0.4 + 0.1
        d0 = 0.0 + 0.81 * -0.1 - 0.2
        a3 = d3
        a2 = d2 + 0.9 * 0.5 * a3
        a1 = d1 + 0.729 * 0.5 * a2
        a0 = d0 + 0.81 * 0.5 * a1
        np.testing.assert_allclose(A, [a0, a1, a2, a3], atol=1e-12)
        np.testing.assert_allclose(ret, np.add([a0, a1, a2, a3], v), atol=1e-12)
        _, ret1 = RL.gae(r, v, [0] * 4, g, 1.0)                           # lambda 1: discount = 0.9^(ticks to end)
        np.testing.assert_allclose(ret1, [0.9 ** 6, 0.9 ** 4, 0.9 ** 1, 1.0], atol=1e-12)

    def test_shaping_telescopes_per_step_gamma(self):
        rng = np.random.default_rng(7)
        rows = np.concatenate([rng.uniform(0, 1, (30, 6)), rng.integers(0, 4, (30, 2))], axis=1)
        g = RL.row_gammas(np.cumsum(rng.integers(1, 9, 30) * 10), 0.999)
        sh = RL.shaping_rewards(rows, {**SHP, "gamma": g})
        _, rtg = RL.gae(sh["F"], np.zeros(30), np.zeros(30), g, 1.0)     # sum_k (prod_{t<=i<k} gamma_i) F_k
        np.testing.assert_allclose(rtg, -sh["phi"], atol=1e-12)         # = -Phi(s_t) on every row
        disc = np.concatenate([[1.0], np.cumprod(g[:-1])])
        self.assertAlmostEqual(float((disc * sh["F"]).sum()), -float(sh["phi"][0]), places=12)

    def test_collate_tick_mode(self):
        """Per-row gamma from the KEPT rows' ticks (dropped rows' gaps add up); F uses the same gamma_t; lambda 1,
        V = 0 return = the outcome discounted by gamma_tick^(ticks to the last kept row) - Phi(s_t)."""
        model = _tiny_model(2)
        res = _with_tick(_with_phi(_results(model, [(0, 0, 9, "win"), (0, 1, 7, "loss"), (1, 0, 8, "draw"),
                                                    (1, 1, 6, "win")], seed=4), seed=1, garbage_unkept=True), seed=5)
        gt = 0.999
        B, st = RL.collate(copy.deepcopy(res), 2.0, advantage="gae", shaping=SHP, gamma_tick=gt)
        Bd, _ = RL.collate(copy.deepcopy(res), 2.0, advantage="gae", shaping=SHP)
        self.assertEqual(sorted(B), sorted(list(Bd) + ["gamma_row"]))
        for j, r in enumerate(res):
            t = r["traj"]
            keep = t["gate_sampled"] | t["played"]
            m = B["match"] == j
            tk = t["tick"][keep]
            np.testing.assert_array_equal(B["gamma_row"][m], RL.row_gammas(tk, gt))
            sh = RL.shaping_rewards(t["phi_state"][keep], {**SHP, "gamma": RL.row_gammas(tk, gt)})
            np.testing.assert_array_equal(B["phi"][m], sh["phi"])
            n = int(m.sum())
            _, ret = RL.gae(B["r_step"][m] + sh["F"], np.zeros(n), np.zeros(n), B["gamma_row"][m], 1.0)
            np.testing.assert_allclose(ret, gt ** (tk[-1] - tk) * RL.reward(r["outcome"]) - sh["phi"], atol=1e-12)
        with self.assertRaises(ValueError):
            RL.collate(copy.deepcopy(res), 2.0, gamma_tick=gt)                # match_loo

    def test_equal_gaps_reproduce_row_unit(self):
        model = _tiny_model(2)
        res = _with_tick(_with_phi(_monitor_fields(_results(model, SPEC, seed=13))), gap=10)
        # every DROPPED row breaks the equal-gap pattern on kept rows, so keep every row for this check
        for r in res:
            r["traj"]["gate_sampled"][:] = True
        gt = 0.9999
        g_row = float(np.float64(gt) ** np.float64(10.0))                 # gamma_tick^gap, the same float op
        Bt, _ = RL.collate(copy.deepcopy(res), 2.0, advantage="gae", shaping={**SHP, "gamma": g_row}, gamma_tick=gt)
        Br, _ = RL.collate(copy.deepcopy(res), 2.0, advantage="gae", shaping={**SHP, "gamma": g_row})
        last = np.append(Bt["match"][1:] != Bt["match"][:-1], True)
        np.testing.assert_array_equal(Bt["gamma_row"][~last], g_row)
        np.testing.assert_array_equal(Bt["phi"], Br["phi"])
        Ft, Fr = [], []
        for j in np.unique(Bt["match"]):                                  # F aligned row for row, same values
            ph = res[j]["traj"]["phi_state"]
            Ft.append(RL.shaping_rewards(ph, {**SHP, "gamma": Bt["gamma_row"][Bt["match"] == j]})["F"])
            Fr.append(RL.shaping_rewards(ph, {**SHP, "gamma": g_row})["F"])
        np.testing.assert_array_equal(np.concatenate(Ft), np.concatenate(Fr))
        v = np.random.default_rng(0).uniform(-1, 1, len(Bt["r_step"]))
        for lam in (0.95, 1.0):                                           # the residual-critic GAE, both units
            At, rt = RL.gae(Bt["r_step"], Bt["phi"] + 1.5 * v, Bt["match"], Bt["gamma_row"], lam)
            Ar, rr = RL.gae(Br["r_step"], Br["phi"] + 1.5 * v, Br["match"], g_row, lam)
            np.testing.assert_array_equal(At, Ar)
            np.testing.assert_array_equal(rt, rr)


# ------------------------------------------------------------------------------------------------------
class TestTickWiring(_Tmp):

    def test_config(self):
        c = RL.adv_cfg({"advantage": "gae", "gae_gamma_unit": "tick"})
        self.assertEqual((c["gae_gamma_unit"], c["gae_gamma_tick"]), ("tick", 0.99994))
        for bad in ({"gae_gamma_unit": "tick"}, {"advantage": "gae", "gae_gamma_unit": "second"},
                    {"advantage": "gae", "gae_gamma_tick": 0.0}, {"advantage": "gae", "gae_gamma_tick": 1.01},
                    {"advantage": "gae", "gae_gamma_tick": "0.9"},
                    {"advantage": "gae", "shaping": "tower_crown", "critic_warmup_updates": 0},
                    {"advantage": "gae", "shaping": "tower_crown", "critic_warmup_updates": 1,
                     "shaping_critic_scale": 1.4},
                    {"advantage": "gae", "shaping_critic_scale": 0.0}):
            with self.assertRaises(SystemExit, msg=bad) as cm:
                RL.adv_cfg(bad)
            self.assertTrue(any(k in str(cm.exception) for k in bad if k not in ("advantage", "shaping")),
                            (bad, str(cm.exception)))
        c = RL.adv_cfg({"advantage": "gae", "shaping": "tower_crown", "critic_warmup_updates": 1})
        self.assertEqual(c["shaping_critic_scale"], 1.5)
        with self.assertRaises(SystemExit):                                  # heavier weights need a larger scale
            RL.adv_cfg({"advantage": "gae", "shaping": "tower_crown", "critic_warmup_updates": 1,
                        "shaping_w_tower": 0.6})

    def test_default_horizon_matches_row_unit(self):
        """league1c: 279 kept rows over ~4330 ticks a match -> 15.5 ticks a row (row_gammas docstring)."""
        gt, gr = RL.GAE_DEFAULTS["gae_gamma_tick"], RL.GAE_DEFAULTS["gae_gamma"]
        self.assertAlmostEqual(gt ** 15.5, gr, delta=2e-4)
        self.assertAlmostEqual(gt ** 4330, gr ** 279, delta=0.02)

    def test_actor_flags(self):
        import yaml
        base = {**yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8")), "grid": "lattice"}
        on = {**base, "advantage": "gae", "gae_gamma_unit": "tick"}
        self.assertTrue(RL.actor_cfg(on, "rollout", 0, "cpu")["record_tick"])
        self.assertNotIn("record_tick", RL.actor_cfg(on, "screen", 0, "cpu"))
        model = _tiny_model(2)
        with tempfile.TemporaryDirectory() as d:
            for extra, want in (({}, False), ({"advantage": "gae", "gae_gamma_unit": "tick"}, True)):
                L = _learner(RL, model, [], Path(d), **extra)
                L.grid = "lattice"
                L.cfg = {**yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8")), **L.cfg}
                b = L.actor_base()
                self.assertEqual("gae_gamma_unit" in b, want)
                self.assertEqual(bool(RL.actor_cfg(b, "rollout", 0, "cpu").get("record_tick")), want)

    def test_recording(self):
        from pipeline import e1_eval as E
        from pipeline.tests import test_league as TL
        learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
        jobs = [(0, TL._spec(0, "snapA", 0), 0, {"rollout_index": 0, "update": 0})]
        for kw, want in (({}, False), ({"record_tick": True}, True)):
            res, _ = TL._run(jobs, learner, {"snapA": (opp, TL._cfg("sample", record=False))}, TL._cfg(**kw), n=1)
            t = res[0]["traj"]
            self.assertEqual("tick" in t, want)
            if want:
                self.assertEqual(t["tick"].dtype, np.int64)
                self.assertEqual(len(t["tick"]), len(t["played"]))
                self.assertTrue((np.diff(t["tick"]) > 0).all())
                self.assertGreaterEqual(int(t["tick"][0]), 0)

    def test_one_update_tick_and_shaping(self):
        model = _tiny_model(6)
        res = _with_tick(_with_phi(_monitor_fields(_results(model, SPEC, seed=13)), seed=2), seed=3)
        L = _learner(RL, model, res, self.tmp, advantage="gae", critic_warmup_updates=1, shaping="tower_crown",
                     gae_gamma_unit="tick")
        for u in range(2):
            rec, _, crash = L.one_update(u)
            self.assertFalse(crash)
            g = rec["gae"]
            self.assertEqual((g["gamma_unit"], g["gamma_tick"]), ("tick", 0.99994))
            self.assertTrue(0.99 < g["gamma_row_mean"] < 1.0)
            self.assertGreater(g["adv_r1_diff"], 0.0)
            self.assertGreater(g["phi_share"], 0.0)
            self.assertEqual(g["critic_scale"], 1.5)


if __name__ == "__main__":
    unittest.main()
