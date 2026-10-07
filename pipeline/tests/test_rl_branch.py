"""opt3 T3: counterfactual gate branching in pipeline/rl_royale.py (scratchpad/gauntlet/L73/opt3/INTERFACE.md).

    ROYALE_RUNTIME=20261006 PYTHONPATH="<runtime>;<repo>" research/ext/Royale/.venv/Scripts/python.exe \
        -m unittest pipeline.tests.test_rl_branch -v

T1 (pipeline.branching) / T2 (pipeline.branch_score) are replaced by the FAKES below (``BranchSpec``, ``BranchRunner``,
``branch_label``): in-process tests monkeypatch ``rl_royale.branch_impl``; spawn branch workers (the CPU smoke) get
them by running ``smoke_worker_main`` (patched over ``rl_royale.branch_worker_main`` in the learner process), which
patches ``branch_impl`` inside the child before the real worker runs. Engine tests need royalegym (skipped elsewhere);
``TestIntegration`` runs only once both real modules import. ``TestDefaultParity`` compares against rl_royale.py at the
opt3 base commit (git show).
"""
from __future__ import annotations

import copy
import importlib.util
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import torch                                                    # noqa: E402

from pipeline import e1_eval as E                               # noqa: E402
from pipeline import rl_royale as RL                            # noqa: E402

BASE_COMMIT = "4b462c5"                                         # opt3 branch point: rl_royale.py before T3
try:
    from pipeline.royale_env import RoyaleSelfPlayEnv
except ImportError:
    RoyaleSelfPlayEnv = None


# ------------------------------------------------------------------------------------------------------
# fakes for T1 / T2 (contract signatures)
# ------------------------------------------------------------------------------------------------------
@dataclass
class BranchSpec:
    hold_s: float
    hold_tau: float = 0.55
    horizon_s: Optional[float] = None
    k: int = 1
    seed: int = 0
    alt: str = "hold"                                           # R4 alternative-action kinds
    a: Optional[tuple] = None
    b: Optional[tuple] = None


class BranchRunner:
    """Records every pair() call; never touches ``m``; sleeps ``sleep_s`` (the smoke's stand-in for a pair's cost)."""
    calls: list = []
    sleep_s = 0.0

    def __init__(self, make_env, learner, opps, learner_cfg, *, device):
        self.opps, self.lcfg, self.device = opps, learner_cfg, device

    def pair(self, m, ds, spec):
        assert m.learner in ds, "pair called at a decision the learner does not make"
        assert m.learner._cur is not None, "pair called before prepare"
        tick = int(m.env.tick)
        BranchRunner.calls.append((m.spec["tag"], tick, spec))
        time.sleep(BranchRunner.sleep_s)
        return SimpleNamespace(tick=tick, phase=RL.phase_of(tick), p_play=0.5, elixir=None, play_end=[], hold_end=[],
                               play_outcome=[None] * spec.k, hold_outcome=[None] * spec.k, wall_s=0.0)


