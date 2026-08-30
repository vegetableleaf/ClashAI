r"""FIXED-STATE RESPONSE-REGRET CORPUS -- v1 of the benchmark (fixes v0's censoring).

    # build once (driver = reference policy; ~15 min):
    PYTHONHASHSEED=0 python tools/regret_corpus.py build --matches 12
    # grade any checkpoint against the same states (~1 min each):
    PYTHONHASHSEED=0 python tools/regret_corpus.py eval --ckpt data/ab3/policy_control_s41.pt ...

WHY v1. v0 measured each policy on its OWN trajectory, which has two confounds (HANDOFF 5ae):
affordability censoring (a starved policy's hardest moments produce <2 candidates and vanish) and
state-distribution drift (83 vs 28 events per 8 matches). v1 freezes ONE set of states, collected
under a fixed DRIVER policy, and grades every checkpoint on all of them. Fully paired: same
states, same candidate sets, same rollout seeds. The 9x seed-variance problem (5ab) never enters.

HOW STATES ARE STORED: not pickled -- REPLAYED. A state is (match_seed, step_index) plus the
driver's logged action for every step. Determinism holds because the env RNG is seeded, actions
are replayed from the log (never recomputed), and PYTHONHASHSEED is pinned. Engine internals
never touch disk, so the corpus survives refactors that keep step semantics.

WHAT IS CACHED: at build time each event state's candidate set is scored ONCE (Searcher._rollout,
H=12 s, outcome-grounded, fixed _rs_seed per event). Grading a checkpoint = replay to each state,
one forward pass for ITS greedy action, look the score up -- or roll out on demand iff its action
is not in the stored set (logged, so off-corpus actions are visible in the stats).

/!\ THE CORPUS IS DRIVER-BIASED: states come from the reference policy's matches. A policy that
would never reach these states is still graded on them. That is the price of pairing; buckets and
the driver checkpoint are recorded in meta.json so a future corpus can diversify drivers.
"""
import argparse
import json
import pathlib
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clashrl.config import Config                      # noqa: E402
from clashrl.sim.env import SimMatchEnv                # noqa: E402
from clashrl.sim import rollout_search as RS           # noqa: E402

CORPUS = ROOT / "data" / "bench" / "regret_corpus"   # overridden by --dir
SEEDS = [70_000 + 31 * i for i in range(64)]


def _mk(cfg, ckpt, reseed=False):
    env = SimMatchEnv(cfg)
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3,
                     reseed_opp=reseed)
    return env, sr


def _sweep(sr, env, event_id):
    """Score this state's candidate set. _rs_seed is a function of EVENT_ID, not of visit
    order, so build and eval rolls use identical RNG streams for the same event."""
    pol, (cq_m, ceq, gq_m, playable) = sr.greedy_action()
    cands = sr.candidates(cq_m, ceq, playable)
    if pol not in cands:
        cands = list(cands) + [pol]
    sr._rs_ctr = event_id
    sr._rs_seed = 1_000_003 * event_id + 7
    sr._clamped_now = 0
    sr._jit_active = False
    return pol, [list(c) for c in cands], [float(sr._rollout(tuple(c))) for c in cands]


def build(cfg, driver, matches, reseed=False):
    CORPUS.mkdir(parents=True, exist_ok=True)
    env, sr = _mk(cfg, driver, reseed)
    corpus, event_id = [], 0
    for seed in SEEDS[:matches]:
        env.rng.seed(seed)
        env.reset()
        acts, last_t, last_sample, done, step = [], -1e9, -1e9, False, 0
        while not done:
            eng = env.eng
            ld = eng.last_deploy.get(1)
            if ld is not None and ld[3] > last_t:
                last_t = ld[3]
                if eng.t - last_sample >= 2.0 and not eng.done:
                    last_sample = eng.t
                    event_id += 1
                    pol, cands, scores = _sweep(sr, env, event_id)
                    if len(cands) >= 2:
                        corpus.append({"event_id": event_id, "seed": seed, "step": step,
                                       "t": round(float(eng.t), 2), "enemy_base": ld[0].base,
                                       "enemy_kind": ld[0].kind, "elixir": round(float(eng.elixir[0]), 2),
                                       "cands": cands, "scores": [round(s, 5) for s in scores],
                                       "driver_action": list(pol)})
            a, _ = sr.act(0)
            acts.append(list(a))
            _o, _r, done, _i = env.step(a)
            step += 1
        (CORPUS / ("actions_%d.json" % seed)).write_text(json.dumps(acts), encoding="utf-8")
        print("seed %d: %d steps, corpus now %d states" % (seed, step, len(corpus)))
    (CORPUS / "states.json").write_text(json.dumps(corpus), encoding="utf-8")
    (CORPUS / "meta.json").write_text(json.dumps({
        "driver": str(driver), "matches": matches, "seeds": SEEDS[:matches],
        "H": 12.0, "cells": 3, "min_gap": 2.0, "view": "belief" if reseed else "oracle",
        "built_under": "post-5ad band retune"}), encoding="utf-8")
    print("CORPUS: %d states from %d matches -> %s" % (len(corpus), matches, CORPUS))


