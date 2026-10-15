"""F6' (rl_royale ``kl_ref_gate_max_elixir`` / ``kl_ref_gate_target_frac``): the gate anchored to the kl_ref_gate net
ONLY on rows with own elixir < X, with its own adaptive coefficient beta_g; + the critic_ctx RNG fix (_ctx_setup).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_f6lo.py

Covers: config hash / validation / overrides / actor flag; the actor's exact-elixir rows (real SelfPlayMatch, fake env);
collate; the low / high split in ref_terms and minibatch_loss against two different gate nets; the shared leash ignores
the low-row KL; beta_g's rule; checkpoint save -> resume of beta_g + the update-0 target; the band monitors; one_update
end to end; absent keys and kl_ref_gate alone = the pre-change trainer (commit a82b137); _ctx_setup leaves the CPU and
CUDA RNG states untouched.
"""
from __future__ import annotations

import copy
import subprocess
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_rl_gae import SPEC, TAU, T, _learner, _strip, _Tmp   # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

PRE = "a82b137"             # the last commit before F6': the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
GAE = dict(advantage="gae", critic_warmup_updates=1, seed=0, beta0=0.3)
LO = dict(kl_ref_gate="imit.pt", kl_ref_gate_max_elixir=4.0)


def _pre_module():
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_pre_f6lo")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_pre_f6lo", "exec"), mod.__dict__)
    return mod


def _with_elixir(results, seed=0):
    """Synthetic own-elixir rows in [0, 10] on every trajectory."""
    rng = np.random.default_rng(seed)
    out = copy.deepcopy(results)
    for r in out:
        r["traj"]["elixir"] = np.round(rng.uniform(0.0, 10.0, len(r["traj"]["played"])), 3)
    return out


def _lo_learner(model, results, tmp, imit, **extra):
    L = _learner(RL, model, results, tmp, **{**GAE, **LO, **extra})
    L.gate_ref = copy.deepcopy(imit).eval()
    return L


# ------------------------------------------------------------------------------------------------------
class TestConfig(unittest.TestCase):
    def test_hash(self):
        cfg = RL.load_config(YAML, [], False)
        self.assertNotIn("kl_ref_gate_max_elixir", cfg)
        P = _pre_module()
        g = dict(cfg, kl_ref_gate="x.pt")
        for c in (cfg, g):                                                       # off, and F6 alone: the old hash
            self.assertEqual(RL.config_sha(c), P.config_sha(c))
            self.assertEqual(RL.config_sha(c), RL.config_sha(dict(c, kl_ref_gate_max_elixir=None)))
        on = RL.config_sha(dict(g, kl_ref_gate_max_elixir=4.0))
        self.assertNotIn(on, (RL.config_sha(cfg), RL.config_sha(g)))
        self.assertNotEqual(on, RL.config_sha(dict(g, kl_ref_gate_max_elixir=4.0, kl_ref_gate_target_frac=0.25)))
        self.assertNotEqual(on, RL.config_sha(dict(g, kl_ref_gate_max_elixir=2.0)))

    def test_validation(self):
        self.assertIsNone(RL.gate_lo_cfg({}))
        self.assertIsNone(RL.gate_lo_cfg({"kl_ref_gate": "x.pt", "kl_ref_gate_max_elixir": None}))
        self.assertEqual(RL.gate_lo_cfg({"kl_ref_gate": "x.pt", "kl_ref_gate_max_elixir": 4}),
                         {"max_elixir": 4.0, "frac": 0.5})
        self.assertEqual(RL.gate_lo_cfg({"kl_ref_gate": "x.pt", "kl_ref_gate_max_elixir": 2.5,
                                         "kl_ref_gate_target_frac": 1})["frac"], 1.0)
        bad = [({"kl_ref_gate_max_elixir": 4.0}, "needs kl_ref_gate"),
               ({"kl_ref_gate": None, "kl_ref_gate_max_elixir": 4.0}, "needs kl_ref_gate"),
               ({"kl_ref_gate": "x.pt", "kl_ref_gate_target_frac": 0.5}, "needs kl_ref_gate_max_elixir")]
        for v in (0, -1.0, "4", True, float("nan"), float("inf"), [4.0]):
            bad.append(({"kl_ref_gate": "x.pt", "kl_ref_gate_max_elixir": v}, "kl_ref_gate_max_elixir must"))
        for v in (0, 0.0, 1.5, -0.5, "0.5", True, float("nan")):
            bad.append(({"kl_ref_gate": "x.pt", "kl_ref_gate_max_elixir": 4.0, "kl_ref_gate_target_frac": v},
                        "kl_ref_gate_target_frac must"))
        for cfg, msg in bad:
            with self.assertRaises(SystemExit, msg=cfg) as cm:
                RL.gate_lo_cfg(cfg)
            self.assertIn(msg, str(cm.exception), cfg)

    def test_load_config_override(self):
        cfg = RL.load_config(YAML, ["kl_ref_gate=x.pt", "kl_ref_gate_max_elixir=4.0", "kl_ref_gate_target_frac=0.5"],
                             False)
        self.assertEqual(RL.gate_lo_cfg(cfg), {"max_elixir": 4.0, "frac": 0.5})

    def test_actor_cfg(self):
        base = {**RL.load_config(YAML, [], False), "grid": "lattice"}
        self.assertNotIn("record_elixir", RL.actor_cfg(base, "rollout", 0, "cpu"))
        self.assertNotIn("record_elixir", RL.actor_cfg({**base, "kl_ref_gate_max_elixir": None}, "rollout", 0, "cpu"))
        on = {**base, "kl_ref_gate_max_elixir": 4.0}
        self.assertIs(RL.actor_cfg(on, "rollout", 0, "cpu")["record_elixir"], True)
        self.assertNotIn("record_elixir", RL.actor_cfg(on, "screen", 0, "cpu"))


