"""B6 stage A: the LEARNED hero-ability press (rl_royale ``ability_head``; e1_eval ``ability_decide``; royale_env
``ability_options`` / ``learned_sides`` / ``ability_outcomes``).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_ability_head.py

Covers: config / hash / validation; head init and detach; the actor message; the imitation fit; the sampler's
Bernoulli (log-prob, commands, greedy, label); collate / the press PPO term reaches the head only / one_update / the
update-0 ratio on REAL recorded rows (= 1) / checkpoint save -> resume; absent = HEAD at dispatch (rl_royale updates +
collate, e1_eval + royale_env on a real hero match); on the real engine: label mode = the rule's match, the rule never
presses for a learned side, a learned press goes through queue -> recheck -> eng.act, opponents keep the rule, the
outcome tally does not change the match; search_s0 applies the head greedily and loads it from a checkpoint.
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
from pipeline.tests.test_rl_gae import SPEC, TAU, T, _learner, _strip, _Tmp   # noqa: E402
from pipeline.tests.test_rl_royale import _monitor_fields, _results, _tiny_model  # noqa: E402

PRE = "2e8bb67"             # HEAD at dispatch: the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
GAE = dict(advantage="gae", critic_warmup_updates=1, seed=0)
AB = dict(ability_head=True, ability_ent_coef=0.01, ability_lr=1e-3, ability_bc_matches=0, ability_bc_steps=10,
          ability_bc_lr=1e-3)
NF = E.ABILITY_FEAT_N


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
    sys.modules[name] = mod
    exec(compile(src.stdout, name, "exec"), mod.__dict__)
    return mod


def _head(d_g, seed=3, scale=0.5):
    """An AbilityHead whose last layer is perturbed (so p depends on the input), deterministic."""
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        h = RL.AbilityHead(d_g)
        with torch.no_grad():
            h.net[2].weight.normal_(0.0, scale)
    return h.eval()


def _forced(d_g, press: bool):
    """A head that always (logit +100) or never (-100) presses."""
    h = RL.AbilityHead(d_g)
    with torch.no_grad():
        h.net[2].bias.fill_(100.0 if press else -100.0)
    return h.eval()


class _FM:
    """What ability_decide / sample_decide_batch read of a match."""

    def __init__(self, seed, side=0):
        self.rng_behave, self.tag, self.side, self.n_dec = np.random.default_rng(seed), f"fm{seed}", side, 0
        self.cfg, self._ability_commands, self._ability_opts = {"rollout_index": 0, "update": 0}, {side: []}, None


def _opts(rng, n):
    return [{"cmd": (b, 7 + b, 100 + b), "card": "Valkyrie", "feat": rng.normal(size=NF).astype(np.float32).tolist()}
            for b in range(n)]


def _synth(model, head, rng, n, seed, mode="sample"):
    """test_rl_royale._synth_match with press decisions: one decision per row of ONE fake match through the real
    sampler; ~60% of the rows have 1-2 pressable options. -> (Match._traj_arrays, the queued commands per row)."""
    from pipeline.dataset import PAST_K
    from pipeline.obs_contract import F as TOK_F, S as SC_S
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
    fm = _FM(seed)
    cfg = {"tau": TAU, "T": T, "ability": {"mode": mode, "head": head}}
    rows, cmds = [], []
    for r in range(n):
        fm._ability_commands = {0: []}
        fm._ability_opts = _opts(rng, int(rng.integers(1, 3))) if rng.random() < 0.6 else []
        fm.n_dec = r
        sl = (lambda d: {k: v[r:r + 1] for k, v in d.items()})
        d = E.sample_decide_batch(model, sl(enc), sl(heads), p[r:r + 1], allowed[r:r + 1], stalled[r:r + 1], [fm], cfg)[0]
        cmds.append(list(fm._ability_commands[0]))
        rows.append({"tok": toks[r], "mask": masks[r], "sc": scs[r], "past": pasts[r],
                     "allowed": d["allowed"], "stalled": d["stalled"], "gate_sampled": d["gate_sampled"],
                     "played": d["play"], "slot": d["slot"], "cell": d["cell"], "lp_gate": d["lp_gate"],
                     "lp_card": d["lp_card"], "lp_cell": d["lp_cell"], "p_gate": d["p_gate"], "T": d["T"],
                     **{k: d[k] for k in E.ability_defaults()}})
    return E.Match._traj_arrays(SimpleNamespace(traj=rows)), cmds


def _ab_results(model, head, seed=13):
    rng = np.random.default_rng(seed)
    res = [{"entry_index": i, "k": g, "outcome": o, "side": 0, "traj": _synth(model, head, rng, n, 100 * i + g)[0]}
           for i, g, n, o in SPEC]
    return _monitor_fields(res)


# ------------------------------------------------------------------------------------------------------
class TestConfig(unittest.TestCase):
    def test_hash(self):
        cfg = RL.load_config(YAML, [], False)
        self.assertFalse(any(k in cfg for k in RL.ABILITY_KEYS))
        P = _pre("pipeline/rl_royale.py", "rl_royale_pre_b6")
        self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg))                     # the historical hash
        for off in (None, False):
            self.assertEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, ability_head=off)))
        on = RL.config_sha(dict(cfg, ability_head=True))
        self.assertNotEqual(on, RL.config_sha(cfg))
        self.assertEqual(on, RL.config_sha(dict(cfg, ability_head="on")))
        self.assertEqual(on, RL.config_sha(dict(cfg, ability_head=True, **{k: v for k, v in RL.ABILITY_DEFAULTS.items()})))
        self.assertNotEqual(on, RL.config_sha(dict(cfg, ability_head=True, ability_ent_coef=0.05)))

    def test_load_config_override(self):
        cfg = RL.load_config(YAML, ["advantage=gae", "ability_head=on", "ability_bc_matches=16"], False)
        self.assertIs(cfg["ability_head"], True)                                  # YAML 1.1: on = true
        self.assertEqual(RL.ability_cfg(cfg), {"ent_coef": 0.01, "lr": 3e-4, "bc_matches": 16, "bc_steps": 300,
                                               "bc_lr": 1e-3})

    def test_validation(self):
        ok = {"advantage": "gae", "ability_head": True}
        self.assertIsNone(RL.ability_cfg({}))
        self.assertIsNone(RL.ability_cfg({"ability_head": False}))
        cfg = dict(ok)
        RL.store_ability_cfg(cfg)                                # every default key stored (the posture_lr lesson)
        self.assertEqual({k: cfg[k] for k in RL.ABILITY_DEFAULTS}, RL.ABILITY_DEFAULTS)
        off = {"advantage": "gae"}
        self.assertIsNone(RL.store_ability_cfg(off))
        self.assertEqual(off, {"advantage": "gae"})
        for bad in ({"ability_lr": 1e-3}, {"ability_head": None, "ability_ent_coef": 0.1},     # keys without the head
                    {**ok, "advantage": "match_loo"}, {"ability_head": True},                  # needs gae (refuse loo)
                    {**ok, "ability_head": "yes"}, {**ok, "ability_ent_coef": -0.1}, {**ok, "ability_lr": 0.0},
                    {**ok, "ability_bc_matches": -1}, {**ok, "ability_bc_steps": 2.5}, {**ok, "ability_bc_lr": "x"},
                    {**ok, "branch_gate": True}):
            with self.assertRaises(SystemExit, msg=bad) as cm:
                RL.ability_cfg(bad)
            self.assertIn("ability", str(cm.exception))

    def test_actor_cfg(self):
        base = {**RL.load_config(YAML, [], False), "grid": "lattice"}
        for k in ("rollout", "screen"):
            self.assertNotIn("ability", RL.actor_cfg(base, k, 0, "cpu"))
        ab = {"d_g": 16, "hidden": 64, "n_feat": NF}
        r, s = (RL.actor_cfg({**base, "ability": ab}, k, 0, "cpu") for k in ("rollout", "screen"))
        self.assertEqual((r["ability"], s["ability"]), ({"mode": "sample"}, {"mode": "greedy"}))


# ------------------------------------------------------------------------------------------------------
class TestHead(unittest.TestCase):
    def test_init_p0_and_detach(self):
        h = RL.AbilityHead(16)
        p = torch.sigmoid(h(torch.randn(30, 16), torch.randn(30, NF)).double())
        self.assertTrue(torch.allclose(p, torch.full((30,), RL.ABILITY_P0, dtype=torch.float64), atol=1e-6))
        self.assertEqual(h.net[0].in_features, 16 + NF)
        g = torch.randn(4, 16, requires_grad=True)
        _head(16)(g, torch.randn(4, NF)).sum().backward()
        self.assertIsNone(g.grad)                                # no ability gradient reaches the trunk
        self.assertFalse(any(k.startswith("ability") for k in _tiny_model(0).state_dict()))

    def test_actor_message(self):
        m, h, ph = _tiny_model(1), _head(16), RL.PostureHead(16)
        self.assertEqual(RL.actor_bytes(m), RL.state_bytes(m))                 # no head: the old message exactly
        for posture in (None, ph):
            msd, psd = RL.split_actor_sd(RL.actor_bytes(m, posture, h), "cpu")
            asd = RL.pop_prefix(msd, RL.ABILITY_SD)
            self.assertEqual(sorted(msd), sorted(m.state_dict()))
            self.assertEqual(bool(psd), posture is not None)
            h2 = RL.AbilityHead(16)
            h2.load_state_dict(asd)
            self.assertTrue(all(torch.equal(a, b) for a, b in zip(h.state_dict().values(), h2.state_dict().values())))
        msd, _ = RL.split_actor_sd(RL.actor_bytes(m, ph), "cpu")
        self.assertEqual(RL.pop_prefix(msd, RL.ABILITY_SD), {})

    def test_bc_fit(self):
        """The warm start: bias -> logit(mean q), then soft BCE down toward its floor; p tracks q."""
        g, f = torch.randn(400, 16), torch.randn(400, NF)
        q = torch.sigmoid(2.0 * f[:, 0] - 1.0)                   # a press probability that depends on one feature
        h = RL.AbilityHead(16)
        st = RL.ability_bc_fit(h, g, f, q, 300, 1e-2)
        self.assertAlmostEqual(st["p_mean_before"], st["q_mean"], places=4)
        self.assertLess(st["bce_after"], st["bce_before"] - 0.05)
        self.assertLess(st["bce_after"] - st["bce_floor"], 0.02)
        with torch.no_grad():
            p = torch.sigmoid(h(g, f))
        self.assertGreater(float(np.corrcoef(p.numpy(), q.numpy())[0, 1]), 0.95)


# ------------------------------------------------------------------------------------------------------
class TestSampler(unittest.TestCase):
    def test_logprob_commands_and_defaults(self):
        model, head = _tiny_model(2), _head(16, scale=2.0)
        tj, cmds = _synth(model, head, np.random.default_rng(0), 60, seed=1)
        s = tj["ab_sampled"]
        self.assertGreater(int(s.sum()), 15)
        self.assertGreater(int(tj["ab_press"][s].sum()), 0)
        self.assertGreater(int((~tj["ab_press"][s]).sum()), 0)
        for r in np.flatnonzero(s):
            self.assertLess(tj["ab_lp"][r], 0.0)
            self.assertEqual(bool(tj["ab_press"][r]), len(cmds[r]) == 1)       # a press queues exactly one command
        self.assertTrue((tj["ab_lp"][~s] == 0).all() and (tj["ab_feat"][~s] == 0).all())
        self.assertFalse(tj["ab_press"][~s].any() or any(cmds[r] for r in np.flatnonzero(~s)))

    def test_gate_card_cell_draws_untouched(self):
        """The press draws come from the match's own rng_ability: the gate / card / cell records equal a run without
        the key (same rows, same rng_behave stream)."""
        model = _tiny_model(2)
        a, _ = _synth(model, _head(16, scale=2.0), np.random.default_rng(4), 40, seed=2)
        b, _ = _synth(model, _forced(16, False), np.random.default_rng(4), 40, seed=2)
        for k in ("gate_sampled", "played", "slot", "cell", "lp_gate", "lp_card", "lp_cell"):
            np.testing.assert_array_equal(a[k], b[k], k)

    def test_greedy_and_label(self):
        fm = _FM(0)
        rng = np.random.default_rng(0)
        enc = {"g": torch.zeros(1, 16)}
        for press in (True, False):
            fm._ability_commands, fm._ability_opts = {0: []}, _opts(rng, 2)
            out = E.ability_decide([fm], enc, {"ability": {"mode": "greedy", "head": _forced(16, press)}})
            self.assertEqual((out[0]["ab_sampled"], out[0]["ab_press"]), (True, press))
            self.assertEqual(fm._ability_commands[0], [(0, 7, 100)] if press else [])   # option n_dec % 2 = 0
            self.assertIsNone(fm._ability_opts)                                          # consumed
        fm.n_dec, fm._ability_commands = 1, {0: ["rule"]}
        fm._ability_opts = [dict(o, q=0.25 * i) for i, o in enumerate(_opts(rng, 2))]
        out = E.ability_decide([fm], enc, {"ability": {"mode": "label"}})
        self.assertEqual((out[0]["ab_cand"], out[0]["ab_q"], out[0]["ab_sampled"]), (True, 0.25, False))
        self.assertEqual(fm._ability_commands[0], ["rule"])                              # label: the rule's untouched
        self.assertIsNone(E.ability_decide([fm], enc, {}))


# ------------------------------------------------------------------------------------------------------
class TestLearner(_Tmp):
    @classmethod
    def setUpClass(cls):
        cls.model = _tiny_model(6)
        cls.head = _head(cls.model.value_head.in_features, scale=1.0)
        cls.results = _ab_results(cls.model, cls.head)

    def _L(self, tmp, **extra):
        L = _learner(RL, self.model, self.results, tmp, **GAE, **AB, **extra)
        L.ability_head = copy.deepcopy(self.head)
        L.ability_opt = torch.optim.Adam(L.ability_head.parameters(), lr=1e-3)
        L.ability_bc = None
        return L

    def _B(self):
        Bn, _ = RL.collate(copy.deepcopy(self.results), 2.0, advantage="gae")
        return Bn, RL.to_device(Bn, "cpu")

    def test_collate(self):
        Bn, _ = self._B()
        for k in ("ab_sampled", "ab_press", "ab_lp", "ab_feat", "w_ab"):
            self.assertIn(k, Bn)
        for j, r in enumerate(self.results):
            t = r["traj"]
            keep = t["gate_sampled"] | t["played"] | t["ab_sampled"]
            np.testing.assert_array_equal(Bn["ab_press"][Bn["match"] == j], t["ab_press"][keep])
            self.assertAlmostEqual(float(Bn["w_ab"][Bn["match"] == j].sum()), 1 / len(self.results), places=12)
        self.assertTrue((Bn["w_ab"][~Bn["ab_sampled"]] == 0).all())

    def test_term_reaches_head_only_and_ratio_one(self):
        _, B = self._B()
        RL.gae_batch(self.model, B, {"advantage": "gae"})
        R = RL.ref_terms(copy.deepcopy(self.model).eval(), B, TAU, T)
        N = len(B["A"])
        kw = dict(tau=TAU, T=T, clip=0.2, beta=0.3, n_total=N)
        model, head = copy.deepcopy(self.model), copy.deepcopy(self.head)
        grads = {}
        for name, ab in (("off", None), ("on", {"head": head, "ent_coef": 0.01})):
            model.zero_grad(set_to_none=True)
            head.zero_grad(set_to_none=True)
            loss, st = RL.minibatch_loss(model, B, R, torch.arange(N), **kw, **({"ability": ab} if ab else {}))
            loss.backward()
            grads[name] = {n: None if p.grad is None else p.grad.clone() for n, p in model.named_parameters()}
        for n, g in grads["off"].items():
            o = grads["on"][n]
            self.assertTrue((g is None and o is None) or torch.equal(g, o), n)
        self.assertTrue(all(p.grad is not None and p.grad.abs().sum() > 0 for p in head.parameters()))
        self.assertLess(st["ab_ratio_maxdev"], 1e-5)                            # on-policy: r = 1
        self.assertEqual(st["ab_n"], int(B["ab_sampled"].sum()))

    def test_one_update_end_to_end(self):
        L = self._L(self.tmp)
        h0 = {n: p.detach().clone() for n, p in L.ability_head.named_parameters()}
        for u in range(3):                                     # warm-up (head not trained), then two policy updates
            rec, reasons, crash = L.one_update(u)
            self.assertFalse(crash, reasons)
            a = rec["ability"]
            self.assertEqual(a["decisions"], int(sum(r["traj"]["ab_sampled"].sum() for r in self.results)))
            self.assertTrue(0 < a["press_rate"] < 1 and 0 < a["p_mean"] < 1)
            if u == 0:
                self.assertFalse(a["trained"])
                self.assertTrue(all(torch.equal(p, h0[n]) for n, p in L.ability_head.named_parameters()))
                self.assertLess(a["first_ratio_maxdev"], RL.ASSERT_RATIO)
            else:
                self.assertTrue(a["trained"] and np.isfinite(a["l_ab"]))
        self.assertTrue(any(not torch.equal(p, h0[n]) for n, p in L.ability_head.named_parameters()))
        self.assertFalse(any("ability" in k for k in L.model.state_dict()))

    def test_checkpoint_resume(self):
        n_thr = torch.get_num_threads()                        # see test_posture_head: 1 thread = bitwise repeatable
        torch.set_num_threads(1)
        self.addCleanup(torch.set_num_threads, n_thr)
        L = self._L(self.tmp / "a")
        for u in range(2):
            L.one_update(u)
        ck = torch.load(L.ck_dir / "unit_latest.pt", map_location="cpu", weights_only=True)
        for k in ("ability_head", "ability_optimizer", "ability"):
            self.assertIn(k, ck["rl"])
        self.assertEqual(ck["rl"]["ability"], {"d_g": 16, "hidden": 64, "n_feat": NF, "bc": None})
        self.assertFalse(any("ability" in k for k in ck["model"]))
        got = RL.load_ability_head(L.ck_dir / "unit_latest.pt")                 # what search_s0 loads
        self.assertEqual(got["mode"], "greedy")
        for a, b in zip(L.ability_head.state_dict().values(), got["head"].state_dict().values()):
            self.assertTrue(torch.equal(a, b))
        L2 = self._L(self.tmp / "b")
        with torch.no_grad():
            for p in L2.ability_head.parameters():
                p.add_(1.0)                                    # a different start: the restore must overwrite it
        L2.ref = copy.deepcopy(L.ref)
        L2._restore(L.ck_dir / "unit_latest.pt")
        for (n, a), b in zip(L.ability_head.state_dict().items(), L2.ability_head.state_dict().values()):
            self.assertTrue(torch.equal(a, b), n)
        ra, _, _ = L.one_update(2)
        rb, _, _ = L2.one_update(2)
        self.assertEqual(_strip(ra), _strip(rb))
        L3 = _learner(RL, self.model, _monitor_fields(_results(self.model, SPEC, seed=13)), self.tmp / "c", **GAE)
        L3.one_update(0)
        L4 = self._L(self.tmp / "d")
        z = {n: p.detach().clone() for n, p in L4.ability_head.named_parameters()}
        L4._restore(L3.ck_dir / "unit_latest.pt")             # a checkpoint without the head: it keeps its start
        self.assertTrue(all(torch.equal(p, z[n]) for n, p in L4.ability_head.named_parameters()))
        self.assertTrue(any("no ability_head" in m for m in L4.log.lines))
        self.assertIsNone(RL.load_ability_head(L3.ck_dir / "unit_latest.pt"))

    def test_actor_base_and_message(self):
        L = self._L(self.tmp)
        _, _ = RL.split_actor_sd(L._actor_bytes(), "cpu")
        msd, _ = RL.split_actor_sd(L._actor_bytes(), "cpu")
        self.assertEqual(sorted(RL.pop_prefix(msd, RL.ABILITY_SD)), sorted(L.ability_head.state_dict()))
        msd, _ = RL.split_actor_sd(L._actor_bytes(L.ref), "cpu")
        self.assertEqual(RL.pop_prefix(msd, RL.ABILITY_SD), {})             # the ref's screen: the rule presses


# ------------------------------------------------------------------------------------------------------
class TestAbsentIsPre(_Tmp):
    """ability_head absent / null / false: collate, whole updates (gae and match_loo: records, weights, beta, rng) and
    the checkpoint's rl keys are those of HEAD at dispatch."""

    @classmethod
    def setUpClass(cls):
        cls.P = _pre("pipeline/rl_royale.py", "rl_royale_pre_b6u")
        cls.model = _tiny_model(6)
        cls.results = _monitor_fields(_results(cls.model, SPEC, seed=13))

    def test_updates_identical(self):
        self.P.CKPT_ROOT = self.tmp
        for adv in (GAE, {"seed": 0}):
            runs = {}
            for name, mod, extra in (("pre", self.P, {}), ("absent", RL, {}), ("null", RL, {"ability_head": None}),
                                     ("false", RL, {"ability_head": False})):
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
try:
    from pipeline import royale_env as RE
    from pipeline import search_s0 as S
    from pipeline.tests.test_royale_forms import ICEBOW, HOGEQ, tiny
    from royalegym.protocol import DeployCommand, DeployStatus, HAND_SIZE
