"""Debug: two PLAY forks with identical seeds -- where do they diverge? (smoke crn_ok was False)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validate as V           # noqa: E402
import numpy as np             # noqa: E402

S, E, BS = V.S, V.E, V.BS
MODE = sys.argv[1] if len(sys.argv) > 1 else "batch"


def run(self, m, ds, forks, tag):
    from pipeline.decision_options import match_kwargs
    first = [f.opp for f in forks] if m.opp in ds else []
    active, log = list(forks), {id(f): [] for f in forks}
    while True:
        due, first = first, []
        if not due:
            for f in list(active):
                got = f.due()
                if got:
                    due += got
                else:
                    active.remove(f)
            if not due:
                break
            for s in due:
                s.prepare()
        groups = {}
        for s in due:
            groups.setdefault((id(s.model), s.side, id(s.cfg)), []).append(s)
        todo = {}
        for sides in groups.values():
            model, c = sides[0].model, sides[0].cfg
            enc, heads, pp, hand = model.forward_batch([s.gen_row(model) for s in sides], c["device"])
            pre = [s.pre(hand[r]) for r, s in enumerate(sides)]
            allowed, stl = np.stack([x[1] for x in pre]), np.array([x[2] for x in pre], dtype=bool)
            if c["policy"] == "sample":
                dec = E.sample_decide_batch(model, enc, heads, pp, allowed, stl, sides, c)
            else:
                dec = E.live_decide_batch(model, enc, heads, pp, allowed, stl, tau=c["tau"], device=c["device"],
                                          **match_kwargs(sides))
            todo.update({id(s): (pp[r], dec[r]) for r, s in enumerate(sides)})
        for s in due:
            s.apply(*todo[id(s)])
        for f in forks:
            if any(s in due for s in f.sides):
                d = [(s.side, round(float(todo[id(s)][0]), 6), todo[id(s)][1]["play"], todo[id(s)][1]["slot"],
                      todo[id(s)][1]["cell"]) for s in f.sides if s in due]
                log[id(f)].append((int(f.env.tick), str(f.env.core.state_hash()), d))
    return [log[id(f)] for f in forks]


def evaluate(self, m, ds, p, plain, force, stalled):
    a = self.a
    ocfg = {**m.opp.cfg, "policy": "sample", "T": a["opp_T"], "tau": a["opp_tau"]}
    blob = m.env.core.save_state()
    forks = [S.fork_into(m, e2, blob) for e2 in self._pool(8)]
    for i, f in enumerate(forks):
        f.opp.cfg = ocfg
        V.reseed(f, 123, 0 if i < 2 else i)
        f.learner.apply(p, force)
    if MODE == "batch":
        la, lb = run(self, m, ds, forks[:2], "ab")
    elif MODE == "solo":
        la, = run(self, m, ds, forks[:1], "a")
        lb, = run(self, m, ds, forks[1:2], "b")
    else:                                    # mixed: A alone, B among 6 fillers
        la, = run(self, m, ds, forks[:1], "a")
        lb = run(self, m, ds, forks[1:], "b")[0]
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            print("DIVERGE at round", i, "\nA", la[i - 1:i + 2], "\nB", lb[i - 1:i + 2], flush=True)
            break
    else:
        print("IDENTICAL", len(la), len(lb), la[-1][:2], flush=True)
    raise SystemExit(0)


V.ValRunner.evaluate = lambda self, m, ds, p, plain, force, stalled: evaluate(self, m, ds, p, plain, force, stalled)
args = {"gen": V.V32, "opp_gen": V.GEN1, "opp_gen_sha256": None, "s1": S.S1_CKPT, "opps": ["gen"], "threads": 2,
        "tail_cap": 7200, "horizon": 12.0, "interval": 1, "topk": 4, "cells": 3, "device": "cpu", "search_min_p": 0.0,
        "rollout_self": "idle", "forms_mode": "deck", "hero_abilities": True, "ability_policy": "v2", "census": V.EVO,
        "tau_plain": 0.35, "phi": V.V32, "k": 2, "band": [0.2, 0.65], "holds": [2.0], "hold_tau": 0.55,
        "horizons": [10.0], "opp_T": 0.3, "opp_tau": 0.35, "per_stratum": [1, 0, 0], "crn_check": False}
V._init(args)
V._job(0)
