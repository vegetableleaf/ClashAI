"""The FUNCTIONAL test of the owner's claim: does grid quantisation ever push a real pro x-bow
from 'reaches the enemy princess tower' to 'does not reach'? x-bow reach 11.5 tiles centre-to-centre
+ 1.5 tile tower radius = 13.0 to tower CENTRE (engine-measured 13.04, HANDOFF 5cs.43)."""
import csv, sys, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.actions import ActionSpace
from clashrl.sim.env import SimMatchEnv

cfg = Config.load("config/config.yaml"); cfg.data.setdefault("action", {})["grid"] = [18, 24]
env = SimMatchEnv(cfg, seed=0); env.reset()
# sim towers are NORMALIZED; convert with the engine convention X = nx*18, Y = (1-ny)*32
TOW = {s: [(o.x * 18.0, (1.0 - o.y) * 32.0) for o in lst if not o.king]
       for s, lst in env.eng.towers.items()}
print("princess towers (tiles):", {k: [(round(a,2), round(b,2)) for a, b in v] for k, v in TOW.items()})

def acts(grid):
    c = Config.load("config/config.yaml"); c.data.setdefault("action", {})["grid"] = list(grid)
    return ActionSpace(c)
def cell_xy(A, cell):
    nx, ny = A.cell_center(int(cell) % A.gw, int(cell) // A.gw); return nx * 18.0, (1.0 - ny) * 32.0
def xy_cell(A, tx, ty):
    gx, gy = A.coords_to_grid(tx / 18.0, 1.0 - ty / 32.0); return gy * A.gw + gx

rows = []
with open("data/royaleapi/crawl2/plays_ext.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["attr_card"] == "x-bow" and r["x_units"] and r["y_units"]:
            rows.append((float(r["x_units"]) / 1000.0, float(r["y_units"]) / 1000.0, r["attr_s"]))
REACH = 13.0
# enemy princess towers, per side, in the 18x32 engine frame (blue attacks +y, red attacks -y)
# The enemy princess towers are the pair on the OTHER half from the placement -- this avoids the
# blue/red label whose mapping to sim side 0/1 is not established.
_LOW  = [t for v in TOW.values() for t in v if t[1] < 16]
_HIGH = [t for v in TOW.values() for t in v if t[1] > 16]
def d_min(tx, ty, s):
    tgt = _HIGH if ty < 16 else _LOW
    return min(((tx - a) ** 2 + (ty - b) ** 2) ** 0.5 for a, b in tgt)

for grid in ([18, 24], [18, 32]):
    A = acts(grid)
    lost = kept = inrange = 0
    worst = 0.0
    for tx, ty, s in rows:
        d0 = d_min(tx, ty, s)
        qx, qy = cell_xy(A, xy_cell(A, tx, ty))
        d1 = d_min(qx, qy, s)
        if d0 <= REACH:
            inrange += 1
            if d1 > REACH: lost += 1
            else: kept += 1
            worst = max(worst, d1 - d0)
    print(f"grid {A.gw}x{A.gh}: pro x-bows in reach {inrange}/{len(rows)} | quantisation puts "
          f"{lost} OUT of reach ({100*lost/max(1,inrange):.2f}%) | worst distance added {worst:+.3f} tiles")
