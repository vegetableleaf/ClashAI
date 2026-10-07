"""Lever C (``shaping: value_phi``) in pipeline/rl_royale.py: potential shaping whose Phi is w x the causal trailing
mean of a FROZEN net's P(win) - P(loss) (evidence: scratchpad/gauntlet/L73/phi_eval/results_smooth.json).

    ROYALE_RUNTIME=20261006 research/ext/Royale/.venv/Scripts/python.exe -m unittest pipeline.tests.test_value_phi -v

Covers: shaping none / tower_crown bit-identical to PRE_COMMIT (collate arrays, actor_cfg, whole updates); telescoping
(gamma 1: sum F = -Phi(s_0)); causality (a later row never moves an earlier Phi, at the smoothing AND through collate
with a real net); the Phi net stays frozen across optimizer steps and is loaded from file with no grad; |Phi| <= w and
the critic-scale validator; one_update with value_phi (+ branch_gate on a fake pool) and its log line. No engine.
"""
from __future__ import annotations

import copy
import unittest

import numpy as np
import torch

from pipeline import reward_shaping as RS
from pipeline import rl_royale as RL
from pipeline.tests.test_rl_gae import SPEC, _learner, _strip, _Tmp
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model
from pipeline.tests.test_rl_shaping import _module_at, _with_phi

PRE_COMMIT = "f639593"                                  # opt3-branching before lever C


def _with_tick(results, seed=0):
    rng = np.random.default_rng(seed)
    out = copy.deepcopy(results)
    for r in out:
        n = len(r["traj"]["played"])
        r["traj"]["tick"] = np.cumsum(rng.integers(5, 40, n)).astype(np.int64)
        r["end_tick"] = int(r["traj"]["tick"][-1]) + 3
    return out


def _vphi_learner(model, results, tmp, **extra):
    cfg = {"advantage": "gae", "critic_warmup_updates": 1, "shaping": "value_phi", **extra}
    L = _learner(RL, model, results, tmp, **cfg)
    L.phi_net = copy.deepcopy(model).eval()
    for p in L.phi_net.parameters():
        p.requires_grad_(False)
    return L


# ------------------------------------------------------------------------------------------------------
class TestDefaultParity(_Tmp):
    """shaping none / tower_crown (row and tick gamma units): byte-identical to the pre-lever-C trainer."""

    @classmethod
    def setUpClass(cls):
        cls.P = _module_at(PRE_COMMIT)
        cls.model = _tiny_model(6)
        cls.results = _with_tick(_with_phi(_monitor_fields(_results(cls.model, SPEC, seed=13)), seed=3))

    def test_actor_cfg(self):
        base = {"tau": 0.3, "afford_mask": True, "stall_elixir": 9, "stall_seconds": 12, "obs": "live", "grid": "lattice",
                "decide_every": 10, "T": 0.3, "noise_off": "all"}
        for extra in ({}, {"shaping": "tower_crown"}, {"gae_gamma_unit": "tick"},
                      {"shaping": "tower_crown", "gae_gamma_unit": "tick"}):
            for kind in ("rollout", "screen"):
                a = RL.actor_cfg({**base, **extra}, kind, 0, "cpu")
                b = self.P.actor_cfg({**base, **extra}, kind, 0, "cpu")
                self.assertEqual(sorted(a), sorted(b), extra)
                self.assertEqual({k: v for k, v in a.items() if k != "noise"},
                                 {k: v for k, v in b.items() if k != "noise"})
        v = RL.actor_cfg({**base, "shaping": "value_phi"}, "rollout", 0, "cpu")
        self.assertTrue(v["record_tick"])
        self.assertNotIn("record_phi", v)

    def test_collate_identical(self):
        shp = {"gamma": 0.9, "w_tower": 0.3, "w_crown": 0.3}
        for kw in ({"advantage": "match_loo"}, {"advantage": "gae"}, {"advantage": "gae", "shaping": shp},
                   {"advantage": "gae", "shaping": shp, "gamma_tick": 0.9999},
                   {"advantage": "gae", "shaping": shp, "gamma_tick": 0.9999, "gae_terminal_gap": True}):
            Bp, sp = self.P.collate(copy.deepcopy(self.results), 2.0, **kw)
            Bn, sn = RL.collate(copy.deepcopy(self.results), 2.0, **kw)
            self.assertEqual(sorted(Bn), sorted(Bp))
            for k in Bp:
                self.assertEqual(Bn[k].dtype, Bp[k].dtype, k)
                self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), (kw, k))
            self.assertEqual(sn, sp)

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        for label, cfg in (("loo", {}), ("gae", {"advantage": "gae", "critic_warmup_updates": 1}),
                           ("tc", {"advantage": "gae", "critic_warmup_updates": 1, "shaping": "tower_crown"}),
                           ("tc_tick", {"advantage": "gae", "critic_warmup_updates": 1, "shaping": "tower_crown",
                                        "gae_gamma_unit": "tick"})):
            runs = []
            for name, mod in (("old", self.P), ("new", RL)):
                L = _learner(mod, self.model, self.results, self.tmp / f"{label}_{name}", **cfg)
                recs = [L.one_update(u)[0] for u in range(2)]
                runs.append(([_strip(r) for r in recs], L.beta, L.rng.bit_generator.state,
                             {k: v.clone() for k, v in L.model.state_dict().items()}, L.log.lines[-2:]))
            (ro, bo, go, so, lo), (rn, bn, gn, sn, ln) = runs
            self.assertEqual(rn, ro, label)
            self.assertEqual((bn, gn), (bo, go), label)
            for k in so:
                self.assertTrue(torch.equal(sn[k], so[k]), (label, k))
            self.assertEqual([x.split(" wall roll")[0] for x in ln], [x.split(" wall roll")[0] for x in lo], label)