def branch_label(result, kind, **kw):
    """+-0.5 alternating on tick / 10, except every 3rd decision tick -> 0.01 (under a 0.05 min |delta|)."""
    if (result.tick // 10) % 3 == 0:
        return 0.01, 1.0
    return (0.5 if (result.tick // 10) % 2 else -0.5), 1.0


def fake_impl():
    return BranchSpec, BranchRunner, branch_label


def smoke_worker_main(*a, **k):
    """The CPU smoke's branch-worker target: the fakes inside the spawn child (a pair costs 20 s), then the real one."""
    RL.branch_impl = fake_impl
    BranchRunner.sleep_s = 20.0
    return RL.branch_worker_main(*a, **k)


def _patch_impl(test, impl=fake_impl):
    orig = RL.branch_impl
    RL.branch_impl = impl
    test.addCleanup(setattr, RL, "branch_impl", orig)


# ------------------------------------------------------------------------------------------------------
def _gate_cfg(**kw) -> dict:
    return {"branch_gate": True, "league": True, "n_actors": 3, "tau": 0.35, "T": 0.3, "branch_phi_ckpt": "x.pt", **kw}


class TestBranchConfig(unittest.TestCase):
    def test_defaults_off_and_valid(self):
        c = RL.branch_cfg({})
        self.assertFalse(c["branch_gate"])
        self.assertEqual(c, RL.BRANCH_DEFAULTS)
        self.assertEqual({k: c[k] for k in ("branch_actors", "branch_threads", "branch_k", "branch_score",
                                            "branch_horizon_s", "branch_min_abs_delta", "branch_max_staleness",
                                            "branch_buffer", "branch_coef", "branch_points_per_match", "branch_lr",
                                            "branch_buffer_max_age", "branch_band")},
                         {"branch_actors": 24, "branch_threads": 1, "branch_k": 16, "branch_score": "outcome",
                          "branch_horizon_s": None, "branch_min_abs_delta": 0.25, "branch_max_staleness": 3,
                          "branch_buffer": 512, "branch_coef": 0.1, "branch_points_per_match": 6, "branch_lr": None,
                          "branch_buffer_max_age": 20, "branch_band": [0.2, 0.55]})
        RL.branch_cfg(_gate_cfg())                              # a valid "on" config passes

    def test_every_key_rejects_bad_values(self):
        bad = {"branch_gate": ["yes", 1], "branch_actors": [0, 1.5, True], "branch_points_per_match": [0, "4"],
               "branch_band": [[0.5, 0.2], [0.2], [-0.1, 0.5], [0.2, 1.5], "0.2,0.65"],
               "branch_hold_s": [[], [0, 2], [-1], 4], "branch_hold_tau": [0.0, 1.0, "x", 0.3],
               "branch_horizon_s": [0, -3, "12"], "branch_k": [0, 2.0], "branch_score": ["towers", None],
               "branch_phi_ckpt": [None, ""], "branch_coef": [-0.1, float("nan"), True],
               "branch_min_abs_delta": [-1, float("inf")], "branch_buffer": [0, 1.5, "512", None],
               "branch_threads": [0, 2.5, None], "branch_max_staleness": [-1, 1.5, None],
               "branch_lr": [-1e-4, "x", float("nan")], "branch_buffer_max_age": [-1, 2.5, None],
               "branch_kinds": [[], ["play"], ["hold", "hold"], "hold", None], "branch_card_points": [0, 1.5, "6"],
               "branch_xbow_points": [0, None], "branch_card_coef": [-1, float("nan")], "branch_xbow_coef": [-0.5, "x"],
               "branch_rocket_band": [0, 1.5, float("nan"), None], "branch_xbow_floor": [0, 0.6, None]}
        self.assertEqual(set(bad), set(RL.BRANCH_DEFAULTS))     # every key is covered
        for k, vals in bad.items():
            for v in vals:
                with self.assertRaises(SystemExit, msg=f"{k}={v!r}") as cm:
                    RL.branch_cfg(_gate_cfg(**({"branch_score": "phi", "branch_horizon_s": 40.0}
                                               if k == "branch_phi_ckpt" else {}), **{k: v}))
                self.assertIn(k, str(cm.exception), (k, v))

    def test_gate_on_needs_league(self):
        with self.assertRaisesRegex(SystemExit, "needs league"):
            RL.branch_cfg(_gate_cfg(league=False))
        RL.branch_cfg(_gate_cfg(branch_actors=40, n_actors=32))   # workers are separate processes, not PPO actors

    def test_refuses_a_deterministic_branch_opponent(self):
        """A greedy (live) league opponent makes all k continuations identical: refused; sampling at T > 0 passes."""
        with self.assertRaisesRegex(SystemExit, "needs league_opp_policy sample, got 'live'"):
            RL.branch_cfg(_gate_cfg(league_opp_policy="live"))
        for T in (0, 0.0, None):
            with self.assertRaisesRegex(SystemExit, "needs T > 0"):
                RL.branch_cfg(_gate_cfg(T=T))
        RL.branch_cfg(_gate_cfg(league_opp_policy="sample"))
        RL.branch_cfg({"league_opp_policy": "live"})             # off: not checked

    def test_band_top_must_not_exceed_hold_tau(self):
        """band hi > hold_tau: at the root the HOLD branch (gate hold_tau) would also play -- a pair with no
        difference; refused when the gate is on."""
        with self.assertRaisesRegex(SystemExit, "branch_band upper edge 0.65 must be <= branch_hold_tau 0.55"):
            RL.branch_cfg(_gate_cfg(branch_band=[0.2, 0.65]))
        RL.branch_cfg(_gate_cfg(branch_band=[0.2, 0.55]))
        RL.branch_cfg({"branch_band": [0.2, 0.65]})               # off: not checked

    def test_hold_tau_must_be_stricter_and_outcome_needs_no_ckpt(self):
        with self.assertRaisesRegex(SystemExit, "branch_hold_tau 0.35 must be > tau 0.35"):
            RL.branch_cfg(_gate_cfg(branch_hold_tau=0.35))
        RL.branch_cfg(_gate_cfg(branch_score="outcome", branch_phi_ckpt=None, branch_horizon_s=None))
        with self.assertRaisesRegex(SystemExit, "outcome needs branch_horizon_s null"):
            RL.branch_cfg(_gate_cfg(branch_score="outcome", branch_horizon_s=12.0))

    def test_load_config_accepts_branch_overrides_only(self):
        cfg = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", ["branch_gate=true", "branch_band=[0.1, 0.5]",
                                                                    "branch_buffer=64"], False)
        self.assertIs(cfg["branch_gate"], True)
        self.assertEqual((cfg["branch_band"], cfg["branch_buffer"]), ([0.1, 0.5], 64))
        base = RL.load_config(REPO / "pipeline" / "rl_royale.yaml", [], False)
        self.assertFalse(any(k.startswith("branch_") for k in base))     # no key injected: config sha unchanged
        with self.assertRaises(SystemExit):
            RL.load_config(REPO / "pipeline" / "rl_royale.yaml", ["branch_typo=1"], False)


class TestTargets(unittest.TestCase):
    def test_phase_of(self):
        self.assertEqual([RL.phase_of(t) for t in (0, 2399, 2400, 3599, 3600, 5999)],
                         ["single", "single", "double", "double", "overtime", "overtime"])

    def test_targets_sorted_and_stratified(self):
        rng = np.random.default_rng(0)
        t = RL.branch_targets(rng, 6)
        self.assertEqual(t, sorted(t))
        allt = np.concatenate([RL.branch_targets(rng, 6) for _ in range(2000)])
        self.assertTrue(((allt >= 0) & (allt < RL.BRANCH_TARGET_END)).all())
        share = [float(np.mean([RL.phase_of(x) == ph for x in allt])) for ph in ("single", "double", "overtime")]
        for s in share:                                         # equal mass per phase = 2x / OT at double density
            self.assertAlmostEqual(s, 1 / 3, delta=0.02)


# ------------------------------------------------------------------------------------------------------
def _tiny(seed: int = 7):
    from pipeline.tests.test_rl_royale import _tiny_model
    return _tiny_model(seed)


def _s1_rows(n: int, seed: int):
    """``n`` branch samples' rows (``branch_row`` of fake sides) on a tiny S1Model's input format."""
    from pipeline.tests.test_rl_royale import _synth_match
    tr = _synth_match(_tiny(), np.random.default_rng(seed), n, seed, all_allowed=True)
    rows = []
    for r in range(n):
        side = SimpleNamespace(_gen_row=None, _obs=(tr["tok"][r], tr["mask"][r], tr["sc"][r], tr["past"][r]))
        rows.append(RL.branch_row(side, tr["allowed"][r], 0.5, 0.3))
    return rows


def _sample(row, delta, phase="single", w=1.0):
    return {"branch": True, "row": row, "delta": delta, "weight": w, "phase": phase, "wall_s": 0.1}


def _p_play(model, Bb, tau, T):
    with torch.no_grad():
        return torch.sigmoid(RL.branch_terms(model, Bb, torch.arange(len(Bb["target"])), tau, T)[0])


STEP_CFG = {"tau": 0.35, "T": 0.3, "minibatch": 2, "grad_clip": 0.5}


class TestBranchStep(unittest.TestCase):
    def _step(self, delta: float) -> tuple[float, float, dict]:
        model = _tiny(3)
        Bb = RL.to_device(RL.branch_batch([_sample(_s1_rows(1, 11)[0], delta)], 0.05), "cpu")
        p0 = float(_p_play(model, Bb, 0.35, 0.3)[0])
        st = RL.branch_step(model, torch.optim.Adam(model.parameters(), lr=1e-2), Bb, STEP_CFG, 1.0)
        return p0, float(_p_play(model, Bb, 0.35, 0.3)[0]), st

    def test_play_better_raises_p_play(self):
        p0, p1, st = self._step(+0.4)
        self.assertGreater(p1, p0)
        self.assertLess(st["bce_after"], st["bce_before"])
        self.assertAlmostEqual(st["dp_abs_mean"], abs(p1 - p0), places=6)

    def test_hold_better_lowers_p_play(self):
        p0, p1, st = self._step(-0.4)
        self.assertLess(p1, p0)
        self.assertLess(st["bce_after"], st["bce_before"])

    def test_parameterisation_is_the_live_gate(self):
        """x = (z - logit(tau)) / T: P(play) = 0.5 exactly where the raw sigmoid(z) = tau (the live threshold)."""
        model = _tiny(3)
        Bb = RL.to_device(RL.branch_batch([_sample(r, 1.0) for r in _s1_rows(5, 2)], 0.0), "cpu")
        with torch.no_grad():
            x, l = RL.branch_terms(model, Bb, torch.arange(5), 0.35, 0.3)
            enc = model.encode(Bb["tok"], Bb["mask"], Bb["sc"], Bb["past"])
            z = model.heads(enc, RL.hand_mask_from_sc(Bb["sc"]))["gate"].double()
        torch.testing.assert_close(x, (z - np.log(0.35 / 0.65)) / 0.3)
        torch.testing.assert_close(l, torch.nn.functional.binary_cross_entropy_with_logits(
            x, torch.ones(5, dtype=torch.float64), reduction="none"))

    def test_one_step_whole_buffer_chunked(self):
        """5 rows in chunks of 2 = ONE optimizer step whose gradient is the full-buffer mean (= a 1-chunk step)."""
        rows = _s1_rows(5, 4)
        Bb = RL.to_device(RL.branch_batch([_sample(r, d) for r, d in zip(rows, [.3, -.2, .4, -.5, .1])], 0.0), "cpu")
        outs = []
        for mb in (2, 64):
            model = _tiny(3)
            opt = torch.optim.SGD(model.parameters(), lr=1.0)    # param change = the (clipped) accumulated gradient
            calls = []
            step = opt.step
            opt.step = (lambda *x, **k: (calls.append(1), step(*x, **k))[1])
            RL.branch_step(model, opt, Bb, {**STEP_CFG, "minibatch": mb}, 0.1)
            self.assertEqual(len(calls), 1)
            outs.append([p.detach().clone() for p in model.parameters()])
        for a, b in zip(*outs):
            torch.testing.assert_close(a, b, rtol=0, atol=1e-6)

    def test_nonfinite_skips_the_step(self):
        model = _tiny(3)
        Bb = RL.to_device(RL.branch_batch([_sample(_s1_rows(1, 11)[0], 0.4)], 0.0), "cpu")
        Bb["weight"][:] = float("nan")
        before = [p.detach().clone() for p in model.parameters()]
        st = RL.branch_step(model, torch.optim.Adam(model.parameters(), lr=1e-2), Bb, STEP_CFG, 1.0)
        self.assertIsNotNone(st["skipped"])
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(before, model.parameters())))


