"""C1 stage A: the learned posture head (rl_royale ``posture_head``; L74 reward/REWARD_ARCHITECTURE.md 5 C1).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_posture_head.py

Covers: config / hash / validation; head init P(balanced) = 0.8; the actor weights message; the sampler's gate under
tau + dtau; z held for posture_every ticks and re-chosen after (real SelfPlayMatch on test_league's fake env); collate;
the learner's gate log-prob under tau + dtau; the posture PPO term reaches only the head; checkpoint save -> resume;
one_update end to end; absent posture = the pre-change code (rl_royale, e1_eval, search_s0 run.json; loaded from git);
search_s0 applies the argmax posture (= the shifted threshold) when the checkpoint has a head; graft_generic carries it.
"""
from __future__ import annotations

import copy
import json
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

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.dataset import PAST_K                                       # noqa: E402
from pipeline.obs_contract import F as TOK_F, S as SC_S                   # noqa: E402
from pipeline.tests.test_rl_gae import SPEC, TAU, T, _learner, _strip, _Tmp   # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

PRE = "6ee9ab9"             # HEAD at dispatch: the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
GAE = dict(advantage="gae", critic_warmup_updates=1, seed=0)
DTAU = [0.10, 0.0, -0.10]
POST = dict(posture_head=True, posture_every=60, posture_dtau=DTAU, posture_ent_coef=0.01)


def _pre(path: str, name: str):
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{path}"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE} failed: {src.stderr.strip()}")
    mod = types.ModuleType(name)
    mod.__file__, mod.__package__ = str(REPO / path), "pipeline"
    exec(compile(src.stdout, name, "exec"), mod.__dict__)
    return mod


def _head(d_g, seed=3, scale=0.5):
    """A PostureHead whose last layer is perturbed (so pi depends on the input), deterministic."""
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        h = RL.PostureHead(d_g)
        with torch.no_grad():
            h.net[2].weight.normal_(0.0, scale)
    return h.eval()


def _forced(d_g, z):
    """A head whose argmax is always posture z."""
    h = RL.PostureHead(d_g)
    with torch.no_grad():
        h.net[2].bias.copy_(torch.tensor([100.0 if i == z else 0.0 for i in range(3)]))
    return h.eval()


