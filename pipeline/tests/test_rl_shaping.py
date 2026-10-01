"""Offline tests for R2 shaping wiring (``shaping: tower_crown``) and the ``vf_trunk_grad`` option in

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_rl_shaping.py

(The L69 7b shaped critic V' = V - Phi and the tick discount: test_rl_gamma_tick.py.)
Covers: defaults (shaping none, vf_trunk_grad true) bit-identical to R1's commit a963b39 (collate arrays + whole
updates in match_loo AND gae mode, weights compared with torch.equal); the telescoping identities on the kept rows
(gamma = 1 and gamma < 1, same gamma unit as GAE); F added to r_step on the right rows only; shaping refused without
gae; e1_eval records phi_state only under record_phi, from the learner's side; vf_trunk_grad false keeps the value
loss off the trunk while the policy-loss gradients are unchanged; an R1-era yaml without the new keys. No engine.
"""
from __future__ import annotations

import copy
import random
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

from pipeline import reward_shaping as RS                                 # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_rl_gae import SPEC, TAU, T, _learner, _strip, _Tmp   # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

R1_COMMIT = "a963b39"
NEW_KEYS = ("shaping", "shaping_w_tower", "shaping_w_crown", "vf_trunk_grad")
SHP = {"gamma": 0.9, "w_tower": 0.3, "w_crown": 0.3}


def _module_at(commit: str):
    """pipeline/rl_royale.py as of ``commit``, imported under another name (SkipTest without git / the commit)."""
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:pipeline/rl_royale.py"], capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {commit} failed: {src.stderr.strip()}")
    mod = types.ModuleType(f"rl_royale_{commit}")
    mod.__file__ = str(REPO / "pipeline" / "rl_royale.py")
    exec(compile(src.stdout, f"rl_royale_{commit}", "exec"), mod.__dict__)
    return mod


def _with_phi(results, seed=0, garbage_unkept=False):
    """Attach a ``phi_state`` [n, 8] (reward_shaping.phi_record layout) to every result's traj. ``garbage_unkept``:
    rows collate drops get 1e6, so any use of them shows up in r_step."""
    rng = np.random.default_rng(seed)
    out = copy.deepcopy(results)
    for r in out:
        t = r["traj"]
        n = len(t["played"])
        ph = np.concatenate([rng.uniform(0, 1, (n, 6)), rng.integers(0, 4, (n, 2)).astype(np.float64)], axis=1)
        if garbage_unkept:
            ph[~(t["gate_sampled"] | t["played"])] = 1e6
        t["phi_state"] = ph
    return out


def _drop_new(rec: dict) -> dict:
    rec = copy.deepcopy(rec)
    for k in ("vf_trunk_share", "vf_trunk_grad", "shaping"):
        (rec.get("gae") or {}).pop(k, None)
    return rec


# ------------------------------------------------------------------------------------------------------
class TestDefaultIsR1(_Tmp):
    """shaping none + vf_trunk_grad true (absent or explicit) = commit a963b39, in match_loo and in gae mode."""

    @classmethod
    def setUpClass(cls):
        cls.P = _module_at(R1_COMMIT)
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_collate_arrays_identical(self):
        for res in (self.results, _with_phi(self.results)):              # a recorded phi_state is never read
            for adv in ("match_loo", "gae"):
                Bp, sp = self.P.collate(copy.deepcopy(res), 2.0, advantage=adv)
                Bn, sn = RL.collate(copy.deepcopy(res), 2.0, advantage=adv)
                self.assertEqual(sorted(Bn), sorted(Bp))
                for k in Bp:
                    self.assertEqual(Bn[k].dtype, Bp[k].dtype, k)
                    self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), (adv, k))
                self.assertEqual(sn, sp)

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        explicit = {"shaping": "none", "shaping_w_tower": 0.7, "shaping_w_crown": 0.1, "vf_trunk_grad": True}
        for label, base in (("match_loo", {}), ("gae", {"advantage": "gae", "critic_warmup_updates": 1})):
            runs = {}
            for name, mod, extra in (("r1", self.P, {}), ("absent", RL, {}), ("explicit", RL, explicit)):
                L = _learner(mod, self.model, self.results, self.tmp / f"{label}_{name}")
                L.cfg.update(base)
                L.cfg.update(extra)
                recs = [L.one_update(u)[0] for u in range(2)]             # gae: u0 warm-up, u1 policy + critic
                runs[name] = ([_strip(_drop_new(r)) for r in recs], recs, L.beta,
                              {k: v.clone() for k, v in L.model.state_dict().items()}, L.rng.bit_generator.state)
            recs_p, _, beta_p, sd_p, rng_p = runs["r1"]
            for name in ("absent", "explicit"):
                recs, raw, beta, sd, rng = runs[name]
                self.assertEqual(recs, recs_p, (label, name))
                self.assertEqual(beta, beta_p, (label, name))
                self.assertEqual(rng, rng_p, (label, name))
                for k in sd_p:
                    self.assertTrue(torch.equal(sd[k], sd_p[k]), (label, name, k))
                self.assertFalse(any("shaping" in r for r in raw))
                if label == "gae":                                        # the only additions: the F2 monitor + keys
                    self.assertIsNone(raw[0]["gae"]["vf_trunk_share"])     # warm-up: trunk frozen, not measured
                    self.assertGreater(raw[1]["gae"]["vf_trunk_share"]["share"], 0.0)
                else:
                    self.assertFalse(any("gae" in r for r in raw))