class TestDropAndStats(unittest.TestCase):
    def test_min_abs_delta_drops(self):
        rows = _s1_rows(4, 5)
        s = [_sample(rows[0], 0.3), _sample(rows[1], -0.04), _sample(rows[2], 0.049), _sample(rows[3], -0.2)]
        B = RL.branch_batch(s, 0.05)
        np.testing.assert_array_equal(B["target"], [1.0, 0.0])
        self.assertEqual(len(B["tok"]), 2)
        self.assertIsNone(RL.branch_batch(s[1:3], 0.05))        # all under the threshold -> no batch
        st = RL.branch_stats(s, 0.05)
        self.assertEqual((st["emitted"], st["dropped"], st["n"]), (4, 2, 2))

    def test_per_phase_stats(self):
        rows = _s1_rows(6, 6)
        s = [_sample(rows[0], 0.2, "single"), _sample(rows[1], -0.4, "single"), _sample(rows[2], -0.1, "double"),
             _sample(rows[3], -0.3, "overtime"), _sample(rows[4], 0.5, "overtime"), _sample(rows[5], 0.01, "double")]
        st = RL.branch_stats(s, 0.05)
        self.assertEqual(st["n"], 5)
        self.assertAlmostEqual(st["hold_better_share"], 3 / 5)
        self.assertAlmostEqual(st["mean_delta"], (0.2 - 0.4 - 0.1 - 0.3 + 0.5) / 5)
        self.assertEqual(st["by_phase"]["single"], {"n": 2, "hold_better_share": 0.5, "mean_delta": -0.1})
        self.assertEqual(st["by_phase"]["double"], {"n": 1, "hold_better_share": 1.0, "mean_delta": -0.1})
        self.assertEqual(st["by_phase"]["overtime"]["n"], 2)
        self.assertAlmostEqual(st["by_phase"]["overtime"]["mean_delta"], 0.1)


# ------------------------------------------------------------------------------------------------------
# one_update: default parity against the base commit, and the branch step in the update
# ------------------------------------------------------------------------------------------------------
def _base_module():
    """rl_royale.py as of BASE_COMMIT, imported under another name (None if git cannot show it)."""
    try:
        src = subprocess.run(["git", "show", f"{BASE_COMMIT}:pipeline/rl_royale.py"], cwd=REPO, capture_output=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    d = Path(tempfile.mkdtemp(prefix="rl_base_"))
    (d / "rl_royale_base.py").write_bytes(src)
    spec = importlib.util.spec_from_file_location("rl_royale_base", d / "rl_royale_base.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _UpdateHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, [(0, 0, 30, "win"), (0, 1, 25, "loss"), (1, 0, 20, "win"),
                                                           (1, 1, 28, "draw")], seed=13))

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rl_branch_upd_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _learner(self, mod, extra: dict, branch: Optional[list] = None, name: str = "a", actors: Optional[dict] = None):
        from pipeline.tests.test_rl_royale import CFG, T, TAU, _Log
        orig = mod.CKPT_ROOT
        mod.CKPT_ROOT = self.tmp / "ck"
        self.addCleanup(setattr, mod, "CKPT_ROOT", orig)
        model = copy.deepcopy(self.model)
        L = mod.Learner.__new__(mod.Learner)
        L.cfg = dict(CFG, init="x.pt", lr=1e-3, tau=TAU, T=T, adv_clip=2.0, minibatch=64, ppo_epochs=2, clip=0.2,
                     grad_clip=0.5, kl_target=0.1, beta_min=0.03, beta_max=3.0, screen_every=1000,
                     proagree_every=1000, save_every=1, max_updates=1, n_actors=3, seed=0, **extra)
        L.run, L.dev, L.model, L.pool_sha = "unit", torch.device("cpu"), model, "sha"
        L.ref = copy.deepcopy(model).eval()
        for p in L.ref.parameters():
            p.requires_grad_(False)
        L.init_meta = {"args": {"d": 16, "layers": 1, "grid": "lattice"}, "deck": "icebow", "epoch": 12, "n_params": 1}
        L.opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        L.update, L.beta, L.rng, L.visits, L.train = 0, 0.3, np.random.default_rng(0), [0, 0], [None, None]
        L.base, L.guards, L.latest_pa = {"init_screen": {}}, mod.Guards(L.cfg), None
        L.run_dir, L.ck_dir = self.tmp / f"run_{name}", self.tmp / "ck" / "unit"
        L.run_dir.mkdir(parents=True)
        L.ck_dir.mkdir(parents=True, exist_ok=True)
        L.log = _Log()
        L.branch_next = list(branch or [])
        info = {"picked": [0, 1], "actors": actors or {}, "skipped": 0}
        L.rollout = lambda u: (list(self.results), {**info, **({"branch": L.branch_next} if branch is not None else {})})
        L.grads = []
        step = L.opt.step

        def step_and_record(*a, **k):                          # every step's gradients, before Adam applies them
            L.grads.append([torch.zeros(0) if p.grad is None else p.grad.detach().clone() for p in model.parameters()])
            return step(*a, **k)
        L.opt.step = step_and_record
        return L


