"""Offline regression tests: actual fork bookkeeping on a tiny stub engine."""
import copy
import json
from pathlib import Path
import random
from types import SimpleNamespace as NS

import numpy as np
import pytest
import torch

import variant_search as V
import xl2_fork as F


def test_search_batches_dev_and_freezes_test(tmp_path):
    calls = []
    path = tmp_path / "search.json"

    def many(split, drill, choices):
        calls.append((split, choices))
        return {v: dict(mean=i / 10, half_width=.01, n=9, matches=3)
                for i, v in enumerate(choices)}

    def one(split, drill, variant):
        assert json.loads(path.read_text())["selected"] == variant == "DO_best_air"
        assert split == "test"
        calls.append((split, variant))
        return dict(mean=-.2, half_width=.01, n=9, matches=3)

    result = V.search("D4", one, path, evaluate_many=many)
    assert calls == [("dev", V.variants("D4")), ("test", "DO_best_air")]
    assert result["label"] == "alt"


def test_incomplete_batch_never_runs_test(tmp_path):
    path = tmp_path / "search.json"
    def one(*args):
        pytest.fail("TEST must not run after an incomplete DEV batch")
    with pytest.raises(ValueError, match="incomplete or reordered"):
        V.search("D4", one, path, evaluate_many=lambda *args: {"DO": {"mean": .9}})
    report = json.loads(path.read_text())
    assert report["selected"] is None and report["test"] is None and report["label"] == "none"


def test_sparse_seeds_and_strict_coverage(tmp_path):
    moments = {"s0:gen:8003": [dict(t=20)], "s0:gen:8001": [dict(t=10), dict(t=30)], "s0:gen:8002": []}
    seeds = V.moment_seeds(moments, (8000, 8010))
    assert seeds == [8001, 8003]
    path = tmp_path / "matches.jsonl"
    path.write_text('\n'.join(json.dumps(dict(seed=s)) for s in reversed(seeds)))
    assert [r["seed"] for r in V.read_matches(tmp_path, (8000, 8010), seeds)] == seeds
    with pytest.raises(ValueError, match="incomplete"):
        V.read_matches(tmp_path, (8000, 8010))
    for bad in ([8001], [8001, 8001], [8001, 8002, 8003]):
        path.write_text('\n'.join(json.dumps(dict(seed=s)) for s in bad))
        with pytest.raises(ValueError, match="incomplete"):
            V.read_matches(tmp_path, (8000, 8010), seeds)
    with pytest.raises(ValueError, match="unexpected moment tag"):
        V.moment_seeds({"s0:gen:7999": [1]}, (8000, 8010))


@pytest.mark.parametrize("split,choices", [("fixed", [None]), ("dev", V.variants("D4")), ("test", ["DO"])])
@pytest.mark.parametrize("empty", [False, True])
def test_runner_skips_empty_jobs_and_preserves_paths(tmp_path, monkeypatch, split, choices, empty):
    runner = object.__new__(V.PodRunner)
    runner.py, runner.repo, runner.ckpt, runner.workers = "python", tmp_path, "unchanged.pt", 28
    root = tmp_path / split
    root.mkdir()
    lo, hi = V.SEEDS[split]["evo"]
    candidates = [] if empty else [(f"s0:gen:{lo+1}", dict(drill="D4", t=10), .4),
                                    (f"s0:gen:{lo+1}", dict(drill="D4", t=30), .4),
                                    (f"s0:gen:{lo+7}", dict(drill="D4", t=20), .6)]
    # Another drill's match must never enter this drill's jobs.
    candidates.append((f"s0:gen:{lo+9}", dict(drill="D5", t=10), .4))
    runner.prepare = lambda _: {"evo": (root, root / "census.json", candidates)}
    calls = []

    def command(args, env, log, cwd):
        calls.append(args)
        assert args[4] == f"{lo+1},{lo+7}"
        assert args[-1] == "unchanged.pt" and env["CENSUS_FILE"] == str(root / "census.json")
        assert ("XL2_VARIANT_ROWS" in env) == (len(choices) > 1)
        moments = json.loads(Path(env["MOMENTS"]).read_text())
        dest = args[3]
        dest.mkdir()
        records = []
        for tag, items in moments.items():
            opps = [dict(drill="D4", t0=mo["t"], **({"variant": v} if v else {}),
                         Ares=dict(outcome="loss"), arms={"do": dict(outcome="win")})
                    for mo in items for v in choices]
            records.append(dict(seed=int(tag.rsplit(':', 1)[-1]), tag=tag,
                                mech=dict(opps=opps, moments=[len(items), len(items)], episodes=len(opps),
                                          no_arm=[], skipped_unsnapshottable=[])))
        (dest / "matches.jsonl").write_text('\n'.join(map(json.dumps, records)))
        (dest / "run.json").write_text('{}')
        (dest / "summary.json").write_text('{}')
        log.write_text('stub replay only\n')

    monkeypatch.setattr(V, "command", command)
    result = runner.evaluate_many(split, "D4", choices)
    assert len(calls) == (0 if empty else 1)
    for variant, stats in result.items():
        assert stats["n"] == (0 if empty else 3)
        assert stats["matches"] == (0 if empty else 2)
        dest = root / "D4" / (variant or "fixed")
        assert stats["match_dirs"] == [str(dest / "forks")]
        assert stats["row_dirs"] == [str(dest / "rows")]
        for name in ("moments.json", "fork.log", "forks/matches.jsonl", "forks/summary.json", "forks/run.json"):
            assert (dest / name).is_file()


