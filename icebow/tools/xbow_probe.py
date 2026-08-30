r"""X-BOW OUTCOME PROBE -- placement, lifetime, impact (owner spec, 2026-08-29).

    python tools/xbow_probe.py --matches 24
    python tools/xbow_probe.py --matches 24 --ckpt data/ab/policy_bank6.pt

WHY. The reward ledger reports `xbow_defends` at +0.07/match against `wincon_reach` +0.58 (5p),
and 5w's human anchor has a pro playing x-bow at 7.1% of plays for a 51% winrate while the m18000
reference plays it at 10.9% for 12.5%. Both point at x-bows being DEPLOYED but not PAYING OFF --
which the endpoint metric (`xbow%` = share of plays) cannot distinguish from x-bows being fine.
This measures what happens AFTER the deploy.

GEOMETRY (read from the engine at run time and printed, so it is auditable rather than asserted):
board 18 x 32 tiles, normalised 0..1. Enemy princess towers y=0.20, ours y=0.80, river y=0.50.
X-Bow reach 11.5 tiles, lifetime 30.0 s, 6 elixir, siege.

REGIONS ARE DERIVED FROM REACH, NOT HAND-DRAWN BANDS. A placement is OFFENSIVE if the x-bow can
reach an enemy princess tower from where it stands, and DEFENSIVE if it can reach OUR OWN princess
tower -- i.e. it covers the ground an attacker must occupy to hit that tower. Those are not
exclusive, so all four cells are reported. NEITHER is the owner's "too far back to hit their tower,
too far up front to defend" dead zone, and it is the cell worth watching.

/!\ DAMAGE ATTRIBUTION IS AN UPPER BOUND. Damage is credited by sampling the locked target's HP
each agent step and attributing the drop to the x-bow. If an ally is hitting the same target this
over-credits. Stated per row rather than hidden: read it as "damage that happened to the thing the
x-bow was shooting", not "damage the x-bow dealt".

/!\ SAMPLED AT agent_dt (0.6 s), NOT PER ENGINE TICK. Over a 30 s lifetime that is ~50 samples --
fine for lifetime and lock fractions, coarse for individual hits.

/!\ ALLY DAMAGE MITIGATED IS NOT DIRECTLY MEASURABLE and is not claimed. The defensive proxies are
damage dealt to the units it was shooting and how many of those targets died.
"""
import argparse
import collections
import math
import pathlib
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clashrl.config import Config                      # noqa: E402
from clashrl.sim.env import SimMatchEnv                # noqa: E402
from clashrl.sim import rollout_search as RS           # noqa: E402
import clashrl.sim.engine as E                         # noqa: E402

PRINCESS_HALF = 1.5


def _tiles(ax, ay, bx, by):
    return math.hypot((ax - bx) * E._TILES_X, (ay - by) * E._TILES_Y)


def classify(eng, x, y, reach):
    """OFFENSIVE / DEFENSIVE flags for a placement, from reach geometry."""
    foe = [t for t in eng.towers[1] if not t.king and t.alive]
    mine = [t for t in eng.towers[0] if not t.king and t.alive]
    off = any(_tiles(x, y, t.x, t.y) - PRINCESS_HALF <= reach for t in foe)
    dfn = any(_tiles(x, y, t.x, t.y) - PRINCESS_HALF <= reach for t in mine)
    return off, dfn


def probe(ckpt, cfg, matches, seed=1234):
    dev = torch.device("cpu")
    env = SimMatchEnv(cfg)
    env.rng.seed(seed)
    env.reset()
    net = RS.load_net(str(ckpt), env, dev)
    sr = RS.Searcher(env, net, dev, 12.0, 0, 4, 1.0, 0.25, cells=3)
    xi = next((i for i, s in enumerate(env.specs) if str(s.key) == "x_bow"), None)
    if xi is None:
        raise SystemExit("[xbow] x_bow is not in this deck")
    reach = float(env.specs[xi].reach)
    life = float(env.specs[xi].lifetime or 0.0)

    live, recs, done = {}, [], 0
    while done < matches:
        act, _ = sr.act(0)
        _o, _r, d, _info = env.step(act)
        eng = env.eng
        seen = set()
        for u in eng.units:
            if u.team != 0 or str(u.spec.key) != "x_bow":
                continue
            k = id(u)
            seen.add(k)
            r = live.get(k)
            if r is None:
                off, dfn = classify(eng, u.x, u.y, reach)
                r = live[k] = {"x": u.x, "y": u.y, "off": off, "dfn": dfn, "age": 0.0,
                               "n": 0, "t_tower": 0, "t_unit": 0, "t_idle": 0,
                               "dmg_tower": 0.0, "dmg_unit": 0.0, "kills": 0,
                               "locked_tower": False, "prev": None}
            r["age"] = float(u.age)
            r["n"] += 1
            tgt = u.target
            prev = r.get("prev")
            if isinstance(tgt, E.Tower):
                r["t_tower"] += 1
                r["locked_tower"] = True
            elif isinstance(tgt, E.Unit):
                r["t_unit"] += 1
            else:
                r["t_idle"] += 1
            if prev is not None:
                pobj, php = prev
                if pobj is tgt and tgt is not None:
                    drop = max(0.0, php - float(getattr(tgt, "hp", php)))
                    if isinstance(tgt, E.Tower):
                        r["dmg_tower"] += drop
                    else:
                        r["dmg_unit"] += drop
                elif isinstance(pobj, E.Unit) and float(getattr(pobj, "hp", 1.0)) <= 0.0:
                    r["kills"] += 1
            r["prev"] = (tgt, float(getattr(tgt, "hp", 0.0))) if tgt is not None else None
        for k in [k for k in live if k not in seen]:
            recs.append(live.pop(k))
        if d:
            for k in list(live):
                recs.append(live.pop(k))
            done += 1
            env.reset()
    return recs, reach, life, matches