SKIP_KEYS = ("time", "wall_rollout_s", "wall_update_s", "wall_save_s", "wall_total_s", "ckpt")


class TestDefaultParity(_UpdateHarness):
    """branch_gate false (absent, or set false with every other branch key present): one update gives bit-identical
    gradients at every step, parameters and log record to the BASE_COMMIT trainer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = _base_module()

    def _compare(self, extra):
        if self.base is None:
            self.skipTest(f"git show {BASE_COMMIT} unavailable")
        old = self._learner(self.base, {}, name="old")
        new = self._learner(RL, extra, name="new")
        r_old, why_old, c_old = old.one_update(0)
        r_new, why_new, c_new = new.one_update(0)
        self.assertEqual((why_old, c_old), (why_new, c_new))
        self.assertEqual(len(old.grads), len(new.grads))
        self.assertGreater(len(new.grads), 1)
        for go, gn in zip(old.grads, new.grads):
            for a, b in zip(go, gn):
                self.assertTrue(torch.equal(a, b))
        for (ka, a), (kb, b) in zip(old.model.state_dict().items(), new.model.state_dict().items()):
            self.assertEqual(ka, kb)
            self.assertTrue(torch.equal(a, b), ka)
        self.assertEqual(old.beta, new.beta)
        self.assertEqual(old.rng.bit_generator.state, new.rng.bit_generator.state)
        strip = (lambda r: {k: v for k, v in r.items() if k not in SKIP_KEYS})
        self.assertEqual(RL._py(strip(r_old)), RL._py(strip(r_new)))
        self.assertNotIn("branch", r_new)
        self.assertFalse(hasattr(new, "branch_buf"))
        self.assertEqual(old.log.lines[-1].split(" wall roll")[0], new.log.lines[-1].split(" wall roll")[0])

    def test_absent_keys(self):
        self._compare({})

    def test_explicit_false_with_branch_keys(self):
        self._compare({**RL.BRANCH_DEFAULTS, "branch_gate": False, "branch_coef": 5.0, "branch_k": 9})


ON = {"branch_gate": True, "league": True, "branch_min_abs_delta": 0.05}


class _FakePool:
    """``BranchPool``'s learner-facing surface: hands out ``pending`` once per drain, counts drains."""

    def __init__(self, samples=()):
        self.pending, self.drains = list(samples), 0

    def drain(self):
        self.drains += 1
        out, self.pending = self.pending, []
        return out, {"errors": 0, "restarted": [], "alive": 24}