class _PM:
    """What posture_dtau / sample_decide_batch read of a match: rng_behave, the decision tick, a ctx row."""

    def __init__(self, seed):
        self.rng_behave, self._cur = np.random.default_rng(seed), (0,)

    def _ctx_row(self, tick):
        return [(tick // 40) % 9, int(tick >= 300), (tick // 200) % 3, min(3, tick // 250), (tick // 170) % 4]


def _synth(model, head, rng, n, seed, every=60, step=20):
    """test_rl_royale._synth_match with a posture: one decision every ``step`` ticks of ONE fake match through the
    real sampler (row by row, so the match's posture state carries over) -> ``Match._traj_arrays`` + ctx rows."""
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
        pasts.append(np.full((PAST_K, 4), -1.0, np.float32))
    enc, heads, p, hand = E.model_forward_batch(model, toks, masks, scs, pasts)
    allowed = hand & (rng.random(hand.shape) < 0.7)
    allowed[rng.random(n) < 0.15] = False
    stalled = np.zeros(n, dtype=bool)
    fm = _PM(seed)
    cfg = {"tau": TAU, "T": T, "posture": {"head": head, "every": every, "dtau": DTAU, "mode": "sample"}}
    rows = []
    for r in range(n):
        fm._cur = (r * step,)
        sl = (lambda d: {k: v[r:r + 1] for k, v in d.items()})
        d = E.sample_decide_batch(model, sl(enc), sl(heads), p[r:r + 1], allowed[r:r + 1], stalled[r:r + 1], [fm], cfg)[0]
        rows.append({"tok": toks[r], "mask": masks[r], "sc": scs[r], "past": pasts[r], "ctx": fm._ctx_row(r * step),
                     "allowed": d["allowed"], "stalled": d["stalled"], "gate_sampled": d["gate_sampled"],
                     "played": d["play"], "slot": d["slot"], "cell": d["cell"], "lp_gate": d["lp_gate"],
                     "lp_card": d["lp_card"], "lp_cell": d["lp_cell"], "p_gate": d["p_gate"], "T": d["T"],
                     **{k: d[k] for k in ("posture", "posture_dtau", "posture_lp", "posture_new")}})
    tj = E.Match._traj_arrays(SimpleNamespace(traj=rows))
    tj["ctx"] = np.array([r["ctx"] for r in rows], dtype=np.int64)
    return tj


def _posture_results(model, head, seed=13):
    rng = np.random.default_rng(seed)
    res = [{"entry_index": i, "k": g, "outcome": o, "traj": _synth(model, head, rng, n, 100 * i + g)}
           for i, g, n, o in SPEC]
    return _monitor_fields(res)


# ------------------------------------------------------------------------------------------------------
class TestConfig(unittest.TestCase):
    def test_hash(self):
        cfg = RL.load_config(YAML, [], False)
        self.assertFalse(any(k in cfg for k in RL.POSTURE_KEYS))
        P = _pre("pipeline/rl_royale.py", "rl_royale_pre_c1")
        self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg))                     # the historical hash
        for off in (None, False):
            self.assertEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, posture_head=off)))
        on = RL.config_sha(dict(cfg, posture_head=True))
        self.assertNotEqual(on, RL.config_sha(cfg))
        self.assertEqual(on, RL.config_sha(dict(cfg, posture_head="on")))
        self.assertEqual(on, RL.config_sha(dict(cfg, posture_head=True, posture_every=200, posture_dtau=[0.1, 0, -0.1],
                                                posture_ent_coef=0.01)))      # explicit defaults = implicit
        self.assertNotEqual(on, RL.config_sha(dict(cfg, posture_head=True, posture_every=100)))

    def test_load_config_override(self):
        cfg = RL.load_config(YAML, ["advantage=gae", "posture_head=on", "posture_every=100"], False)
        self.assertIs(cfg["posture_head"], True)                                  # YAML 1.1: on = true
        self.assertEqual(RL.posture_cfg(cfg), {"every": 100, "dtau": DTAU, "ent_coef": 0.01, "lr": 3e-4})

    def test_validation(self):
        ok = {"advantage": "gae", "tau": TAU, "posture_head": True}
        self.assertIsNone(RL.posture_cfg({}))
        self.assertIsNone(RL.posture_cfg({"posture_head": False}))
        self.assertEqual(RL.posture_cfg(ok), {"every": 200, "dtau": DTAU, "ent_coef": 0.01, "lr": 3e-4})
        self.assertEqual(RL.posture_cfg({**ok, "posture_lr": 1e-3})["lr"], 1e-3)
        # Learner.__init__'s own step (store_posture_cfg) must leave EVERY default key in cfg (10-15: posture_lr was
        # missed there and every pod smoke died with KeyError before update 0); off -> cfg untouched
        cfg = dict(ok)
        RL.store_posture_cfg(cfg)
        self.assertEqual({k: cfg[k] for k in RL.POSTURE_DEFAULTS}, {**RL.POSTURE_DEFAULTS, "posture_dtau": DTAU})
        self.assertIsInstance(cfg["posture_lr"], float)
        off = {"advantage": "gae", "tau": TAU}
        self.assertIsNone(RL.store_posture_cfg(off))
        self.assertEqual(off, {"advantage": "gae", "tau": TAU})
        for bad in ({"posture_every": 100}, {"posture_head": None, "posture_dtau": DTAU},       # keys without the head
                    {**ok, "advantage": "match_loo"}, {"tau": TAU, "posture_head": True},      # needs gae
                    {**ok, "posture_head": "yes"}, {**ok, "posture_every": 0}, {**ok, "posture_every": 20.0},
                    {**ok, "posture_every": True}, {**ok, "posture_dtau": [0.1, 0.0]},
                    {**ok, "posture_dtau": [0.8, 0.0, -0.1]}, {**ok, "posture_dtau": [0.1, 0.0, -0.3]},
                    {**ok, "posture_ent_coef": -0.1}, {**ok, "branch_gate": True}, {**ok, "posture_lr": 0.0},
                    {**ok, "posture_lr": "3e-4"}, {"posture_lr": 1e-3}):
            with self.assertRaises(SystemExit, msg=bad) as cm:
                RL.posture_cfg(bad)
            self.assertIn("posture", str(cm.exception))

    def test_actor_cfg(self):
        base = {**RL.load_config(YAML, [], False), "grid": "lattice"}
        for k in ("rollout", "screen"):
            c = RL.actor_cfg(base, k, 0, "cpu")
            self.assertFalse("posture" in c or "record_ctx" in c)
        pb = {"every": 200, "dtau": DTAU, "d_g": 16, "hidden": 64}
        r, s = (RL.actor_cfg({**base, "posture": pb}, k, 0, "cpu") for k in ("rollout", "screen"))
        self.assertEqual(r["posture"], {"every": 200, "dtau": DTAU, "mode": "sample"})
        self.assertIs(r["record_ctx"], True)                    # ctx rows WITHOUT critic_ctx (the critic stays plain)
        self.assertEqual(s["posture"], {"every": 200, "dtau": DTAU, "mode": "argmax"})
        self.assertNotIn("record_ctx", s)