def evaluate(cfg, ckpt):
    states = json.loads((CORPUS / "states.json").read_text(encoding="utf-8"))
    meta = json.loads((CORPUS / "meta.json").read_text(encoding="utf-8"))
    # the on-demand rollout MUST use the same view the corpus was scored under
    env, sr = _mk(cfg, ckpt, reseed=(meta.get("view") == "belief"))
    by_seed = {}
    for st in states:
        by_seed.setdefault(st["seed"], []).append(st)
    regrets, agree, offc, waitpol, fn_wait, played, fp_play = [], 0, 0, 0, 0, 0, 0
    rows = []
    for seed, sts in by_seed.items():
        acts = json.loads((CORPUS / ("actions_%d.json" % seed)).read_text(encoding="utf-8"))
        sts = sorted(sts, key=lambda s: s["step"])
        env.rng.seed(seed)
        env.reset()
        step = 0
        for st in sts:
            while step < st["step"]:
                env.step(tuple(acts[step]))
                step += 1
            # AT the state: the graded policy's own choice
            mine, (cq_m, ceq, gq_m, playable) = sr.greedy_action()
            cands = [tuple(c) for c in st["cands"]]
            scores = list(st["scores"])
            if mine not in cands:
                offc += 1
                sr._rs_ctr = st["event_id"]
                sr._rs_seed = 1_000_003 * st["event_id"] + 7
                sr._clamped_now = 0
                sr._jit_active = False
                cands.append(mine)
                scores.append(float(sr._rollout(mine)))
            mi, bi = cands.index(mine), int(np.argmax(scores))
            r = scores[bi] - scores[mi]
            regrets.append(r)
            agree += (bi == mi)
            if mine[0] == 0:
                waitpol += 1
                fn_wait += (cands[bi][0] == 1)
            else:
                played += 1
                if (0, 0, 0) in cands:
                    fp_play += (bi == cands.index((0, 0, 0)))
            rows.append([st["enemy_kind"], r])
    r = np.asarray(regrets)
    name = pathlib.Path(ckpt).stem.replace("policy_", "")
    print("%-22s states=%d | regret mean %.4f  median %.4f  p90 %.4f | top-1 %.0f%% | off-corpus %d"
          % (name, len(r), r.mean(), float(np.median(r)), float(np.percentile(r, 90)),
             100.0 * agree / len(r), offc))
    print("   waited %d (missed-play %.0f%%) | played %d (worse-than-WAIT %.0f%%)"
          % (waitpol, 100.0 * fn_wait / max(1, waitpol), played, 100.0 * fp_play / max(1, played)))
    fam = {}
    for k, v in rows:
        fam.setdefault(k, []).append(v)
    for k in sorted(fam):
        v = np.asarray(fam[k])
        print("   enemy %-9s n=%-4d mean %.4f  p90 %.4f" % (k, len(v), v.mean(),
                                                            float(np.percentile(v, 90))))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["build", "eval"])
    ap.add_argument("--matches", type=int, default=12)
    ap.add_argument("--driver", default="data/policy_BEST_m18000_20260826.pt")
    ap.add_argument("--ckpt", nargs="*", default=[])
    ap.add_argument("--config", default=None)
    ap.add_argument("--reseed-opp", action="store_true", help="BELIEF view (sampled futures)")
    ap.add_argument("--dir", default=None, help="corpus directory override")
    args = ap.parse_args()
    global CORPUS
    if args.dir: CORPUS = pathlib.Path(args.dir)
    ctrl = pathlib.Path(args.config) if args.config else (ROOT / "data" / "ab" / "control.yaml")
    cfg = Config.load(ctrl if ctrl.exists() else (ROOT / "config" / "config.yaml"))
    if args.mode == "build":
        build(cfg, args.driver, args.matches, reseed=args.reseed_opp)
    else:
        for ck in args.ckpt:
            evaluate(cfg, ck)


if __name__ == "__main__":
    main()
