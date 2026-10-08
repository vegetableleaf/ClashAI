"""R4: counterfactual branching beyond play/wait -- Rocket vs the top card ("card") and the X-Bow reach class
("xbow_class"), in pipeline/branching.py + pipeline/rl_royale.py (branch_kinds; default ["hold"] = opt3 exactly).

    ROYALE_RUNTIME=20261006 PYTHONPATH="<runtime>;<repo>" research/ext/Royale/.venv/Scripts/python.exe \
        -m unittest pipeline.tests.test_branch_r4 -v

Default parity: hold-only against rl_royale.py / branching.py at OPT3_BASE (git show); everything off against main is
test_rl_branch.TestDefaultParity (BASE_COMMIT 4b462c5; the R4 verifier also re-ran it with BASE_COMMIT=main: OK).
"""
from __future__ import annotations

import copy
import importlib.util
import math
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np
import torch

from pipeline import e1_eval as E
from pipeline import rl_royale as RL
from pipeline.branching import card_alt, xbow_alt
from pipeline.decision_options import is_xbow, xbow_offensive_cells
from pipeline.tests import test_rl_branch as TB

REPO = Path(__file__).resolve().parents[2]
OPT3_BASE = "f4621b6"                       # opt3-branching head R4 is built on (hold-only parity reference)
GRID_X = 36