# ------------------------------------------------------------------------------------------------------
class TestHead(unittest.TestCase):
    def test_init_p_balanced(self):
        h = RL.PostureHead(16)
        g, ctx = torch.randn(50, 16), torch.tensor([[i % 9, i % 2, i % 3, i % 4, (i + 1) % 4] for i in range(50)])
        p = torch.softmax(h(g, ctx).double(), -1)
        self.assertTrue(torch.allclose(p, torch.tensor([0.1, 0.8, 0.1], dtype=torch.float64).expand(50, 3), atol=1e-6))
        self.assertEqual(h.net[0].in_features, 16 + 21)
        self.assertFalse(any(k.startswith("posture") for k in _tiny_model(0).state_dict()))

    def test_g_is_detached(self):
        g = torch.randn(4, 16, requires_grad=True)
        _head(16)(g, torch.zeros(4, 5, dtype=torch.long)).sum().backward()
        self.assertIsNone(g.grad)

    def test_actor_message(self):
        m, h = _tiny_model(1), _head(16)
        self.assertEqual(RL.actor_bytes(m), RL.state_bytes(m))                # no head: the old message exactly
        msd, psd = RL.split_actor_sd(RL.actor_bytes(m), "cpu")
        self.assertEqual(psd, {})
        msd, psd = RL.split_actor_sd(RL.actor_bytes(m, h), "cpu")
        self.assertEqual(sorted(msd), sorted(m.state_dict()))
        h2 = RL.PostureHead(16)
        h2.load_state_dict(psd)
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(h.state_dict().values(), h2.state_dict().values())))


# ------------------------------------------------------------------------------------------------------
class TestSampler(unittest.TestCase):
    def test_gate_uses_tau_plus_dtau(self):
        model = _tiny_model(2)
        rng = np.random.default_rng(0)
        for z in range(3):
            tj = _synth(model, _forced(16, z), rng, 25, seed=z)
            self.assertTrue((tj["posture"] == z).all())
            np.testing.assert_array_equal(tj["posture_dtau"], np.full(25, DTAU[z]))
            gs = tj["gate_sampled"]
            self.assertGreater(int(gs.sum()), 5)
            pg = tj["p_gate"][gs].astype(np.float64)
            x = (np.log(pg / (1 - pg)) - np.log((TAU + DTAU[z]) / (1 - TAU - DTAU[z]))) / T
            pb = 1 / (1 + np.exp(-x))
            want = np.where(tj["played"][gs], pb, 1 - pb)
            np.testing.assert_allclose(np.exp(tj["lp_gate"][gs]), want, rtol=1e-5)
            if DTAU[z]:                                         # non-vacuous: the plain-tau probability differs
                x0 = (np.log(pg / (1 - pg)) - np.log(TAU / (1 - TAU))) / T
                p0 = np.where(tj["played"][gs], 1 / (1 + np.exp(-x0)), 1 / (1 + np.exp(x0)))
                self.assertGreater(float(np.abs(np.exp(tj["lp_gate"][gs]) - p0).max()), 1e-3)

    def test_choice_cadence(self):
        """every 60 ticks, a decision every 20: chosen at rows 0, 3, 6, ...; z constant in between; log pi(z) only on
        the choice rows; the rows with no card allowed choose too."""
        tj = _synth(_tiny_model(2), _head(16), np.random.default_rng(1), 30, seed=5)
        self.assertEqual(np.flatnonzero(tj["posture_new"]).tolist(), list(range(0, 30, 3)))
        for a in range(0, 30, 3):
            self.assertEqual(len(set(tj["posture"][a:a + 3].tolist())), 1)
        self.assertTrue((tj["posture_lp"][tj["posture_new"]] < 0).all())
        self.assertTrue((tj["posture_lp"][~tj["posture_new"]] == 0).all())
        self.assertGreater(len(set(tj["posture"].tolist())), 1)                 # the sampled head varies


