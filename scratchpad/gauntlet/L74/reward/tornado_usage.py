"""Did --tornado-river ever change a live decision? (owner 10-14: "deploy the tornado fix for 40 matches just to see if it ever
gets put to use"). Over live logs: every logged decision row with Rocket AND Tornado in hand -> the combo rule's best Tornado
centre with the river rule off vs on, on the same logged bodies (decision_options.rocket_bodies / best_tornado_centre, the
deployed mode / hitbox / min_y / V). Counts: rows where off would fire but on does not (suppressed), rows where both fire at
different cells (re-aimed), and combos that actually fired with an enemy-bank ground body in Tornado reach (river relevant).
Decision rows are logged every 10 ticks (+ every play), so counts are sampled states, not distinct opportunities.
    python -m ... tornado_usage.py LOG [LOG ...]   (run from the repo root, PYTHONPATH=.)
"""
import json
import sys
from types import SimpleNamespace

import numpy as np

from pipeline.decision_options import best_tornado_centre, cell_centres_tiles, river_held, rocket_bodies, tornado_radius_tiles


def run(paths):
    c = dict(matches=0, rows=0, suppressed=0, reaimed=0, fired=0, fired_relevant=0)
    x, y = cell_centres_tiles("lattice")
    for path in paths:
        opts, seen = None, False
        for line in open(path, encoding="utf-8", errors="replace"):
            if opts is None and '"event": "start"' in line:
                opts = json.loads(line).get("decision_options") or {}
                continue
            if not line.startswith('{"event": "decision"'):
                continue
            d = json.loads(line)
            p = d.get("public") or {}
            if not {"Rocket", "Tornado"} <= {h.get("name") for h in p.get("own_hand", [])}:
                continue
            seen = True
            bs = SimpleNamespace(units=[SimpleNamespace(cls=u["cls"], side=u["side"], x=u["x"], y=u["y"], hp_frac=u["hp_frac"])
                                        for u in p.get("model_bodies") or []])
            b = rocket_bodies(bs, opts.get("rocket_value_mode", "cost"))
            hb, my, V = opts.get("rocket_value_hitbox", "centre"), opts.get("rocket_value_min_y", 16.0), opts.get("rocket_value", 9.0)
            v0, c0 = best_tornado_centre(b, "lattice", hb, my)
            v1, c1 = best_tornado_centre(b, "lattice", hb, my, river=True)
            c["rows"] += 1
            c["suppressed"] += int(v0 >= V > v1)
            c["reaimed"] += int(v0 >= V and v1 >= V and c0 != c1)
            if (d.get("decision") or {}).get("why") == "rocket_tornado":
                c["fired"] += 1
                if c1 is not None and len(b):
                    held = river_held(b)
                    reach = np.hypot(b[:, 1] - x[c1], b[:, 2] - y[c1]) <= tornado_radius_tiles()
                    c["fired_relevant"] += int((held & reach).any())
        c["matches"] += int(seen)
    return c


if __name__ == "__main__":
    r = run(sys.argv[1:])
    print(json.dumps(r))
    print(f"{len(sys.argv) - 1} logs; {r['matches']} with Rocket+Tornado in hand at some point; {r['rows']} sampled rows: the river rule "
          f"SUPPRESSED a combo on {r['suppressed']}, RE-AIMED one on {r['reaimed']}; combos fired {r['fired']} "
          f"({r['fired_relevant']} with enemy-bank ground in reach)")