def test_dump_count_workload(tmp_path):
    candidates = [("s0:gen:12000", dict(drill="D4", t=10), .3),
                  ("s0:gen:12000", dict(drill="D4", t=30), .3),
                  ("s0:gen:12003", dict(drill="D4", t=20), .4),
                  ("s0:gen:12002", dict(drill="D5", t=20), .4)]
    counts = V.workload("dev", "D4", candidates, (12000, 14000))
    assert counts == dict(moments=3, nonempty_matches=2, variants=5, replays_before=10000,
                          replays_after=2, forks_before=30, forks_after=18)
    runner = object.__new__(V.PodRunner)
    runner.out, runner.work, runner.workers = tmp_path, {}, 28
    runner.report_work("dev", {"evo": (tmp_path, None, candidates), "lad": (tmp_path, None, [])})
    totals = json.loads((tmp_path / "workload.json").read_text())["dev"]["totals"]
    assert totals["dump_matches"] == 4000
    assert totals["replays_before"] == 84000
    assert totals["replays_after"] == 3
    assert totals["forks_before"] == 38 and totals["forks_after"] == 23


class Core:
    def __init__(self):
        self.tick, self.value, self.applied = 0, 0, 0

    def save_state(self):
        return (self.tick, self.value, self.applied)

    def load_state(self, blob):
        if blob[0] == 40:
            raise ValueError("stub unsnapshottable buff")
        self.tick, self.value, self.applied = blob

    def state(self):
        return NS(entities=[NS(buffs=["stub buff"])])


class Env:
    def __init__(self):
        self.core = Core()
        self.eng = NS(last_episode={})

    @property
    def tick(self):
        return self.core.tick

    @property
    def done(self):
        return self.tick >= 50

    def outcome(self, side):
        return ("win" if self.core.value % 3 else "loss", None)


class Side:
    def __init__(self, env, seed, side):
        self.env, self.rng, self.side = env, np.random.default_rng([seed, side]), side
        self.cfg, self.plays, self.done_plays = {}, [], []
        self.deck = NS(cards=["knight", "rocket"])

    def apply(self, p, d):
        self.plays.append(dict(tick=self.env.tick, card=d["slot"], accepted=True, reason=d["why"]))
        self.env.core.value += d["cell"] + d["slot"] + sum(d.get("follow_ups", []))
        self.env.core.applied += 1
        if self.env.core.applied % 2 == 0:
            self.env.core.tick += 10


class Match:
    def __init__(self, seed):
        self.env = Env()
        self.spec = dict(seed=seed, tag=f"s0:gen:{seed}")
        self.learner, self.opp = Side(self.env, seed, 0), Side(self.env, seed, 1)
        self.learner.other, self.opp.other = self.opp, self.learner
        self.sides = [self.learner, self.opp]

    def due(self):
        return [] if self.env.done else self.sides


