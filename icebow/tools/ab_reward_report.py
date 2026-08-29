r"""Compare the reward-A/B arms on the metrics that actually move (HANDOFF 5p/5q).

    python tools/ab_reward_report.py                      # every arm found in data/ab
    python tools/ab_reward_report.py --matches 24         # more matches per arm = tighter
    python tools/ab_reward_report.py --ckpt a.pt b.pt     # arbitrary checkpoints instead

WHY NOT WINRATE. At 150 matches winrate carries about +/-5pp, which cannot separate these arms at
any sample size we can afford -- the m5400-vs-m18000 gap needed 150 matches/arm to reach 2 sigma.
The MECHANISM metrics move by 35x in the same comparison and are averaged over thousands of steps:

    metric              m18000 reference     the pathology (m5400)
    elixir >= 6              35.4%                   1.0%
    x_bow share of plays     12.5%                   2.7%
    plays                     8.5%                  12.5%

So those are the endpoints. Winrate stays in the table as a GUARDRAIL -- "did this break anything"
-- not as the discriminator.

/!\ EVERY ARM IS EVALUATED UNDER THE **CONTROL** CONFIG, not its own. The arms differ in reward
weights, and reward does not affect a frozen greedy policy's actions at all -- but it does change
the term ledger, so scoring each arm under its own config would compare policies AND scorers at
once. One scorer, four policies.

/!\ HOARDING IS THE NAMED RISK OF THE `bank*` ARMS, and it does not show up in the elixir
histogram -- a hoarding policy looks GREAT there. `wincon_reach: 2.0` already failed this way:
leak fired 24x and crowns taken HALVED. So `leak` and `crowns` are printed next to the target
metrics, and an arm that lifts banking while lifting leak has bought the failure, not fixed it.

/!\ PYTHONHASHSEED must be pinned for cross-process comparability -- MEASURED at 1.9847 vs 2.0383
elixir mean between two unpinned processes. This script pins its own RNG and env seed, but run it
with PYTHONHASHSEED=0 to match how the arms were trained.
"""
import argparse
import collections
import math
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np                                          # noqa: E402
import torch                                                # noqa: E402

from clashrl.config import Config                           # noqa: E402
from clashrl.sim.env import SimMatchEnv                     # noqa: E402
from clashrl.sim import rollout_search as RS                # noqa: E402

ABDIR = ROOT / "data" / "ab"
WINCON = "x_bow"