class TestSelfPlayRecording(unittest.TestCase):
    """e1_eval's real SelfPlayMatch on test_league's fake env (decide_every 100, ticks 2200..3800, posture_every 300):
    z held for 300 ticks and re-chosen after, rows recorded through Match._record; absent posture = the pre-change
    e1_eval (the same records, byte for byte)."""

    def _env(self):
        from pipeline.tests import test_league as TL

        class Env(TL._SPEnv):
            def reset(self, *a, **k):
                st = super().reset(*a, **k)
                self.tick, self.tail_cap = 2200, 3800
                return st
        return Env

    def _run(self, mod, side=0, posture=None, **cfg):
        from pipeline.tests import test_league as TL
        learner, opp = mod.GenPolicy(TL._tiny_gen(1), TL.VOCAB), mod.GenPolicy(TL._tiny_gen(2), TL.VOCAB)
        lc = TL._cfg(decide_every=100, record_tick=True, stall_elixir=None, **cfg)
        if posture is not None:
            lc["posture"] = posture
        out = []
        mod.run_selfplay_batch(self._env(), learner, {"snapA": (opp, TL._cfg("live", record=False, decide_every=100,
                                                                              stall_elixir=None))},
                               [(0, TL._spec(0, "snapA", side), 0, {"rollout_index": 0, "update": 0})], lc, 1,
                               on_result=out.append)
        return out[0]

    def test_held_and_rechosen(self):
        from pipeline.tests import test_league as TL
        d_g = TL._tiny_gen(1).value_head.in_features
        for side in (0, 1):
            tj = self._run(E, side, posture={"head": _head(d_g, scale=3.0), "every": 300, "dtau": DTAU,
                                             "mode": "sample"}, record_ctx=True)["traj"]
            tick, new, z = tj["tick"], tj["posture_new"], tj["posture"]
            last, want = None, []
            for t in tick.tolist():
                want.append(last is None or t - last >= 300)
                last = t if want[-1] else last
            self.assertEqual(new.tolist(), want, side)
            self.assertGreater(int(new.sum()), 2)
            for a, b in zip(np.flatnonzero(new), list(np.flatnonzero(new)[1:]) + [len(z)]):
                self.assertEqual(len(set(z[a:b].tolist())), 1)
            np.testing.assert_array_equal(tj["posture_dtau"], np.asarray(DTAU)[z])
            self.assertEqual(tj["ctx"].shape, (len(tick), 5))

    def test_absent_is_pre(self):
        P = _pre("pipeline/e1_eval.py", "pipeline.e1_eval_pre_c1")
        for side in (0, 1):
            a, b = self._run(P, side, record_ctx=True), self._run(E, side, record_ctx=True)
            for r in (a, b):
                r.pop("wall_s")
            ta, tb = a.pop("traj"), b.pop("traj")
            self.assertEqual(a, b)
            self.assertEqual(sorted(ta), sorted(tb))
            for k in ta:
                self.assertEqual(ta[k].tobytes(), tb[k].tobytes(), k)
            self.assertFalse(any(k.startswith("posture") for k in tb))