class TestUpdateWithBranch(_UpdateHarness):
    def _samples(self, deltas, seed=21, version=0):
        rows = _s1_rows(len(deltas), seed)
        return [{**_sample(r, d, ph), "version": version, "worker": i % 2}
                for i, (r, d, ph) in enumerate(zip(rows, deltas, ["single", "double", "overtime"] * 4))]

    def _on(self, samples, name, **extra):
        L = self._learner(RL, {**ON, **extra}, name=name)
        L.branch_pool = _FakePool(samples)
        L.sent = []
        L._branch_send = (lambda u, bc: L.sent.append(u))
        return L

    def test_one_step_after_ppo_and_logged(self):
        L = self._on(self._samples([0.5, -0.4, 0.02, -0.3, 0.6, -0.2]), "on")
        off = self._learner(RL, {}, name="off")
        rec, reasons, crash = L.one_update(0)                   # includes the update-0 on-policy assertion
        off.one_update(0)
        self.assertFalse(crash)
        self.assertEqual((L.sent, L.branch_pool.drains), ([0], 1))   # weights out at the start, ONE drain
        # PPO untouched: the same steps with bit-identical gradients, its Adam state bit-identical; the ONE branch
        # step went through the branch's own Adam (one step in its state)
        self.assertEqual(len(L.grads), len(off.grads))
        for go, gn in zip(off.grads, L.grads):
            self.assertTrue(all(torch.equal(a, b) for a, b in zip(go, gn)))
        _same_opt_state(self, L.opt, off.opt)
        self.assertEqual({float(v["step"]) for v in L.branch_opt.state_dict()["state"].values()}, {1.0})
        self.assertTrue(any(not torch.equal(a, b) for a, b in zip(L.model.parameters(), off.model.parameters())))
        self.assertEqual(rec["first_minibatch"], off.log.recs[-1]["first_minibatch"])
        self.assertEqual((rec["kl_gate"], rec["beta_next"]), (off.log.recs[-1]["kl_gate"], off.log.recs[-1]["beta_next"]))
        b = rec["branch"]
        self.assertEqual((b["drained"], b["stale_dropped"], b["emitted"], b["dropped"], b["n"], b["buffer"]),
                         (6, 0, 6, 1, 5, 5))
        self.assertEqual(b["by_worker"], {0: 3, 1: 3})
        self.assertAlmostEqual(b["hold_better_share"], 3 / 5)
        st = b["step"]
        self.assertEqual(st["rows"], 5)
        self.assertIsNone(st["skipped"])
        self.assertLess(st["bce_after"], st["bce_before"])
        self.assertGreater(st["dp_abs_mean"], 0.0)
        line = L.log.lines[-1]
        self.assertIn("| branch n 5/6 hold+ 0.600", line)
        self.assertIn("[single 2 0.500", line)
        self.assertIn(" buf 5 aged-0 bce ", line)
        self.assertIn("| drained 6 stale-0 lag 0.0 workers 24/24 err 0", line)

    def test_staleness_drop(self):
        """u - version > branch_max_staleness -> dropped before stats and buffer; at the limit -> kept."""
        L = self._learner(RL, {**ON, "branch_max_staleness": 3}, name="stale")
        smp = (self._samples([0.5, -0.5], version=1) + self._samples([0.4, -0.4], seed=23, version=2)
               + self._samples([0.3], seed=24, version=5))
        st = L._branch_update(smp, RL.branch_cfg(L.cfg), apply=False, u=5)
        self.assertEqual((st["drained"], st["stale_dropped"], st["emitted"], st["buffer"]), (5, 2, 3, 3))
        self.assertAlmostEqual(st["staleness_mean"], (4 + 4 + 3 + 3 + 0) / 5)
        self.assertEqual(sorted(x["version"] for x in L.branch_buf), [2, 2, 5])

    def test_drained_once_per_update_and_fifo(self):
        L = self._on(self._samples([0.5, -0.4, 0.3, -0.3, 0.6]), "fifo", branch_buffer=6)
        L.one_update(0)
        first = [id(x) for x in L.branch_buf]
        L.branch_pool.pending = self._samples([0.2, -0.2, 0.3], seed=22, version=1)
        rec, _, _ = L.one_update(1)
        self.assertEqual((L.sent, L.branch_pool.drains), ([0, 1], 2))
        self.assertEqual((rec["branch"]["buffer"], rec["branch"]["step"]["rows"]), (6, 6))
        self.assertEqual([id(x) for x in L.branch_buf[:3]], first[2:])      # the 2 oldest left
        self.assertEqual([x["delta"] for x in L.branch_buf[3:]], [0.2, -0.2, 0.3])

    def test_no_step_without_buffer_or_in_warmup(self):
        L = self._on(self._samples([0.01, -0.02]), "drop")
        off = self._learner(RL, {}, name="ref")
        rec, _, _ = L.one_update(0)
        off.one_update(0)
        self.assertIsNone(rec["branch"]["step"])
        self.assertEqual(rec["branch"]["buffer"], 0)
        self.assertIn("(no step)", L.log.lines[-1])
        self.assertEqual(len(L.grads), len(off.grads))         # no extra optimizer step
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(L.model.parameters(), off.model.parameters())))
        st = L._branch_update(self._samples([0.5, -0.5]), RL.branch_cfg(L.cfg), apply=False, u=0)   # warm-up
        self.assertEqual((st["buffer"], st["step"]), (2, None))

    def _after_ppo(self, name, **extra):
        """A learner after one gate-off update (PPO's Adam holds momentum), with a 5-row buffer ready."""
        L = self._learner(RL, {**ON, **extra}, name=name)
        L.branch_pool, L._branch_send = _FakePool(), (lambda u, bc: None)
        L.one_update(0)
        return L

    def test_own_optimizer_zero_coef_or_lr_is_bit_identical(self):
        """The verifier's case: with the SHARED Adam a coef-0 branch step still moved the params by PPO's leftover
        momentum. Own Adam: coef 0 or branch_lr 0 -> parameters and PPO's Adam state bit-identical."""
        for extra in ({"branch_coef": 0.0}, {"branch_lr": 0.0}):
            L = self._after_ppo(f"zero{len(extra)}{list(extra)[0]}", **extra)
            before = [p.detach().clone() for p in L.model.parameters()]
            opt_before = copy.deepcopy(L.opt.state_dict())
            st = L._branch_update(self._samples([0.5, -0.4, 0.3, -0.6, 0.7], version=1), RL.branch_cfg(L.cfg),
                                  apply=True, u=1)
            self.assertIsNotNone(st["step"])
            self.assertIsNone(st["step"]["skipped"])
            self.assertTrue(all(torch.equal(a, b) for a, b in zip(before, L.model.parameters())), extra)
            self.assertEqual(st["step"]["dp_abs_mean"], 0.0)
            _same_opt_state(self, L.opt, SimpleNamespace(state_dict=lambda: opt_before))

    def test_own_optimizer_sign_and_ppo_state_untouched(self):
        for delta, sign in ((0.6, 1.0), (-0.6, -1.0)):
            L = self._after_ppo(f"sign{int(sign)}", branch_lr=1e-2, branch_coef=1.0)
            smp = self._samples([delta] * 4, version=1)
            Bb = RL.to_device(RL.branch_batch(smp, 0.0), "cpu")
            p0 = _p_play(L.model, Bb, L.cfg["tau"], L.cfg["T"])
            opt_before = copy.deepcopy(L.opt.state_dict())
            L._branch_update(smp, RL.branch_cfg(L.cfg), apply=True, u=1)
            dp = (_p_play(L.model, Bb, L.cfg["tau"], L.cfg["T"]) - p0).numpy()
            self.assertTrue((sign * dp > 0).all(), (delta, dp))
            _same_opt_state(self, L.opt, SimpleNamespace(state_dict=lambda: opt_before))

    def test_branch_optimizer_rides_the_checkpoint(self):
        L = self._after_ppo("ck", branch_lr=1e-3)
        L._branch_update(self._samples([0.6, -0.6], version=1), RL.branch_cfg(L.cfg), apply=True, u=1)
        rl = L._rl_state()
        self.assertIn("branch_optimizer", rl)
        path = L.save(None, numbered=False)                     # _latest only (returns None)
        L2 = self._learner(RL, {**ON, "branch_lr": 1e-3}, name="ck2")
        L2.branch_opt = L2._branch_optimizer(RL.branch_cfg(L2.cfg))
        L2._restore(L.ck_dir / "unit_latest.pt")
        _same_opt_state(self, L2.branch_opt, L.branch_opt)
        _same_opt_state(self, L2.opt, L.opt)
        self.assertIsNone(path)
        off = self._learner(RL, {}, name="ckoff")
        self.assertNotIn("branch_optimizer", off._rl_state())    # gate off: the checkpoint layout is unchanged

    def test_buffer_rows_age_out(self):
        """Rows labelled under weights older than u - branch_buffer_max_age are evicted at each drain."""
        L = self._learner(RL, {**ON, "branch_buffer_max_age": 20, "branch_max_staleness": 100}, name="age")
        bc = RL.branch_cfg(L.cfg)
        L._branch_update(self._samples([0.5, -0.5], version=0) + self._samples([0.4], seed=23, version=5), bc,
                         apply=False, u=5)
        st = L._branch_update(self._samples([0.3], seed=24, version=21), bc, apply=False, u=21)
        self.assertEqual((st["buffer"], st["buffer_aged_out"]), (2, 2))      # v0 rows: 21 - 0 > 20
        self.assertEqual(sorted(x["version"] for x in L.branch_buf), [5, 21])
        st = L._branch_update([], bc, apply=False, u=25)
        self.assertEqual((st["buffer"], st["buffer_aged_out"]), (2, 0))      # 25 - 5 = 20: kept at the limit
        st = L._branch_update([], bc, apply=False, u=26)
        self.assertEqual((st["buffer"], st["buffer_aged_out"]), (1, 1))


    def test_learner_update_does_not_wait(self):
        """one_update with a real BranchPool whose workers take 20 s per label: returns before any label arrives."""
        L = self._learner(RL, ON, name="nowait")
        L.branch_pool = RL.BranchPool({"slow_s": 20.0}, 2, lambda m: None, target=_slow_worker, ctx=THREAD_CTX)
        self.addCleanup(L.branch_pool.close)
        L._branch_send = (lambda u, bc: L.branch_pool.send(u, b"w", [[], []]))
        t = time.perf_counter()
        rec, _, _ = L.one_update(0)
        self.assertLess(time.perf_counter() - t, 15.0)
        self.assertEqual(rec["branch"]["drained"], 0)


