r"""RESPONSE-REGRET BENCHMARK (BRAINSTORM P1, HANDOFF 5ab power fix) -- v0.

    PYTHONHASHSEED=0 python tools/response_regret.py --matches 8 --ckpt data/policy_BEST_m18000_20260826.pt

At every ENEMY-PLAY EVENT (detected by the timestamp on `eng.last_deploy[1]` changing), this
clones the state and scores the full candidate set -- WAIT plus the policy's top cards at their
top cells -- through the measured 12 s horizon with the outcome-grounded Scorer, exactly the way
`Searcher.act` does. Regret = best_score - policy_score, on the SAME state with common random
numbers.

WHY THIS IS THE POWER FIX AND NOT JUST ANOTHER METRIC (5ab): control's >=6-elixir endpoint read
2.2% and 20.3% at two seeds of identical config -- a 9x spread that made the 4-arm A/B
underpowered ~10x. Regret is a PAIRED design: every candidate is scored on the same cloned state,
so match-level variance never enters the arm comparison. This is the instrument reward and
architecture changes get judged on from now on.

WHAT IT REUSES rather than rebuilds (the brainstorm's harness already exists inside Searcher):
`candidates()` enumerates WAIT-first; `_rollout()` plays each candidate forward H=12 s and scores
princess-tower fractions; `_rs_seed` gives every candidate at one decision the same RNG stream.

/!\ HONESty NOTES
* The policy's own action drives the match forward, so regret is measured ON the policy's state
  distribution. A different policy visits different states; cross-checkpoint comparisons are
  paired per-seed, not per-state.
* `_rollout` replays the opponent's actual RNG (the oracle-fork problem, 4x). v0 accepts that:
  it is the ORACLE-regret view. `--reseed-opp` switches to sampled futures (belief view).
* Events within `--min-gap` seconds of the previous sampled event are skipped to bound cost.
* Rows go to a CSV so buckets (spells, x-bow, per-enemy-family) are sliced offline without rerun.

Per-event CSV row:
    seed, t, enemy_base, enemy_kind, pol_gate, pol_base, best_gate, best_base,
    pol_score, best_score, regret, n_cands, wait_score, best_same_card_score
`best_same_card_score` lets card-regret vs placement-regret be separated offline:
placement regret = best_same_card - pol; card regret = best - best_same_card (when pol played).
"""
import argparse
import collections
import csv
import pathlib
import sys
import time

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clashrl.config import Config                      # noqa: E402
from clashrl.sim.env import SimMatchEnv                # noqa: E402
from clashrl.sim import rollout_search as RS           # noqa: E402


def score_event(sr, env):
    """Candidate sweep at the current state. Returns (pol, cands, scores) or None."""
    pol, (cq_m, ceq, gq_m, playable) = sr.greedy_action()
    cands = sr.candidates(cq_m, ceq, playable)
    if pol not in cands:
        cands = list(cands) + [pol]
    if len(cands) < 2:
        return None
    # mirror Searcher.act's per-decision setup so _rollout sees the state it expects
    sr._rs_ctr += 1
    sr._rs_seed = 1_000_003 * sr._rs_ctr + 7
    sr._clamped_now = 0
    sr._jit_active = False
    scores = [sr._rollout(a) for a in cands]
    return pol, list(cands), scores


