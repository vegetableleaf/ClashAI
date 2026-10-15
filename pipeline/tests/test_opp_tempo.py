"""L74 human-tempo opponent knobs (``opp_decide_every`` / ``opp_reaction_ticks``, e1_eval.opp_tempo): opponent-only,
opt-in; absent = the pre-change behaviour (compared with commit 6099c63 where a module is involved).

    research/ext/Royale/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider pipeline/tests/test_opp_tempo.py

Covers: the helper (identity when off, validation, values); the REAL SelfPlayMatch on test_league's fake env (neutral
values = the same match play by play; the learner untouched by the knobs; the opponent on its own interval with its
plays landing the extra ticks later; an interval on no common grid with the env's decision_ticks); rl_royale (config
hash vs 6099c63, load_config validation, actor_base, the actor's and the branch worker's opponent cfg); search_s0 (flags,
run.json + worker args vs 6099c63, the worker's opponent cfg, a real-engine match); gap.py / livecal.py commands.
"""
from __future__ import annotations

import io
import json
import queue
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import e1_eval as E                                         # noqa: E402
from pipeline import rl_royale as RL                                      # noqa: E402
from pipeline.tests.test_league import (_SPEnv, _cfg, _run, _spec, _tiny_gen, VOCAB, D)   # noqa: E402

PRE = "6099c63"             # the last commit before the opponent-tempo knobs: the absent-key reference
YAML = REPO / "pipeline" / "rl_royale.yaml"
GAP = REPO / "scratchpad" / "gauntlet" / "L74" / "gap"
LIVECAL = REPO / "scratchpad" / "gauntlet" / "L74" / "livecal"

try:
    from pipeline.royale_env import RoyaleSelfPlayEnv                   # noqa: F401
    from pipeline import search_s0 as S
except ImportError:                                                     # no royalegym in this venv
    S = None


def _pre_module(rel: str, name: str, file: Path, inject: dict | None = None):
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show", f"{PRE}:{rel}"], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise unittest.SkipTest(f"git unavailable: {exc}")
    if src.returncode:
        raise unittest.SkipTest(f"git show {PRE}:{rel} failed: {src.stderr.strip()}")
    mod = types.ModuleType(name)
    mod.__file__ = str(file)
    saved = {k: sys.modules.get(k) for k in (inject or {})}
    sys.modules.update(inject or {})
    try:
        exec(compile(src.stdout, name, "exec"), mod.__dict__)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return mod


def _traced(fn):
    """Run ``fn`` with every SelfPlaySide decision logged as (side, tick, played)."""
    log, orig = [], E.SelfPlaySide.apply

    def apply(self, p, d):
        log.append((self.side, int(self.env.tick), bool(d["play"])))
        return orig(self, p, d)
    E.SelfPlaySide.apply = apply
    try:
        return fn(), log
    finally:
        E.SelfPlaySide.apply = orig


# ------------------------------------------------------------------------------------------------------
class TestHelper(unittest.TestCase):
    def test_off_is_the_same_object(self):
        c = _cfg()
        self.assertIs(E.opp_tempo(c), c)
        self.assertIs(E.opp_tempo(c, None, None), c)

    def test_values(self):
        c = _cfg(action_delay_ticks=26)
        o = E.opp_tempo(c, 17, 13)
        self.assertEqual((o["decide_every"], o["action_delay_ticks"]), (17, 39))
        self.assertEqual({k: v for k, v in o.items() if k not in ("decide_every", "action_delay_ticks")},
                         {k: v for k, v in c.items() if k not in ("decide_every", "action_delay_ticks")})
        self.assertEqual((c["decide_every"], c["action_delay_ticks"]), (10, 26))          # input untouched
        self.assertEqual(E.opp_tempo(_cfg(), None, 13)["action_delay_ticks"], 13)         # no delay key -> 0 + R
        self.assertEqual(E.opp_tempo(c, 10, 0), c)                                        # neutral = equal cfg
        self.assertNotIn("action_delay_ticks", E.opp_tempo(_cfg(), 12, 0))               # R 0 adds no key

    def test_validation(self):
        for de in (0, -10, 1.5, True, "10", np.float64(10)):
            with self.assertRaises(ValueError, msg=repr(de)):
                E.opp_tempo(_cfg(), de, None)
        for r in (-1, 2.0, False, "3"):
            with self.assertRaises(ValueError, msg=repr(r)):
                E.opp_tempo(_cfg(), None, r)
        E.opp_tempo(_cfg(), 1, 0)