def _same_opt_state(test, a, b):
    sa, sb = a.state_dict(), b.state_dict()
    test.assertEqual(sa["param_groups"], sb["param_groups"])
    test.assertEqual(set(sa["state"]), set(sb["state"]))
    for k in sa["state"]:
        for n, v in sa["state"][k].items():
            w = sb["state"][k][n]
            test.assertTrue(torch.equal(v, w) if torch.is_tensor(v) else v == w, (k, n))


# ------------------------------------------------------------------------------------------------------
# BranchPool: never waited on
# ------------------------------------------------------------------------------------------------------
class _MQ(queue.Queue):
    """queue.Queue with the mp.Queue method ``actor_sender`` calls."""

    def cancel_join_thread(self):
        pass


class _TProc(threading.Thread):
    pid, exitcode = 0, None

    def __init__(self, target, args, daemon):
        super().__init__(target=target, args=args, daemon=daemon)

    def terminate(self):
        pass


THREAD_CTX = SimpleNamespace(Queue=_MQ, Process=_TProc)


def _slow_worker(wid, in_q, out_q, base):
    """A fake worker: takes ``base['slow_s']`` per label, one sample per weights message, until None."""
    while True:
        msg = in_q.get()
        if msg is None:
            return
        time.sleep(base["slow_s"])
        out_q.put(("sample", wid, {"version": msg[0], "worker": wid, "delta": 0.5}))


def _never_reads(wid, in_q, out_q, base):
    """A worker stuck mid-pair: never reads its queue."""
    time.sleep(3600)


def _exit_scenario():
    """Child-process scenario for TestPoolExit: 2 workers that never read, 3 x 6 MB weights messages each, close()
    twice (idempotent), then return -- the interpreter must exit promptly."""
    P = RL.BranchPool({}, 2, lambda m: None, target=_never_reads)
    for v in range(3):
        P.send(v, b"x" * 6_000_000, [[], []])
    time.sleep(2)
    P.close()
    P.close()
    print(f"CLOSED {time.time():.3f}", flush=True)


class TestPoolExit(unittest.TestCase):
    """Verifier [must]: terminate() with ~6 MB unread weights in the workers' queues made the learner wait forever at
    interpreter exit. close() cancels every queue's feeder first; the parent exits within 10 s of close()."""

    def test_parent_exits_after_close_with_unread_weights(self):
        code = "from pipeline.tests.test_rl_branch import _exit_scenario; _exit_scenario()"
        try:
            r = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            self.fail("the learner-like parent did not exit within 180 s after close()")
        end = time.time()
        closed = [float(x.split()[1]) for x in r.stdout.splitlines() if x.startswith("CLOSED ")]
        self.assertEqual(len(closed), 1, r.stdout + r.stderr[-2000:])
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertLess(end - closed[0], 10.0)


class TestBranchPool(unittest.TestCase):
    def test_update_never_blocks_on_a_slow_worker(self):
        P = RL.BranchPool({"slow_s": 1.5}, 2, lambda m: None, target=_slow_worker, ctx=THREAD_CTX)
        self.addCleanup(P.close)
        t = time.perf_counter()
        P.send(0, b"w0", [[], []])
        got, info = P.drain()                                   # the workers are mid-label
        self.assertLess(time.perf_counter() - t, 0.5)
        self.assertEqual((got, info["alive"]), ([], 2))
        deadline = time.time() + 10
        out = []
        while len(out) < 2 and time.time() < deadline:
            time.sleep(0.2)
            out += P.drain()[0]
        self.assertEqual(sorted((x["worker"], x["version"]) for x in out), [(0, 0), (1, 0)])

    def test_dead_worker_restarted_and_gets_the_newest_weights(self):
        def dies(wid, in_q, out_q, base):
            return
        P = RL.BranchPool({}, 1, lambda m: None, target=dies, ctx=THREAD_CTX, max_restarts=1)
        self.addCleanup(P.close)
        P.send(4, b"w4", [["spec"]])
        P.procs[0].join(5)
        P.target = _slow_worker
        P.base = {"slow_s": 0.0}
        _, info = P.drain()
        self.assertEqual(info["restarted"], [0])
        deadline, out = time.time() + 5, []
        while not out and time.time() < deadline:
            time.sleep(0.1)
            out += P.drain()[0]
        self.assertEqual(out[0]["version"], 4)                  # the restarted worker got version 4 at once


