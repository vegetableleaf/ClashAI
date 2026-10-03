"""Offline tests for R1 per-decision credit (``advantage: gae``) in pipeline/rl_royale.py

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_rl_gae.py

Covers: the default ``match_loo`` is bit-identical to the parent commit (collate arrays + a full ``Learner.one_update``,
final weights compared with torch.equal); GAE on a hand-computed trajectory; terminal reward placement; value sign
conventions for learner side 0 and 1; critic warm-up freezes every non-critic parameter exactly; the generalist rows;
config validation. No engine, no GPU.
"""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                              # noqa: E402

from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_rl_royale import (CFG, _Log, _monitor_fields, _results,  # noqa: E402
                                           _tiny_model)

TAU, T = 0.27, 0.5
PARENT = "7e72196"          # the last commit before R1: the match_loo reference
SPEC = [(0, 0, 30, "win"), (0, 1, 25, "loss"), (1, 0, 20, "win"), (1, 1, 28, "draw")]


def _parent_module():
    """pipeline/rl_royale.py as of PARENT, imported under another name (SkipTest without git / the commit)."""
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PARENT}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PARENT} failed: {src.stderr.strip()}")
    mod = types.ModuleType("rl_royale_parent")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, "rl_royale_parent", "exec"), mod.__dict__)
    return mod


def _learner(mod, model, results, tmp: Path, **cfg_extra):
    """test_rl_royale.TestOneUpdate._learner for module ``mod`` (the current or the parent rl_royale)."""
    model = copy.deepcopy(model)
    L = mod.Learner.__new__(mod.Learner)
    L.cfg = dict(CFG, init="x.pt", lr=1e-4, tau=TAU, T=T, adv_clip=2.0, minibatch=64, ppo_epochs=2, clip=0.2,
                 grad_clip=0.5, kl_target=0.1, beta_min=0.03, beta_max=3.0, screen_every=1000,
                 proagree_every=1000, save_every=1, max_updates=3, **cfg_extra)
    L.run, L.dev, L.model, L.pool_sha = "unit", torch.device("cpu"), model, "sha"
    L.ref = copy.deepcopy(model).eval()
    for p in L.ref.parameters():
        p.requires_grad_(False)
    L.init_meta = {"args": {"d": 16, "layers": 1, "grid": "lattice"}, "deck": "icebow", "epoch": 12, "n_params": 1}
    L.opt = torch.optim.Adam(model.parameters(), lr=1e-4)
    L.update, L.beta, L.rng, L.visits, L.train = 0, 0.3, np.random.default_rng(0), [0, 0], [None, None]
    L.base, L.guards, L.latest_pa = {"init_screen": {}}, mod.Guards(L.cfg), None
    L.run_dir, L.ck_dir = tmp / "run", tmp / "ck" / "unit"
    L.run_dir.mkdir(parents=True, exist_ok=True)
    L.ck_dir.mkdir(parents=True, exist_ok=True)
    L.log = _Log()
    L.rollout = lambda u: (copy.deepcopy(results), {"picked": [0, 1], "actors": {}, "skipped": 0})
    return L


def _strip(rec: dict) -> str:
    """An update record without its wall-clock fields, as canonical JSON."""
    drop = {"time", "learner_gpu_peak_mb", "ckpt"}
    # 2026-10-02 critic monitors (nested under the gae stats): logging only, no training quantity, absent from HEAD-era
    # records; their values are tested in test_rl_terminal_gap.py
    logonly = {"value_target_outside_share", "value_saturation_share", "value_mae"}
    nest = (lambda o: {k: nest(v) for k, v in o.items() if k not in logonly} if isinstance(o, dict) else o)
    return json.dumps(RL._py(nest({k: v for k, v in rec.items() if k not in drop and not k.startswith("wall")})),
                      sort_keys=True)


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_gae_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        orig = RL.CKPT_ROOT
        RL.CKPT_ROOT = self.tmp
        self.addCleanup(setattr, RL, "CKPT_ROOT", orig)