def _module_at(commit: str, rel: str, name: str):
    """``rel`` as of ``commit``, imported as module ``name`` (None if git cannot show it)."""
    try:
        src = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=REPO, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    d = Path(tempfile.mkdtemp(prefix="r4_base_"))
    (d / f"{name}.py").write_bytes(src)
    spec = importlib.util.spec_from_file_location(name, d / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod                                     # dataclasses resolve annotations through it
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------------------
class TestR4Config(unittest.TestCase):
    def test_defaults_hold_only(self):
        c = RL.branch_cfg({})
        self.assertEqual({k: c[k] for k in RL.R4_KEYS},
                         {"branch_kinds": ["hold"], "branch_card_points": 6, "branch_xbow_points": 6,
                          "branch_card_coef": 0.1, "branch_xbow_coef": 0.1, "branch_rocket_band": 0.5,
                          "branch_xbow_floor": 0.2})
        self.assertIsNot(c["branch_kinds"], RL.BRANCH_DEFAULTS["branch_kinds"])     # never the shared default list

    def test_overrides_parse(self):
        cfg = RL.load_config(REPO / "pipeline" / "rl_royale.yaml",
                             ["branch_kinds=[hold, card, xbow_class]", "branch_rocket_band=0.4"], False)
        c = RL.branch_cfg(cfg)
        self.assertEqual((c["branch_kinds"], c["branch_rocket_band"]), (["hold", "card", "xbow_class"], 0.4))
        RL.branch_cfg(TB._gate_cfg(branch_kinds=["card"]))           # a kind subset without hold is valid


# ------------------------------------------------------------------------------------------------------
NAMES = ["tornado", "tesla", "ice_wizard", "x_bow", "rocket", "knight", "the_log", "skeletons"]
PLAY = {"play": True, "slot": 0, "cell": 5, "why": "gate"}


class TestSelection(unittest.TestCase):
    """card_alt / xbow_alt pick exactly the intended rows (band and floor boundaries included)."""

    def _z(self, rocket_ratio):
        z = np.zeros(8)
        z[0] = 2.0
        z[4] = 2.0 + math.log(rocket_ratio)
        return z

    def test_rocket_band(self):
        al = np.ones(8, bool)
        self.assertEqual(card_alt(self._z(0.5001), al, NAMES, PLAY, 0.5), (0, 4))       # at the band: in
        self.assertEqual(card_alt(self._z(0.9), al, NAMES, PLAY, 0.5), (0, 4))
        self.assertIsNone(card_alt(self._z(0.4999), al, NAMES, PLAY, 0.5))               # just below: out
        self.assertIsNone(card_alt(self._z(0.9), al, NAMES, {**PLAY, "play": False}, 0.5))   # live rule waits
        no_r = al.copy()
        no_r[4] = False
        self.assertIsNone(card_alt(self._z(0.9), no_r, NAMES, PLAY, 0.5))                # Rocket unaffordable
        self.assertIsNone(card_alt(self._z(1.5), al, NAMES, {**PLAY, "slot": 4}, 0.5))   # Rocket IS the top card
        self.assertIsNone(card_alt(self._z(0.9), al, NAMES, {**PLAY, "slot": 4}, 0.5))   # live rule plays Rocket
        z = self._z(0.6)
        z[2] = 9.0                                                     # top card unaffordable: the top is slot 0
        no2 = al.copy()
        no2[2] = False
        self.assertEqual(card_alt(z, no2, NAMES, PLAY, 0.5), (0, 4))
        self.assertIsNone(card_alt(z, al, NAMES, {**PLAY, "slot": 2}, 0.5))              # vs an affordable 9.0: out

    def _cells(self, def_mass):
        """Logits with defensive mass ``def_mass``: offensive = the first half of the cells; one peak per class."""
        off = np.zeros(2304, bool)
        off[:1152] = True
        p = np.where(off, (1 - def_mass) / 1152, def_mass / 1152)
        p[100] *= 1.5                                                  # offensive peak
        p[2000] *= 1.5                                                 # defensive peak
        return np.log(p), off

    def test_xbow_floor(self):
        for dm, want in ((0.3, ("off", 100, 2000)), (0.7, ("def", 2000, 100)), (0.21, ("off", 100, 2000)),
                         (0.79, ("def", 2000, 100))):
            x, off = self._cells(dm)
            a, b, a_cls, d = xbow_alt(x, off, 0.2)
            self.assertEqual((a, b), want[1:], dm)
            np.testing.assert_array_equal(a_cls, off if want[0] == "off" else ~off)
            self.assertAlmostEqual(d, dm, delta=0.002)
        for dm in (0.19, 0.81, 0.0):
            x, off = self._cells(dm) if dm else (np.zeros(2304), np.ones(2304, bool))
            self.assertIsNone(xbow_alt(x, off, 0.2), dm)

    def test_reach_rule_is_decision_options(self):
        off = xbow_offensive_cells((True, True, True), "lattice")
        self.assertTrue(off[38 * GRID_X + 7])                         # (3.5, 19): 12.5 tiles from the left princess
        self.assertFalse(off[52 * GRID_X + 18])                       # (9, 26): out of reach of every tower
        self.assertTrue(is_xbow("x_bow") and is_xbow("Xbow") and not is_xbow("rocket"))


# ------------------------------------------------------------------------------------------------------
STEP = {"tau": 0.35, "T": 0.3, "minibatch": 2, "grad_clip": 0.5}


def _rows(n, seed, **extra):
    return [{**r, **extra} for r in TB._s1_rows(n, seed)]


def _smp(row, delta, kind):
    return {**TB._sample(row, delta), "kind": kind}


def _card_z(model, Bb):
    with torch.no_grad():
        enc = model.encode(Bb["tok"], Bb["mask"], Bb["sc"], Bb["past"])
        return model.heads(enc, RL.hand_mask_from_sc(Bb["sc"]))["card"].double()


def _class_mass(model, Bb):
    """log mass of the A class and of the B class (cell softmax, temperature 1, the row's slot)."""
    with torch.no_grad():
        lp = RL.policy_terms(model, Bb, torch.arange(len(Bb["target"])), 0.35, 1.0)["cell_lp"]
        m = Bb["cls_a"]
        return (torch.logsumexp(lp.masked_fill(~m, -math.inf), -1), torch.logsumexp(lp.masked_fill(m, -math.inf), -1))


XB_MASK = xbow_offensive_cells((True, True, True), "lattice")


class TestPerKindSign(unittest.TestCase):
    @staticmethod
    def _in_hand(model, row):
        """Two in-hand slots of ``row`` (the S1 hand mask leaves the other four at -1e4)."""
        Bb = RL.to_device(RL.branch_batch([_smp({**row, "slot_a": 0, "slot_b": 1}, 0.4, "card")], 0.0), "cpu")
        z = _card_z(model, Bb)[0]
        a, b = [i for i in range(8) if float(z[i]) > -1e3][:2]
        return a, b

    def _card(self, delta):
        model = TB._tiny(3)
        row = _rows(1, 11)[0]
        a, b = self._in_hand(model, row)
        Bb = RL.to_device(RL.branch_batch([_smp({**row, "slot_a": a, "slot_b": b}, delta, "card")], 0.0), "cpu")
        z0 = _card_z(model, Bb)[0]
        st = RL.branch_step(model, torch.optim.Adam(model.parameters(), lr=1e-2), {"card": Bb}, STEP, {"card": 1.0})
        return a, b, z0, _card_z(model, Bb)[0], st

    def test_card_b_better_raises_b(self):
        a, b, z0, z1, st = self._card(-0.4)                           # B (the Rocket slot) better
        self.assertGreater(float(z1[b] - z1[a]), float(z0[b] - z0[a]))
        self.assertGreater(float(z1[b]), float(z0[b]))                # B's own logit rises
        self.assertGreater(float(torch.softmax(z1, -1)[b]), float(torch.softmax(z0, -1)[b]))
        self.assertLess(st["bce_after"], st["bce_before"])
        self.assertEqual(set(st["by_kind"]), {"card"})

    def test_card_a_better_raises_a(self):
        a, b, z0, z1, _ = self._card(+0.4)
        self.assertGreater(float(z1[a] - z1[b]), float(z0[a] - z0[b]))
        self.assertGreater(float(z1[a]), float(z0[a]))

    def test_card_x_is_the_logit_difference(self):
        model = TB._tiny(3)
        rows = _rows(3, 5)
        ab = [self._in_hand(model, r) for r in rows]
        Bb = RL.to_device(RL.branch_batch([_smp({**r, "slot_a": a, "slot_b": b}, 0.4, "card")
                                           for r, (a, b) in zip(rows, ab)], 0.0), "cpu")
        with torch.no_grad():
            x, _ = RL.branch_terms(model, Bb, torch.arange(3), 0.35, 0.3, "card")
        z = _card_z(model, Bb)
        # lead ruling 2026-10-07: card/X-Bow losses at the training T (0.3), like the hold gate term
        torch.testing.assert_close(x, torch.stack([z[i, a] - z[i, b] for i, (a, b) in enumerate(ab)]) / 0.3)

    def _xbow(self, delta):
        model = TB._tiny(4)
        row = _rows(1, 12, played=True, slot=3, cell=0, cls_a=XB_MASK.copy())[0]
        Bb = RL.to_device(RL.branch_batch([_smp(row, delta, "xbow_class")], 0.0), "cpu")
        a0, b0 = _class_mass(model, Bb)
        st = RL.branch_step(model, torch.optim.Adam(model.parameters(), lr=1e-2), {"xbow_class": Bb}, STEP,
                            {"xbow_class": 1.0})
        a1, b1 = _class_mass(model, Bb)
        return float(a0), float(b0), float(a1), float(b1), st

    def test_xbow_b_better_raises_b_class_mass(self):
        a0, b0, a1, b1, st = self._xbow(-0.4)
        self.assertGreater(b1, b0)
        self.assertLess(a1, a0)
        self.assertLess(st["bce_after"], st["bce_before"])

    def test_xbow_a_better_raises_a_class_mass(self):
        a0, b0, a1, b1, _ = self._xbow(+0.4)
        self.assertGreater(a1, a0)
        self.assertLess(b1, b0)

    def test_coef_routes_per_kind(self):
        """One step over three kinds; a kind with coef 0 contributes nothing (= the step without it)."""
        bh = RL.to_device(RL.branch_batch([_smp(r, d, "hold") for r, d in zip(_rows(3, 1), (.3, -.4, .5))], 0), "cpu")
        bc = RL.to_device(RL.branch_batch([_smp(r, -.5, "card") for r in _rows(2, 2, slot_a=0, slot_b=4)], 0), "cpu")
        bx = RL.to_device(RL.branch_batch([_smp(r, .5, "xbow_class") for r in
                                           _rows(2, 3, played=True, slot=3, cell=0, cls_a=XB_MASK.copy())], 0), "cpu")
        outs = []
        for batches, coefs in (({"hold": bh, "card": bc, "xbow_class": bx}, {"hold": .1, "card": 0.0, "xbow_class": .2}),
                               ({"hold": bh, "xbow_class": bx}, {"hold": .1, "xbow_class": .2})):
            model = TB._tiny(3)
            opt = torch.optim.SGD(model.parameters(), lr=1.0)
            n = []
            step = opt.step
            opt.step = (lambda *a, **k: (n.append(1), step(*a, **k))[1])
            st = RL.branch_step(model, opt, batches, STEP, coefs)
            self.assertEqual(len(n), 1)                                  # ONE optimizer step for all kinds
            self.assertEqual({k: v["rows"] for k, v in st["by_kind"].items()}, {k: len(b["target"]) for k, b in batches.items()})
            outs.append([p.detach().clone() for p in model.parameters()])
        for a, b in zip(*outs):
            torch.testing.assert_close(a, b, rtol=0, atol=1e-7)

    def test_stats_by_kind(self):
        s = ([_smp(r, d, "hold") for r, d in zip(_rows(2, 1), (.3, -.4))]
             + [_smp(r, d, "card") for r, d in zip(_rows(3, 2), (-.5, -.3, .01))])
        st = RL.branch_stats(s, 0.05, ["hold", "card", "xbow_class"])
        self.assertEqual(st["by_kind"]["card"], {"emitted": 3, "n": 2, "b_better_share": 1.0, "mean_delta": -0.4})
        self.assertEqual(st["by_kind"]["xbow_class"]["n"], 0)
        self.assertNotIn("by_kind", RL.branch_stats(s, 0.05, ["hold"]))
        self.assertNotIn("by_kind", RL.branch_stats(s, 0.05))


# ------------------------------------------------------------------------------------------------------
class TestHoldOnlyParity(TB._UpdateHarness):
    """branch_gate on, branch_kinds default: one update (PPO + the branch step) bit-identical to OPT3_BASE."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = _module_at(OPT3_BASE, "pipeline/rl_royale.py", "rl_royale_opt3")

    def test_update_bit_identical(self):
        if self.base is None:
            self.skipTest(f"git show {OPT3_BASE} unavailable")
        rows = TB._s1_rows(6, 21)
        smp = [{**TB._sample(r, d, ph), "version": 0, "worker": i % 2, "kind": "hold"}
               for i, (r, d, ph) in enumerate(zip(rows, [0.5, -0.4, 0.02, -0.3, 0.6, -0.2],
                                                  ["single", "double", "overtime"] * 2))]
        Ls = []
        for mod, name in ((self.base, "old"), (RL, "new")):
            L = self._learner(mod, dict(TB.ON), name=name)
            L.branch_pool = TB._FakePool(copy.deepcopy(smp))
            L._branch_send = (lambda u, bc: None)
            Ls.append((L, L.one_update(0)))
        (old, r_old), (new, r_new) = Ls
        self.assertEqual(r_old[1:], r_new[1:])
        self.assertEqual(len(old.grads), len(new.grads))
        for go, gn in zip(old.grads, new.grads):
            self.assertTrue(all(torch.equal(a, b) for a, b in zip(go, gn)))
        for a, b in zip(old.model.state_dict().values(), new.model.state_dict().values()):
            self.assertTrue(torch.equal(a, b))
        for r in (r_old[0], r_new[0]):
            self.assertIsNotNone(r["branch"]["step"])
            r["branch"]["step"].pop("wall_s")                         # timing
        strip = (lambda r: {k: v for k, v in r.items() if k not in TB.SKIP_KEYS})
        self.assertEqual(RL._py(strip(r_old[0])), RL._py(strip(r_new[0])))
        self.assertIn("branch", r_new[0])
        self.assertNotIn("by_kind", r_new[0]["branch"])
        self.assertEqual(old.log.lines[-1].split(" wall roll")[0], new.log.lines[-1].split(" wall roll")[0])


# ------------------------------------------------------------------------------------------------------
@unittest.skipIf(TB.RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestBranchMatchR4(unittest.TestCase):
    TAIL = 1500

    def setUp(self):
        TB._patch_impl(self)
        TB.BranchRunner.calls = []

    def _env(self):
        return TB.RoyaleSelfPlayEnv(tail_cap=self.TAIL)

    def test_hold_only_samples_match_opt3(self):
        """Default kinds: the same pair() calls (ticks, specs) and the same samples as OPT3_BASE's play_branch_match
        (+ the "kind" key)."""
        base = _module_at(OPT3_BASE, "pipeline/rl_royale.py", "rl_royale_opt3m")
        if base is None:
            self.skipTest(f"git show {OPT3_BASE} unavailable")
        base.branch_impl = TB.fake_impl
        gen, opp_gen, lcfg, ocfg, specs, bc = TB._engine_setup("sample")
        outs, calls = [], []
        for mod in (base, RL):
            TB.BranchRunner.calls = []
            out, _ = mod.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg, bc, 0)
            outs.append(out)
            calls.append([(t, k, (s.hold_s, s.hold_tau, s.horizon_s, s.k, s.seed)) for t, k, s in TB.BranchRunner.calls])
        self.assertEqual(calls[0], calls[1])
        self.assertGreater(len(outs[1]), 3)
        for a, b in zip(*outs):
            self.assertEqual(b.pop("kind"), "hold")
            ra, rb = a.pop("row"), b.pop("row")
            a.pop("wall_s"), b.pop("wall_s")
            self.assertEqual(a, b)
            self.assertEqual(set(ra), set(rb))
            for k in ra:
                np.testing.assert_array_equal(ra[k], rb[k], k)

    def test_selection_matches_an_oracle_and_quotas(self):
        """kinds card + xbow_class, every target due at once: a fork fires at EXACTLY the decisions an independent
        oracle (raw heads, band / floor) calls eligible, with the oracle's root actions; quotas cap each kind."""
        gen, opp_gen, lcfg, ocfg, specs, bc = TB._engine_setup("sample")
        bc = {**bc, "branch_kinds": ["card", "xbow_class"], "branch_card_points": 10000, "branch_xbow_points": 10000,
              "branch_rocket_band": 0.02}                       # the tiny model's card head is peaked
        seen = []
        real_alt, real_t = RL.fork_alt, RL.branch_targets

        def spy(kind, s, enc, heads, d, allowed, bcfg):
            got = real_alt(kind, s, enc, heads, d, allowed, bcfg)
            seen.append((kind, int(s._cur[0]), _oracle(kind, s, enc, heads, d, allowed, bcfg), got))
            return got
        RL.fork_alt, RL.branch_targets = spy, (lambda rng, n: [0] * int(n))
        self.addCleanup(setattr, RL, "fork_alt", real_alt)
        self.addCleanup(setattr, RL, "branch_targets", real_t)
        out, _ = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg, bc, 0)
        for kind in ("card", "xbow_class"):
            calls = [x for x in seen if x[0] == kind]
            yes = [x for x in calls if x[2] is not None]
            self.assertTrue(yes and len(yes) < len(calls), (kind, len(yes), len(calls)))   # both outcomes occurred
            for _, tick, want, got in calls:
                self.assertEqual(want is None, got is None, (kind, tick))
                if want is not None:
                    self.assertEqual((tuple(got["a"]), tuple(got["b"])), want, (kind, tick))
            smp = [s for s in out if s["kind"] == kind]
            self.assertEqual([s["tick"] for s in smp], [t for _, t, w, _ in calls if w is not None])
            for s, (_, tick, spec) in zip(smp, [c for c in TB.BranchRunner.calls if c[2].alt == kind]):
                self.assertEqual((spec.alt, list(spec.a), list(spec.b), tick), (kind, s["alt"]["a"], s["alt"]["b"], s["tick"]))
                if kind == "card":
                    self.assertEqual((s["row"]["slot_a"], s["row"]["slot_b"]), (spec.a[0], spec.b[0]))
                else:
                    self.assertTrue(s["row"]["played"] and s["row"]["slot"] == spec.a[0] == spec.b[0])
                    self.assertEqual(bool(s["row"]["cls_a"][spec.a[1]]), True)
                    self.assertEqual(bool(s["row"]["cls_a"][spec.b[1]]), False)
        # quotas: 2 card points, 1 xbow point per match
        TB.BranchRunner.calls = []
        out2, _ = RL.branch_jobs(self._env, gen, {"o": (opp_gen, ocfg)}, specs, lcfg,
                                 {**bc, "branch_kinds": ["hold", "card", "xbow_class"], "branch_points_per_match": 3,
                                  "branch_card_points": 2, "branch_xbow_points": 1}, 0)
        got = {k: sum(s["kind"] == k for s in out2) for k in ("hold", "card", "xbow_class")}
        self.assertEqual(got, {"hold": 3, "card": 2, "xbow_class": 1})
        B = RL.branch_batches(out2, "cpu")
        self.assertEqual({k: len(b["target"]) for k, b in B.items()}, got)