# ------------------------------------------------------------------------------------------------------
class TestMath(unittest.TestCase):
    def test_trailing_mean_window(self):
        t = [0, 100, 150, 400, 401]
        v = [1.0, 3.0, 5.0, 7.0, -7.0]
        np.testing.assert_allclose(RS.trailing_mean(v, t, 200), [1.0, 2.0, 3.0, 7.0, 0.0])   # [tick-200, tick]
        np.testing.assert_array_equal(RS.trailing_mean(v, t, 0), v)
        with self.assertRaises(ValueError):
            RS.trailing_mean(v, [0, 2, 1, 3, 4], 10)

    def test_telescopes_gamma_one(self):
        rng = np.random.default_rng(0)
        for _ in range(5):
            n = int(rng.integers(2, 60))
            raw, ticks = rng.uniform(-1, 1, n), np.cumsum(rng.integers(1, 50, n))
            out = RL.value_phi_rewards(raw, ticks, {"gamma": 1.0, "w_value": 0.5, "window_ticks": 200})
            self.assertAlmostEqual(float(out["F"].sum()), -float(out["phi"][0]), places=12)
            g = rng.uniform(0.9, 1.0, n)                             # per-row gamma: return-to-go identity
            out = RL.value_phi_rewards(raw, ticks, {"gamma": g, "w_value": 0.5, "window_ticks": 200})
            G = 0.0
            for t in range(n - 1, -1, -1):
                G = out["F"][t] + (g[t] * G if t < n - 1 else 0.0)
            self.assertAlmostEqual(G, -float(out["phi"][0]), places=12)

    def test_causal(self):
        rng = np.random.default_rng(1)
        raw, ticks = rng.uniform(-1, 1, 50), np.cumsum(rng.integers(1, 50, 50))
        base = RS.trailing_mean(raw, ticks, 200)
        for k in (10, 30, 49):
            r2 = raw.copy()
            r2[k:] = rng.uniform(-1, 1, 50 - k)
            self.assertEqual(RS.trailing_mean(r2, ticks, 200)[:k].tobytes(), base[:k].tobytes())

    def test_bound(self):
        rng = np.random.default_rng(2)
        for w in (0.1, 0.5, 1.3):
            raw = np.sign(rng.normal(size=300))                      # the extremes of P(win) - P(loss)
            out = RL.value_phi_rewards(raw, np.arange(300) * 7, {"gamma": 0.999, "w_value": w, "window_ticks": 200})
            self.assertLessEqual(float(np.abs(out["phi"]).max()), w + 1e-12)

    def test_validator(self):
        g = {"advantage": "gae", "critic_warmup_updates": 1, "shaping": "value_phi"}
        c = RL.adv_cfg(g)                                            # defaults: w 0.5, scale 1.5 = 1 + w (exact)
        self.assertEqual((c["shaping_w_value"], c["shaping_phi_window_s"], c["shaping_phi_ckpt"]), (0.5, 10.0, None))
        for bad in ({"shaping_critic_scale": 1.49}, {"shaping_w_value": 0.8}, {"critic_warmup_updates": 0},
                    {"advantage": "match_loo"}, {"shaping_w_value": -0.1}, {"shaping_phi_window_s": -1},
                    {"shaping_phi_ckpt": ""}, {"shaping_phi_ckpt": 3}):
            with self.assertRaises(SystemExit, msg=bad):
                RL.adv_cfg({**g, **bad})
        RL.adv_cfg({**g, "shaping_w_value": 0.8, "shaping_critic_scale": 1.8, "shaping_phi_ckpt": "a/b.pt"})
        with self.assertRaisesRegex(SystemExit, "1 \\+ w_value"):
            RL.adv_cfg({**g, "shaping_critic_scale": 1.2})
        RL.adv_cfg({**g, "shaping": "tower_crown"})                  # tower_crown's bound unchanged: 1.5 >= 1.5