@pytest.mark.parametrize("choices", [V.variants("D5"), V.variants("D4")])
def test_one_pass_equals_separate_passes_on_stub_engine(monkeypatch, choices):
    # Exercise real mech_round/mech_fork/mech_play/run_branch and fork_into.
    # Only engine I/O, decision inference and arm construction are stubbed.
    import mech_fork as M
    monkeypatch.setattr(M, "MECH", "drills")
    monkeypatch.setattr(M, "WK", True)
    monkeypatch.setattr(M, "CHECK", 100)
    monkeypatch.setattr(M, "ROWS_DIR", "stub")
    monkeypatch.setattr(M, "trigger", lambda side, *args: side._cur[0] == 0)
    monkeypatch.setattr(M.DA, "is_ordinary", lambda tag, t: t % 20 == 0)
    monkeypatch.setattr(M.DA, "STAT", {})
    dr = "D4" if "DO_best_air" in choices else "D5"
    branch_calls, saved, snapshots = [], {}, []

    def snap(m):
        return dict(h=str(m.env.core.save_state()), over=m.env.done)

    def decide(m, ds, probe_cfg=None):
        todo = []
        for side in ds:
            side._cur = (m.env.tick, NS(my_elixir=10., t_sec=m.env.tick / 20))
            # Global RNGs AND independently seeded side generators must agree.
            draws = [random.randrange(100), int(np.random.randint(100)), int(torch.randint(100, (1,))),
                     int(side.rng.integers(100))]
            d = dict(play=True, slot=0, cell=sum(draws), why="model", follow_ups=[7])
            todo.append([side, .5, d])
            if side is m.learner:
                ctx = dict(d=d, probe=dict(play=False, slot=-1, cell=-1, why="none"),
                           tick=m.env.tick, p=.5, bs=side._cur[1])
        return todo, ctx

    def build(mo, m, learner, ctx):
        if ctx["tick"] == 30:  # no-arm accounting must survive projection too
            return {"_skip": "stub infeasible"}
        v = mo["variant"]
        d = dict(ctx["d"])
        if not v.startswith("DO_when_") or mo["p_pro"] >= float(v.removeprefix("DO_when_")):
            d.update(slot=1, cell=100 if v == "DO_best_air" else 50, follow_ups=[])
        return dict(do=dict(root=d, script=None), alt=dict(root=dict(ctx["d"]), script=None))

    actual_branch = M.run_branch

    def branch(*args, **kwargs):
        branch_calls.append((args[0].spec["tag"], args[4], copy.deepcopy(args[2])))
        snapshots.append((args[0].spec["tag"], args[4], args[3]))
        return actual_branch(*args, **kwargs)

    def save(directory, name, learner, ctx, extra=None):
        saved.setdefault(directory, {})[name] = copy.deepcopy(extra)

    def play(runner, arm, m, deadline):
        while m.due():
            M.mech_round(runner, m, m.due(), arm, {}, None)
        return dict(tag=m.spec["tag"], seed=m.spec["seed"])

    monkeypatch.setattr(M, "snap", snap)
    monkeypatch.setattr(M, "decide_round", decide)
    monkeypatch.setattr(M.DA, "build_arms", build)
    monkeypatch.setattr(M.DA, "save_row", save)
    monkeypatch.setattr(M, "run_branch", branch)
    monkeypatch.setattr(M, "_orig_play", play)
    # Register adapter mutations with monkeypatch so subsequent tests are isolated.
    monkeypatch.setattr(M.S.Runner, "_mech_fork", M.mech_fork)
    runner = NS(_pool=lambda n: [Env()])

    def passes(variants, shared):
        random.seed(80); np.random.seed(81); torch.manual_seed(82)
        M._CHECKS[0] = 0
        runner._mech_fork = lambda *a, **kw: (M.S.Runner._mech_fork if shared else M.mech_fork)(runner, *a, **kw)
        rows = []
        for seed in (12000, 12001):
            mo = {t: [dict(t=t, drill=dr, variant=variants[0], p_pro=.4)] for t in (10, 20, 30, 40)}
            monkeypatch.setattr(M, "MOMENTS", {f"s0:gen:{seed}": mo})
            rows.append(M.mech_play(runner, "plain", Match(seed)))
        continuation = (random.random(), float(np.random.random()), float(torch.rand(1)))
        return rows, continuation

    separate = {}
    for v in choices:
        monkeypatch.setattr(M, "ROWS_DIR", v)
        separate[v] = passes([v], False)
    before_saved, old_calls = copy.deepcopy(saved), len(branch_calls)
    saved.clear(); branch_calls.clear(); snapshots.clear()
    F.install(M, {v: v for v in choices})
    combined, continuation = passes(choices, True)
    for v in choices:
        rows = [F.project(r, v) for r in combined]
        assert rows == separate[v][0]
        assert continuation == separate[v][1]
        assert V.estimate(rows, dr, v) == V.estimate(separate[v][0], dr, v)
        assert saved[v] == before_saved[v]  # targets, metadata, ordinary rows
        assert sum(len(r["mech"]["no_arm"]) for r in rows) == 2
        assert sum(len(r["mech"]["skipped_unsnapshottable"]) for r in rows) == 2
    assert old_calls == (4 * 3 + 4) * len(choices)  # do/alt/Acheck + incidental D10/check
    assert len(branch_calls) == 4 * (1 + len(choices)) + 4  # shared A, every B, incidental D10/check
    for tag, tick in {(tag, tick) for tag, tick, _ in snapshots}:
        assert len({blob for t, n, blob in snapshots if (t, n) == (tag, tick)}) == 1
