"""pipeline/branching.py (opt3 T1): fork fidelity, common random numbers, the HOLD gate, stop rules, isolation.

    ROYALE_RUNTIME=20261006 research/ext/Royale/.venv/Scripts/python.exe -m pytest -q pipeline/tests/test_branching.py

Tiny random models (test_search_s0's): the properties are about the machinery, not the policy.
"""
from __future__ import annotations

import collections
import contextlib
import random
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import pipeline.royale_runtime as RR
if not RR.RUNTIME.is_dir() and RR.REPO.parent.name == "worktrees":
    # a git worktree has no untracked research/ext: verify + load the main checkout's pinned runtime instead
    RR.RUNTIME = RR.REPO.parents[2] / RR.RUNTIME.relative_to(RR.REPO)

from pipeline.tests import test_search_s0 as T                     # noqa: E402

if T.RoyaleSelfPlayEnv is not None:
    from pipeline import branching as B, e1_eval as E, search_s0 as S
    from pipeline.royale_env import RoyaleSelfPlayEnv
    SIDE_SKIP, ENV_SKIP = S.SHARED_SIDE, S.SHARED_ENV + ("core", "eng")    # shared by design (search_s0.fork_into)


class Steered(E.GenPolicy if T.RoyaleSelfPlayEnv is not None else object):
    """The tiny GenPolicy with every cell argmax at T.CELL (own half, so plays are accepted and the anti-stall clock
    resets) and, with ``gate``, p(play) a fixed function of the decision tick (0.2 .. 0.8 in 0.1 steps, cycling every
    70 ticks), so the gate thresholds are exercised deterministically."""

    def __init__(self, base, gate=False):
        self.model, self.gid, self.gate = base.model, base.gid, gate

    def forward_batch(self, rows, device="cpu"):
        enc, heads, p, hand = super().forward_batch(rows, device)
        if self.gate:
            p = [round(0.2 + 0.1 * (round(float(r["sc"][0]) * 300 / E.TICK_S) // 10 % 7), 4) for r in rows]
        return enc, heads, p, hand

    def cell_logits(self, enc, slot):
        out = super().cell_logits(enc, slot).clone()
        out[:, T.CELL] = out.max() + 1.0
        return out


def make(tail_cap=7200, opp_policy="sample", tau=0.35, gated=False):
    gen, opp_gen, _ = T.tiny_models()
    gen = Steered(gen, gated)
    lcfg = S.live_cfg(tau, "lattice")
    opps = {"gen": (opp_gen, {**S.live_cfg(S.TAU_OPP, "lattice"), "policy": opp_policy})}
    mk = lambda: RoyaleSelfPlayEnv(tail_cap=tail_cap)
    return S.Runner(gen, opps, lcfg, mk), B.BranchRunner(mk, gen, opps, lcfg)


MAIN = RR.REPO.parents[2] if RR.REPO.parent.name == "worktrees" else RR.REPO    # where untracked data lives


@contextlib.contextmanager
def main_catalog():
    """A git worktree has no untracked research/ext: read the main checkout's live card catalog (v3.1 public
    features and hero forms need it) for one test; the catalog caches are refilled from it."""
    from pipeline import obs_contract as O, public_observation as P
    if (O.REPO / "research/ext").is_dir() or RR.REPO.parent.name != "worktrees":
        yield
        return
    main = MAIN
    O._CATALOG_NAMES = None
    if hasattr(O.catalog_card_form, "table"):
        del O.catalog_card_form.table
    P._native_ids.cache_clear()
    with patch.object(O, "REPO", main), patch.object(P, "REPO", main):
        yield


def mutables(obj, skip) -> dict:
    """id -> attribute path of every mutable object reachable from ``obj``'s attributes, ``skip`` keys excepted."""
    imm = (str, bytes, int, float, bool, type(None), np.generic, types.ModuleType, type, types.FunctionType,
           types.BuiltinFunctionType)
    out: dict = {}

    def reach(x, path):
        if isinstance(x, imm) or id(x) in out:
            return
        if not isinstance(x, (tuple, frozenset)):
            out[id(x)] = path
        if isinstance(x, dict):
            items = ((repr(k), v) for k, v in x.items())
        elif isinstance(x, (list, tuple, set, frozenset, collections.deque)):
            items = ((str(i), v) for i, v in enumerate(x))
        elif hasattr(x, "__dict__"):
            items = vars(x).items()
        else:
            return
        for k, v in items:
            reach(v, f"{path}.{k}")
    for k, v in vars(obj).items():
        if k not in skip:
            reach(v, k)
    return out


def aliases(m, f) -> list:
    """Attribute paths of mutable python state that fork ``f`` SHARES with ``m`` (models / cfg / deck / engine are
    shared by design and skipped): [] = the fork copied all of it."""
    out = []
    for a, b, skip in ((m.env, f.env, ENV_SKIP), (m.learner, f.learner, SIDE_SKIP), (m.opp, f.opp, SIDE_SKIP)):
        A, Bm = mutables(a, skip), mutables(b, skip)
        out += sorted(A[i] for i in set(A) & set(Bm))
    return out


def snap(m):
    return (m.env.core.state_hash(), T.env_digest(m.env), T.side_digest(m.learner), T.side_digest(m.opp))


def run_out(drive, m):
    st, rng = T.new_st(), random.Random(0)
    while True:
        ds = m.due()
        if not ds:
            return m.result()
        drive.round(m, ds, "plain", st, rng)


@unittest.skipIf(T.RoyaleSelfPlayEnv is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestBranching(unittest.TestCase):
    def test_a_fork_determinism(self):
        """(a) extrapolation 26, delay 26, opp-elixir counter, hero abilities pressed AFTER the fork; gen v3.1 (public
        observer: counter + opponent cycle) and gen v1 (OppElixirCounter): a fork driven by the same scripted actions
        as the original ends with the same engine hash AND the same python state of env + both sides; two reseeded
        forks with the same (seed, j) likewise."""
        from pipeline.tests.gen_v3.test_sim_integration import NAMES, policy
        cfg = S.live_cfg(S.TAU_PLAIN, "lattice")
        spec = {"tag": "branch-a", "opp": {"id": "x"}, "learner_deck": NAMES, "opp_deck": NAMES, "learner_side": 0,
                "seed": 5}
        mk = lambda: RoyaleSelfPlayEnv(forms_mode="deck", hero_abilities=True)
        with main_catalog():
            for version in (4, 1, 5):
                with self.subTest(feature_version=version):
                    if version == 5:                                   # R3's base: the real gen_v32 checkpoint
                        ckpt = MAIN / "icebow/data/pipeline/gen_v32_s0/gen_s0.pt"
                        if not ckpt.is_file():
                            self.skipTest(f"{ckpt} missing")
                        pol = E.load_policy(ckpt)[0]
                    else:
                        pol = policy(version)
                    self._fork_determinism(mk, spec, cfg, pol, version)

    def _fork_determinism(self, mk, spec, cfg, pol, version):
        m = E.SelfPlayMatch(mk(), spec, 0, cfg, {**cfg, "tau": S.TAU_OPP}, pol, pol)
        while True:
            ds = m.due()
            if m.env.tick >= 130:                                   # our hero lands at 160 and is pressed later
                break
            T.scripted_round(m, ds)
        L = m.learner
        self.assertEqual(L.feature_version, version)
        self.assertTrue(L._prev_raw is not None and (L.public.plays if version == 4 else L.opp_counter))
        pressed = sum(sum(c.values()) for c in m.env.ability_presses.values())
        blob = m.env.core.save_state()
        plain = S.fork_into(m, mk(), blob)
        twins = [S.fork_into(m, mk(), blob) for _ in range(2)]
        for f in twins:
            B.reseed(f, 7, 1)
        for f in [plain] + twins:
            self.assertEqual(aliases(m, f), [])                     # nothing mutable shared with the original
        runs = [(m, ds)] + [(f, T.same_ds(f, m, ds)) for f in [plain] + twins]
        for x, xds in runs:
            while xds and x.env.tick < 2400:
                T.scripted_round(x, xds)
                xds = x.due()
        self.assertGreater(L.n_acc, 8)
        self.assertGreater(sum(sum(c.values()) for c in m.env.ability_presses.values()), pressed)   # ability state moved after the fork
        self.assertEqual(snap(plain), snap(m))
        self.assertEqual(snap(twins[0]), snap(twins[1]))
        self.assertEqual(twins[0].env.core.state_hash(), m.env.core.state_hash())   # RNGs unused by scripted plays

    def test_b_common_random_numbers(self):
        """(b) k=2, sampling opponent. reseed: same (seed, j) -> same RNG states, other j -> other states. A HOLD that
        does not hold (hold_tau -1, 1 tick) is the PLAY branch exactly, per j; j=0 and j=1 differ (opponent sampling).
        A real HOLD: the opponent's plays decided before our root play lands are the same in PLAY_j and HOLD_j."""
        drive, br = make()
        m, ds, *_ = T.to_root(self, drive, "gen", T.HOGEQ, 3)
        blob = m.env.core.save_state()
        fs = [S.fork_into(m, RoyaleSelfPlayEnv(), blob) for _ in range(3)]
        for f, j in zip(fs, (0, 0, 1)):
            B.reseed(f, 11, j)
        rng_state = lambda f: T.digest([f.learner.rng_behave, f.opp.rng_behave, f.opp.rng_obs, f.opp.rng_rand,
                                        f.opp.rng_decision_options, f.env.seed])
        self.assertEqual(rng_state(fs[0]), rng_state(fs[1]))
        self.assertNotEqual(rng_state(fs[0]), rng_state(fs[2]))

        r = br.pair(m, ds, B.BranchSpec(hold_s=0.05, hold_tau=-1.0, horizon_s=8.0, k=2, seed=11))
        h = {(b, j): f.env.core.state_hash() for b, j, f in br.last_forks}
        self.assertEqual(h[("play", 0)], h[("hold", 0)])
        self.assertEqual(h[("play", 1)], h[("hold", 1)])
        self.assertNotEqual(h[("play", 0)], h[("play", 1)])
        self.assertEqual(r.play_end[0]["tick"], r.tick + 160)

        n_opp = len(m.opp.plays)
        r = br.pair(m, ds, B.BranchSpec(hold_s=4.0, hold_tau=0.99, horizon_s=8.0, k=2, seed=11))
        fk = {(b, j): f for b, j, f in br.last_forks}
        land = r.tick + 26
        for j in range(2):
            pl, hd = fk[("play", j)], fk[("hold", j)]
            self.assertNotEqual(pl.env.core.state_hash(), hd.env.core.state_hash())
            cut = lambda f: [(x["tick"], x["slot"], x["cell"]) for x in f.opp.plays[n_opp:] if x["tick"] < land]
            self.assertEqual(cut(pl), cut(hd))
            self.assertTrue(cut(pl))                                  # the opponent did decide plays in that window

    def test_c_hold_gate(self):
        """(c) during hold_s the HOLD branch plays only at p > hold_tau (or anti-stall) and waits at
        tau < p <= hold_tau; after hold_s it plays at tau < p <= hold_tau again. PLAY plays at the root."""
        drive, br = make(tau=0.35, gated=True)
        m, ds, *_ = T.to_root(self, drive, "gen", T.HOGEQ, 3)
        n0 = len(m.learner.plays)
        calls, real = [], E.live_decide_batch

        def spy(model, enc, heads, p, allowed, stalled, *, tau, **kw):
            out = real(model, enc, heads, p, allowed, stalled, tau=tau, **kw)
            calls.append((tau, list(p), allowed.any(axis=1).tolist(), out))
            return out
        with patch.object(E, "live_decide_batch", spy):
            r = br.pair(m, ds, B.BranchSpec(hold_s=4.0, hold_tau=0.55, horizon_s=20.0, k=1, seed=0))
        until = r.tick + 80
        fk = {b: f for b, _, f in br.last_forks}
        self.assertEqual(fk["play"].learner.plays[n0]["tick"], r.tick)
        hold = fk["hold"].learner.plays[n0:]
        inside = [x for x in hold if x["tick"] < until]
        after = [x for x in hold if x["tick"] >= until]
        self.assertTrue(all(x["p"] > 0.55 or x["why"] == "stall" for x in inside), inside)
        self.assertTrue(any(0.35 < x["p"] <= 0.55 and x["why"] == "gate" for x in after), after)
        withheld = [(q, d["why"]) for tau, ps, al, out in calls if tau == 0.55
                    for q, a, d in zip(ps, al, out) if a and 0.35 < q <= 0.55]
        self.assertTrue(withheld and all(w == "wait" for _, w in withheld), withheld)

    def test_d_stops(self):
        """(d) horizon: every end at root + horizon, outcome None; end of match (tail_cap) with horizon None:
        every end at the cap, outcome in {-1, 0, 1}; snapshots survive the pool's reuse."""
        drive, br = make(tail_cap=1300)
        m, ds, *_ = T.to_root(self, drive, "gen", T.HOGEQ, 3)
        r = br.pair(m, ds, B.BranchSpec(hold_s=2.0, horizon_s=3.0, k=2, seed=0))
        self.assertEqual([e["tick"] for e in r.play_end + r.hold_end], [r.tick + 60] * 4)
        self.assertEqual(r.play_outcome + r.hold_outcome, [None] * 4)
        self.assertTrue(all(e["learner"].env is None and e["side"] == m.learner.side for e in r.play_end))
        r2 = br.pair(m, ds, B.BranchSpec(hold_s=2.0, horizon_s=None, k=2, seed=0))
        self.assertEqual([e["tick"] for e in r2.play_end + r2.hold_end], [1300] * 4)
        self.assertTrue(all(o in (-1, 0, 1) for o in r2.play_outcome + r2.hold_outcome))
        self.assertEqual(int(r.play_end[0]["state"].tick), r.tick + 60)                # not overwritten by r2
        r3 = br.pair(m, ds, B.BranchSpec(hold_s=2.0, horizon_s=60.0, k=1, seed=0))     # horizon past the end
        self.assertEqual((r3.play_end[0]["tick"], r3.play_outcome[0] is None), (1300, False))

    def test_e_original_untouched(self):
        """(e) pair() leaves m's engine, env fields and both sides unchanged, and m continued afterwards plays out
        exactly like the same seed never forked."""
        drive, br = make(tail_cap=1600)
        m, ds, *_ = T.to_root(self, drive, "gen", T.HOGEQ, 3)
        before = snap(m)
        br.pair(m, ds, B.BranchSpec(hold_s=4.0, horizon_s=None, k=2, seed=0))
        self.assertEqual(snap(m), before)
        st, rng = T.new_st(), random.Random(0)
        drive.round(m, ds, "plain", st, rng)
        res = run_out(drive, m)
        ref_drive, _ = make(tail_cap=1600)
        m2, ds2, *_ = T.to_root(self, ref_drive, "gen", T.HOGEQ, 3)
        ref_drive.round(m2, ds2, "plain", T.new_st(), random.Random(0))
        res2 = run_out(ref_drive, m2)
        self.assertEqual(m.env.core.state_hash(), m2.env.core.state_hash())
        drop = lambda r: {k: v for k, v in r.items() if k != "wall_s"}
        self.assertEqual(drop(res), drop(res2))


class TestCatalogFailsClosed(unittest.TestCase):
    def test_missing_catalog_raises_naming_the_path(self):
        """obs_contract._catalog_names: a missing live_card_catalog.json is a FileNotFoundError naming the expected
        path, never a silently empty id -> name table."""
        import tempfile
        from pipeline import obs_contract as O
        saved = O._CATALOG_NAMES
        try:
            with tempfile.TemporaryDirectory() as d, patch.object(O, "REPO", Path(d)):
                O._CATALOG_NAMES = None
                with self.assertRaises(FileNotFoundError) as cm:
                    O._catalog_names()
                self.assertIn(str(Path(d) / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json"),
                              str(cm.exception))
                self.assertIsNone(O._CATALOG_NAMES)                    # nothing cached from the failure
        finally:
            O._CATALOG_NAMES = saved


if __name__ == "__main__":
    unittest.main()