# ------------------------------------------------------------------------------------------------------
class TestLearner(_Tmp):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.head = _head(cls.model.value_head.in_features)
        cls.results = _posture_results(cls.model, cls.head)

    def _L(self, tmp, **extra):
        L = _learner(RL, self.model, self.results, tmp, **GAE, **POST, **extra)
        L.posture_head = copy.deepcopy(self.head)
        L.posture_opt = torch.optim.Adam(L.posture_head.parameters(), lr=1e-3)
        return L

    def _B(self):
        Bn, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        return Bn, RL.to_device(Bn, "cpu")

    def test_collate(self):
        Bn, B = self._B()
        for k in ("posture", "posture_dtau", "posture_lp", "posture_new", "w_post", "ctx"):
            self.assertIn(k, Bn)
        n_keep = 0
        for j, r in enumerate(self.results):
            t = r["traj"]
            keep = t["gate_sampled"] | t["played"] | t["posture_new"]
            n_keep += int(keep.sum())
            np.testing.assert_array_equal(Bn["posture"][Bn["match"] == j], t["posture"][keep])
            self.assertAlmostEqual(float(Bn["w_post"][Bn["match"] == j].sum()), 1 / len(self.results), places=12)
        self.assertEqual(len(Bn["A"]), n_keep)
        extra = Bn["posture_new"] & ~(Bn["gate_sampled"] | Bn["played"])
        self.assertTrue(extra.any())                            # a choice row with no card allowed is kept
        self.assertTrue((Bn["w_post"][~Bn["posture_new"]] == 0).all())

    def test_gate_logprob_uses_tau_plus_dtau(self):
        _, B = self._B()
        idx = torch.arange(len(B["A"]))
        with torch.no_grad():
            t = RL.policy_terms(self.model, B, idx, TAU, T)
            self.assertLess(float((t["lp_gate"] - B["lp_gate"]).abs().max()), 1e-5)
            B0 = {k: v for k, v in B.items() if k != "posture_dtau"}
            t0 = RL.policy_terms(self.model, B0, idx, TAU, T)
        self.assertGreater(float((t0["lp_gate"] - B["lp_gate"]).abs().max()), 1e-3)

    def test_posture_term_reaches_head_only(self):
        _, B = self._B()
        RL.gae_batch(self.model, B, {"advantage": "gae"})
        R = RL.ref_terms(copy.deepcopy(self.model).eval(), B, TAU, T)
        N = len(B["A"])
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
        model, head = copy.deepcopy(self.model), copy.deepcopy(self.head)
        grads = {}
        for name, post in (("off", None), ("on", {"head": head, "ent_coef": 0.01})):
            model.zero_grad(set_to_none=True)
            head.zero_grad(set_to_none=True)
            loss, st = RL.minibatch_loss(model, B, R, torch.arange(N), **kw, **({"posture": post} if post else {}))
            loss.backward()
            grads[name] = {n: None if p.grad is None else p.grad.clone() for n, p in model.named_parameters()}
        for n, g in grads["off"].items():
            o = grads["on"][n]
            self.assertTrue((g is None and o is None) or torch.equal(g, o), n)
        self.assertTrue(all(p.grad is not None and p.grad.abs().sum() > 0 for p in head.parameters()))
        self.assertLess(st["post_ratio_maxdev"], 1e-5)                          # on-policy: r = 1
        self.assertEqual(st["post_n"], int(B["posture_new"].sum()))

    def test_one_update_end_to_end(self):
        L = self._L(self.tmp)
        h0 = {n: p.detach().clone() for n, p in L.posture_head.named_parameters()}
        recs = []
        for u in range(3):                                     # warm-up (posture not trained), then two policy updates
            rec, reasons, crash = L.one_update(u)
            self.assertFalse(crash, reasons)
            recs.append(rec)
            ps = rec["posture"]
            self.assertEqual(ps["share"]["n"], rec["rows"])
            self.assertAlmostEqual(sum(ps["share"][p] for p in RL.POSTURES), 1.0)
            self.assertEqual(ps["share_by_tank"]["tank"]["n"] + ps["share_by_tank"]["no_tank"]["n"], rec["rows"])
            self.assertEqual(sum(v["n"] for v in ps["share_by_phase"].values()), rec["rows"])
            self.assertTrue(np.isfinite(ps["entropy"]) and ps["entropy"] > 0)
            if u == 0:
                self.assertFalse(ps["trained"])
                self.assertEqual(ps["kl_prev"], 0.0)                         # warm-up: the head did not move
                self.assertTrue(all(torch.equal(p, h0[n]) for n, p in L.posture_head.named_parameters()))
                self.assertLess(ps["first_ratio_maxdev"], RL.ASSERT_RATIO)
            else:
                self.assertTrue(ps["trained"])
                self.assertGreater(ps["kl_prev"], 0.0)
                self.assertTrue(np.isfinite(ps["l_post"]))
        self.assertTrue(all(not torch.equal(p, h0[n]) for n, p in L.posture_head.named_parameters()))
        self.assertFalse(any("posture" in k for k in L.model.state_dict()))

    def test_checkpoint_resume(self):
        # one intra-op thread: on THIS data two fresh identical learners already differ at update 2 by ~1e-8 with the
        # default thread count, with or without the posture term (measured 10-15; 1 thread: identical) -- multi-thread
        # CPU float nondeterminism, not state the restore could carry
        n_thr = torch.get_num_threads()
        torch.set_num_threads(1)
        self.addCleanup(torch.set_num_threads, n_thr)
        L = self._L(self.tmp / "a")
        for u in range(2):
            L.one_update(u)
        ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        for k in ("posture_head", "posture_optimizer", "posture"):
            self.assertIn(k, ck["rl"])
        self.assertEqual(ck["rl"]["posture"], {"every": 60, "dtau": DTAU, "d_g": 16, "hidden": 64})
        self.assertFalse(any("posture" in k for k in ck["model"]))
        got = RL.load_posture_head(L.ck_dir / "unit_latest.pt")                 # what search_s0 loads
        self.assertEqual((got["every"], got["dtau"], got["mode"]), (60, DTAU, "argmax"))
        for a, b in zip(L.posture_head.state_dict().values(), got["head"].state_dict().values()):
            self.assertTrue(torch.equal(a, b))
        L2 = self._L(self.tmp / "b")
        with torch.no_grad():
            for p in L2.posture_head.parameters():
                p.add_(1.0)                                    # a different start: the restore must overwrite it
        L2.ref = copy.deepcopy(L.ref)
        L2._restore(L.ck_dir / "unit_latest.pt")
        for (n, a), b in zip(L.posture_head.state_dict().items(), L2.posture_head.state_dict().values()):
            self.assertTrue(torch.equal(a, b), n)
        ra, _, _ = L.one_update(2)
        rb, _, _ = L2.one_update(2)
        self.assertEqual(_strip(ra), _strip(rb))
        L3 = _learner(RL, self.model, _monitor_fields(_results(self.model, SPEC, seed=13)), self.tmp / "c", **GAE)
        L3.one_update(0)
        L4 = self._L(self.tmp / "d")
        z = {n: p.detach().clone() for n, p in L4.posture_head.named_parameters()}
        L4._restore(L3.ck_dir / "unit_latest.pt")             # a checkpoint without the head: it keeps its start
        self.assertTrue(all(torch.equal(p, z[n]) for n, p in L4.posture_head.named_parameters()))
        self.assertTrue(any("no posture_head" in m for m in L4.log.lines))
        self.assertIsNone(RL.load_posture_head(L3.ck_dir / "unit_latest.pt"))

    def test_actor_base_and_message(self):
        L = self._L(self.tmp)
        self.assertEqual(L._posture_meta(), {"every": 60, "dtau": DTAU, "d_g": 16, "hidden": 64})
        _, psd = RL.split_actor_sd(L._actor_bytes(), "cpu")
        self.assertEqual(sorted(psd), sorted(L.posture_head.state_dict()))
        self.assertEqual(RL.split_actor_sd(L._actor_bytes(L.ref), "cpu")[1], {})   # the ref's screen: no posture