def _oracle(kind, s, enc, heads, d, allowed, bc):
    """Eligibility + root actions recomputed from the raw heads, independently of branching.card_alt / xbow_alt."""
    if not d["play"]:
        return None
    names = [str(n) for n in s.deck.cards]
    z = heads["card"][0].double()
    if kind == "card":
        r = [i for i, n in enumerate(names) if n.lower() == "rocket"]
        if not r or not allowed[r[0]]:
            return None
        top = max((i for i in range(8) if allowed[i]), key=lambda i: float(z[i]))
        if r[0] in (top, d["slot"]) or float(z[r[0]] - z[top]) < math.log(bc["branch_rocket_band"]):
            return None
        cb = int(s.model.cell_logits(enc, torch.tensor([r[0]]))[0].argmax())
        return (d["slot"], d["cell"]), (r[0], cb)
    if names[d["slot"]].lower().replace("_", "").replace("-", "") not in ("xbow",):
        return None
    cl = s.model.cell_logits(enc, torch.tensor([d["slot"]]))[0].double()
    off = torch.as_tensor(xbow_offensive_cells(tuple(bool(t.alive) for t in s._cur[1].towers[3:6]), s.cfg["grid"]))
    dm = float(torch.softmax(cl, -1)[~off].sum())
    if min(dm, 1 - dm) < bc["branch_xbow_floor"]:
        return None
    maj = ~off if dm > 0.5 else off
    return ((d["slot"], int(cl.masked_fill(~maj, -math.inf).argmax())),
            (d["slot"], int(cl.masked_fill(maj, -math.inf).argmax())))