# ------------------------------------------------------------------------------------------------------
class TestShapingMath(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(3)
        self.rows = np.concatenate([rng.uniform(0, 1, (40, 6)), rng.integers(0, 4, (40, 2))], axis=1)

    def test_telescopes_gamma_one(self):
        sh = RL.shaping_rewards(self.rows, {**SHP, "gamma": 1.0})
        self.assertAlmostEqual(float(sh["F"].sum()), -float(sh["phi"][0]), places=12)
        np.testing.assert_allclose(sh["F"], sh["tower"] + sh["crown"], atol=1e-15)
        np.testing.assert_allclose(sh["phi"], sh["phi_tower"] + sh["phi_crown"], atol=1e-15)

    def test_discounted_identity(self):
        g = 0.9
        sh = RL.shaping_rewards(self.rows, {**SHP, "gamma": g})
        self.assertAlmostEqual(float(sum(g ** t * f for t, f in enumerate(sh["F"]))), -float(sh["phi"][0]), places=12)
        np.testing.assert_allclose(RS.returns_to_go(sh["F"], g), -sh["phi"], atol=1e-12)   # every row: -Phi(s_t)

    def test_rows_match_state_functions(self):
        from pipeline.tests.test_reward_shaping import random_match
        states = random_match(random.Random(5), 30)
        for side in (0, 1):
            rows = np.array([RS.phi_record(s, side) for s in states])
            pt, pc = RS.phi_parts(rows)
            np.testing.assert_allclose(pt, [RS.phi_tower(s, side) for s in states], atol=1e-15)
            np.testing.assert_allclose(pc, [RS.phi_crown(s, side) for s in states], atol=1e-15)
            want = RS.shaping_terms(states, side, 0.99, (0.3, 0.3))
            got = RL.shaping_rewards(rows, {"gamma": 0.99, "w_tower": 0.3, "w_crown": 0.3})
            np.testing.assert_allclose(got["F"], want["F"], atol=1e-15)

    def test_record_side_symmetry(self):
        from pipeline.tests.test_reward_shaping import state
        s = state(hp0=(4824, 0, 1000), hp1=(2412, 3052, 0))
        r0, r1 = RS.phi_record(s, 0), RS.phi_record(s, 1)
        self.assertEqual(r0[:3], r1[3:6])
        self.assertEqual(r0[6:], r1[6:][::-1])
        self.assertEqual(r0[6:], [1.0, 1.0])                              # one princess dead each side


# ------------------------------------------------------------------------------------------------------
class TestCollateShaping(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(2)
        cls.results = _with_phi(_results(cls.model, [(0, 0, 9, "win"), (0, 1, 7, "loss"), (1, 0, 8, "draw"),
                                                     (1, 1, 6, "win")], seed=4), seed=1, garbage_unkept=True)

    def test_F_added_on_kept_rows(self):
        """L69 7b: r_step stays the UNSHAPED reward; Phi(s_t) rides as ``phi`` (the residual critic's base)."""
        B, st = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae", shaping=SHP)
        Bd, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        self.assertEqual(sorted(B), sorted(list(Bd) + ["phi"]))
        for k in Bd:
            self.assertEqual(B[k].tobytes(), Bd[k].tobytes(), k)          # r_step included: unshaped
        self.assertLess(float(np.abs(B["phi"]).max()), 3.0)                # the 1e6 unkept rows never entered
        all_f = []
        for j, r in enumerate(self.results):
            t = r["traj"]
            keep = t["gate_sampled"] | t["played"]
            self.assertTrue((~keep).any() or j)                             # the fixture does drop rows
            sh = RL.shaping_rewards(t["phi_state"][keep], SHP)
            np.testing.assert_array_equal(B["phi"][B["match"] == j], sh["phi"])
            all_f.append(sh)
        want = RL.shaping_stats(all_f)
        self.assertEqual(st["shaping"], want)
        self.assertEqual(st["shaping"]["shaping_dominates"], st["shaping"]["mean_abs_phi"])
        self.assertEqual(st["shaping"]["rows"], len(B["A"]))

    def test_same_gamma_unit_as_gae(self):
        """lambda 1, V = 0: GAE's return on kept row t = gamma^(n-1-t) R - Phi(s_t) -- exactly, only because the
        shaping's gamma and GAE's gamma count the same steps (kept rows)."""
        g = SHP["gamma"]
        B, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae", shaping=SHP)
        for j, r in enumerate(self.results):
            m = B["match"] == j
            n = int(m.sum())
            t = r["traj"]
            sh = RL.shaping_rewards(t["phi_state"][t["gate_sampled"] | t["played"]], SHP)
            _, ret = RL.gae(B["r_step"][m] + sh["F"], np.zeros(n), np.zeros(n), g, 1.0)
            want = g ** np.arange(n - 1, -1, -1) * RL.reward(r["outcome"]) - sh["phi"]
            np.testing.assert_allclose(ret, want, atol=1e-12)

    def test_refused_without_gae(self):
        for bad in ({"shaping": "tower_crown"}, {"shaping": "tower_crown", "advantage": "match_loo"},
                    {"vf_trunk_grad": False}, {"advantage": "gae", "shaping": "elixir"},
                    {"advantage": "gae", "shaping_w_tower": -0.1}, {"advantage": "gae", "shaping_w_crown": "0.3"},
                    {"advantage": "gae", "vf_trunk_grad": "no"}, {"advantage": "gae", "vf_trunk_grad": 0}):
            with self.assertRaises(SystemExit, msg=bad) as cm:
                RL.adv_cfg(bad)
            self.assertTrue(any(k in str(cm.exception) for k in bad), (bad, str(cm.exception)))
        c = RL.adv_cfg({"advantage": "gae", "shaping": "tower_crown", "vf_trunk_grad": False,
                        "critic_warmup_updates": 1})
        self.assertEqual((c["shaping"], c["shaping_w_tower"], c["shaping_w_crown"], c["vf_trunk_grad"]),
                         ("tower_crown", 0.3, 0.3, False))
        with self.assertRaises(ValueError):
            RL.collate(copy.deepcopy(self.results), 2.0, shaping=SHP)

    def test_actor_cfg_flag(self):
        import yaml
        base = {**yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8")), "grid": "lattice"}
        self.assertNotIn("record_phi", RL.actor_cfg(base, "rollout", 0, "cpu"))
        old = {k: v for k, v in base.items() if k not in NEW_KEYS}          # an R1-era / pre-R1 config
        self.assertEqual(RL.actor_cfg(old, "rollout", 0, "cpu"), RL.actor_cfg(base, "rollout", 0, "cpu"))
        on = {**base, "advantage": "gae", "shaping": "tower_crown"}
        self.assertTrue(RL.actor_cfg(on, "rollout", 0, "cpu")["record_phi"])
        self.assertNotIn("record_phi", RL.actor_cfg(on, "screen", 0, "cpu"))

    def test_actor_base_carries_shaping(self):
        """The actor processes get ``Learner.actor_base()``, not the cfg: shaping must reach it (the CPU smoke caught
        this), and the default base is unchanged (no key)."""
        import yaml
        model = _tiny_model(2)
        with tempfile.TemporaryDirectory() as d:
            for extra, want in (({}, None), ({"advantage": "gae", "shaping": "tower_crown"}, True)):
                L = _learner(RL, model, [], Path(d), **extra)
                L.grid = "lattice"
                L.cfg = {**yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8")), **L.cfg}
                base = L.actor_base()
                self.assertEqual("shaping" in base, want is not None)
                self.assertEqual(RL.actor_cfg(base, "rollout", 0, "cpu").get("record_phi"), want)


# ------------------------------------------------------------------------------------------------------
class TestRecording(unittest.TestCase):
    """e1_eval (the real SelfPlayMatch on test_league's fake env): phi_state rows only under record_phi, one per
    recorded decision, = reward_shaping.phi_record of the state decided in, from the LEARNER's side."""

    def _run(self, side, **kw):
        from pipeline import e1_eval as E
        from pipeline.tests import test_league as TL
        learner, opp = E.GenPolicy(TL._tiny_gen(1), TL.VOCAB), E.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
        jobs = [(0, TL._spec(0, "snapA", side), 0, {"rollout_index": 0, "update": 0})]
        res, envs = TL._run(jobs, learner, {"snapA": (opp, TL._cfg("sample", record=False))}, TL._cfg(**kw), n=1)
        return res[0], envs[0]

    def test_phi_state_per_row_learner_side(self):
        rows = {}
        for side in (0, 1):
            r, env = self._run(side, record_phi=True)
            ph = r["traj"]["phi_state"]
            self.assertEqual(ph.shape, (len(r["traj"]["played"]), 8))
            self.assertEqual(ph.dtype, np.float64)
            want = RS.phi_record(env.raw(), side)                         # the fake env's towers never change
            np.testing.assert_array_equal(ph, np.tile(want, (len(ph), 1)))
            rows[side] = ph[0]
        np.testing.assert_array_equal(rows[0][:3], rows[1][3:6])          # own/foe swap with the side
        self.assertGreater(RS.phi_parts(rows[0])[0], 0.0)                 # TOWERS: side 0 has more tower HP left
        self.assertAlmostEqual(float(RS.phi_parts(rows[1])[0]), -float(RS.phi_parts(rows[0])[0]), places=15)

    def test_not_recorded_by_default(self):
        r, _ = self._run(0)
        self.assertNotIn("phi_state", r["traj"])


# ------------------------------------------------------------------------------------------------------
class TestVfTrunkGrad(_Tmp):

    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))
        Bn, _ = RL.collate(copy.deepcopy(cls.results), 2.0, advantage="gae")
        cls.B = RL.to_device(Bn, "cpu")
        RL.gae_batch(cls.model, cls.B, {"advantage": "gae"})
        cls.R = RL.ref_terms(copy.deepcopy(cls.model).eval(), cls.B, TAU, T)

    def _grads(self, model, vf):
        N = len(self.B["A"])
        model.zero_grad(set_to_none=True)
        loss, _ = RL.minibatch_loss(model, self.B, self.R, torch.arange(N), tau=TAU, T=T, clip=0.2, beta=0.3,
                                    n_total=N, vf=vf)
        loss.backward()
        return {n: (None if p.grad is None else p.grad.clone()) for n, p in model.named_parameters()}

    def test_value_loss_reaches_value_head_only(self):
        model = copy.deepcopy(self.model)
        vf = {"coef": 0.5, "clip": 0.2, "policy": False}
        off = self._grads(model, {**vf, "trunk_grad": False})
        on = self._grads(model, {**vf, "trunk_grad": True})
        trunk = [n for n in off if not n.startswith("value_head.")]
        self.assertTrue(all(off[n] is None or not off[n].any() for n in trunk))
        self.assertTrue(off["value_head.weight"].abs().sum() > 0)
        self.assertTrue(torch.equal(off["value_head.weight"], on["value_head.weight"]))   # the head's grad is the same
        self.assertTrue(any(on[n] is not None and on[n].any() for n in trunk))          # default: it reaches the trunk

    def test_policy_loss_grads_unchanged(self):
        model = copy.deepcopy(self.model)
        pol = self._grads(model, None)
        full = self._grads(model, {"coef": 0.5, "clip": 0.2, "policy": True, "trunk_grad": False})
        for n, g in pol.items():
            if n.startswith("value_head."):
                continue
            if g is None:
                self.assertTrue(full[n] is None or not full[n].any(), n)
            else:
                torch.testing.assert_close(full[n], g, rtol=0, atol=1e-12, msg=n)

    def test_grad_share_monitor(self):
        cfg = {"minibatch": 64, "tau": TAU, "T": T, "clip": 0.2}
        vf = {"coef": 0.5, "clip": 0.2, "policy": True}
        model = copy.deepcopy(self.model)
        before = {n: p.detach().clone() for n, p in model.named_parameters()}
        off = RL.vf_grad_share(model, self.B, self.R, cfg, 0.3, {**vf, "trunk_grad": False})
        on = RL.vf_grad_share(model, self.B, self.R, cfg, 0.3, {**vf, "trunk_grad": True})
        self.assertEqual((off["share"], off["grad_v"]), (0.0, 0.0))
        self.assertGreater(off["grad_pg"], 0.0)
        self.assertTrue(0.0 < on["share"] < 1.0)
        self.assertEqual(on["grad_pg"], off["grad_pg"])
        self.assertGreater(on["trunk_tensors"], 0)
        self.assertTrue(all(p.grad is None for p in model.parameters()))  # monitor writes no .grad, moves nothing
        self.assertTrue(all(torch.equal(p, before[n]) for n, p in model.named_parameters()))

    def test_one_update_shaping_and_detached_critic(self):
        res = _with_phi(self.results, seed=2)
        L = _learner(RL, self.model, res, self.tmp, advantage="gae", critic_warmup_updates=1, shaping="tower_crown",
                     vf_trunk_grad=False)
        rec0, _, crash0 = L.one_update(0)
        rec1, _, crash1 = L.one_update(1)
        self.assertFalse(crash0 or crash1)
        for rec in (rec0, rec1):
            self.assertEqual(rec["gae"]["shaping"], "tower_crown")
            self.assertFalse(rec["gae"]["vf_trunk_grad"])
            sh = rec["shaping"]
            self.assertEqual(sh["rows"], rec["rows"])
            self.assertTrue(0.0 < sh["mean_abs_phi"] <= 0.5)                 # |Phi| <= (5/3) 0.3 = 0.5
            self.assertEqual(sh["shaping_dominates"], sh["mean_abs_phi"])
        self.assertIsNone(rec0["gae"]["vf_trunk_share"])
        self.assertEqual(rec1["gae"]["vf_trunk_share"]["share"], 0.0)
        self.assertTrue(any("| shape |F|" in m and "dom" in m for m in L.log.lines))
        self.assertTrue(any("vshare 0.000" in m for m in L.log.lines))


# ------------------------------------------------------------------------------------------------------
class TestOldYaml(unittest.TestCase):
    def test_r1_era_yaml_without_new_keys(self):
        """A yaml copy taken at R1 (its gae keys, none of NEW_KEYS) loads, validates and runs the defaults; a yaml
        with none of the advantage keys at all is test_rl_gae.TestAdvConfig.test_old_yaml_without_the_keys."""
        import yaml
        text = (REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8")
        old = "\n".join(ln for ln in text.splitlines() if not any(ln.startswith(k + ":") for k in NEW_KEYS))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r1.yaml"
            path.write_text(old, encoding="utf-8")
            cfg = RL.load_config(path, ["advantage=gae"], False)
        self.assertFalse(set(NEW_KEYS) & set(cfg))
        c = RL.adv_cfg(cfg)
        self.assertEqual((c["advantage"], c["shaping"], c["vf_trunk_grad"]), ("gae", "none", True))
        self.assertNotIn("record_phi", RL.actor_cfg({**cfg, "grid": "lattice"}, "rollout", 0, "cpu"))
        y = yaml.safe_load(text)
        self.assertEqual({k: y[k] for k in NEW_KEYS}, {k: RL.GAE_DEFAULTS[k] for k in NEW_KEYS})


if __name__ == "__main__":
    unittest.main()