# ------------------------------------------------------------------------------------------------------
# the branch match loop and the worker on the engine (fake T1 / T2)
# ------------------------------------------------------------------------------------------------------
ICEBOW = ["Tornado", "Tesla@evolution", "IceWizard", "Xbow", "Rocket", "Knight@evolution", "Log", "Skeletons"]
HOGEQ = ["HogRider", "Earthquake", "Log", "Cannon", "Musketeer", "IceSpirits", "Skeletons", "Valkyrie"]


def _engine_setup(opp_policy="sample", n_specs=1):
    from pipeline import search_s0 as S
    from pipeline.tests.test_search_s0 import tiny_models
    gen, opp_gen, _ = tiny_models()
    lcfg = {**S.live_cfg(0.05, "lattice"), "T": 0.3}            # tau 0.05: the tiny random gate plays often
    ocfg = {**S.live_cfg(0.27, "lattice"), "policy": opp_policy, "T": 0.5}
    specs = [(i, {"tag": f"br0000_{i:03d}", "opp": {"id": "o", "path": "unused"}, "learner_deck": ICEBOW,
                  "opp_deck": HOGEQ, "learner_side": 1, "seed": 3 + i}, 0) for i in range(n_specs)]
    bc = {**RL.BRANCH_DEFAULTS, "branch_gate": True, "branch_points_per_match": 60, "branch_band": [0.0, 1.0],
          "branch_k": 2}
    return gen, opp_gen, lcfg, ocfg, specs, bc


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestBranchMatch(unittest.TestCase):
    TAIL = 1500

    def setUp(self):
        _patch_impl(self)
        BranchRunner.calls = []

    def _env(self):
        return RoyaleSelfPlayEnv(tail_cap=self.TAIL)

    def test_emits_samples_and_main_trajectory_is_run_selfplay_batch(self):
        gen, opp_gen, lcfg, ocfg, specs, bc = _engine_setup("sample")
        spec = specs[0][1]
        emitted = []
        out, info = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg, bc, 0, emit=emitted.append)
        self.assertGreater(len(out), 3)
        self.assertEqual(emitted, out)                          # streamed as labelled
        self.assertEqual(info, {"matches": 1, "pairs": len(out), "stopped": False})
        self.assertEqual(len(out), len(BranchRunner.calls))
        for s in out:
            self.assertTrue(s["branch"])
            self.assertEqual(s["phase"], RL.phase_of(s["tick"]))
            self.assertEqual(set(s), {"branch", "kind", "tag", "k", "entry_index", "side", "tick", "phase", "p_gate",
                                      "p_play", "hold_s", "delta", "weight", "wall_s", "row"})
            self.assertEqual(s["kind"], "hold")
            self.assertIn(s["hold_s"], (2.0, 4.0, 8.0))
            self.assertEqual(s["side"], 1)
            for k in E.gen_row_keys(gen.model):
                self.assertIn(k, s["row"])
        sp = BranchRunner.calls[0][2]
        self.assertEqual((sp.hold_tau, sp.horizon_s, sp.k), (0.55, None, 2))
        Bb = RL.to_device(RL.branch_batch(out, 0.0), "cpu")
        with torch.no_grad():
            z = RL.branch_terms(gen.model, Bb, torch.arange(len(out)), 0.05, 0.3)[0] * 0.3 + np.log(0.05 / 0.95)
        np.testing.assert_allclose(torch.sigmoid(z).numpy(), [s["p_gate"] for s in out], atol=1e-5)

        # the main trajectory = run_selfplay_batch's (learner live, opponent SAMPLING on its own RNG), branching or not
        over = RL.rollout_jobs(specs, 0)[0][3]
        m = E.SelfPlayMatch(self._env(), spec, 0, {**lcfg, **over, "entry_index": 0},
                            {**ocfg, **{x: v for x, v in over.items() if x != "obs_seed"}, "entry_index": 0}, gen, opp_gen)
        RL.play_branch_match(m, BranchRunner(None, None, None, None, device="cpu"), fake_impl(), bc)
        mine = m.result()
        ref = []
        E.run_selfplay_batch(self._env, gen, {"o": (opp_gen, ocfg)}, RL.rollout_jobs(specs, 0), lcfg, 1,
                             on_result=ref.append)
        for k in ("plays", "outcome", "end_tick", "decisions"):
            self.assertEqual(mine[k], ref[0][k], k)
        self.assertEqual(mine["opp_side"], ref[0]["opp_side"])

    def test_sync_false_stops_at_once(self):
        """sync() False after the 3rd pair: no 4th pair, no further match."""
        gen, opp_gen, lcfg, ocfg, specs, bc = _engine_setup("live", n_specs=3)
        out, info = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg, bc, 0,
                                   sync=lambda: len(BranchRunner.calls) < 3)
        self.assertEqual((len(out), len(BranchRunner.calls), info["stopped"]), (3, 3, True))
        self.assertEqual(info["matches"], len({s["tag"] for s in out}))

    def test_wait_points_below_tau_are_branched(self):
        """The band straddles tau: a decision the live rule WAITS on (p <= tau, affordable, no stall) is eligible too
        (T1 forces the PLAY branch there)."""
        gen, opp_gen, lcfg, ocfg, specs, bc = _engine_setup("live")
        lcfg = {**lcfg, "tau": 0.97}                            # the tiny gate (p ~ 0.5) now waits almost always
        out, _ = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg, bc, 0)
        self.assertGreater(len(out), 0)
        self.assertTrue(all(s["p_gate"] <= 0.97 for s in out))

    def test_stalled_points_are_not_branched(self):
        """Anti-stall firing at every decision (stall_elixir 0, 0 s): every play is forced -> no branch point; the
        same match without the stall rule does branch."""
        gen, opp_gen, lcfg, ocfg, specs, bc = _engine_setup("live")
        out, _ = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs,
                                {**lcfg, "stall_elixir": 0, "stall_seconds": 0.0}, bc, 0)
        self.assertEqual(out, [])
        out, _ = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg, bc, 0)
        self.assertGreater(len(out), 0)
        self.assertTrue(all(s["row"]["stalled"] is False for s in out))

    def test_band_excludes(self):
        gen, opp_gen, lcfg, ocfg, specs, bc = _engine_setup("live")
        out, _ = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg, {**bc, "branch_band": [0.0, 1e-4]}, 0)
        self.assertEqual(out, [])