# ------------------------------------------------------------------------------------------------------
class TestDefaultIsParent(_Tmp):
    """``advantage`` absent or ``match_loo``: collate and a whole update are bit-identical to the parent commit."""

    @classmethod
    def setUpClass(cls):
        cls.P = _parent_module()
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_collate_arrays_identical(self):
        Bp, sp = self.P.collate(copy.deepcopy(self.results), 2.0)
        for kw in ({}, {"advantage": "match_loo"}):
            Bn, sn = RL.collate(copy.deepcopy(self.results), 2.0, **kw)
            self.assertEqual(sorted(Bn), sorted(Bp))
            for k in Bp:
                self.assertEqual(Bn[k].dtype, Bp[k].dtype, k)
                self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)
            self.assertEqual(sn, sp)

    def test_one_update_identical(self):
        self.P.CKPT_ROOT = self.tmp
        runs = {}
        for name, mod, extra in (("parent", self.P, {}), ("absent", RL, {}),
                                 ("match_loo", RL, {"advantage": "match_loo", "gae_gamma": 0.9, "vf_coef": 3.0,
                                                    "critic_warmup_updates": 5})):
            L = _learner(mod, self.model, self.results, self.tmp / name)
            L.cfg.update(extra)
            recs = [_strip(L.one_update(u)[0]) for u in range(2)]
            runs[name] = (recs, L.beta, {k: v.clone() for k, v in L.model.state_dict().items()},
                          L.rng.bit_generator.state)
        recs_p, beta_p, sd_p, rng_p = runs["parent"]
        for name in ("absent", "match_loo"):
            recs, beta, sd, rng = runs[name]
            self.assertEqual(recs, recs_p, name)                      # losses, KLs, entropies, A stats, guards ...
            self.assertEqual(beta, beta_p, name)
            self.assertEqual(rng, rng_p, name)
            for k in sd_p:
                self.assertTrue(torch.equal(sd[k], sd_p[k]), (name, k))
        self.assertFalse(any('"gae"' in r for r in runs["match_loo"][0]))


# ------------------------------------------------------------------------------------------------------
class TestGae(unittest.TestCase):
    R5, V5 = [0.0, 0.0, 0.0, 0.0, 1.0], [0.1, 0.2, -0.1, 0.3, 0.5]

    def test_hand_computed_5_steps(self):
        # gamma 0.9, lambda 0.8; delta_t = r_t + 0.9 V_{t+1} - V_t (V_5 = 0):
        #   delta = [0.08, -0.29, 0.37, 0.15, 0.5]; A_t = delta_t + 0.72 A_{t+1}
        A, ret = RL.gae(self.R5, self.V5, [0] * 5, 0.9, 0.8)
        np.testing.assert_allclose(A, [0.25336448, 0.240784, 0.7372, 0.51, 0.5], atol=1e-12)
        np.testing.assert_allclose(ret, [0.35336448, 0.440784, 0.6372, 0.81, 1.0], atol=1e-12)

    def test_lambda_one_is_discounted_return_to_go(self):
        A, ret = RL.gae(self.R5, self.V5, [0] * 5, 0.9, 1.0)
        np.testing.assert_allclose(ret, [0.9 ** 4, 0.9 ** 3, 0.9 ** 2, 0.9, 1.0], atol=1e-12)

    def test_lambda_zero_is_one_step_td(self):
        A, _ = RL.gae(self.R5, self.V5, [0] * 5, 0.9, 0.0)
        np.testing.assert_allclose(A, [0.08, -0.29, 0.37, 0.15, 0.5], atol=1e-12)

    def test_match_boundary_resets(self):
        r2, v2 = [0.0, 0.0, -1.0], [0.4, -0.2, 0.0]
        A, ret = RL.gae(self.R5 + r2, self.V5 + v2, [3] * 5 + [7] * 3, 0.9, 0.8)
        A1, ret1 = RL.gae(self.R5, self.V5, [0] * 5, 0.9, 0.8)
        A2, ret2 = RL.gae(r2, v2, [0] * 3, 0.9, 0.8)
        np.testing.assert_array_equal(A, np.concatenate([A1, A2]))
        np.testing.assert_array_equal(ret, np.concatenate([ret1, ret2]))
        self.assertEqual(ret2[-1], -1.0)

    def test_explained_variance(self):
        self.assertEqual(RL.explained_variance([1, 2, 3], [1, 2, 3]), 1.0)
        self.assertEqual(RL.explained_variance([2, 2, 2], [1, 2, 3]), 0.0)
        self.assertIsNone(RL.explained_variance([0, 1], [1, 1]))


