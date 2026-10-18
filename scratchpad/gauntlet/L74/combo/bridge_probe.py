"""L74 combo (10-17): how the SIM's Tornado moves GROUND troops at and near a bridge (item 5 of the combo rules: the bridge-edge hold).
Red units placed already deployed (MatchSetup.spawns); Blue casts a Tornado from hand; positions every tick for 30 ticks.
Engine frame millitiles (Blue at the bottom); water y 15000..17000 except the bridges x 2500..4500 / 13500..15500. Red walks toward
-y (toward Blue). The board frame of the combo rule (me = Blue at the bottom) is x / 1000, 32 - y / 1000.
    PYTHONPATH=<repo> ROYALE_RUNTIME=fork36-linux python bridge_probe.py [out.json]"""
import json
import sys

from pipeline.royale_env import RustEngine, heroiw
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode, SpawnSpec

K = 18
RED, BLUE = 1, 0
CASES = {  # name: (red card, spawn (x, y) mt engine frame, tornado (x, y))
    "on_bridge_centre_in_river": ("Knight", (3500, 16000), (8500, 16000)),     # the 182814 geometry: centre off the bridge, in the river rows
    "on_bridge_centre_land_near": ("Knight", (3500, 16000), (6500, 13500)),    # centre on Blue's land beside the bridge exit
    "on_bridge_centre_land_far": ("Knight", (3500, 16000), (8500, 13000)),
    "on_bridge_along": ("Knight", (3500, 16500), (3500, 13500)),               # pulled along the bridge
    "bank_in_column_centre_in_river": ("Knight", (3500, 17600), (8500, 16000)),  # Red bank, bridge column, walking onto the bridge
    "ramrider_bank_in_column_river": ("RamRider", (3500, 17500), (8500, 16000)),  # 182814: Ram Rider entering the left bridge
    "bank_off_column_centre_in_river": ("Knight", (6500, 17600), (8500, 16000)),  # held at the bank, slides along it
    "bank_in_column_centre_land": ("Knight", (3500, 17600), (7000, 13500)),
    "giant_on_bridge_centre_in_river": ("Giant", (3500, 16000), (8500, 16000)),  # slow body (pull step ~ catalog speed)
}
FILL = ["Knight", "Archer", "Giant", "Musketeer", "Fireball", "Arrows", "Skeletons", "Goblins"]


def run(case):
    card, (sx, sy), (tx, ty) = CASES[case]
    c = RustEngine(**heroiw.engine_options())
    ids = {x.name: x.card_id for x in c.cards()}
    blue = [ids["Tornado"]] + [ids[n] for n in FILL[:7]]
    red = [ids[n] for n in FILL]
    c.reset(1, MatchSetup(decks=[blue, red], shuffle=ShuffleMode.NONE, start_tick=200, elixir_milli=[10000, 10000],
                          spawns=[SpawnSpec(RED, ids[card], sx * K, sy * K)]))
    b = c._battle
    (r,) = c.step([DeployCommand(BLUE, 0, tx * K, ty * K)], 0)
    out = {"case": case, "card": card, "spawn": [sx, sy], "tap": [tx, ty], "cast": str(r.status), "ticks": []}
    for t in range(30):
        c.step([], 1)
        out["ticks"].append([t + 1, [[u[1], u[2] // K, u[3] // K] for u in b.debug_units() if u[1] == card]])
    return out


if __name__ == "__main__":
    res = [run(k) for k in CASES]
    for o in res:
        tr = [(t, rows[0][1], rows[0][2]) for t, rows in o["ticks"] if rows]
        print(o["case"], o["card"], "spawn", o["spawn"], "tornado", o["tap"], o["cast"])
        print("   " + " ".join(f"t{t}:({x},{y})" for t, x, y in tr[::3]) + f"  end t{tr[-1][0]}:({tr[-1][1]},{tr[-1][2]})")
    if len(sys.argv) > 1:
        json.dump(res, open(sys.argv[1], "w"))