def _worker_base(bc):
    from pipeline.dataset_gen import card_key
    from pipeline.royale_runtime import activate
    vocab = ["<pad>"] + sorted({card_key(n) for n in ICEBOW + HOGEQ})
    return {"actor_threads": 1, "actor_device": "cpu", "tau": 0.05, "T": 0.3, "afford_mask": True, "stall_elixir": 9,
            "stall_seconds": 12.0, "obs": "live", "decide_every": 10, "in_flight": 1, "d": 16, "layers": 1,
            "grid": "lattice", "noise_off": "all", "opp_elixir": "counter", "action_delay_ticks": 26,
            "extrapolate_ticks": 26, "gen": {"d_c": 8, "card_vocab": vocab}, "runtime": activate(),
            "league_opp_policy": "sample", "hero_abilities": False, "ability_policy": "generic", "forms_mode": "base",
            "branch": bc}, vocab


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestBranchWorker(unittest.TestCase):
    """``branch_worker_main`` itself (in a thread, fake T1/T2, tiny models): it keeps playing the SAME match across an
    update boundary, labels with the new version after it, and exits on None."""

    def test_continues_across_an_update_boundary(self):
        from pipeline.model_gen import GenModel
        _patch_impl(self)
        BranchRunner.calls = []
        bc = {**RL.BRANCH_DEFAULTS, "branch_gate": True, "branch_points_per_match": 60, "branch_band": [0.0, 1.0],
              "branch_k": 2}
        base, vocab = _worker_base(bc)
        torch.manual_seed(0)
        net = GenModel(d=16, layers=1, d_c=8, n_cards=len(vocab)).eval()
        opp = E.GenPolicy(GenModel(d=16, layers=1, d_c=8, n_cards=len(vocab)).eval(), vocab)
        orig = E.load_policy
        E.load_policy = (lambda path, dev: (opp, {"grid": "lattice"}))
        self.addCleanup(setattr, E, "load_policy", orig)
        spec = {"opp": {"id": "o", "path": "fake.pt"}, "learner_deck": ICEBOW, "opp_deck": HOGEQ, "learner_side": 0,
                "seed": 5}
        in_q, out_q = _MQ(), _MQ()
        th = threading.Thread(target=RL.branch_worker_main, args=(0, in_q, out_q, base), daemon=True)
        th.start()
        self.assertEqual(out_q.get(timeout=60)[0], "ready")
        in_q.put((0, RL.state_bytes(net), [spec]))

        def take(pred, timeout=120):
            deadline = time.time() + timeout
            while time.time() < deadline:
                msg = out_q.get(timeout=timeout)
                self.assertNotEqual(msg[0], "error", msg)
                if pred(msg[2]):
                    return msg[2]
            self.fail("no such sample")
        s0 = take(lambda x: True)
        self.assertEqual((s0["version"], s0["worker"]), (0, 0))
        with torch.no_grad():
            for p in net.parameters():
                p.add_(0.01)
        in_q.put((1, RL.state_bytes(net), []))                  # update boundary: new weights, no new spec
        s1 = take(lambda x: x["version"] == 1)
        self.assertEqual(s1["tag"], s0["tag"])                  # the same match, continued
        self.assertGreater(s1["tick"], s0["tick"])
        self.assertTrue(th.is_alive())
        in_q.put(None)
        th.join(60)
        self.assertFalse(th.is_alive())


def _spawn_target(*a, **k):
    """Spawn-child target for TestBranchPoolSpawn: fake T1/T2 (a pair costs 0.5 s), a tiny frozen opponent."""
    from pipeline.model_gen import GenModel
    RL.branch_impl = fake_impl
    BranchRunner.sleep_s = 0.5
    vocab = a[3]["gen"]["card_vocab"]
    opp = E.GenPolicy(GenModel(d=16, layers=1, d_c=8, n_cards=len(vocab)).eval(), vocab)
    E.load_policy = (lambda path, dev: (opp, {"grid": "lattice"}))
    return RL.branch_worker_main(*a, **k)


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestBranchPoolSpawn(unittest.TestCase):
    """Real spawn workers + mp queues: what one drain returns carries the weights version just sent (lag <= 1). The
    first build fell behind by 1-2 updates because sample messages (observation rows) backed up in the pipe between
    non-blocking drains; ``BranchPool._read`` keeps the pipe flowing."""

    def test_drained_versions_track_the_sends(self):
        from pipeline.model_gen import GenModel
        bc = {**RL.BRANCH_DEFAULTS, "branch_gate": True, "branch_points_per_match": 200, "branch_band": [0.0, 1.0],
              "branch_k": 2}
        base, vocab = _worker_base(bc)
        net = GenModel(d=16, layers=1, d_c=8, n_cards=len(vocab)).eval()
        spec = {"opp": {"id": "o", "path": "fake.pt"}, "learner_deck": ICEBOW, "opp_deck": HOGEQ, "learner_side": 0,
                "seed": 5}
        P = RL.BranchPool(base, 1, lambda m: None, target=_spawn_target)
        self.addCleanup(P.close)
        drains = []
        for v in range(4):
            P.send(v, RL.state_bytes(net), [[spec, spec, spec]])
            time.sleep(10 if v else 25)                         # v0: worker start-up (imports, engine)
            drains.append([x["version"] for x in P.drain()[0]])
        for v, got in list(enumerate(drains))[1:]:
            self.assertTrue(got, f"no samples after v{v}: {drains}")
            self.assertTrue(set(got) <= {v - 1, v} and v in got, f"v{v}: {drains}")


try:                                                            # T1 + T2 landed?
    import pipeline.branch_score  # noqa: F401
    import pipeline.branching  # noqa: F401
    HAVE_T12 = True
except ImportError:
    HAVE_T12 = False


@unittest.skipUnless(HAVE_T12 and RoyaleSelfPlayEnv is not None, "pipeline.branching / branch_score not importable yet")
class TestIntegration(unittest.TestCase):
    def test_real_runner_and_label(self):
        gen, opp_gen, lcfg, ocfg, specs, bc = _engine_setup("sample")
        bc = {**bc, "branch_horizon_s": 2.0, "branch_k": 2, "branch_score": "towers"}
        out, info = RL.branch_jobs(lambda: RoyaleSelfPlayEnv(tail_cap=600), gen, {"o": (opp_gen, ocfg)}, specs, lcfg,
                                   bc, 0)
        self.assertGreaterEqual(len(out), 1)
        self.assertEqual(info["pairs"], len(out))
        for s in out:
            self.assertTrue(np.isfinite(s["delta"]) and np.isfinite(s["weight"]))
        RL.branch_batch(out, 0.0)


if __name__ == "__main__":
    unittest.main()