# ------------------------------------------------------------------------------------------------------
class TestTerminalRewardAndSign(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(2)
        cls.results = _results(cls.model, [(0, 0, 9, "win"), (0, 1, 7, "loss"), (1, 0, 8, "draw"), (1, 1, 6, "win")],
                               seed=4)

    def test_terminal_reward_on_last_contributing_row_only(self):
        B, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        Bd, _ = RL.collate(copy.deepcopy(self.results), 2.0)
        self.assertEqual(sorted(B), sorted(set(Bd) | {"r_step"}))           # gae adds r_step only
        np.testing.assert_array_equal(B["A"], Bd["A"])                      # A is replaced later by gae_batch
        for j, r in enumerate(self.results):
            rs = B["r_step"][B["match"] == j]
            self.assertGreater(len(rs), 1)
            self.assertEqual(rs[-1], RL.reward(r["outcome"]))
            self.assertFalse(rs[:-1].any())
        self.assertEqual(float(B["r_step"].sum()), 1.0 - 1.0 + 0.0 + 1.0)

    def test_terminal_rewards_empty_match(self):
        out = RL.terminal_rewards([0, 3], ["win", "loss"])
        self.assertEqual(len(out[0]), 0)
        np.testing.assert_array_equal(out[1], [0.0, 0.0, -1.0])

    def test_value_mapping(self):
        big = 40.0
        for cls_, want in ((6, 1.0), (4, 1.0), (3, 0.0), (2, -1.0), (0, -1.0)):
            logits = torch.full((7,), -big)
            logits[cls_] = big
            self.assertAlmostEqual(float(RL.value_scalar(logits)), want, places=12)
        self.assertAlmostEqual(float(RL.value_scalar(torch.zeros(7))), 0.0, places=12)   # uniform: 3/7 - 3/7

    def test_sign_per_learner_side(self):
        """The learner may be side 0 or 1: e1_eval reports ``outcome`` and crowns_for / crowns_against for the
        LEARNER's side (``SelfPlaySide._outcome`` = env.outcome(self.side)) and the value head's classes are the
        observing side's crown difference, so the target and V agree in sign on both sides."""
        base = copy.deepcopy(self.results[:2])
        for side in (0, 1):
            res = copy.deepcopy(base)
            for r, (o, cf, ca) in zip(res, (("win", 2, 1), ("loss", 0, 3))):
                r.update({"side": side, "outcome": o, "crowns_for": cf, "crowns_against": ca,
                          "league": {"learner_side": side}})
            B, _ = RL.collate(res, 2.0, advantage="gae")
            for j, r in enumerate(res):
                last = B["r_step"][B["match"] == j][-1]
                logits = torch.full((7,), -40.0)
                logits[r["crowns_for"] - r["crowns_against"] + 3] = 40.0       # train_s1.Rows: class = mine - theirs + 3
                self.assertEqual(last, {"win": 1.0, "loss": -1.0}[r["outcome"]], side)
                self.assertEqual(np.sign(float(RL.value_scalar(logits))), np.sign(last), side)
                _, ret = RL.gae(B["r_step"][B["match"] == j], np.zeros(int((B["match"] == j).sum())),
                                np.zeros(int((B["match"] == j).sum())), 0.999, 0.95)
                self.assertTrue(np.all(np.sign(ret) == np.sign(last)), side)   # every row's target has the sign


# ------------------------------------------------------------------------------------------------------
class TestGaeUpdate(_Tmp):

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_gae_batch(self):
        Bn, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        B = RL.to_device(Bn, "cpu")
        st = RL.gae_batch(self.model, B, {"advantage": "gae", "gae_gamma": 0.99, "gae_lambda": 0.9})
        v = B["v_old"].numpy()
        self.assertTrue(np.all(np.abs(v) <= 1.0))
        with torch.no_grad():
            t = RL.policy_terms(self.model, B, torch.arange(len(v)), TAU, T, value=True)
        np.testing.assert_allclose(t["v"].numpy(), v, atol=1e-6)            # same V as the loss's forward
        A, ret = RL.gae(Bn["r_step"], v, Bn["match"], 0.99, 0.9)
        np.testing.assert_allclose(B["ret"].numpy(), ret)
        np.testing.assert_allclose(B["A"].numpy(), (A - A.mean()) / (A.std() + 1e-8))
        self.assertAlmostEqual(float(B["A"].mean()), 0.0, places=10)
        self.assertAlmostEqual(float(B["A"].std(unbiased=False)), 1.0, places=6)
        self.assertAlmostEqual(st["adv_mean"], float(A.mean()))
        self.assertAlmostEqual(st["ret_mean"], float(ret.mean()))
        self.assertAlmostEqual(st["explained_var"], RL.explained_variance(v, ret))

    def test_warmup_freezes_policy_exactly(self):
        L = _learner(RL, self.model, self.results, self.tmp, advantage="gae", critic_warmup_updates=1)
        before = {n: p.detach().clone() for n, p in L.model.named_parameters()}
        rec, reasons, crash = L.one_update(0)                     # includes the update-0 on-policy assertion
        self.assertFalse(crash)
        self.assertTrue(rec["gae"]["critic_warmup"])
        self.assertTrue(np.isfinite(rec["gae"]["l_v"]))
        self.assertIsNotNone(rec["gae"]["explained_var"])
        self.assertEqual(L.beta, 0.3)                              # no KL step
        moved = [n for n, p in L.model.named_parameters() if not torch.equal(p, before[n])]
        self.assertTrue(moved)
        self.assertTrue(all(n.startswith("value_head.") for n in moved), moved)
        self.assertTrue(all(p.requires_grad for p in L.model.parameters()))   # unfrozen again afterwards
        self.assertTrue(any("WARMUP" in m for m in L.log.lines))
        # warm-up over: the policy moves and beta adapts on the leash KL
        pol = {n: p.detach().clone() for n, p in L.model.named_parameters() if not n.startswith("value_head.")}
        rec1, _, crash1 = L.one_update(1)
        self.assertFalse(crash1)
        self.assertFalse(rec1["gae"]["critic_warmup"])
        self.assertTrue(any(not torch.equal(p, pol[n]) for n, p in L.model.named_parameters() if n in pol))
        self.assertNotEqual(L.beta, 0.3)

    def test_warmup_loss_is_value_only(self):
        Bn, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        B = RL.to_device(Bn, "cpu")
        RL.gae_batch(self.model, B, {"advantage": "gae"})
        ref = copy.deepcopy(self.model).eval()
        R = RL.ref_terms(ref, B, TAU, T)
        N = len(B["A"])
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
        vf = {"coef": 0.5, "clip": 0.2}
        l_warm, st = RL.minibatch_loss(self.model, B, R, torch.arange(N), vf={**vf, "policy": False}, **kw)
        l_full, _ = RL.minibatch_loss(self.model, B, R, torch.arange(N), vf={**vf, "policy": True}, **kw)
        l_pol, st0 = RL.minibatch_loss(self.model, B, R, torch.arange(N), **kw)
        self.assertAlmostEqual(float(l_warm.detach()), 0.5 * st["l_v"], places=12)
        self.assertAlmostEqual(float(l_full.detach()), float(l_pol.detach()) + 0.5 * st["l_v"], places=10)
        # on-policy, V == V_old: the clipped and unclipped terms agree -> 0.5 sum_i w_i (V_i - ret_i)^2
        want = float((B["w"] * 0.5 * (B["v_old"] - B["ret"]) ** 2).sum())
        self.assertAlmostEqual(st["l_v"], want, places=6)
        self.assertNotIn("l_v", st0)

    def test_generalist_rows(self):
        from pipeline.tests.test_e1_eval_gen import VOCAB, _tiny_gen
        from pipeline.tests.test_rl_gen import _rollouts
        from pipeline import e1_eval as E
        model = _tiny_gen(3)
        res = _rollouts(E.GenPolicy(model, VOCAB))
        Bn, _ = RL.collate(res, 2.0, advantage="gae")
        B = RL.to_device(Bn, "cpu")
        RL.gae_batch(model, B, {"advantage": "gae"})
        with torch.no_grad():
            b = {k: B[k] for k in E.GEN_ROW_KEYS}
            want = RL.value_scalar(model(b)["value"])                   # GenModel.forward's own value head
        np.testing.assert_allclose(B["v_old"].numpy(), want.numpy(), atol=1e-6)
        R = RL.ref_terms(copy.deepcopy(model).eval(), B, TAU, T)
        N = len(B["A"])
        loss, st = RL.minibatch_loss(model, B, R, torch.arange(N), tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N,
                                     vf={"coef": 0.5, "clip": 0.2, "policy": True})
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertIsNotNone(model.value_head.weight.grad)
        self.assertTrue(torch.isfinite(model.value_head.weight.grad).all())


# ------------------------------------------------------------------------------------------------------
class TestAdvConfig(unittest.TestCase):
    def test_defaults_and_yaml(self):
        import yaml
        self.assertEqual(RL.adv_cfg({}), RL.GAE_DEFAULTS)
        self.assertEqual(RL.GAE_DEFAULTS["advantage"], "match_loo")
        y = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        self.assertEqual({k: y[k] for k in RL.GAE_DEFAULTS}, RL.GAE_DEFAULTS)

    def test_old_yaml_without_the_keys_is_match_loo(self):
        """league1c runs from a copy of rl_royale.yaml taken BEFORE R1 and may --resume on this code: a yaml without
        the new keys must load, validate, and run match_loo (an override of a new key on it is refused loudly)."""
        import yaml
        text = (REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8")
        old = "\n".join(ln for ln in text.splitlines() if not any(ln.startswith(k + ":") for k in RL.GAE_DEFAULTS))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "old.yaml"
            path.write_text(old, encoding="utf-8")
            cfg = RL.load_config(path, [], False)
            self.assertFalse(set(RL.GAE_DEFAULTS) & set(cfg))
            self.assertEqual(RL.adv_cfg(cfg)["advantage"], "match_loo")
            self.assertEqual(cfg, {k: v for k, v in yaml.safe_load(text).items() if k not in RL.GAE_DEFAULTS})
            with self.assertRaises(SystemExit):
                RL.load_config(path, ["advantage=gae"], False)
        # ... and an update under that config is the parent's (TestDefaultIsParent "absent" = no R1 key at all)
        model = _tiny_model(6)
        res = _monitor_fields(_results(model, SPEC[:2], seed=13))
        with tempfile.TemporaryDirectory() as d:
            orig = RL.CKPT_ROOT
            RL.CKPT_ROOT = Path(d)
            try:
                L = _learner(RL, model, res, Path(d))
                L.cfg.update({k: v for k, v in cfg.items() if k not in L.cfg and k not in ("league",)})
                self.assertFalse(set(RL.GAE_DEFAULTS) & set(L.cfg))
                rec, _, crash = L.one_update(0)
            finally:
                RL.CKPT_ROOT = orig
        self.assertFalse(crash)
        self.assertNotIn("gae", rec)
        self.assertFalse(any("| gae" in m for m in L.log.lines))

    def test_bad_values(self):
        for k, v in (("advantage", "td"), ("gae_gamma", 0.0), ("gae_gamma", 1.5), ("gae_lambda", -0.1),
                     ("vf_coef", -1), ("vf_clip", 0), ("critic_warmup_updates", -1), ("critic_warmup_updates", 1.5),
                     ("critic_warmup_updates", True), ("gae_gamma", "0.9")):
            with self.assertRaises(SystemExit, msg=(k, v)) as cm:
                RL.adv_cfg({k: v})
            self.assertIn(k, str(cm.exception))


if __name__ == "__main__":
    unittest.main()
