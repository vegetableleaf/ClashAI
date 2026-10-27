"""F1 acceptance on pod 32657 (pipeline/crforge_core.py). Parts (each writes one JSON to --out-dir):

  saveload  N matches (icebow vs the census decks): an uninterrupted run vs the same run saved at a random tick and
            loaded into a FRESH CrforgeCore; state_json byte-compared at every tick after the load to the end.
  forks     from one saved state per match, F forks in fresh cores with the same action script -> identical states every
            decision; forks with another script differ; the blob loads unchanged after them.
  obs       e1_eval.run_selfplay_batch with CLXIII on both sides (live cfg: obs live, opp_elixir counter, extrapolate 26,
            fv6 + cues + public observer) on RoyaleSelfPlayEnv whose core is CrforgeCore: >= 20 matches, no pipeline edit.
  cost      core-s per match: facade-only (step + check, as CfSpeed core) / + state() per decision / + env.raw().

usage: ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I accept_f1.py <part> [--n N] --out-dir DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/f1/cb"]

from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode  # noqa: E402

from pipeline.crforge_core import CrforgeCore  # noqa: E402

DECKS = Path("/workspace/cfspeed/decks.tsv")
CLXIII = "/workspace/f1/models/succ48_o_s91_u0075_grafted.pt"
SFX = {0: "", 1: "@evolution", 2: "@hero"}


def census():
    out = []
    for line in DECKS.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            f = line.split("\t")
            out.append((f[1].split(","), [int(v) for v in f[2].split(",")], f[3].split(","), [int(v) for v in f[4].split(",")]))
    return out


def setup(core, pair):
    d0, f0, d1, f1 = pair
    return MatchSetup(decks=[[core.ids[n] for n in d0], [core.ids[n] for n in d1]], shuffle=ShuffleMode.NONE,
                      forms=[f0, f1])


def act(core, rng, p=0.3):
    """S3's workload: per seat, a random hand slot with probability p at a random point (crforge units -> x18)."""
    cmds = []
    for side in (0, 1):
        if rng.random() < p:
            cmds.append(DeployCommand(side, rng.randrange(4), 18 * rng.randrange(500, 17500), 18 * rng.randrange(500, 31500)))
    return cmds


def run(core, rng, until=None, every_tick=False, log=None):
    """Play to the end (or tick ``until``) deciding every 10 ticks; ``log`` gets a sha of state_json at every
    decision (every tick with every_tick)."""
    while not core.state().game_over and (until is None or core._cf.tick() < until):
        core.step(act(core, rng), 0)
        for _ in range(10):
            core.step([], 1)
            if log is not None and (every_tick or _ == 9):
                log.append(hashlib.sha256(core._battle.state_json()).hexdigest()[:16])
            if core.state().game_over:
                break


def part_saveload(a):
    pairs, res = census(), []
    for i in range(a.n):
        pair = pairs[i % len(pairs)]
        seed, cut = 1000 + i, random.Random(i).randrange(200, 3200)
        c1 = CrforgeCore()
        c1.reset(seed, setup(c1, pair))
        r1, full = random.Random(seed), []
        run(c1, r1, until=cut)
        rng_state = r1.getstate()
        run(c1, r1, every_tick=True, log=full)
        c2 = CrforgeCore()
        c2.reset(seed, setup(c2, pair))
        r2 = random.Random(seed)
        run(c2, r2, until=cut)
        blob = c2.save_state()
        c3 = CrforgeCore()                        # a fresh core: nothing but the blob
        c3.load_state(blob)
        assert r2.getstate() == rng_state
        resumed = []
        run(c3, r2, every_tick=True, log=resumed)
        same = full == resumed
        res.append(dict(i=i, seed=seed, cut=cut, opp=pair[2], ticks_compared=len(full), identical=same,
                        end_tick=int(c1._cf.tick()), crowns=[p.crowns for p in c1.state().players]))
        print(json.dumps(res[-1]), flush=True)
    return dict(matches=len(res), identical=sum(r["identical"] for r in res),
                ticks_compared=sum(r["ticks_compared"] for r in res), rows=res)


def part_forks(a):
    pairs, res = census(), []
    for i in range(a.n):
        pair, seed = pairs[(7 * i) % len(pairs)], 2000 + i
        c = CrforgeCore()
        cut = random.Random(-i).randrange(300, 3000)
        while True:                               # a fork point inside the match (some end before tick 3000)
            c.reset(seed, setup(c, pair))
            run(c, random.Random(seed), until=cut)
            if not c.state().game_over:
                break
            cut //= 2
        blob = c.save_state()
        before = c._battle.state_json()
        logs = []
        for f in range(a.forks):
            fc = CrforgeCore()
            fc.load_state(blob)
            logs.append([])
            run(fc, random.Random(f"script:{i}"), log=logs[-1])
        other = CrforgeCore()
        other.load_state(blob)
        olog = []
        run(other, random.Random(f"other:{i}"), log=olog)
        c.load_state(blob)
        res.append(dict(i=i, cut=cut, forks=a.forks, all_identical=all(lg == logs[0] for lg in logs),
                        decisions=len(logs[0]), other_script_differs=olog != logs[0],
                        blob_unchanged=c._battle.state_json() == before))
        print(json.dumps(res[-1]), flush=True)
    return dict(matches=len(res), ok=sum(r["all_identical"] and r["other_script_differs"] and r["blob_unchanged"]
                                         for r in res), rows=res)