# ------------------------------------------------------------------------------------------------------
class TestLearner(_Tmp):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.results = _with_tick(_monitor_fields(_results(cls.model, SPEC, seed=13)))

    def _shp(self, L):
        return {"mode": "value_phi", "gamma": 0.999, "w_value": 0.5, "window_ticks": 200, "phi_fn": L._phi_values}

    def test_collate_causal_through_the_net(self):
        """A later row's INPUTS changed -> every earlier Phi of that match byte-identical, later ones move."""
        L = _vphi_learner(self.model, self.results, self.tmp)
        B0, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae", shaping=self._shp(L))
        res = copy.deepcopy(self.results)
        t = res[1]["traj"]
        kept = np.flatnonzero(t["gate_sampled"] | t["played"])
        k = kept[len(kept) // 2]
        t["sc"][k] = t["sc"][k] + 3.0
        B1, _ = RL.collate(res, 2.0, advantage="gae", shaping=self._shp(L))
        m = B0["match"] == 1
        i = len(kept) // 2
        self.assertEqual(B1["phi"][m][:i].tobytes(), B0["phi"][m][:i].tobytes())
        self.assertNotEqual(B1["phi"][m][i], B0["phi"][m][i])
        for j in (0, 2, 3):
            self.assertEqual(B1["phi"][B0["match"] == j].tobytes(), B0["phi"][B0["match"] == j].tobytes())
        with self.assertRaisesRegex(ValueError, "record_tick"):
            bare = copy.deepcopy(self.results)
            del bare[0]["traj"]["tick"]
            RL.collate(bare, 2.0, advantage="gae", shaping=self._shp(L))

    def test_phi_frozen_across_steps(self):
        L = _vphi_learner(self.model, self.results, self.tmp)
        sd0 = {k: v.clone() for k, v in L.phi_net.state_dict().items()}
        m0 = {k: v.clone() for k, v in L.model.state_dict().items()}
        B0, s0 = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae", shaping=self._shp(L))
        recs = [L.one_update(u)[0] for u in range(3)]
        self.assertTrue(any(not torch.equal(m0[k], v) for k, v in L.model.state_dict().items()))   # model moved
        self.assertTrue(all(torch.equal(sd0[k], v) for k, v in L.phi_net.state_dict().items()))     # Phi net did not
        B1, s1 = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae", shaping=self._shp(L))
        self.assertEqual(B1["phi"].tobytes(), B0["phi"].tobytes())
        self.assertEqual(s1["shaping"], s0["shaping"])
        self.assertTrue(all(r["shaping"] == s0["shaping"] for r in recs))   # every update saw the same Phi

    def test_one_update_logs(self):
        L = _vphi_learner(self.model, self.results, self.tmp, gae_gamma_unit="tick")
        recs = [L.one_update(u) for u in range(2)]
        for rec, why, crash in recs:
            self.assertFalse(crash)
            sh = rec["shaping"]
            self.assertEqual((sh["mode"], sh["rows"], sh["matches"]), ("value_phi", rec["rows"], 4))
            self.assertLessEqual(sh["max_abs_phi"], 0.5)
            for k in ("mean_abs_F", "phi_step_std", "raw_step_std", "phi_end_corr"):
                self.assertIsNotNone(sh[k], k)
            self.assertLess(sh["phi_step_std"], sh["raw_step_std"])
            self.assertGreater(rec["gae"]["phi_share"], 0.0)
            self.assertGreater(rec["gae"]["adv_r1_diff"], 0.0)
            self.assertEqual(rec["gae"]["shaping"], "value_phi")
        self.assertTrue(all(" | vphi |F| " in x and " end-corr " in x and " share " in x
                            for x in L.log.lines[-2:]), L.log.lines[-2:])
        self.assertNotIn("| shape |F|", L.log.lines[-1])

    def test_with_branch_gate(self):
        from pipeline.tests.test_rl_branch import ON, _FakePool, _s1_rows, _sample
        L = _vphi_learner(self.model, self.results, self.tmp, **ON)
        rows = _s1_rows(4, 21)
        L.branch_pool = _FakePool([{**_sample(r, d, "single"), "version": 0, "worker": 0}
                                   for r, d in zip(rows, [0.5, -0.4, 0.3, -0.6])])
        L._branch_send = (lambda u, bc: None)
        rec0, _, c0 = L.one_update(0)                                # critic warm-up: buffered, no step
        L.branch_pool.pending = [{**_sample(r, d, "single"), "version": 1, "worker": 0}
                                 for r, d in zip(rows, [0.5, -0.4, 0.3, -0.6])]
        rec1, _, c1 = L.one_update(1)
        self.assertFalse(c0 or c1)
        self.assertIsNone(rec0["branch"]["step"])
        self.assertIsNotNone(rec1["branch"]["step"])
        self.assertEqual(rec1["shaping"]["mode"], "value_phi")
        self.assertIn(" | vphi |F| ", L.log.lines[-1])
        self.assertIn(" | branch n ", L.log.lines[-1])

    def test_load_phi_net_from_file(self):
        L0 = _learner(RL, self.model, self.results, self.tmp / "save")
        rec, _, _ = L0.one_update(0)
        path = rec["ckpt"]
        ick = torch.load(path, map_location="cpu")
        L = _vphi_learner(self.model, self.results, self.tmp, shaping_phi_ckpt=str(path))
        net = L._load_phi_net(ick)
        self.assertFalse(net.training)
        self.assertFalse(any(p.requires_grad for p in net.parameters()))
        sd = torch.load(path, map_location="cpu")["model"] if "model" in ick else None
        if sd is not None:
            self.assertTrue(all(torch.equal(sd[k], v) for k, v in net.state_dict().items()))
        with self.assertRaisesRegex(SystemExit, "row inputs differ"):
            L._load_phi_net({**ick, "args": {**ick["args"], "feature_version": 9}})
        L.cfg["shaping_phi_ckpt"] = str(self.tmp / "missing.pt")
        with self.assertRaisesRegex(SystemExit, "not found"):
            L._load_phi_net(ick)

    def test_load_config_accepts_new_keys(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.yaml"
            p.write_text("shaping: none\n", encoding="utf-8")
            cfg = RL.load_config(p, ["shaping=value_phi", "shaping_w_value=0.4", "shaping_phi_window_s=5",
                                     "shaping_phi_ckpt=a/b.pt"], False)
        self.assertEqual((cfg["shaping_w_value"], cfg["shaping_phi_window_s"], cfg["shaping_phi_ckpt"]),
                         (0.4, 5, "a/b.pt"))


if __name__ == "__main__":
    unittest.main()
