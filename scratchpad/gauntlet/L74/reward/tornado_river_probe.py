"""Tornado vs river probe (owner fact 2026-10-14: real CR holds a pulled GROUND troop at the bank; air crosses).

Red units are placed directly with MatchSetup.spawns (deployed, no deploy timer); Blue casts a Tornado from hand on
the other bank. Every tick for 40 ticks after the cast, every troop's position is recorded (millitiles).
Water (RoyaleSim passable_half_cells): y 15000..17000; bridges x 2500..4500 and 13500..15500.
Run: PYTHONPATH=<repo> ROYALE_RUNTIME=20261012-linux python tornado_river_probe.py [out.json]
"""
import json
import sys

from pipeline.royale_env import RustEngine, heroiw
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode, SpawnSpec

K = 18  # subtiles per millitile
RED, BLUE = 1, 0
CASES = {  # name: (red card, spawn (x, y) mt, tornado tap (x, y) mt)
    "knight_bank":     ("Knight",    (9000, 18000), (9500, 13500)),
    "skeletons_bank":  ("Skeletons", (9000, 18000), (9500, 13500)),
    "goblins_bank":    ("Goblins",   (9000, 18000), (9500, 13500)),
    "minions_bank":    ("Minions",   (9000, 18000), (9500, 13500)),   # air control
    "knight_bridge_lateral": ("Knight", (14500, 16000), (11500, 14500)),  # on the bridge, pull mostly toward water
    "knight_bridge_along":   ("Knight", (14500, 16500), (14500, 13500)),  # on the bridge, pull along it
}
FILL = ["Knight", "Archer", "Giant", "Musketeer", "Fireball", "Arrows", "Skeletons", "Goblins"]


def water(x, y):
    return 15000 <= y < 17000 and not (2500 <= x < 4500 or 13500 <= x < 15500)


def run(case, arm=None):
    card, (sx, sy), (tx, ty) = CASES[case]
    opts = heroiw.engine_options()
    if arm:
        opts = {"calibration_overrides": {**opts.get("calibration_overrides", {}), "status.ATTRACT_WATER_EDGE": arm}}
    c = RustEngine(**opts)
    ids = {x.name: x.card_id for x in c.cards()}
    blue = [ids["Tornado"]] + [ids[n] for n in FILL[:7]]
    red = [ids[n] for n in FILL]
    c.reset(1, MatchSetup(decks=[blue, red], shuffle=ShuffleMode.NONE, start_tick=200, elixir_milli=[10000, 10000],
                          spawns=[SpawnSpec(RED, ids[card], sx * K, sy * K)]))
    b = c._battle
    (r,) = c.step([DeployCommand(BLUE, 0, tx * K, ty * K)], 0)
    out = {"case": case, "arm": arm or "shipped", "card": card, "spawn": [sx, sy], "tap": [tx, ty],
           "cast": {"status": str(r.status), "x": r.x // K, "y": r.y // K}, "ticks": []}
    for t in range(40):
        c.step([], 1)
        rows = [(u[0], u[1], u[2] // K, u[3] // K, u[4]) for u in b.debug_units()]
        out["ticks"].append([t + 1, [[uid, name, x, y, dep, water(x, y)] for uid, name, x, y, dep in rows]])
    first = {u[0]: (u[2], u[3]) for u in out["ticks"][0][1]}
    per = {}
    for t, rows in out["ticks"]:
        for uid, name, x, y, dep, w in rows:
            p = per.setdefault(uid, dict(name=name, start=first.get(uid), min_y=y, water_ticks=0, crossed=False))
            p["min_y"] = min(p["min_y"], y)
            p["water_ticks"] += w
            p["crossed"] |= y < 15000
            p["end"] = (x, y)
    out["summary"] = per
    return out


if __name__ == "__main__":
    res = [run(k) for k in CASES] + [run("knight_bank", "walk_rule"), run("skeletons_bank", "walk_rule")]
    for o in res:
        print(o["case"], o["arm"], "cast", o["cast"])
        for uid, p in o["summary"].items():
            print("   uid", uid, p)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as f:
            json.dump(res, f)