# ------------------------------------------------------------------------------------------------------
class TestFakeMatch(unittest.TestCase):
    """The REAL SelfPlayMatch / run_selfplay_batch on test_league's fake env (board = f(tick), so the learner's inputs
    do not depend on the opponent's plays and its decisions can be compared across opponent tempos)."""

    TAIL = 600

    def _match(self, ocfg, lcfg):
        learner, opp = E.GenPolicy(_tiny_gen(11), VOCAB), E.GenPolicy(_tiny_gen(12), VOCAB)
        spy = []

        def go():
            return _run([(0, _spec(0, "o", 0), 0, {"rollout_index": 0, "update": 0})], learner, {"o": (opp, ocfg)},
                        lcfg, make_env=lambda: _SPEnv(tail=self.TAIL), n=1, spy=spy)
        (res, envs), log = _traced(go)
        return spy[0], res[0], envs[0], log

    @staticmethod
    def _plays(side):
        return [(p["tick"], p.get("land_tick"), p["slot"], p["cell"], p["accepted"]) for p in side.plays]

    def _same(self, a, b, learner_only=False):
        (ma, ra, ea, la), (mb, rb, eb, lb) = a, b
        L = ma.learner.side
        pick = (lambda xs, i: [x for x in xs if x[i] == L]) if learner_only else (lambda xs, i: xs)
        self.assertEqual(pick(la, 0), pick(lb, 0))                              # decisions: side, tick, played
        self.assertEqual(pick(ea.log, 1), pick(eb.log, 1))                      # engine acts: tick, side, slot, x, y
        self.assertEqual(self._plays(ma.learner), self._plays(mb.learner))
        for k in ra["traj"]:
            np.testing.assert_array_equal(np.asarray(ra["traj"][k]), np.asarray(rb["traj"][k]), err_msg=k)
        if not learner_only:
            self.assertEqual(self._plays(ma.opp), self._plays(mb.opp))
            strip = (lambda r: {k: v for k, v in r.items() if k not in ("traj", "wall_s")})
            self.assertEqual(json.dumps(strip(ra), sort_keys=True, default=str),
                             json.dumps(strip(rb), sort_keys=True, default=str))

    def _schedule(self, log, side, start, de, delay):
        """The decision ticks ``side`` must have: start, then +de, or +de * (delay // de + 1) after a delayed play."""
        got = [(t, pl) for s, t, pl in log if s == side]
        self.assertTrue(got)
        self.assertEqual(got[0][0], start)
        for (t, pl), (t2, _) in zip(got, got[1:]):
            self.assertEqual(t2, t + (de * (delay // de + 1) if (pl and delay) else de), (t, pl, t2))
        return got

    def test_neutral_values_are_the_same_match(self):
        for d in (0, D):
            lcfg = _cfg(action_delay_ticks=d)
            ocfg = _cfg("sample", record=False, action_delay_ticks=d)
            base = self._match(ocfg, lcfg)
            self.assertGreater(base[0].opp.n_att, 0)
            self._same(base, self._match(E.opp_tempo(ocfg, 10, 0), lcfg))

    def test_learner_untouched_opponent_on_its_own_tempo(self):
        for d, de, r in ((D, 17, 13), (0, 17, 13), (D, 13, 0), (0, 7, 5)):
            lcfg = _cfg(action_delay_ticks=d)
            ocfg = _cfg("sample", record=False, action_delay_ticks=d)
            base = self._match(ocfg, lcfg)
            knob = self._match(E.opp_tempo(ocfg, de, r), lcfg)
            self._same(base, knob, learner_only=True)
            m, res, env, log = knob
            self.assertEqual((m.learner.cfg["decide_every"], m.learner.delay), (10, d))
            self.assertEqual((m.opp.cfg["decide_every"], m.opp.delay), (de, d + r))
            self._schedule(log, m.learner.side, 90, 10, d)
            got = self._schedule(log, m.opp.side, 90, de, d + r)
            self.assertTrue(any(pl for _, pl in got), (d, de, r))
            ops = [p for p in m.opp.plays]
            for p in ops:
                if d + r:
                    self.assertEqual(p["land_tick"], p["tick"] + d + r)
                else:
                    self.assertNotIn("land_tick", p)
            acts = [t for (t, sd, *_) in env.log if sd == m.opp.side]
            self.assertEqual(acts, [p.get("land_tick", p["tick"]) for p in ops
                                    if p.get("reason") != "match_over_before_landing"])
            self.assertEqual(res["opp_side"]["decisions"], len(got))
            if de % 10:                                 # off the env's decision grid: opponent decisions between ours
                self.assertTrue({t for _, t in got} - set(range(90, 90 + self.TAIL, 10)))


# ------------------------------------------------------------------------------------------------------
class TestRLConfig(unittest.TestCase):
    def test_hash_absent_is_pre(self):
        cfg = RL.load_config(YAML, [], False)
        for k in RL.OPP_TEMPO_KEYS:
            self.assertNotIn(k, cfg)
        P = _pre_module("pipeline/rl_royale.py", "rl_royale_pre_tempo", REPO / "pipeline" / "rl_royale.py")
        self.assertEqual(RL.config_sha(cfg), P.config_sha(cfg))
        self.assertEqual(RL.config_sha(cfg), RL.config_sha(dict(cfg, opp_decide_every=None, opp_reaction_ticks=None)))
        on = {RL.config_sha(dict(cfg, **kw)) for kw in ({"opp_decide_every": 17}, {"opp_reaction_ticks": 13},
                                                         {"opp_decide_every": 17, "opp_reaction_ticks": 13})}
        self.assertEqual(len(on), 3)
        self.assertNotIn(RL.config_sha(cfg), on)

    def test_load_config(self):
        cfg = RL.load_config(YAML, ["league=true", "opp_decide_every=17", "opp_reaction_ticks=13"], False)
        self.assertEqual((cfg["opp_decide_every"], cfg["opp_reaction_ticks"]), (17, 13))
        RL.load_config(YAML, ["league=true", "opp_reaction_ticks=0"], False)
        RL.load_config(YAML, ["opp_decide_every=null"], False)                  # null = off, no league needed
        for bad in (["opp_decide_every=17"], ["league=true", "opp_decide_every=0"],
                    ["league=true", "opp_decide_every=1.5"], ["league=true", "opp_decide_every=true"],
                    ["league=true", "opp_reaction_ticks=-1"], ["league=true", "opp_reaction_ticks=x"]):
            with self.assertRaises(SystemExit, msg=bad):
                RL.load_config(YAML, bad, False)

    def _base(self, *over, **attrs):
        cfg = RL.load_config(YAML, list(over), False)
        return RL.Learner.actor_base(SimpleNamespace(cfg=cfg, init_meta={"args": {"d": 16, "layers": 1}},
                                                     grid="floor", **attrs))

    def test_actor_base(self):
        b = self._base()
        for k in RL.OPP_TEMPO_KEYS:
            self.assertNotIn(k, b)
        b = self._base("league=true", "opp_decide_every=17", "opp_reaction_ticks=13")
        self.assertEqual((b["opp_decide_every"], b["opp_reaction_ticks"]), (17, 13))
        self.assertEqual(b["decide_every"], 10)                                  # the learner's interval unchanged


@unittest.skipIf(S is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestRLWorkers(unittest.TestCase):
    """The actor's and the branch worker's opponent cfg (in-process, the match runner replaced by a spy)."""

    SPEC = {"tag": "t", "opp": {"id": "a", "path": "x.pt"}, "learner_deck": [], "opp_deck": [], "learner_side": 0,
            "seed": 1}

    def _base(self, *over):
        from pipeline.royale_runtime import activate
        cfg = RL.load_config(YAML, ["league=true", "action_delay_ticks=26"] + list(over), False)
        b = RL.Learner.actor_base(SimpleNamespace(cfg=cfg, init_meta={"args": {"d": 16, "layers": 1}}, grid="floor",
                                                  runtime=activate()))
        b.update(actor_device="cpu", actor_threads=1, in_flight=1)
        return b

    @staticmethod
    def _sd():
        import torch
        from pipeline.model_v3 import S1Model
        torch.manual_seed(0)
        buf = io.BytesIO()
        torch.save(S1Model(d=16, layers=1).state_dict(), buf)
        return buf.getvalue()

    def _actor(self, base):
        got = {}
        o_load, o_run = E.load_policy, E.run_selfplay_batch
        E.load_policy = lambda path, dev="cpu": ("POL", {"grid": "lattice"})
        E.run_selfplay_batch = lambda mk, model, opps, jobs, cfg, n, **k: got.update(opps=opps, cfg=cfg)

        class Out(list):
            def cancel_join_thread(self):
                pass

            def put(self, m, *a, **k):
                self.append(m)
        in_q, out = queue.Queue(), Out()
        in_q.put(("selfplay", 0, self._sd(), [(0, self.SPEC, 0)]))
        in_q.put(None)
        try:
            RL.actor_main(0, 0, in_q, out, base)
        finally:
            E.load_policy, E.run_selfplay_batch = o_load, o_run
        self.assertFalse([m for m in out if m[0] == "error"], out)
        return got["cfg"], got["opps"]["a"][1]

    def _branch(self, base):
        got = {}
        base = {**base, "branch": dict(RL.BRANCH_DEFAULTS)}
        in_q = queue.Queue()

        def spy(mk, model, opps, jobs, lcfg, bc, version, **k):
            got.update(opps=opps, lcfg=lcfg)
            in_q.put(None)
            return [], {}
        o_load, o_bj = E.load_policy, RL.branch_jobs
        E.load_policy = lambda path, dev="cpu": ("POL", {"grid": "lattice"})
        RL.branch_jobs = spy

        class Out(list):
            def cancel_join_thread(self):
                pass

            def put(self, m, *a, **k):
                self.append(m)
        out = Out()
        in_q.put((0, self._sd(), [self.SPEC]))
        try:
            RL.branch_worker_main(0, in_q, out, base)
        finally:
            E.load_policy, RL.branch_jobs = o_load, o_bj
        self.assertFalse([m for m in out if m[0] == "error"], out)
        return got["lcfg"], got["opps"]["a"][1]

    def test_actor_absent_is_pre_and_set_is_opponent_only(self):
        base = self._base()
        lcfg, ocfg = self._actor(base)
        want = {**RL.actor_cfg(base, "rollout", 0, "cpu"), "policy": base["league_opp_policy"], "record": False,
                "T_gate": None, "T": RL.opp_T(base), "grid": "lattice"}          # the pre-change expression
        self.assertEqual(ocfg, want)
        l2, o2 = self._actor(self._base("opp_decide_every=17", "opp_reaction_ticks=13"))
        self.assertEqual(l2, lcfg)                                              # the learner's cfg unchanged
        self.assertEqual(o2, {**want, "decide_every": 17, "action_delay_ticks": 39})

    def test_branch_worker(self):
        base = self._base()
        lcfg, ocfg = self._branch(base)
        want = {**RL.actor_cfg(base, "rollout", 0, "cpu"), "policy": base["league_opp_policy"], "record": False,
                "T_gate": None, "T": RL.opp_T(base), "grid": "lattice"}
        self.assertEqual(ocfg, want)
        l2, o2 = self._branch(self._base("opp_decide_every=17", "opp_reaction_ticks=13"))
        self.assertEqual(l2, lcfg)
        self.assertEqual(o2, {**want, "decide_every": 17, "action_delay_ticks": 39})


# ------------------------------------------------------------------------------------------------------
@unittest.skipIf(S is None, "royalegym not importable (run in research/ext/Royale/.venv)")
class TestSearchS0(unittest.TestCase):
    def _main(self, mod, extra=()):
        """``mod.main`` with the worker stubbed: -> (run.json minus started/out, the worker args)."""
        seen = {}
        o_init, o_job = mod._init_worker, mod._run_job
        mod._init_worker = lambda args: seen.update(args)
        mod._run_job = lambda job: {"arm": job[0], "opp": job[1], "seed": job[2], "skipped": "stub"}
        try:
            with tempfile.TemporaryDirectory() as d:
                mod.main(["--out", str(Path(d) / "o"), "--seeds", "0:1", "--opps", "gen", "--arms", "plain"] + list(extra))
                run = json.loads((Path(d) / "o" / "run.json").read_text(encoding="utf-8"))
        finally:
            mod._init_worker, mod._run_job = o_init, o_job
        return {k: v for k, v in run.items() if k not in ("started", "out")}, seen

    def test_run_json_absent_is_pre(self):
        P = _pre_module("pipeline/search_s0.py", "search_s0_pre_tempo", REPO / "pipeline" / "search_s0.py")
        for extra in ((), ("--opp-policy", "sample", "--opp-T", "0.1", "--own-effects")):
            self.assertEqual(self._main(S, extra), self._main(P, extra))
        run, args = self._main(S, ("--opp-decide-every", "17", "--opp-reaction-ticks", "13"))
        self.assertEqual((run["opp_decide_every"], run["opp_reaction_ticks"]), (17, 13))
        self.assertEqual((args["opp_decide_every"], args["opp_reaction_ticks"]), (17, 13))
        run, args = self._main(S, ("--opp-reaction-ticks", "0"))
        self.assertEqual(run["opp_reaction_ticks"], 0)
        self.assertNotIn("opp_decide_every", run)
        for bad in (("--opp-decide-every", "0"), ("--opp-reaction-ticks", "-1")):
            with self.assertRaises(SystemExit, msg=bad):
                self._main(S, bad)

    def _worker(self, **extra):
        from pipeline.tests.test_search_s0 import tiny_models
        tiny = tiny_models()
        orig = S.E.load_policy
        S.E.load_policy = lambda path, dev="cpu": (tiny[0 if Path(path).name == "A" else 1], {"grid": "lattice"})
        try:
            S._W.clear()
            S._init_worker({"gen": "A", "opp_gen": "B", "s1": "S", "opps": ["gen"], "threads": 1, "tail_cap": 900,
                            "horizon": 4.0, "interval": 1, "topk": 4, "cells": 3, "device": "cpu", "search_min_p": 0.0,
                            "opp_policy": "sample", "opp_T": 0.5, **extra})
        finally:
            S.E.load_policy = orig
        return S._W["runner"]

    def _play(self, run):
        rec, log = _traced(lambda: run.play("plain", run.setup("gen", 2, ["HogRider", "Earthquake", "Log", "Cannon",
                                                                        "Musketeer", "IceSpirits", "Skeletons",
                                                                        "Valkyrie"])))
        res = dict(run.last_result)
        for r in (rec, res):
            r.pop("wall_s", None)
        return rec, res, log

    def test_worker_and_real_engine_match(self):
        r0 = self._worker()
        o0 = r0.opps["gen"][1]
        a = self._play(r0)
        b = self._play(self._worker(opp_decide_every=10, opp_reaction_ticks=0))   # neutral: the same match
        for x, y in zip(a, b):
            self.assertEqual(json.dumps(x, sort_keys=True, default=str), json.dumps(y, sort_keys=True, default=str))
        r = self._worker(opp_decide_every=17, opp_reaction_ticks=13)
        self.assertEqual(r.lcfg, r0.lcfg)                                       # our side's cfg unchanged
        self.assertEqual(r.opps["gen"][1], {**o0, "decide_every": 17, "action_delay_ticks": 39})
        rec, res, log = self._play(r)
        L = res["side"]
        dl = r.lcfg["action_delay_ticks"]
        start = log[0][1]
        TestFakeMatch._schedule(self, log, L, start, 10, dl)                    # env decision_ticks 10, ours 10
        got = TestFakeMatch._schedule(self, log, 1 - L, start, 17, dl + 13)     # the opponent: 17, lands +39
        self.assertTrue(any(pl for _, pl in got))
        self.assertTrue({t - start for _, t in got if (t - start) % 10})       # off the env's 10-tick grid
        self.assertEqual(res["opp_side"]["decisions"], len(got))


# ------------------------------------------------------------------------------------------------------
class TestGapCommands(unittest.TestCase):
    def test_absent_is_pre_and_flags_pass_through(self):
        for p in (str(GAP), str(LIVECAL), str(GAP.parent / "heroiw")):
            if p not in sys.path:
                sys.path.insert(0, p)
        import gap
        import livecal
        pl = _pre_module("scratchpad/gauntlet/L74/livecal/livecal.py", "livecal", LIVECAL / "livecal.py")
        pg = _pre_module("scratchpad/gauntlet/L74/gap/gap.py", "gap_pre_tempo", GAP / "gap.py", inject={"livecal": pl})
        job = {"seeds": [1, 2], "checkpoint": "c.pt", "opponent": {"path": "o.pt", "temperature": .1}, "fast": False}
        for fast in (False, True):
            j = dict(job, fast=fast)
            self.assertEqual(livecal.command(j, "c.json", "out", python="py"), pl.command(j, "c.json", "out", python="py"))
            for arm in ("D0", "D1", "D2", "D3", "G", "Gc") if not fast else ():   # gap plans are never fast (both refuse)
                for kw in ({}, {"drop": ("tau_threatened",)}, {"extra": ("--river", "on")}):
                    self.assertEqual(gap.command(arm, j, "c.json", "d", "py", **kw),
                                     pg.command(arm, j, "c.json", "d", "py", **kw), (arm, kw))
        self.assertEqual(gap.opp_flags(), [])
        opp = gap.opp_flags(17, 13)
        self.assertEqual(opp, ["--opp-decide-every", "17", "--opp-reaction-ticks", "13"])
        self.assertEqual(gap.opp_flags(None, 0), ["--opp-reaction-ticks", "0"])
        for arm in ("D0", "D1", "D3"):
            c = gap.command(arm, job, "c.json", "d", "py", opp=opp)
            ref = gap.command(arm, job, "c.json", "d", "py")
            i = c.index("--opp-decide-every")
            self.assertEqual(c[:i] + c[i + 4:], ref)
            self.assertEqual(c[i - 2:i], ["--opp-T", "0.1"])


if __name__ == "__main__":
    unittest.main()