except ImportError:                                      # no royalegym in this venv
    RE = None

if RE is not None:
    HERO = [n.replace("Knight@evolution", "Knight@hero") for n in ICEBOW]           # Hero Knight: v2 'knight-hero'
    VALK = ["Valkyrie@hero" if n == "Knight@evolution" else n for n in ICEBOW]       # the bait deck's hero


def _scfg(delay=0, **kw):
    return {"policy": "live", "tau": .27, "afford_mask": True, "stall_elixir": 9., "stall_seconds": 12., "obs": "clean",
            "noise": E.parse_noise_off("all"), "p_random": 0., "random_hand_only": False, "grid": "lattice",
            "device": "cpu", "decide_every": 10, "slot": 0, "port": 0, "entry_index": 0, "action_delay_ticks": delay,
            **kw}


def _env(policy="v2", **kw):
    """Hero buttons on. v2 = the training rule; "generic" (the range rule) presses Hero Knight in every scripted match
    (v2 measured: 0 Knight presses in 4 tiny-model self-play matches of 4,000 ticks, q mean 0.005 per decision), so the
    tests that need rule presses use it."""
    return RE.RoyaleSelfPlayEnv(forms_mode="deck", hero_abilities=True, ability_policy=policy, **kw)


def _drive(env, ldeck, odeck, delay=0, ability=None, seed=0, learner_side=0):
    """test_hero_abilities.drive with an optional learned press on the LEARNER side (scripted cards, left lane, 3
    elixir reserved on both sides). -> (result, per-step state hashes, ability_decide outputs, the match)."""
    spec = {"tag": "ab_acceptance", "learner_side": learner_side, "learner_deck": ldeck, "opp_deck": odeck,
            "seed": seed, "opp": {"id": "script"}}
    m = E.SelfPlayMatch(env, spec, 0, _scfg(delay, **({"ability": ability} if ability else {})), _scfg(delay))
    hashes, decided = [], []
    while True:
        due = m.due()
        if not due:
            break
        for s in due:
            s.prepare()
        for s in due:
            if s is m.learner:
                out = E.ability_decide([s], {"g": torch.zeros(1, 16)}, s.cfg)
                if out:
                    decided.append((int(env.tick), out[0]))
            player = env.core.state().players[s.side]
            hand = set(player.hand)
            choices = [(0 if env.names[cid] in ("Knight", "Valkyrie") else 1, s.costs[slot], slot)
                       for slot, ix in s.deck_index_of_slot.items()
                       if (cid := env.deck_ids[s.side][ix]) in hand and s.costs[slot] <= s._cur[1].my_elixir - 3]
            d = {"play": False, "slot": -1, "cell": -1, "why": "wait"}
            if choices:
                d = {"play": True, "slot": min(choices)[2], "cell": 44 * 36 + 7, "why": "script"}
            s.apply(.5, d)
        hashes.append(env.core.state_hash())
    return m.result(), hashes, decided, m