# ------------------------------------------------------------------------------------------------------
class TestRecording(unittest.TestCase):
    """e1_eval's real SelfPlayMatch on test_league's fake env whose TRUE elixir varies per (side, tick): each recorded
    row's ``elixir`` is the learner side's exact elixir at that decision tick."""

    @staticmethod
    def truth(s, t):
        return ((7 * t + 3 * s) % 101) / 10.0

    def _run(self, side, **cfg):
        from pipeline import e1_eval as E
        from pipeline.tests import test_league as TL
        learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
        jobs = [(0, TL._spec(0, "snapA", side), 0, {"rollout_index": 0, "update": 0})]
        res, _ = TL._run(jobs, learner, {"snapA": (opp, TL._cfg("sample", record=False))},
                         TL._cfg(record_tick=True, **cfg), make_env=lambda: TL._SPEnv(truth=self.truth), n=1)
        return res[0]["traj"]

    def test_rows(self):
        for side in (0, 1):
            tj = self._run(side, record_elixir=True)
            el, tick = tj["elixir"], tj["tick"]
            self.assertEqual((el.dtype, el.shape), (np.dtype(np.float64), tick.shape))
            self.assertGreater(len(el), 3)
            np.testing.assert_allclose(el, [min(10.0, self.truth(side, int(t))) for t in tick], atol=1e-9)
            self.assertGreater(len(set(el.tolist())), 1)                              # non-vacuous

    def test_absent_is_unchanged(self):
        on, off = self._run(0, record_elixir=True), self._run(0)
        self.assertNotIn("elixir", off)
        self.assertEqual(sorted(off), sorted(k for k in on if k != "elixir"))
        for k in off:
            self.assertEqual(off[k].tobytes(), on[k].tobytes(), k)


