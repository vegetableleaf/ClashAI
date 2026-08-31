r"""CONTINUATION REPORT (P4 step 2) -- a checkpoint's follow-up behaviour vs the PRO anchors.

    PYTHONHASHSEED=0 python tools/continuation_report.py --matches 16 --ckpt <a.pt> [<b.pt> ...]

Measures, per checkpoint, greedy and search-free on FIXED seeds (paired across checkpoints):
  * inter-play gap distribution (median / p10 / p90) and play rate per minute;
  * AFTER-X-BOW: dt to the next own play and the follow-up card distribution;
  * AFTER-TESLA: same;
  * L1 distance between each follow-up distribution and the PRO population distribution.

PRO ANCHORS (population, n=24 players / 45,335 plays, HANDOFF 5ag -- measured 2026-08-31 from
icebow/data/royaleapi/crawl2; evaluation targets ONLY, never gradient, per the 5af owner ruling):
  gap median 3.85 s (p10 1.55, p90 10.15), rate 11.7/min
  after-bow   (median 5.5 s): knight .20 tesla .17 skeletons .17 the_log .16 ice_wizard .16
  after-tesla (median 4.2 s): skeletons .22 knight .19 the_log .18 ice_wizard .17

/!\ APPLES-TO-APPLES CAVEATS, stated rather than hidden:
  * The sim's opponents are not ladder opponents; a perfect policy would NOT necessarily match
    the pro distribution here. L1 distance is a compass, not a target to hit exactly.
  * Pro follow-ups are conditioned on REAL pushes; greedy eval sees the sim's meta pool.
  * Card names are normalised to base keys (evo suffixes stripped) on both sides.
"""
import argparse
import collections
import pathlib
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clashrl.config import Config                      # noqa: E402
from clashrl.sim.env import SimMatchEnv                # noqa: E402
from clashrl.sim import rollout_search as RS           # noqa: E402

SEEDS = [80_000 + 17 * i for i in range(64)]
PRO = {
    "gap_median": 3.85, "rate_per_min": 11.7,
    "after": {
        "x_bow": {"dt_median": 5.5, "dist": {"knight": .20, "tesla": .17, "skeletons": .17,
                                             "the_log": .16, "ice_wizard": .16}},
        "tesla": {"dt_median": 4.2, "dist": {"skeletons": .22, "knight": .19,
                                             "the_log": .18, "ice_wizard": .17}},
    },
}


def _base(key):
    k = str(key)
    for suf in ("_ev1", "_ev2", "_hero"):
        if k.endswith(suf):
            k = k[: -len(suf)]
    return k


def run(ckpt, cfg, matches):
    env = SimMatchEnv(cfg)
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
    plays_all = []                      # list of (match_idx, t_seconds, base_key)
    for mi, seed in enumerate(SEEDS[:matches]):
        env.rng.seed(seed)
        env.reset()
        done, step = False, 0
        while not done:
            act, _ = sr.act(0)
            if act[0] == 1:
                plays_all.append((mi, step * env.agent_dt, _base(env.deck_keys[act[1]])))
            _o, _r, done, _i = env.step(act)
            step += 1
    name = pathlib.Path(str(ckpt)).stem.replace("policy_", "")
    bym = collections.defaultdict(list)
    for mi, t, c in plays_all:
        bym[mi].append((t, c))
    gaps, follow = [], {"x_bow": [], "tesla": []}
    for mi, rows in bym.items():
        rows.sort()
        ts = [t for t, _ in rows]
        gaps += [b - a for a, b in zip(ts, ts[1:])]
        for i, (t, c) in enumerate(rows[:-1]):
            if c in follow:
                follow[c].append((rows[i + 1][0] - t, rows[i + 1][1]))
    if not gaps:
        print("%-20s NO PLAYS in %d matches" % (name, matches))
        return
    g = np.asarray(gaps)
    total_min = sum(max(t for t, _ in rows) for rows in bym.values() if rows) / 60.0
    print("%-20s plays=%d | gap median %.2fs (pro %.2f)  p10 %.2f  p90 %.2f | rate %.1f/min (pro %.1f)"
          % (name, len(plays_all), float(np.median(g)), PRO["gap_median"],
             float(np.percentile(g, 10)), float(np.percentile(g, 90)),
             len(plays_all) / max(0.1, total_min), PRO["rate_per_min"]))
    for card in ("x_bow", "tesla"):
        rows = follow[card]
        anchor = PRO["after"][card]
        if not rows:
            print("   after %-7s NO OCCURRENCES" % card)
            continue
        dts = np.asarray([d for d, _ in rows])
        cnt = collections.Counter(c for _, c in rows)
        n = len(rows)
        dist = {k: cnt.get(k, 0) / n for k in anchor["dist"]}
        other = 1.0 - sum(dist.values())
        l1 = sum(abs(dist[k] - v) for k, v in anchor["dist"].items()) + abs(other - (1.0 - sum(anchor["dist"].values())))
        top = ", ".join("%s %.0f%%" % (k, 100 * v / n) for k, v in cnt.most_common(4))
        print("   after %-7s n=%-4d dt median %.1fs (pro %.1f) | L1-to-pro %.3f | %s"
              % (card, n, float(np.median(dts)), anchor["dt_median"], l1, top))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=16)
    ap.add_argument("--ckpt", nargs="+", required=True)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    ctrl = pathlib.Path(args.config) if args.config else (ROOT / "data" / "ab" / "control.yaml")
    cfg = Config.load(ctrl if ctrl.exists() else (ROOT / "config" / "config.yaml"))
    print("continuation report | %d matches/ckpt | greedy, search-free | fixed seeds | pro anchors 5ag\n"
          % args.matches)
    for ck in args.ckpt:
        run(ck, cfg, args.matches)


if __name__ == "__main__":
    main()
