"""L64c: L62i probe re-run through the SIM trainer action space (_board_action_space, arena_box [0,0,1,1]) instead of the live-screen ActionSpace(cfg); the live space returns FRAME coords, which L62i read as board fractions (unit error)."""
"""Owner claim (2026-09-05): at action.grid 432 (18x24) the placement grid snaps an OFFENSIVE x-bow
one tile too far back, so it cannot reach the tower; 576 (18x32) would fix it.
Test on REAL pro x-bow placements from the crawl, through the SAME ActionSpace the trainer uses,
in the engine's coordinate convention (X = nx*18000, Y = (1-ny)*32000, 1000 units = 1 tile).
Read-only: touches no checkpoint, no running process."""
import csv, sys, numpy as np
sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.actions import ActionSpace
from clashrl.sim.env import _board_action_space

def acts(grid):
    cfg = Config.load("config/config.yaml")
    cfg.data.setdefault("action", {})["grid"] = list(grid)
    return _board_action_space(cfg)

def cell_xy(A, cell):
    nx, ny = A.cell_center(int(cell) % A.gw, int(cell) // A.gw)
    return nx * 18.0, (1.0 - ny) * 32.0            # tiles

def xy_cell(A, tx, ty):
    nx, ny = tx / 18.0, 1.0 - ty / 32.0
    gx, gy = A.coords_to_grid(nx, ny)
    return gy * A.gw + gx

rows = []
with open("data/royaleapi/crawl2/plays_ext.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["attr_card"] != "x-bow" or not r["x_units"] or not r["y_units"]:
            continue
        rows.append((float(r["x_units"]) / 1000.0, float(r["y_units"]) / 1000.0))
print(f"real pro x-bow placements with positions: {len(rows)}")
ty_all = np.array([t[1] for t in rows])
print(f"their tile_y: min {ty_all.min():.2f} p10 {np.percentile(ty_all,10):.2f} median "
      f"{np.median(ty_all):.2f} p90 {np.percentile(ty_all,90):.2f} max {ty_all.max():.2f}")

for grid in ([18, 24], [18, 32]):
    A = acts(grid)
    # row pitch straight from the grid itself
    y0 = cell_xy(A, 0 * A.gw)[1]; y1 = cell_xy(A, 1 * A.gw)[1]
    dy, err, sy = abs(y1 - y0), [], []
    for tx, ty in rows:
        qx, qy = cell_xy(A, xy_cell(A, tx, ty))
        err.append(((qx - tx) ** 2 + (qy - ty) ** 2) ** 0.5)
        sy.append(qy - ty)
    e, s = np.array(err), np.array(sy)
    print(f"grid {A.gw}x{A.gh} ({A.gw*A.gh} cells): row pitch {dy:.3f} tiles | "
          f"err mean {e.mean():.3f} p90 {np.percentile(e,90):.3f} max {e.max():.3f}")
    print(f"    signed dy (tiles, + = snapped FURTHER from the enemy tower): mean {s.mean():+.3f} "
          f"max {s.max():+.3f} | moved back >0.5: {(s>0.5).mean()*100:.1f}%  >0.75: {(s>0.75).mean()*100:.1f}%  "
          f">1.0: {(s>1.0).mean()*100:.2f}%")