# ------------------------------------------------------------------------------------------------------
class TestSplit(_Tmp):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.imit = _tiny_model(6), _tiny_model(7)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))
        cls.el_results = _with_elixir(cls.results)

    def _B(self):
        Bn, _ = RL.collate(copy.deepcopy(self.el_results), 2.0, advantage="gae")
        return Bn, RL.to_device(Bn, "cpu")

    def test_band_helper(self):
        el = np.array([0.0, 1.99, 2.0, 3.5, 4.0, 6.9, 7.0, 10.0, 1.0])
        gs = np.array([1, 1, 1, 1, 1, 1, 1, 1, 0], bool)
        pl = np.array([1, 0, 1, 1, 0, 0, 1, 1, 1], bool)
        out = RL.elixir_band_play(el, gs, pl)
        self.assertEqual(list(out), ["[0,2)", "[2,4)", "[4,7)", "[7,11)"])
        self.assertEqual(out["[0,2)"], {"rows": 2, "play_rate": 0.5})            # the ungated 1.0 row is excluded
        self.assertEqual(out["[2,4)"], {"rows": 2, "play_rate": 1.0})
        self.assertEqual(out["[4,7)"], {"rows": 2, "play_rate": 0.0})
        self.assertEqual(out["[7,11)"], {"rows": 2, "play_rate": 1.0})
        self.assertEqual(RL.elixir_band_play([5.0], [False], [False])["[4,7)"], {"rows": 0, "play_rate": None})

    def test_collate(self):
        Bn, _ = self._B()
        B0, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        self.assertEqual(sorted(Bn), sorted(list(B0) + ["elixir"]))
        for k in B0:
            self.assertEqual(Bn[k].tobytes(), B0[k].tobytes(), k)
        for j, r in enumerate(self.el_results):
            t = r["traj"]
            np.testing.assert_array_equal(Bn["elixir"][Bn["match"] == j], t["elixir"][t["gate_sampled"] | t["played"]])

    def test_ref_terms_split(self):
        _, B = self._B()
        N = len(B["A"])
        ref = copy.deepcopy(self.model).eval()
        with torch.no_grad():
            x_init = RL.policy_terms(ref, B, torch.arange(N), TAU, T)["x"]
            x_imit = RL.policy_terms(self.imit, B, torch.arange(N), TAU, T)["x"]
        R = RL.ref_terms(ref, B, TAU, T, gate_ref=self.imit, gate_lo_max=4.0)
        low, gs = B["elixir"] < 4.0, B["gate_sampled"]
        self.assertTrue(torch.equal(R["low"], low))
        self.assertTrue((gs & low).sum() >= 10 and (gs & ~low).sum() >= 10)          # both sides populated
        self.assertTrue(torch.equal(R["x"][low], x_imit[low]))
        self.assertTrue(torch.equal(R["x"][~low], x_init[~low]))
        sel = gs & low
        self.assertAlmostEqual(R["kl_lo_init"], float(RL.bern_kl(x_init[sel], x_imit[sel]).mean()), places=12)
        self.assertGreater(R["kl_lo_init"], 1e-4)
        self.assertAlmostEqual(R["ent"]["gate"], float(RL.bern_ent(R["x"][gs]).mean()), places=12)
        base = RL.ref_terms(ref, B, TAU, T)                                         # card / cell untouched
        for k in ("card_lp", "cell_lp", "play_pos"):
            self.assertTrue(torch.equal(R[k], base[k]), k)
        with self.assertRaises(ValueError):
            RL.ref_terms(ref, B, TAU, T, gate_lo_max=4.0)                         # no gate_ref
        Bx = {k: v for k, v in B.items() if k != "elixir"}
        with self.assertRaises(ValueError):
            RL.ref_terms(ref, Bx, TAU, T, gate_ref=self.imit, gate_lo_max=4.0)    # no elixir rows

    def test_minibatch_split(self):
        """Low rows' KL is against the imitation gate, high rows' against init; beta_g scales only the low term."""
        _, B = self._B()
        N = len(B["A"])
        idx = torch.arange(N)
        ref = copy.deepcopy(self.model).eval()
        R = RL.ref_terms(ref, B, TAU, T, gate_ref=self.imit, gate_lo_max=4.0)
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
        low, gs = B["elixir"] < 4.0, B["gate_sampled"]
        third = _tiny_model(9)                                                      # differs from both nets
        with torch.no_grad():
            x_init = RL.policy_terms(ref, B, idx, TAU, T)["x"]
            x_imit = RL.policy_terms(self.imit, B, idx, TAU, T)["x"]
            x3 = RL.policy_terms(third, B, idx, TAU, T)["x"]
        for net, x in ((self.model, x_init), (third, x3)):
            losses = {}
            for bg in (0.0, 1.0):
                loss, st = RL.minibatch_loss(net, B, {**R, "beta_g": bg}, idx, **kw)
                losses[bg] = float(loss)
            want_lo = float(RL.bern_kl(x[gs & low], x_imit[gs & low]).mean())
            want_hi = float(RL.bern_kl(x[gs & ~low], x_init[gs & ~low]).mean())
            # float32 forwards with / without grad differ in the last bits: 1e-6 relative
            self.assertAlmostEqual(st["kl_gate_imit_low"] / want_lo, 1.0, places=6)
            self.assertAlmostEqual(st["kl_gate"], want_hi, delta=1e-6 * max(want_hi, 1e-4))
            self.assertAlmostEqual((losses[1.0] - losses[0.0]) / want_lo, 1.0, places=5)
            self.assertGreater(want_lo, 1e-4)
            if net is self.model:
                self.assertLess(st["kl_gate"], 1e-10)                              # the init = the high rows' ref
            else:
                self.assertGreater(st["kl_gate"], 1e-4)
        # without the split the same R keys give the plain loss (no kl_gate_imit_low key)
        _, st0 = RL.minibatch_loss(self.model, B, RL.ref_terms(ref, B, TAU, T), idx, **kw)
        self.assertNotIn("kl_gate_imit_low", st0)

    def test_update0_leash_and_beta_g(self):
        """Update 0 without warm-up: target = frac x KL(init || imit) on the low rows; the on-policy check includes
        the high-row KL_gate; the shared leash = max(KL_gate_high, card, cell), never the low-row KL; beta_g follows
        adapt_beta around the target."""
        for frac in (0.5, 0.25):
            L = _lo_learner(self.model, self.el_results, self.tmp / str(frac), self.imit, critic_warmup_updates=0,
                            leash="max", kl_ref_gate_target_frac=frac)
            rec, _, crash = L.one_update(0)
            self.assertFalse(crash)
            g = rec["gate_lo"]
            self.assertAlmostEqual(g["target"], frac * g["kl_lo_init"], places=12)
            self.assertEqual(L.gate_lo_target, g["target"])
            self.assertLess(rec["first_minibatch"]["kl_gate"], RL.ASSERT_KL)       # high rows vs init: ~0 at u0
            self.assertEqual(rec["kl_leash"], max(rec["kl_gate"], rec["kl_card"], rec["kl_cell"]))
            self.assertGreater(g["kl_gate_imit_low"], rec["kl_leash"])            # non-vacuous: the low KL is larger
            self.assertEqual(rec["beta_next"], RL.adapt_beta(rec["beta_used"], rec["kl_leash"], 0.1, 0.03, 3.0))
            self.assertEqual(g["beta_g_used"], 0.3)
            self.assertEqual(g["beta_g_next"], RL.adapt_beta(0.3, g["kl_gate_imit_low"], g["target"], 0.03, 3.0))
            self.assertEqual(g["beta_g_next"], 0.6)                               # KL ~ 1/frac x target > 1.5 x
            self.assertEqual(L.beta_g, 0.6)
            self.assertTrue(any(m.startswith("[rl] kl_ref_gate_max_elixir 4.0: update-0 KL_gate_imit_low")
                                for m in L.log.lines))

    def test_adapt_rule(self):
        for kl, want in ((0.31, 0.6), (0.3, 0.3), (0.14, 0.3), (0.13, 0.15)):      # target 0.2: x2 > 0.3, /2 < 0.133
            self.assertAlmostEqual(RL.adapt_beta(0.3, kl, 0.2, 0.03, 3.0), want)
        self.assertEqual(RL.adapt_beta(2.0, 10.0, 0.2, 0.03, 3.0), 3.0)
        self.assertEqual(RL.adapt_beta(0.04, 0.0, 0.2, 0.03, 3.0), 0.03)

    def test_monitors(self):
        L = _lo_learner(self.model, self.el_results, self.tmp, self.imit, critic_warmup_updates=0)
        rec, _, _ = L.one_update(0)
        g = rec["gate_lo"]
        Bn, _ = self._B()
        self.assertEqual(g["play_rate_by_elixir"], RL.elixir_band_play(Bn["elixir"], Bn["gate_sampled"], Bn["played"]))
        self.assertEqual(sum(v["rows"] for v in g["play_rate_by_elixir"].values()), int(Bn["gate_sampled"].sum()))
        lo = Bn["gate_sampled"] & (Bn["elixir"] < 4.0)
        self.assertEqual(g["rows_low"], int(lo.sum()))
        self.assertAlmostEqual(g["learner_play_rate_low"], float(Bn["played"][lo].mean()), places=12)
        _, B = self._B()
        with torch.no_grad():
            xi = RL.policy_terms(self.imit, B, torch.arange(len(B["A"])), TAU, T)["x"]
        self.assertAlmostEqual(g["imit_p_play_low"], float(torch.sigmoid(xi[torch.from_numpy(lo)]).mean()), places=12)
        for k in ("kl_gate_imit_low", "target", "beta_g_used", "beta_g_next", "kl_gate_init_high"):
            self.assertIsNotNone(g[k], k)
        self.assertEqual(g["kl_gate_init_high"], rec["kl_gate"])
        self.assertIn("gate_lo KL", L.log.lines[-1])

    def test_one_update_end_to_end(self):
        L = _lo_learner(self.model, self.el_results, self.tmp, self.imit)          # warm-up 1, then 2 policy updates
        for u in range(3):
            rec, _, crash = L.one_update(u)
            self.assertFalse(crash)
            g = rec["gate_lo"]
            self.assertTrue(np.isfinite(g["kl_gate_imit_low"]))
            if u == 0:
                self.assertTrue(rec["gae"]["critic_warmup"])
                self.assertEqual(g["beta_g_next"], g["beta_g_used"])            # held through the warm-up
        self.assertFalse(rec["gae"]["critic_warmup"])
        self.assertEqual(L.update, 3)

    def test_checkpoint_resume(self):
        L = _lo_learner(self.model, self.el_results, self.tmp / "a", self.imit)
        for u in range(2):
            L.one_update(u)
        ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        self.assertEqual((ck["rl"]["beta_g"], ck["rl"]["gate_lo_target"]), (L.beta_g, L.gate_lo_target))
        self.assertIsNotNone(L.gate_lo_target)
        L2 = _lo_learner(_tiny_model(11), self.el_results, self.tmp / "b", self.imit)
        L2.ref = copy.deepcopy(L.ref)
        L2._restore(L.ck_dir / "unit_latest.pt")
        self.assertEqual((L2.beta_g, L2.gate_lo_target), (L.beta_g, L.gate_lo_target))
        ra, _, _ = L.one_update(2)
        rb, _, _ = L2.one_update(2)
        self.assertEqual(_strip(ra), _strip(rb))
        # a checkpoint from a run WITHOUT the key: beta_g restarts at beta0, no target -> refuses past update 0
        L3 = _learner(RL, self.model, self.results, self.tmp / "c", **GAE)
        L3.one_update(0)
        L4 = _lo_learner(self.model, self.el_results, self.tmp / "d", self.imit)
        L4._restore(L3.ck_dir / "unit_latest.pt")
        self.assertEqual((L4.beta_g, L4.gate_lo_target), (0.3, None))
        self.assertTrue(any("no beta_g" in m for m in L4.log.lines))
        with self.assertRaises(SystemExit):
            L4.one_update(1)


