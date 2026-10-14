"""Live audit of the Rocket+Tornado combo vs the river (owner fact 2026-10-14: a Tornado cannot drag GROUND troops over the river).

For every live decision with why == 'rocket_tornado', rebuild the rule's own body set from the logged model_bodies (the
BoardState the rule read: rocket_bodies on the same frame, own edge y = 32), check that best_tornado_centre reproduces the
logged aim, and split the bodies the rule counted as pulled (within the Tornado radius) by river side.
Own frame (tiles): my half y >= 16; river rows 15 <= y < 17; bridges x 2.5-4.5 and 13.5-15.5 (RoyaleSim passable_half_cells).
Run: python scratchpad/gauntlet/L74/reward/tornado_river_live.py $(grep -l '"why": "rocket_tornado"' <LOGS>)
"""
import glob
import json
import sys
from types import SimpleNamespace

import numpy as np

from pipeline.decision_options import (best_tornado_centre, cell_centres_tiles, log_air_traits, rocket_bodies,
                                       rocket_radius_tiles, tornado_radius_tiles)

LOGS = "scratchpad/gauntlet/L68/live_reader/live_play_2026101*.jsonl"


def on_bridge(x):
    return 2.5 <= x < 4.5 or 13.5 <= x < 15.5


def audit(path):
    opts, out = None, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if '"event": "start"' in line and opts is None:
                opts = json.loads(line).get("decision_options") or {}
            if '"why": "rocket_tornado"' not in line:
                continue
            d = json.loads(line)
            mb = d["public"]["model_bodies"]
            bs = SimpleNamespace(units=[SimpleNamespace(cls=u["cls"], side=u["side"], x=u["x"], y=u["y"], hp_frac=u["hp_frac"])
                                        for u in mb])
            mode, hitbox = opts.get("rocket_value_mode", "cost"), opts.get("rocket_value_hitbox", "centre")
            bodies = rocket_bodies(bs, mode)
            cx, cy = d["decision"]["xy"][0] * 18.0, d["decision"]["xy"][1] * 32.0
            grid_ok = {}
            for grid in ("lattice", "floor"):
                _, cell = best_tornado_centre(bodies, grid, hitbox, opts.get("rocket_value_min_y", 16.0))
                if cell is not None:
                    x, y = cell_centres_tiles(grid)
                    grid_ok[grid] = bool(abs(x[cell] - cx) < 1e-6 and abs(y[cell] - cy) < 1e-6)
            reach = tornado_radius_tiles() + (bodies[:, 4] if hitbox == "edge" else 0.0)
            blast = rocket_radius_tiles() + (bodies[:, 4] if hitbox == "edge" else 0.0)
            dist = np.hypot(bodies[:, 1] - cx, bodies[:, 2] - cy)
            inside = dist <= reach
            air = np.array([log_air_traits().get(int(c), (False, 0))[0] for c in bodies[:, 0]], dtype=bool)
            bx, by, val = bodies[:, 1], bodies[:, 2], bodies[:, 3]
            bridge = np.array([on_bridge(v) for v in bx], dtype=bool)
            far = inside & ~air & (by < 15.0)                                 # ground, enemy bank: held at y 15
            river = inside & ~air & (by >= 15.0) & (by < 17.0)                # ground on the river rows (a bridge)
            near = inside & ~air & (by >= 17.0)                               # ground, my bank
            # where the river holds a far-bank ground body: (its x, y 15), no x slide credited (conservative)
            far_hit = far & (np.hypot(bx - cx, 15.0 - cy) <= blast)
            # counterfactual: the rule's value with far-bank off-bridge ground bodies the held Rocket misses removed
            drop = far & ~bridge & ~far_hit
            keep = bodies[~drop]
            v_fix, _ = best_tornado_centre(keep, "lattice", hitbox, opts.get("rocket_value_min_y", 16.0))
            out.append(dict(file=path.split("live_play_")[-1], tick=d["tick"], xy=(round(cx, 2), round(cy, 2)),
                            V=opts.get("rocket_value"), value=float((inside * val).sum()), grid_ok=grid_ok,
                            n_far=int(far.sum()), far_value=float(val[far].sum()), n_far_hit=int(far_hit.sum()),
                            n_river=int(river.sum()), n_near=int(near.sum()), near_value=float(val[near].sum()),
                            n_air=int((inside & air).sum()), air_value=float(val[inside & air].sum()),
                            span=bool(far.any() and near.any()), v_fix=float(v_fix),
                            fires_fixed=bool(v_fix + 1e-9 >= (opts.get("rocket_value") or 0))))
    return out


if __name__ == "__main__":
    rows = [r for p in sorted(sys.argv[1:] or glob.glob(LOGS)) for r in audit(p)]
    for r in rows:
        print(json.dumps(r))
    n = len(rows)
    print(f"combos {n}; aim reproduced (lattice) {sum(r['grid_ok'].get('lattice', False) for r in rows)}; "
          f"aim y==16.0 {sum(r['xy'][1] == 16.0 for r in rows)}")
    print(f"counted far-bank ground {sum(r['n_far'] > 0 for r in rows)}; spanning both banks {sum(r['span'] for r in rows)}; "
          f"any far body Rocket-covered where held {sum(r['n_far_hit'] > 0 for r in rows)}; "
          f"would NOT fire without uncoverable far-bank ground {sum(not r['fires_fixed'] for r in rows)}")
    tv = sum(r["value"] for r in rows) or 1.0
    print(f"value share: far-bank ground {sum(r['far_value'] for r in rows) / tv:.3f}, my-bank ground "
          f"{sum(r['near_value'] for r in rows) / tv:.3f}, air {sum(r['air_value'] for r in rows) / tv:.3f}")