def _strip_res(r):
    return {k: v for k, v in r.items() if k not in ("wall_s", "ability_head")}


@unittest.skipIf(RE is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestRealEngine(unittest.TestCase):
    def test_feature_width_and_radius(self):
        self.assertEqual(RE.ABILITY_FEAT_N, E.ABILITY_FEAT_N)
        env = _env()
        env.reset(VALK, HERO, 0)
        self.assertEqual(env._hero_radius[env.ids["Valkyrie"]], 5500 * RE.SCALE)    # the spin's 5.5 tiles

    def test_label_mode_is_the_rule(self):
        """Label mode (no head: the rule presses) plays the rule's match exactly (v2: Hero Valkyrie, the bait hero;
        generic: Hero Knight); each decision with a pressable button records the rule's q, and every learner press
        the rule made was decided at a labelled decision with q > 0 (generic: q = 1)."""
        for policy, deck, card in (("v2", VALK, "Valkyrie"), ("generic", HERO, "Knight")):
            ref, h_ref, _, _ = _drive(_env(policy), deck, deck, delay=26)
            env, acted = _env(policy), []
            act = env.eng.act

            def spy(act=act, env=env, acted=acted, **kw):
                r = act(**kw)
                if kw.get("ability_button") is not None and kw["side"] == 0 and r["accepted"]:
                    acted.append(env.tick)
                return r
            env.eng.act = spy
            res, h, dec, m = _drive(env, deck, deck, delay=26, ability={"mode": "label"})
            self.assertEqual((_strip_res(res), h), (_strip_res(ref), h_ref), policy)
            lab = {t: o["ab_q"] for t, o in dec if o["ab_cand"]}
            self.assertGreater(len(lab), 3)
            self.assertTrue(all(0.0 <= q <= 1.0 for q in lab.values()))
            self.assertEqual(len(acted), res["ability_presses"][0].get(card, 0))
            self.assertTrue(acted, policy)
            for t in acted:
                self.assertGreater(lab[t - 26], 0.0)
                if policy == "generic":
                    self.assertEqual(lab[t - 26], 1.0)
            self.assertEqual(m.env.learned_sides, set())

    def test_rule_never_presses_for_a_learned_side(self):
        """Head on, never pressing: the learner (Hero Knight, side 0 and 1) presses NOTHING all match while the same
        scripted match with the rule presses; the opponent's Hero Knight keeps pressing by the rule."""
        for side in (0, 1):
            rule, _, _, _ = _drive(_env("generic"), HERO, HERO, delay=26, learner_side=side)
            res, _, dec, m = _drive(_env("generic"), HERO, HERO, delay=26, learner_side=side,
                                    ability={"mode": "greedy", "head": _forced(16, False)})
            self.assertGreater(rule["ability_presses"][side].get("Knight", 0), 0)
            self.assertEqual(res["ability_presses"][side], {})
            self.assertGreater(res["ability_presses"][1 - side].get("Knight", 0), 0)
            self.assertGreater(res["ability_head"]["decisions"], 3)
            self.assertEqual(res["ability_head"]["presses"], 0)
            self.assertEqual(m.env.learned_sides, {side})

    def test_learned_press_goes_through_the_engine_path(self):
        """Head on, always pressing (delay 0 and 26): every accepted learner press was decided by the head at a
        decision, queued for decision tick + delay, re-scanned ready (check_deploy OK, the button free, the decided
        hero body) and pressed through eng.act(ability_button) -- and the presses are the env's tally."""
        for delay in (0, 26):
            env = _env()
            queued, acted = [], []
            act, queue = env.eng.act, env.queue_abilities

            def audited_queue(s, commands, d, queue=queue):
                queued.extend((env.tick + d, s, *c) for c in commands)
                return queue(s, commands, d)

            def audited_act(act=act, **kw):
                if "ability_button" not in kw:
                    return act(**kw)
                s, b = kw["side"], kw["ability_button"]
                st = env.core.state()
                self.assertEqual(env.core.check_deploy(DeployCommand(s, HAND_SIZE + b, 0, 0)), DeployStatus.OK)
                q = [x for x in queued if x[0] == env.tick and x[1] == s and x[2] == b]
                self.assertTrue(q)
                self.assertTrue(any(e.uid == q[-1][4] and e.hp > 0 for e in st.entities))
                r = act(**kw)
                if s == 0:
                    acted.append((env.tick, b, r["accepted"]))
                return r
            env.eng.act, env.queue_abilities = audited_act, audited_queue
            res, _, dec, _ = _drive(env, HERO, HERO, delay=delay, ability={"mode": "greedy", "head": _forced(16, True)})
            pressed = [t for t, o in dec if o["ab_press"]]
            self.assertTrue(pressed)
            self.assertEqual(res["ability_head"]["presses"], len(pressed))
            ok = [a for a in acted if a[2]]
            self.assertTrue(ok)
            self.assertEqual(sum(res["ability_presses"][0].values()), len(ok))
            for t, b, _ in ok:                                   # each press landed delay ticks after a head press
                self.assertIn(t - delay, pressed)

    def test_opponents_unaffected(self):
        """Learner deck without a hero, opponent with Hero Knight: the head (any mode) never decides and the match --
        the opponent's rule presses included -- is the head-off match exactly."""
        ref, h_ref, _, _ = _drive(_env("generic"), ICEBOW, HERO, delay=26)
        self.assertGreater(ref["ability_presses"][1].get("Knight", 0), 0)
        for ab in ({"mode": "greedy", "head": _forced(16, True)}, {"mode": "label"}):
            res, h, dec, _ = _drive(_env("generic"), ICEBOW, HERO, delay=26, ability=ab)
            self.assertEqual((_strip_res(res), h), (_strip_res(ref), h_ref))
            self.assertFalse(any(o["ab_sampled"] or o["ab_cand"] for _, o in dec))

    def test_outcome_tally_does_not_change_the_match(self):
        ref, h_ref, _, _ = _drive(_env("generic"), HERO, HERO, delay=26)
        res, h, _, _ = _drive(_env("generic", ability_outcomes=True), HERO, HERO, delay=26)
        st = res.pop("ability_stats")
        self.assertGreater(st["presses"], 0)
        self.assertEqual((_strip_res(res), h), (_strip_res(ref), h_ref))
        self.assertEqual(st["presses"], ref["ability_presses"][0].get("Knight", 0))
        self.assertEqual(st["elixir"], 2.0 * st["presses"])                       # Hero Knight's ability: 2 elixir
        self.assertEqual(st["resolved"], st["presses"])
        self.assertTrue(0 <= st["killed_2s"] <= st["hit_2s"] <= st["in_radius"])

    def test_absent_is_pre_real_match(self):
        """e1_eval + royale_env without the key = HEAD at dispatch: two recorded self-play rollouts (tiny gen models,
        Hero Knight both sides, v2 presses, sample policy) give the same records, rows and RNG states."""
        import random
        from pipeline.tests.test_royale_forms import selfplay_rows
        Pe = _pre("pipeline/e1_eval.py", "pipeline.e1_eval_pre_b6")
        Pr = _pre("pipeline/royale_env.py", "pipeline.royale_env_pre_b6")

        from pipeline.tests.test_royale_forms import digest

        def run(emod, factory, deck):
            random.seed(1903)
            np.random.seed(1903)
            res, rows = selfplay_rows(emod, factory, [deck, deck])
            return res, rows, random.getstate()
        for policy, deck in (("v2", VALK), ("generic", HERO)):
            a = run(Pe, lambda: Pr.RoyaleSelfPlayEnv(forms_mode="deck", hero_abilities=True, ability_policy=policy,
                                                     tail_cap=2400), deck)
            b = run(E, lambda: RE.RoyaleSelfPlayEnv(forms_mode="deck", hero_abilities=True, ability_policy=policy,
                                                    tail_cap=2400), deck)
            self.assertEqual(digest(a[0]), digest(b[0]), policy)
            self.assertEqual(digest(a[1]), digest(b[1]), policy)
            self.assertEqual(a[2], b[2], policy)
            if policy == "generic":                                   # non-vacuous: presses happened
                self.assertTrue(any(sum(r["ability_presses"][s].values()) for r in b[0] for s in (0, 1)))

    def test_update0_ratio_on_real_rows(self):
        """A REAL recorded rollout with the head sampling (tiny gen model, Hero Knight learner, v2 rule opponent): the
        learner's recompute of every press log-prob from the stored rows equals the actor's (ratio 1), and collate
        keeps every decision row."""
        from pipeline.e1_view import Noise
        vocab, a, b = tiny([HERO, HERO])
        learner, snap = E.GenPolicy(a, vocab), E.GenPolicy(b, vocab)
        head = _head(a.value_head.in_features, scale=1.0)
        cfg = {"policy": "sample", "tau": 0.27, "afford_mask": True, "stall_elixir": None, "stall_seconds": 12.0,
               "obs": "live", "noise": Noise(**{n: False for n in E.NOISE_NAMES}), "p_random": 0.0,
               "random_hand_only": False, "grid": "lattice", "device": "cpu", "decide_every": 10, "slot": 0,
               "port": 0, "T": 0.5, "record": True, "opp_elixir": "counter", "action_delay_ticks": 26,
               "ability": {"mode": "sample", "head": head}}
        spec = {"tag": "sp_ab", "opp": {"id": "snap", "type": "snapshot"}, "learner_deck": HERO, "opp_deck": HERO,
                "learner_side": 0, "seed": 5}
        out = []
        ocfg = {k: v for k, v in cfg.items() if k != "ability"}
        E.run_selfplay_batch(lambda: _env(tail_cap=3000), learner, {"snap": (snap, {**ocfg, "record": False})},
                             [(0, spec, 0, {"rollout_index": 0, "update": 0}), (1, dict(spec, tag="sp_ab2", seed=6), 0,
                                                                                {"rollout_index": 0, "update": 0})],
                             cfg, 2, on_result=out.append)
        res = out
        n_dec = sum(int(r["traj"]["ab_sampled"].sum()) for r in res)
        self.assertGreater(n_dec, 3)
        self.assertGreater(sum(r["ability_head"]["presses"] for r in res if "ability_head" in r), 0)
        Bn, _ = RL.collate(copy.deepcopy(res), 2.0, advantage="gae")
        self.assertEqual(int(Bn["ab_sampled"].sum()), n_dec)
        B = RL.to_device(Bn, "cpu")
        RL.gae_batch(a, B, {"advantage": "gae"})
        R = RL.ref_terms(copy.deepcopy(a).eval(), B, 0.27, 0.5)
        _, st = RL.minibatch_loss(a, B, R, torch.arange(len(B["A"])), tau=0.27, T=0.5, clip=0.2, beta=0.3,
                                  n_total=len(B["A"]), ability={"head": head, "ent_coef": 0.01})
        self.assertLess(st["ab_ratio_maxdev"], RL.ASSERT_RATIO)
        self.assertLess(st["ratio_maxdev"], RL.ASSERT_RATIO)


    def test_warm_start_on_real_label_rows(self):
        """Learner._ability_warm_start end to end on REAL label-mode rollouts (tiny gen model, Hero Valkyrie both sides,
        v2 rule pressing, recorded): the actors' run is stubbed with them; every labelled decision is used, the head is
        fitted (BCE down), and the per-card count names Valkyrie."""
        from pipeline.e1_view import Noise
        vocab, a, b = tiny([VALK, VALK])
        learner, snap = E.GenPolicy(a, vocab), E.GenPolicy(b, vocab)
        cfg = {"policy": "sample", "tau": 0.27, "afford_mask": True, "stall_elixir": None, "stall_seconds": 12.0,
               "obs": "live", "noise": Noise(**{n: False for n in E.NOISE_NAMES}), "p_random": 0.0,
               "random_hand_only": False, "grid": "lattice", "device": "cpu", "decide_every": 10, "slot": 0,
               "port": 0, "T": 0.5, "record": True, "action_delay_ticks": 26, "ability": {"mode": "label"}}
        spec = {"tag": "sp_lab", "opp": {"id": "snap", "type": "snapshot"}, "learner_deck": VALK, "opp_deck": VALK,
                "learner_side": 0, "seed": 5}
        out = []
        ocfg = {k: v for k, v in cfg.items() if k != "ability"}
        E.run_selfplay_batch(lambda: _env(tail_cap=3000), learner, {"snap": (snap, {**ocfg, "record": False})},
                             [(i, dict(spec, tag=f"sp_lab{i}", seed=5 + i, learner_side=i % 2), 0,
                               {"rollout_index": 0, "update": 0}) for i in range(2)], cfg, 2, on_result=out.append)
        n_lab = sum(int(r["traj"]["ab_cand"].sum()) for r in out)
        self.assertGreater(n_lab, 5)
        self.assertFalse(any(r["traj"]["ab_sampled"].any() for r in out))       # label mode decides nothing
        L = RL.Learner.__new__(RL.Learner)
        L.cfg = {"hero_abilities": True, "seed": 0, **{k: v for k, v in AB.items()}, "ability_bc_matches": 2,
                 "ability_bc_steps": 50}
        L.model, L.dev, L.league, L.train = a, torch.device("cpu"), None, [None, None, None]
        L.log = lambda msg, L=L: L.__dict__.setdefault("lines", []).append(msg)
        L.ability_head, L.ability_bc = RL.AbilityHead(a.value_head.in_features), None
        sent = []
        L.actors = SimpleNamespace(run=lambda kind, u, sd, jobs: (sent.append((kind, sd, jobs)) or (out, [], {})))
        b0 = float(L.ability_head.net[2].bias)
        L._ability_warm_start()
        kind, sd, jobs = sent[0]
        self.assertEqual((kind, len(jobs)), ("rollout", 2))
        msd, _ = RL.split_actor_sd(sd, "cpu")
        self.assertEqual(RL.pop_prefix(msd, RL.ABILITY_SD), {})             # no head in the message -> label mode
        st = L.ability_bc
        self.assertEqual(st["n"], n_lab)
        self.assertEqual(set(st["by_card"]), {"Valkyrie"})
        self.assertLessEqual(st["bce_after"], st["bce_before"])
        self.assertNotEqual(float(L.ability_head.net[2].bias), b0)
        self.assertTrue(any("warm start" in m for m in L.lines))


@unittest.skipIf(RE is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestSearchS0(unittest.TestCase):
    def _play(self, ability=None, stats=False):
        """Our side samples (search_s0 --learner-policy sample: the tiny model's live gate at .35 almost never plays,
        measured) Hero Knight on side 0; the generic rule presses for a head-less side."""
        from pipeline.tests.test_search_s0 import tiny_models
        gen, opp_gen, s1 = tiny_models()
        lcfg = {**S.live_cfg(S.TAU_PLAIN, "lattice"), "policy": "sample", "T": 0.5}
        if ability is not None:
            lcfg["ability"] = ability
        run = S.Runner(gen, {"gen": (opp_gen, S.live_cfg(S.TAU_OPP, "lattice"))}, lcfg,
                       lambda: _env("generic", tail_cap=3000, ability_outcomes=stats), horizon_s=4.0)
        spec = {"tag": "s0:gen:3", "opp": {"id": "gen"}, "learner_deck": HERO, "opp_deck": HOGEQ, "learner_side": 0,
                "seed": 3}
        m = E.SelfPlayMatch(run.make_env(), spec, 0, {**run.lcfg, "entry_index": 0},
                            {**run.opps["gen"][1], "entry_index": 0}, run.learner, run.opps["gen"][0])
        rec = run.play("plain", m)
        rec.pop("wall_s")
        return rec

    def test_greedy_press(self):
        d_g = 16
        on, off, rule = (self._play({"head": _forced(d_g, True), "mode": "greedy"}, stats=True),
                         self._play({"head": _forced(d_g, False), "mode": "greedy"}, stats=True), self._play(stats=True))
        self.assertGreater(on["ability_head"]["decisions"], 0)
        self.assertEqual(on["ability_head"]["presses"], on["ability_head"]["decisions"])
        self.assertGreater(on["ability_presses"][0].get("Knight", 0), 0)
        self.assertEqual(on["ability_stats"]["presses"], on["ability_presses"][0]["Knight"])
        self.assertEqual(off["ability_head"]["presses"], 0)
        self.assertGreater(off["ability_head"]["decisions"], 0)
        self.assertEqual(off["ability_presses"][0], {})
        self.assertEqual(off["ability_stats"]["presses"], 0)
        self.assertNotIn("ability_head", rule)
        self.assertGreater(rule["ability_presses"][0].get("Knight", 0), 0)     # the head-less side: the rule
        self.assertNotIn("ability_stats", self._play())                 # no --ability-stats: the line unchanged

    def test_init_worker_loads_the_head(self):
        import tempfile
        from pipeline.tests.test_search_s0 import tiny_models
        gen = tiny_models()[0]
        L = SimpleNamespace(ability_head=_head(16))
        ck = Path(tempfile.mkdtemp(prefix="s0_ab_")) / "ck.pt"
        torch.save({"rl": {"ability_head": L.ability_head.state_dict(), "ability": {"d_g": 16, "hidden": 64,
                                                                                   "n_feat": NF, "bc": None}}}, ck)
        o_load = E.load_policy
        args = {"gen": str(ck), "opps": [], "threads": 1, "tail_cap": 600, "horizon": 12.0, "interval": 1, "topk": 4,
                "cells": 3, "device": "cpu", "search_min_p": 0.0, "hero_abilities": True}
        try:
            E.load_policy = lambda path, dev: (gen, {"grid": "lattice"})
            import pipeline.rl_royale as R2
            o_ph = R2.load_posture_head
            R2.load_posture_head = lambda path, dev: None
            S._init_worker(args)
            ab = S._W["runner"].lcfg["ability"]
            self.assertEqual(ab["mode"], "greedy")
            for a, b in zip(L.ability_head.state_dict().values(), ab["head"].state_dict().values()):
                self.assertTrue(torch.equal(a, b))
            with self.assertRaises(ValueError):                  # a head without --hero-abilities would never decide
                S._init_worker({**args, "hero_abilities": False})
        finally:
            E.load_policy, R2.load_posture_head = o_load, o_ph

    def test_run_json_unchanged(self):
        import tempfile
        P = _pre("pipeline/search_s0.py", "pipeline.search_s0_pre_b6")
        out = {}
        for name, mod in (("pre", P), ("now", S)):
            d = Path(tempfile.mkdtemp(prefix="s0_b6_")) / "o"
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