# ------------------------------------------------------------------------------------------------------
class TestAbsentIsPre(_Tmp):
    """kl_ref_gate_max_elixir absent / null -- with and without kl_ref_gate (F6 alone) -- = commit a82b137: whole gae
    updates (records, weights, beta, rng), checkpoint rl keys and config hash."""

    @classmethod
    def setUpClass(cls):
        cls.P = _pre_module()
        cls.model, cls.imit = _tiny_model(6), _tiny_model(7)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        for gate in (False, True):
            extra = {"kl_ref_gate": "imit.pt"} if gate else {}
            runs = {}
            for name, mod, ex in (("pre", self.P, {}), ("absent", RL, {}), ("null", RL, {"kl_ref_gate_max_elixir": None})):
                L = _learner(mod, self.model, self.results, self.tmp / f"{gate}_{name}", **GAE, **extra, **ex)
                if gate:
                    L.gate_ref = copy.deepcopy(self.imit).eval()
                recs = [_strip(L.one_update(u)[0]) for u in range(3)]
                ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
                runs[name] = (recs, L.beta, {k: v.clone() for k, v in L.model.state_dict().items()},
                              L.rng.bit_generator.state, sorted(ck["rl"]), ck["rl"]["config_sha256"])
                self.assertIsNone(getattr(L, "beta_g", None))
            recs_p, beta_p, sd_p, rng_p, keys_p, sha_p = runs["pre"]
            for name in ("absent", "null"):
                recs, beta, sd, rng, keys, sha = runs[name]
                self.assertEqual(recs, recs_p, (gate, name))
                self.assertEqual((beta, rng, keys, sha), (beta_p, rng_p, keys_p, sha_p), (gate, name))
                for k in sd_p:
                    self.assertTrue(torch.equal(sd[k], sd_p[k]), (gate, name, k))
            self.assertFalse(any("gate_lo" in r for r in runs["absent"][0]))

    def test_minibatch_identical(self):
        B = RL.to_device(RL.collate(copy.deepcopy(self.results), 2.0)[0], "cpu")
        N = len(B["A"])
        ref = copy.deepcopy(self.model).eval()
        for gr in (None, self.imit):
            Rp, Rn = self.P.ref_terms(ref, B, TAU, T, gate_ref=gr), RL.ref_terms(ref, B, TAU, T, gate_ref=gr)
            self.assertEqual(sorted(Rp), sorted(Rn))
            kw = dict(tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
            lp, sp = self.P.minibatch_loss(self.model, B, Rp, torch.arange(N), **kw)
            ln, sn = RL.minibatch_loss(self.model, B, Rn, torch.arange(N), **kw)
            self.assertEqual((float(lp), sp), (float(ln), sn))


# ------------------------------------------------------------------------------------------------------
class TestCtxSetupRng(unittest.TestCase):
    """Blind-verifier finding on a82b137: torch.manual_seed reseeds CUDA too, fork_rng(devices=[]) restored CPU only."""

    def _L(self, mod):
        L = mod.Learner.__new__(mod.Learner)
        L.cfg = {"critic_ctx": "full", "seed": 3, "lr": 1e-4}
        L.model, L.dev = SimpleNamespace(value_head=SimpleNamespace(in_features=16)), torch.device("cpu")
        return L

    def test_rng_states_untouched(self):
        torch.manual_seed(1234)
        torch.rand(5)
        cuda = torch.cuda.is_available()
        if cuda:
            torch.cuda.manual_seed_all(4321)
            torch.rand(3, device="cuda")
        cpu0 = torch.get_rng_state().clone()
        cuda0 = [torch.cuda.get_rng_state(i).clone() for i in range(torch.cuda.device_count())] if cuda else []
        L = self._L(RL)
        L._ctx_setup()
        self.assertTrue(torch.equal(torch.get_rng_state(), cpu0))
        for i, s in enumerate(cuda0):
            self.assertTrue(torch.equal(torch.cuda.get_rng_state(i), s), f"cuda:{i}")
        # the head's init is unchanged by the fix (same seed, same draws as the pre-fix code)
        Lp = self._L(_pre_module())
        Lp._ctx_setup()
        for (n, a), b in zip(L.ctx_head.state_dict().items(), Lp.ctx_head.state_dict().values()):
            self.assertTrue(torch.equal(a, b), n)


if __name__ == "__main__":
    unittest.main()