def report(name, recs, reach, life, matches):
    if not recs:
        print("%-14s NO X-BOW DEPLOYED in %d matches" % (name, matches))
        return
    n = len(recs)
    cell = collections.Counter()
    for r in recs:
        if r["off"] and r["dfn"]:
            cell["BOTH"] += 1
        elif r["off"]:
            cell["OFFENSIVE"] += 1
        elif r["dfn"]:
            cell["DEFENSIVE"] += 1
        else:
            cell["NEITHER(dead)"] += 1
    ages = np.array([r["age"] for r in recs])
    expired = sum(1 for r in recs if r["age"] >= life - 1.0)
    off = [r for r in recs if r["off"]]
    dfn = [r for r in recs if r["dfn"] and not r["off"]]
    print("%s   %d x-bows in %d matches (%.2f/match)" % (name, n, matches, n / max(1, matches)))
    print("   PLACEMENT   " + "   ".join("%s=%d(%.0f%%)" % (k, v, 100.0 * v / n)
                                         for k, v in cell.most_common()))
    print("   LIFETIME    mean %.1fs of %.0fs   median %.1fs   reached-full %d/%d (%.0f%%)   "
          "died<5s %d (%.0f%%)"
          % (ages.mean(), life, float(np.median(ages)), expired, n, 100.0 * expired / n,
             int((ages < 5).sum()), 100.0 * float((ages < 5).mean())))
    lock = np.array([r["t_tower"] / max(1, r["n"]) for r in recs])
    unit = np.array([r["t_unit"] / max(1, r["n"]) for r in recs])
    idle = np.array([r["t_idle"] / max(1, r["n"]) for r in recs])
    print("   TIME SPENT  on TOWER %.0f%%   on UNITS %.0f%%   IDLE(no target) %.0f%%"
          % (100 * lock.mean(), 100 * unit.mean(), 100 * idle.mean()))
    if off:
        got = sum(1 for r in off if r["locked_tower"])
        dmg = np.array([r["dmg_tower"] for r in off])
        print("   OFFENSIVE   %d placed | got a TOWER LOCK %d (%.0f%%) | tower dmg/xbow mean %.0f "
              "median %.0f  [upper bound]"
              % (len(off), got, 100.0 * got / len(off), dmg.mean(), float(np.median(dmg))))
    if dfn:
        du = np.array([r["dmg_unit"] for r in dfn])
        kl = sum(r["kills"] for r in dfn)
        print("   DEFENSIVE   %d placed | unit dmg/xbow mean %.0f median %.0f | targets that died "
              "%d  [upper bound]" % (len(dfn), du.mean(), float(np.median(du)), kl))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=24)
    ap.add_argument("--ckpt", nargs="*", default=None)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    ctrl = pathlib.Path(args.config) if args.config else (ROOT / "data" / "ab" / "control.yaml")
    cfg = Config.load(ctrl if ctrl.exists() else (ROOT / "config" / "config.yaml"))
    cks = [pathlib.Path(c) for c in args.ckpt] if args.ckpt else \
        sorted((ROOT / "data" / "ab").glob("policy_*.pt"))
    print("scorer config: %s | %d matches/ckpt | greedy, search-free" % (ctrl.name, args.matches))
    print("geometry: board %.0fx%.0f tiles | x-bow reach 11.5 tiles | enemy towers y=0.20 | "
          "ours y=0.80\n" % (E._TILES_X, E._TILES_Y))
    for ck in cks:
        if not ck.exists():
            print("%-14s MISSING" % ck.name)
            continue
        recs, reach, life, m = probe(ck, cfg, args.matches)
        report(ck.stem.replace("policy_", ""), recs, reach, life, m)
        print()


if __name__ == "__main__":
    main()