def evaluate(ckpt, cfg, matches, seed=1234):
    """Mechanism metrics for one checkpoint, greedy and SEARCH-FREE (interval 0).

    Search off on purpose: it would replace the policy's own decisions, which are exactly what is
    being measured. This reports what the POLICY learned, not what a searcher can do on top of it.
    """
    dev = torch.device("cpu")
    env = SimMatchEnv(cfg)
    env.rng.seed(seed)
    env.reset()
    net = RS.load_net(str(ckpt), env, dev)
    sr = RS.Searcher(env, net, dev, 12.0, 0, 4, 1.0, 0.25, cells=3)

    cards = collections.Counter()
    elix, plays, steps, done = [], 0, 0, 0
    wins = losses = draws = 0
    while done < matches:
        act, _ = sr.act(0)
        elix.append(float(env.eng.elixir[0]))
        steps += 1
        if act[0] == 1:
            plays += 1
            cards[env.deck_keys[act[1]]] += 1
        _o, _r, d, info = env.step(act)
        if d:
            out = info.get("outcome")
            wins += out == "win"
            losses += out == "loss"
            draws += out not in ("win", "loss")
            done += 1
            env.reset()

    e = np.asarray(elix)
    pr = np.asarray([v / max(1, plays) for v in cards.values()])
    ledger = env.rw_stats.run_summary()
    n = max(1, ledger["matches"])

    def term(name):
        t = ledger["terms"].get(name)
        return (t["total"] / n) if t else 0.0

    return {
        "elixir_ge6": 100.0 * float((e >= 6.0).mean()),
        "elixir_mean": float(e.mean()),
        "wincon_share": 100.0 * cards.get(WINCON, 0) / max(1, plays),
        "plays": 100.0 * plays / max(1, steps),
        "distinct": len(cards),
        "play_entropy": float(-(pr * np.log(pr)).sum()) if plays else 0.0,
        "entropy_max": math.log(max(2, env.n_cards)),
        "winrate": 100.0 * wins / max(1, done),
        "record": "%dW-%dL-%dD" % (wins, losses, draws),
        "leak": term("leak"),
        "crowns": term("take_enemy_tower") + term("lose_own_tower"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=16)
    ap.add_argument("--ckpt", nargs="*", default=None, help="explicit checkpoints instead of data/ab")
    ap.add_argument("--config", default=None, help="scorer config (default: the control arm)")
    args = ap.parse_args()

    if os.environ.get("PYTHONHASHSEED") != "0":
        print("[ab-report] /!\\ PYTHONHASHSEED is not 0; cross-process numbers drift "
              "(measured 1.9847 vs 2.0383). Re-run with PYTHONHASHSEED=0 for comparable figures.")

    # ONE scorer for every arm -- see the module docstring.
    ctrl = pathlib.Path(args.config) if args.config else (ABDIR / "control.yaml")
    cfg = Config.load(ctrl if ctrl.exists() else (ROOT / "config" / "config.yaml"))

    if args.ckpt:
        targets = [(pathlib.Path(c).stem, pathlib.Path(c)) for c in args.ckpt]
    else:
        targets = []
        for name in ("control", "restraint", "bank2", "bank6"):
            for cand in (ABDIR / ("policy_%s_best.pt" % name), ABDIR / ("policy_%s.pt" % name)):
                if cand.exists():
                    targets.append((name, cand))
                    break
    if not targets:
        raise SystemExit("[ab-report] no arm checkpoints found in %s -- has the A/B run yet?" % ABDIR)

    print("scorer config: %s | %d matches/arm | greedy, search-free" % (ctrl.name, args.matches))
    print("%-11s %8s %7s %9s %7s %6s %7s %9s %7s %7s"
          % ("arm", ">=6 el%", "mean", "xbow%", "plays%", "dist", "playH", "winrate", "leak", "crowns"))
    rows = {}
    for name, path in targets:
        r = evaluate(path, cfg, args.matches)
        rows[name] = r
        print("%-11s %8.1f %7.2f %9.1f %7.1f %6d %7.2f %8.1f%% %7.2f %7.2f"
              % (name[:11], r["elixir_ge6"], r["elixir_mean"], r["wincon_share"], r["plays"],
                 r["distinct"], r["play_entropy"], r["winrate"], r["leak"], r["crowns"]))

    if "control" in rows:
        c = rows["control"]
        print("\nvs control (the endpoints that matter):")
        for name, r in rows.items():
            if name == "control":
                continue
            flag = ""
            # An arm that lifts banking AND leak has bought hoarding, which is the failure
            # `wincon_reach: 2.0` already produced -- say so rather than calling it a win.
            if r["elixir_ge6"] > c["elixir_ge6"] and r["leak"] < c["leak"] - 0.05:
                flag = "   /!\\ banking up but LEAK WORSE -- check for hoarding, not a fix"
            print("  %-11s >=6 elixir %+6.1f pp | xbow %+6.1f pp | winrate %+5.1f pp%s"
                  % (name, r["elixir_ge6"] - c["elixir_ge6"], r["wincon_share"] - c["wincon_share"],
                     r["winrate"] - c["winrate"], flag))
        print("\nREMINDER: one seed per arm is a SCREEN. Gate collapse has a measured 4/6 escape "
              "rate,\nso confirm any winner at 3 seeds before acting on it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