# ------------------------------------------------------------------------------------------------------
@unittest.skipIf(TB.RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestForkActions(unittest.TestCase):
    """The real BranchRunner applies the alternative root actions: the ENGINE's own play log (env.public_plays) of
    branch B holds Rocket / the minority-class X-Bow cell, branch A the other action; the original match untouched."""

    @classmethod
    def setUpClass(cls):
        from pipeline.tests import test_branching as TBr
        cls.TBr = TBr

    def _root(self, slot):
        """Play until our side decides with deck slot ``slot`` (of ``slot(names)``) affordable: our side waits below 7
        elixir and, at 7+ without it in hand, cycles the first other affordable card at test_search_s0.CELL."""
        from pipeline.tests import test_search_s0 as T
        drive, br = self.TBr.make(tail_cap=3000)
        m = drive.setup("gen", 3, T.HOGEQ)
        want = slot([str(n) for n in m.learner.deck.cards])
        st, rng = T.new_st(), __import__("random").Random(0)
        while True:
            ds = m.due()
            self.assertTrue(ds, "no root found")
            if m.learner not in ds:
                drive.round(m, ds, "plain", st, rng)
                continue
            for s in ds:
                s.prepare()
            _, _, _, hand = self.TBr.S.forward(m.learner)
            el, allowed, _ = m.learner.pre(hand)
            if m.env.tick >= 300 and allowed[want] and allowed.sum() >= 2:
                return m, ds, br, want, allowed
            other = [i for i in range(8) if allowed[i] and i != want]
            d = ({"play": True, "slot": other[0], "cell": T.CELL, "why": "gate"} if el >= 7 and other
                 else {"play": False, "slot": -1, "cell": -1, "why": "wait"})
            for s in ds:
                s.apply(0.5, d if s is m.learner else {"play": False, "slot": -1, "cell": -1, "why": "wait"})

    def _run(self, kind, a, b, m, ds, br):
        """pair() under a spy on the engine's act(): per branch, our first deploy command at/after the root as the
        ENGINE received and accepted it (side, deck index -> engine card name, engine x / y)."""
        from unittest.mock import patch
        from pipeline import branching as Bm
        from pipeline import royale_env as RE
        log, real = [], RE._Core.act

        def act(self_, **kw):
            t = int(self_.env.core.state().tick)
            r = real(self_, **kw)
            log.append((id(self_.env), t, kw, r["accepted"]))
            return r
        before = TB_snap(m)
        n0 = len(m.learner.plays)
        with patch.object(RE._Core, "act", act):
            r = br.pair(m, ds, Bm.BranchSpec(hold_s=0.0, horizon_s=4.0, k=1, seed=3, alt=kind, a=a, b=b))
        self.assertEqual(TB_snap(m), before)                          # the original is untouched
        out = {}
        for branch, _, f in br.last_forks:
            pl, act_ = f.learner.plays[n0], (a if branch == "play" else b)
            self.assertEqual((pl["tick"], pl["slot"], pl["cell"], pl["accepted"]), (r.tick, act_[0], act_[1], True))
            eid, t, kw, acc = next(x for x in log if x[0] == id(f.env) and x[2].get("side") == f.learner.side
                                   and x[2].get("ability_button") is None and x[1] >= r.tick)
            X, Y = f.learner.ep.cell_to_engine(act_[1], f.learner.mirror, "lattice")
            self.assertTrue(acc)
            self.assertEqual((kw["x"], kw["y"]), (X, Y))
            out[branch] = {"card": f.env.names[f.env.deck_ids[f.learner.side][kw["deck_index"]]], "x": X, "y": Y,
                           "tick": t}
        return out

    def test_card_branch_b_plays_rocket(self):
        m, ds, br, rk, allowed = self._root(lambda n: n.index("rocket"))
        top = next(i for i in range(8) if allowed[i] and i != rk)
        cell_r = 20 * GRID_X + 18                                    # enemy half: a spell goes anywhere
        eng = self._run("card", (top, self.TBr.T.CELL), (rk, cell_r), m, ds, br)
        self.assertIn("rocket", eng["hold"]["card"].lower())
        self.assertNotIn("rocket", eng["play"]["card"].lower())

    def test_xbow_branch_b_plays_the_minority_cell(self):
        m, ds, br, xb, _ = self._root(lambda n: next(i for i, x in enumerate(n) if is_xbow(x)))
        off = xbow_offensive_cells(tuple(bool(t.alive) for t in m.learner._cur[1].towers[3:6]), "lattice")
        c_def, c_off = 52 * GRID_X + 18, 38 * GRID_X + 7
        self.assertTrue(off[c_off] and not off[c_def])
        eng = self._run("xbow_class", (xb, c_def), (xb, c_off), m, ds, br)
        self.assertTrue(all(is_xbow(eng[b]["card"]) for b in eng), eng)
        self.assertNotEqual((eng["play"]["x"], eng["play"]["y"]), (eng["hold"]["x"], eng["hold"]["y"]))

    def test_alt_spec_validated(self):
        from pipeline import branching as Bm
        m, ds, br, xb, _ = self._root(lambda n: next(i for i, x in enumerate(n) if is_xbow(x)))
        with self.assertRaisesRegex(ValueError, "two different root actions"):
            br.pair(m, ds, Bm.BranchSpec(hold_s=0, horizon_s=1.0, k=1, seed=0, alt="card", a=(xb, 5), b=(xb, 5)))
        with self.assertRaisesRegex(ValueError, "not in"):
            br.pair(m, ds, Bm.BranchSpec(hold_s=0, horizon_s=1.0, k=1, seed=0, alt="rocket", a=(xb, 5), b=(xb, 6)))


def TB_snap(m):
    from pipeline.tests import test_branching as TBr
    return TBr.snap(m)


@unittest.skipIf(TB.RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestHoldPairParity(unittest.TestCase):
    def test_hold_pair_matches_opt3(self):
        """BranchSpec without alt (hold): the same ends, outcomes and engine hashes as OPT3_BASE's branching.py."""
        from pipeline.tests import test_branching as TBr
        from pipeline.tests import test_search_s0 as T
        old = _module_at(OPT3_BASE, "pipeline/branching.py", "branching_opt3")
        if old is None:
            self.skipTest(f"git show {OPT3_BASE} unavailable")
        from pipeline import branching as Bm
        drive, br = TBr.make(tail_cap=1400)
        m, ds, *_ = T.to_root(self, drive, "gen", T.HOGEQ, 3)
        br_old = old.BranchRunner(br.make_env, br.learner, br.opps, {"tau": br.tau})
        res = []
        for runner, spec in ((br_old, old.BranchSpec(hold_s=4.0, horizon_s=None, k=2, seed=5)),
                             (br, Bm.BranchSpec(hold_s=4.0, horizon_s=None, k=2, seed=5))):
            r = runner.pair(m, ds, spec)
            res.append((r.tick, r.p_play, r.play_outcome, r.hold_outcome,
                        [(b, j, f.env.core.state_hash()) for b, j, f in runner.last_forks]))
        self.assertEqual(res[0], res[1])


# ------------------------------------------------------------------------------------------------------
def _pool_target(*a, **k):
    """BranchPool thread target: the real worker on fake T1/T2 (patched in-process by the test)."""
    return RL.branch_worker_main(*a, **k)


@unittest.skipIf(TB.RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestPoolCarriesKinds(unittest.TestCase):
    def test_labels_flow_with_kind_and_train(self):
        """branch_worker_main inside a BranchPool (threads), all three kinds: drained samples carry their kind and the
        kind's row fields, and one branch_step on them gives a by_kind record for every kind."""
        from pipeline.model_gen import GenModel
        TB._patch_impl(self)
        TB.BranchRunner.calls, TB.BranchRunner.sleep_s = [], 0.0
        bc = {**RL.BRANCH_DEFAULTS, "branch_gate": True, "branch_points_per_match": 20, "branch_band": [0.0, 1.0],
              "branch_k": 2, "branch_kinds": ["hold", "card", "xbow_class"], "branch_card_points": 20,
              "branch_xbow_points": 20, "branch_rocket_band": 0.001}
        base, vocab = TB._worker_base(bc)
        torch.manual_seed(0)
        net = GenModel(d=16, layers=1, d_c=8, n_cards=len(vocab)).eval()
        opp = E.GenPolicy(GenModel(d=16, layers=1, d_c=8, n_cards=len(vocab)).eval(), vocab)
        orig = E.load_policy
        E.load_policy = (lambda path, dev: (opp, {"grid": "lattice"}))
        self.addCleanup(setattr, E, "load_policy", orig)
        P = RL.BranchPool(base, 1, lambda m: None, target=_pool_target, ctx=TB.THREAD_CTX)
        self.addCleanup(P.close)
        spec = {"opp": {"id": "o", "path": "fake.pt"}, "learner_deck": TB.ICEBOW, "opp_deck": TB.HOGEQ,
                "learner_side": 0, "seed": 5}
        P.send(0, RL.state_bytes(net), [[spec, dict(spec, seed=6)]])
        got, deadline = [], time.time() + 240
        while time.time() < deadline and not {"hold", "card", "xbow_class"} <= {s["kind"] for s in got}:
            time.sleep(1.0)
            got += P.drain()[0]
        self.assertEqual({s["kind"] for s in got}, {"hold", "card", "xbow_class"}, [s["kind"] for s in got])
        for s in got:
            self.assertEqual((s["version"], s["worker"]), (0, 0))
            self.assertEqual("slot_a" in s["row"], s["kind"] == "card")
            self.assertEqual("cls_a" in s["row"], s["kind"] == "xbow_class")
        model = copy.deepcopy(net).train()
        st = RL.branch_step(model, torch.optim.Adam(model.parameters(), lr=1e-3), RL.branch_batches(got, "cpu"),
                            {"tau": 0.05, "T": 0.3, "minibatch": 8, "grad_clip": 0.5},
                            {k: 0.1 for k in RL.BRANCH_KIND_KEYS})
        self.assertIsNone(st["skipped"])
        self.assertEqual(set(st["by_kind"]), {"hold", "card", "xbow_class"})


# ------------------------------------------------------------------------------------------------------
_REAL_WORKER = RL.branch_worker_main          # captured before the smoke driver patches rl_royale's name


def r4_smoke_worker_main(*a, **k):
    """The R4 CPU smoke's branch-worker target (spawn child): fake T1/T2 -- a pair costs R4_SMOKE_SLEEP s and the
    label is test_rl_branch's +-0.5 -- then the real worker (selection by fork_alt on the real model)."""
    import os
    RL.branch_impl = TB.fake_impl
    TB.BranchRunner.sleep_s = float(os.environ.get("R4_SMOKE_SLEEP", "2"))
    return _REAL_WORKER(*a, **k)


if __name__ == "__main__":
    unittest.main()