# ------------------------------------------------------------------------------------------------------
class TestAbsentIsPre(_Tmp):
    """posture_head absent / null / false: collate, whole updates (gae and match_loo: records, weights, beta, rng) and
    the checkpoint's rl keys are those of HEAD at dispatch."""

    @classmethod
    def setUpClass(cls):
        cls.P = _pre("pipeline/rl_royale.py", "rl_royale_pre_c1")
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        for adv in (GAE, {"seed": 0}):
            runs = {}
            for name, mod, extra in (("pre", self.P, {}), ("absent", RL, {}), ("null", RL, {"posture_head": None}),
                                     ("false", RL, {"posture_head": False})):
                L = _learner(mod, self.model, self.results, self.tmp / f"{name}{len(adv)}", **adv, **extra)
                recs = [_strip(L.one_update(u)[0]) for u in range(3)]
                ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
                runs[name] = (recs, L.beta, {k: v.clone() for k, v in L.model.state_dict().items()},
                              L.rng.bit_generator.state, sorted(ck["rl"]), ck["rl"]["config_sha256"])
            recs_p, beta_p, sd_p, rng_p, keys_p, sha_p = runs["pre"]
            for name in ("absent", "null", "false"):
                recs, beta, sd, rng, keys, sha = runs[name]
                self.assertEqual(recs, recs_p, name)
                self.assertEqual((beta, rng, keys, sha), (beta_p, rng_p, keys_p, sha_p), name)
                for k in sd_p:
                    self.assertTrue(torch.equal(sd[k], sd_p[k]), (name, k))

    def test_collate_identical(self):
        for adv in ("match_loo", "gae"):
            Bp, sp = self.P.collate(copy.deepcopy(self.results), 2.0, advantage=adv)
            Bn, sn = RL.collate(copy.deepcopy(self.results), 2.0, advantage=adv)
            self.assertEqual(sorted(Bn), sorted(Bp))
            for k in Bp:
                self.assertEqual(Bn[k].tobytes(), Bp[k].tobytes(), k)
            self.assertEqual(sn, sp)