def part_obs(a):
    import torch
    torch.set_num_threads(4)
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
    from pipeline.opp_elixir_count import REGEN_SCHEDULE
    from pipeline.royale_env import RoyaleSelfPlayEnv

    class CfEnv(RoyaleSelfPlayEnv):
        """The seam this ticket proposes for royale_env (not edited): crforge core + crforge's (= the real) regen."""
        def __init__(self, **kw):
            super().__init__(**kw)
            self.core = CrforgeCore()
            self.elixir_regen_schedule = REGEN_SCHEDULE

    model, info = E.load_policy(CLXIII)
    cfg = S.live_cfg(0.5, info["grid"])
    cfg.update(action_delay_ticks=6, feature_version=6)   # live 26 = crforge's built-in 20 + 6 (seam note)
    jobs, pairs = [], census()
    for i in range(a.n):
        d1, f1 = pairs[i % len(pairs)][2], pairs[i % len(pairs)][3]
        jobs.append((i, {"tag": f"f1obs{i}", "seed": 3000 + i, "learner_side": i % 2,
                         "learner_deck": list(E.ICEBOW_ENGINE_DECK), "opp_deck": [n + SFX[f] for n, f in zip(d1, f1)],
                         "opp": {"id": "clxiii"}}, 0))
    rows, skips, envs, t0 = [], [], [], time.time()

    def make():
        envs.append(CfEnv(decision_ticks=10, forms_mode="deck"))
        return envs[-1]

    def on_result(r):
        rows.append({k: r.get(k) for k in ("tag", "outcome", "crowns", "decisions", "plays_attempted", "plays_accepted", "refuse_reasons", "stall_fired",
                                           "opp_err_mean", "unmapped", "degraded")} | {"opp_side": r.get("opp_side")})
        print(json.dumps(rows[-1], default=str)[:400], flush=True)

    E.run_selfplay_batch(make, model, {"clxiii": (model, dict(cfg))}, jobs, cfg, min(a.n, 8), on_result,
                         on_skip=lambda spec, exc: skips.append((spec["tag"], repr(exc))))
    unm = {}
    for e in envs:
        for k, v in e.core.unmapped()["missing"].items():
            unm[k] = unm.get(k, 0) + v
    unres, agg = {}, {}
    for e in envs:
        for k, v in e.core.unmapped()["stats"].items():
            agg[k] = agg.get(k, 0) + v
    for e in envs:
        for k, v in e.core.unmapped()["unresolved_creations"].items():
            unres[k] = unres.get(k, 0) + v
    return dict(matches=len(rows), skipped=skips, wall_s=round(time.time() - t0, 1), rows=rows, unresolved=unres,
                facade_unmapped=unm, stats=agg)


def part_cost(a):
    pairs = census()

    def matches(mode, seconds, warm):
        c = CrforgeCore()
        env = None
        if mode == "raw":
            from pipeline.royale_env import RoyaleSelfPlayEnv
            env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6)
            env.core = c
        k, n, t_end, c0 = 0, 0, time.time() + warm + seconds, None
        while time.time() < t_end:
            if c0 is None and time.time() > t_end - seconds:
                c0, n = time.process_time(), 0
            pair = pairs[k % len(pairs)]
            k += 1
            if env is None:
                c.reset(k, setup(c, pair))
            else:                                 # the env deals (deck_ids, forms) and warms up to tick 90
                env.reset([n + SFX[f] for n, f in zip(pair[0], pair[1])], [n + SFX[f] for n, f in zip(pair[2], pair[3])], seed=k)
            rng = random.Random(k)
            while not c._cf.over():
                for side in (0, 1):
                    if rng.random() < 0.3:
                        slot = rng.randrange(4)
                        if int(c._cf.check(side, slot)) == 0:
                            c._cf.play(side, slot, rng.randrange(500, 17500), rng.randrange(500, 31500))
                c._cf.step(10)
                if mode == "state":
                    c.state()
                elif mode == "raw":
                    env.raw()
            n += 1
        return dict(mode=mode, matches=n, core_s_per_match=round((time.process_time() - c0) / max(n, 1), 4))

    def fork_ms(reps=200):
        """CPU ms of one save_state and of one load_state at tick ~1,800 of a census match (after the warm runs)."""
        c = CrforgeCore()
        c.reset(7, setup(c, pairs[3]))
        run(c, random.Random(7), until=1800)
        t0 = time.process_time()
        for _ in range(reps):
            blob = c.save_state()
        t1 = time.process_time()
        for _ in range(reps):
            c.load_state(blob)
        t2 = time.process_time()
        return dict(mode="fork", tick=int(c._cf.tick()), save_ms=round((t1 - t0) / reps * 1e3, 3),
                    load_ms=round((t2 - t1) / reps * 1e3, 3))

    rows = [matches(m, a.seconds, a.warm) for m in ("core", "state", "raw")]
    return dict(rows=rows + [fork_ms()],
                note="process CPU (all JVM + Python threads) per match after the warm-up; S3 bare harness 0.088-0.093")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=("saveload", "forks", "obs", "cost"))
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--forks", type=int, default=8)
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--warm", type=int, default=60)
    ap.add_argument("--out-dir", default="/workspace/f1/out")
    a = ap.parse_args()
    out = dict(part=a.part, n=a.n, result=globals()[f"part_{a.part}"](a))
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    Path(a.out_dir, f"{a.part}.json").write_text(json.dumps(out, indent=1, default=str))
    r = out["result"]
    print(json.dumps({k: v for k, v in r.items() if k != "rows"}, default=str)[:3000])


if __name__ == "__main__":
    main()
