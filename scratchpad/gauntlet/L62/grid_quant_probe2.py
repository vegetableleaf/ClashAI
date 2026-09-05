"""Follow-up: split the quantisation error into X and Y, get both pitches, and resolve the sign
per side (mirror as the engine env does for icebow_side==1)."""
import csv, sys, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.actions import ActionSpace

def acts(grid):
    cfg = Config.load("config/config.yaml")
    cfg.data.setdefault("action", {})["grid"] = list(grid)
    return ActionSpace(cfg)
def cell_xy(A, cell):
    nx, ny = A.cell_center(int(cell) % A.gw, int(cell) // A.gw)
    return nx * 18.0, (1.0 - ny) * 32.0
def xy_cell(A, tx, ty):
    gx, gy = A.coords_to_grid(tx / 18.0, 1.0 - ty / 32.0)
    return gy * A.gw + gx

rows = []
with open("data/royaleapi/crawl2/plays_ext.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["attr_card"] == "x-bow" and r["x_units"] and r["y_units"]:
            rows.append((float(r["x_units"]) / 1000.0, float(r["y_units"]) / 1000.0, r["attr_s"]))

for grid in ([18, 24], [18, 32]):
    A = acts(grid)
    px = abs(cell_xy(A, 1)[0] - cell_xy(A, 0)[0])
    py = abs(cell_xy(A, A.gw)[1] - cell_xy(A, 0)[1])
    x0, x1 = cell_xy(A, 0)[0], cell_xy(A, A.gw - 1)[0]
    yA, yB = cell_xy(A, 0)[1], cell_xy(A, (A.gh - 1) * A.gw)[1]
    dx = np.array([cell_xy(A, xy_cell(A, tx, ty))[0] - tx for tx, ty, _ in rows])
    dy = np.array([cell_xy(A, xy_cell(A, tx, ty))[1] - ty for tx, ty, _ in rows])
    # + = away from the enemy tower, per side (blue attacks +y, red attacks -y)
    back = np.array([d if s == "red" else -d for d, (_, _, s) in zip(dy, rows)])
    print(f"grid {A.gw}x{A.gh}: x pitch {px:.3f} tiles (cols span {x0:.2f}..{x1:.2f}) | "
          f"y pitch {py:.3f} tiles (rows span {yA:.2f}..{yB:.2f})")
    print(f"   |dx| mean {np.abs(dx).mean():.3f} p99 {np.percentile(np.abs(dx),99):.3f} max {np.abs(dx).max():.3f}"
          f" | |dy| mean {np.abs(dy).mean():.3f} p99 {np.percentile(np.abs(dy),99):.3f} max {np.abs(dy).max():.3f}")
    print(f"   BACKWARD (toward own king) tiles: mean {back.mean():+.3f} p99 {np.percentile(back,99):+.3f} "
          f"max {back.max():+.3f} | >0.5 tile {(back>0.5).mean()*100:.2f}%  >1.0 tile {(back>1.0).mean()*100:.2f}%")