# ------------------------------------------------------------------------------------------------------
class TestGraft(_Tmp):
    def test_graft_carries_the_head(self):
        """graft_generic.py (run_rlarm2.sh's D3 checkpoint) replaces only ``model`` entries: rl (posture head + meta)
        survives, and search_s0's loader reads the same head from the grafted file."""
        h = _head(16)
        arm = {"model": {"gate_head.weight": torch.ones(2)}, "card_vocab": ["<pad>", "log"],
               "rl": {"posture_head": h.state_dict(), "posture": {"every": 200, "dtau": DTAU, "d_g": 16, "hidden": 64}}}
        live = {"model": {"cell_refine.w": torch.zeros(3), "other.w": torch.zeros(1)}, "card_vocab": ["<pad>", "log"]}
        pa, pl, po = self.tmp / "arm.pt", self.tmp / "live.pt", self.tmp / "out.pt"
        torch.save(arm, pa)
        torch.save(live, pl)
        r = subprocess.run([sys.executable, str(REPO / "scratchpad/gauntlet/L74/weekend/graft_generic.py"), str(pa),
                            str(pl), str(po)], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = torch.load(po, map_location="cpu")
        self.assertEqual(sorted(out["model"]), ["cell_refine.w", "gate_head.weight"])
        got = RL.load_posture_head(po)
        self.assertEqual(got["every"], 200)
        for a, b in zip(h.state_dict().values(), got["head"].state_dict().values()):
            self.assertTrue(torch.equal(a, b))


# ------------------------------------------------------------------------------------------------------
try:
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline import search_s0 as S
except ImportError:                                      # no royalegym in this venv
    RoyaleSelfPlayEnv = None


@unittest.skipIf(RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestSearchS0(unittest.TestCase):
    def _play(self, tau=None, posture_z=None, tail_cap=1200, dtau=DTAU, **lcfg_extra):
        from pipeline.tests.test_search_s0 import HOGEQ, runner
        run = runner(tail_cap=tail_cap)
        if tau is not None:
            run.lcfg = S.live_cfg(tau, "lattice")
        run.lcfg = {**run.lcfg, **lcfg_extra}
        if posture_z is not None:
            d_g = run.learner.model.value_head.in_features
            run.lcfg["posture"] = {"head": _forced(d_g, posture_z), "every": 200, "dtau": dtau, "mode": "argmax"}
        rec = run.play("plain", run.setup("gen", 3, HOGEQ))
        res = dict(run.last_result)
        for r in (rec, res):
            r.pop("wall_s")
        for k in ("tau", "frac_gt_tau"):                     # the cfg tau itself (0.35 vs the shifted reference's)
            res.pop(k)
        return rec, res

    def _dtau(self, tail_cap=1200):
        """A pressure offset that moves the threshold onto this tiny model's mean gate p (else DTAU's +-0.10 can miss
        every p it produces and the equivalence would be vacuous)."""
        m = self._play(tail_cap=tail_cap)[1]["p_gate_mean"]
        return [0.10, 0.0, round(m - S.TAU_PLAIN, 3)]

    def test_argmax_posture_is_the_shifted_threshold(self):
        """posture z at tau .35 plays exactly the plain rule at tau .35 + dtau[z] (z = pressure with the offset on the
        model's mean p, and balanced), and the pressure posture's plays differ from the plain .35 rule's."""
        dt = self._dtau()
        for z in (2, 1):
            rec, res = self._play(posture_z=z, dtau=dt)
            ref_rec, ref_res = self._play(tau=S.TAU_PLAIN + dt[z])
            self.assertEqual(res, ref_res, z)
            self.assertEqual({k: v for k, v in rec.items() if not k.startswith("posture")}, ref_rec, z)
            self.assertEqual(rec["posture_shares"][RL.POSTURES[z]], 1.0)
            self.assertEqual(rec["posture_decisions"], rec["decisions"])
            self.assertGreater(rec["posture_choices"], 1)                     # re-chosen every 200 ticks (same z)
        self.assertNotEqual(self._play(posture_z=2, dtau=dt)[1]["plays"], self._play()[1]["plays"])   # non-vacuous

    def test_decision_options_tau_phase(self):
        """With decision options (tau_phase) the offset rides decide_batch's tau_delta: pressure on [.35 .45 .55] =
        the rule on [.35 .45 .55] + dtau, across the 1x / 2x edge; and it changes play."""
        dt = self._dtau(2600)
        base = (0.35, 0.45, 0.55)
        rec, res = self._play(posture_z=2, dtau=dt, tail_cap=2600, tau_phase=base)
        ref_rec, ref_res = self._play(tail_cap=2600, tau_phase=tuple(t + dt[2] for t in base))
        self.assertEqual(res, ref_res)
        self.assertEqual({k: v for k, v in rec.items() if not k.startswith("posture")}, ref_rec)
        self.assertNotEqual(res["plays"], self._play(tail_cap=2600, tau_phase=base)[1]["plays"])

    def test_absent_head_no_fields(self):
        rec, _ = self._play()
        self.assertFalse(any(k.startswith("posture") for k in rec))

    def test_init_worker_loads_the_head(self):
        from pipeline.tests.test_search_s0 import tiny_models
        gen = tiny_models()[0]
        sentinel = {"head": "h", "every": 200, "dtau": DTAU, "mode": "argmax"}
        o_load, o_ph = E.load_policy, RL.load_posture_head
        args = {"gen": str(Path(__file__).resolve()), "opps": [], "threads": 1, "tail_cap": 600, "horizon": 12.0, "interval": 1, "topk": 4,
                "cells": 3, "device": "cpu", "search_min_p": 0.0}
        try:
            E.load_policy = lambda path, dev: (gen, {"grid": "lattice"})
            for ret in (None, sentinel):
                RL.load_posture_head = lambda path, dev, ret=ret: ret
                S._init_worker(args)
                lc = S._W["runner"].lcfg
                self.assertIs(lc.get("posture"), ret) if ret else self.assertNotIn("posture", lc)
        finally:
            E.load_policy, RL.load_posture_head = o_load, o_ph

    def test_run_json_unchanged(self):
        import tempfile
        P = _pre("pipeline/search_s0.py", "pipeline.search_s0_pre_c1")
        out = {}
        for name, mod in (("pre", P), ("now", S)):
            d = Path(tempfile.mkdtemp(prefix="s0_c1_")) / "o"
            o_init, o_job = mod._init_worker, mod._run_job
            mod._init_worker = lambda args: None
            mod._run_job = lambda job: {"arm": job[0], "opp": job[1], "seed": job[2], "skipped": "stub"}
            try:
                mod.main(["--out", str(d), "--seeds", "0:1", "--opps", "gen", "--arms", "plain"])
            finally:
                mod._init_worker, mod._run_job = o_init, o_job
            run = json.loads((d / "run.json").read_text())
            run.pop("started")
            run.pop("out")
            out[name] = run
        self.assertEqual(out["pre"], out["now"])


if __name__ == "__main__":
    unittest.main()