def run(ckpt, cfg, matches, seeds, min_gap, reseed_opp, out_csv):
    dev = torch.device("cpu")
    env = SimMatchEnv(cfg)
    net = RS.load_net(str(ckpt), env, dev)
    # interval=0: sr.act() is never used to override; we drive the sweep ourselves
    sr = RS.Searcher(env, net, dev, 12.0, 0, 4, 1.0, 0.25, cells=3, reseed_opp=reseed_opp)

    rows, regrets = [], []
    agree = wait_fp = wait_fn = played = waited = 0
    t_bench = 0.0
    for seed in seeds[:matches]:
        env.rng.seed(seed)
        env.reset()
        last_t = -1e9          # enemy-deploy timestamp already seen
        last_sample = -1e9     # engine time of the last SAMPLED event
        done = False
        while not done:
            eng = env.eng
            ld = eng.last_deploy.get(1)
            if ld is not None and ld[3] > last_t:
                last_t = ld[3]
                if eng.t - last_sample >= min_gap and not eng.done:
                    last_sample = eng.t
                    t0 = time.perf_counter()
                    out = score_event(sr, env)
                    t_bench += time.perf_counter() - t0
                    if out is not None:
                        pol, cands, scores = out
                        pi = cands.index(pol)
                        bi = int(np.argmax(scores))
                        regret = scores[bi] - scores[pi]
                        regrets.append(regret)
                        agree += (bi == pi)
                        wait_i = cands.index((0, 0, 0)) if (0, 0, 0) in cands else None
                        wait_s = scores[wait_i] if wait_i is not None else float("nan")
                        if pol[0] == 1:
                            played += 1
                            if wait_i is not None and bi == wait_i:
                                wait_fp += 1          # played when WAIT was best
                            same = [scores[j] for j, c in enumerate(cands)
                                    if c[0] == 1 and c[1] == pol[1]]
                            best_same = max(same) if same else scores[pi]
                        else:
                            waited += 1
                            if cands[bi][0] == 1:
                                wait_fn += 1          # waited when a play was best
                            best_same = scores[pi]
                        spec = ld[0]
                        rows.append([seed, round(float(eng.t), 2), spec.base, spec.kind,
                                     pol[0], (env.specs[pol[1]].base if pol[0] else "WAIT"),
                                     cands[bi][0],
                                     (env.specs[cands[bi][1]].base if cands[bi][0] else "WAIT"),
                                     round(scores[pi], 4), round(scores[bi], 4),
                                     round(regret, 4), len(cands), round(wait_s, 4),
                                     round(best_same, 4)])
            act, _ = sr.act(0)                 # interval=0 -> pure policy greedy, no override
            _o, _r, done, _i = env.step(act)
        # match ended; next seed

    r = np.asarray(regrets) if regrets else np.zeros(1)
    name = pathlib.Path(ckpt).stem.replace("policy_", "")
    print("%-22s events=%d | regret mean %.4f  median %.4f  p90 %.4f | top-1 agree %.0f%%"
          % (name, len(regrets), r.mean(), float(np.median(r)),
             float(np.percentile(r, 90)), 100.0 * agree / max(1, len(regrets))))
    print("   WAIT: policy played %d (FP-vs-WAIT %d = %.0f%%) | waited %d (FN missed-play %d = %.0f%%)"
          % (played, wait_fp, 100.0 * wait_fp / max(1, played),
             waited, wait_fn, 100.0 * wait_fn / max(1, waited)))
    fam = collections.defaultdict(list)
    for row in rows:
        fam[row[3]].append(row[10])
    for k in sorted(fam):
        v = np.asarray(fam[k])
        print("   enemy %-9s n=%-4d regret mean %.4f  p90 %.4f" % (k, len(v), v.mean(),
                                                                   float(np.percentile(v, 90))))
    print("   bench overhead %.1fs" % t_bench)
    if out_csv:
        new = not pathlib.Path(out_csv).exists()
        with open(out_csv, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["ckpt", "seed", "t", "enemy_base", "enemy_kind", "pol_gate",
                            "pol_base", "best_gate", "best_base", "pol_score", "best_score",
                            "regret", "n_cands", "wait_score", "best_same_card_score"])
            for row in rows:
                w.writerow([name] + row)
        print("   %d rows -> %s" % (len(rows), out_csv))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=8)
    ap.add_argument("--ckpt", nargs="+", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--min-gap", type=float, default=2.0,
                    help="min engine seconds between sampled events (cost bound)")
    ap.add_argument("--reseed-opp", action="store_true",
                    help="belief view: sampled opponent futures instead of the oracle fork")
    ap.add_argument("--csv", default="data/bench/response_regret.csv")
    args = ap.parse_args()
    ctrl = pathlib.Path(args.config) if args.config else (ROOT / "data" / "ab" / "control.yaml")
    cfg = Config.load(ctrl if ctrl.exists() else (ROOT / "config" / "config.yaml"))
    seeds = [90_000 + 13 * i for i in range(64)]      # FIXED seed list -- paired across ckpts
    print("response-regret v0 | %d matches/ckpt | H=12s cells=3 | min-gap %.1fs | %s view | seeds fixed"
          % (args.matches, args.min_gap, "BELIEF" if args.reseed_opp else "ORACLE"))
    for ck in args.ckpt:
        run(ck, cfg, args.matches, seeds, args.min_gap, args.reseed_opp, args.csv)


if __name__ == "__main__":
    main()
