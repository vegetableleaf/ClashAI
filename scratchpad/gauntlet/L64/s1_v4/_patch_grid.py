import re
def sub(path, pairs):
    s = open(path, encoding="utf-8", newline="").read()
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:60], s.count(old))
        s = s.replace(old, new)
    open(path, "w", encoding="utf-8", newline="").write(s)

sub("pipeline/model_v3.py", [(
'''def _fourier(xy: torch.Tensor, n: int = 8) -> torch.Tensor:''',
'''def cell_label(xy: torch.Tensor, grid: str = "floor", gx: int = GRID_X, gy: int = GRID_Y) -> torch.Tensor:
    """Placement LABEL cell. ``floor``: ``cell_index`` (the v3 checkpoints). ``lattice``: pro placements sit on the
    500-unit lattice, i.e. x * 36 is an integer to +-0.002, so floor let a 1-unit jitter in the crawl (500k vs 500k-1,
    random at the same point) flip the label one cell (§5cs.70); round makes lattice points the cell centres."""
    if grid == "floor":
        return cell_index(xy, gx, gy)
    if grid != "lattice":
        raise ValueError(f"grid {grid!r}")
    cx = torch.round(xy[..., 0] * gx).long().clamp_(0, gx - 1)
    cy = torch.round(xy[..., 1] * gy).long().clamp_(0, gy - 1)
    return cy * gx + cx


def tile_of_cell(cell: torch.Tensor) -> torch.Tensor:
    """Half-tile cell id -> 1-tile id on the (GRID_X // 2, GRID_Y // 2) grid (pairs of adjacent half-cells)."""
    return (cell // GRID_X // 2) * (GRID_X // 2) + (cell % GRID_X) // 2


def cell_xy(cell: int, grid: str = "floor", gx: int = GRID_X, gy: int = GRID_Y) -> tuple[float, float]:
    """Inverse of ``cell_label``: board-frame (x, y) in [0, 1] -- the cell centre under ``floor``, the lattice point
    under ``lattice`` (so the engine places where the pros place, not 250 units off)."""
    cell = int(cell)
    off = 0.5 if grid == "floor" else 0.0
    return (cell % gx + off) / gx, (cell // gx + off) / gy


def _fourier(xy: torch.Tensor, n: int = 8) -> torch.Tensor:''')])

sub("pipeline/train_s1.py", [
('''from .model_v3 import (GRID_X, GRID_Y, N_SLOTS, S1Model, VALUE_CLASSES, cell_index, hand_mask_from_sc,''',
 '''from .model_v3 import (GRID_X, GRID_Y, N_SLOTS, S1Model, VALUE_CLASSES, cell_index, cell_label, hand_mask_from_sc,
                       tile_of_cell,'''),
('''def losses(model: S1Model, b: dict, mirror: bool) -> tuple[torch.Tensor, dict]:''',
 '''def losses(model: S1Model, b: dict, mirror: bool, grid: str = "floor") -> tuple[torch.Tensor, dict]:'''),
('''        cell_t = cell_index(xy[play])''', '''        cell_t = cell_label(xy[play], grid)'''),
('''def evaluate(model: S1Model, rows: Rows, bs: int = 512) -> dict:''',
 '''def evaluate(model: S1Model, rows: Rows, bs: int = 512, grid: str = "floor") -> dict:'''),
('''            t_half = cell_index(xy)
            pred = logits.argmax(-1)''', '''            t_half = cell_label(xy, grid)
            pred = logits.argmax(-1)'''),
('''            t_tile = cell_index(xy, GRID_X // 2, GRID_Y // 2)
            tile_ok''', '''            t_tile = cell_index(xy, GRID_X // 2, GRID_Y // 2) if grid == "floor" else tile_of_cell(t_half)
            tile_ok'''),
('''def baseline(arrs: dict) -> dict:''', '''def baseline(arrs: dict, grid: str = "floor") -> dict:'''),
('''        c = cell_index(xy, gx, gy).numpy()''',
 '''        c = (cell_index(xy, gx, gy) if grid == "floor" else
             (cell_label(xy, grid) if name == "half" else tile_of_cell(cell_label(xy, grid)))).numpy()'''),
('''    ap.add_argument("--tag", default="", help="checkpoint name suffix: s1_<deck>[_<tag>]_s<seed>.pt (default: none)")''',
 '''    ap.add_argument("--tag", default="", help="checkpoint name suffix: s1_<deck>[_<tag>]_s<seed>.pt (default: none)")
    ap.add_argument("--grid", default="floor", choices=("floor", "lattice"),
                    help="placement label convention (model_v3.cell_label); stored in the checkpoint args")'''),
('''        r = baseline(arrs)''', '''        r = baseline(arrs, a.grid)'''),
('''            loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5)''',
 '''            loss, parts = losses(model, b, mirror=(not a.no_mirror) and rng.random() < 0.5, grid=a.grid)'''),
('''        ev = evaluate(model, va)''', '''        ev = evaluate(model, va, grid=a.grid)'''),
('''    ev_tr = evaluate(model, sub)''', '''    ev_tr = evaluate(model, sub, grid=a.grid)'''),
])

sub("pipeline/eval_s1.py", [
('''            ev = evaluate(model, rows)''', '''            ev = evaluate(model, rows, grid=args.get("grid", "floor"))'''),
('''                   "trained_on": str(args.get("data"))})''',
 '''                   "trained_on": str(args.get("data")), "grid": args.get("grid", "floor")})'''),
])

sub("pipeline/engine_play.py", [
('''from pipeline.model_v3 import GRID_X, GRID_Y, N_SLOTS, S1Model, hand_mask_from_sc     # noqa: E402''',
 '''from pipeline.model_v3 import GRID_X, GRID_Y, N_SLOTS, S1Model, cell_xy, hand_mask_from_sc     # noqa: E402'''),
('''def cell_center(cell: int, gx: int = GRID_X, gy: int = GRID_Y) -> tuple[float, float]:
    """Inverse of ``model_v3.cell_index`` at the cell centre: board-frame (x, y) in [0, 1]."""
    cell = int(cell)
    return (cell % gx + 0.5) / gx, (cell // gx + 0.5) / gy''',
 '''def cell_center(cell: int, grid: str = "floor") -> tuple[float, float]:
    """Inverse of the checkpoint's label convention (``model_v3.cell_xy``): board-frame (x, y) in [0, 1]."""
    return cell_xy(cell, grid)'''),
('''def cell_to_engine(cell: int, mirror: bool) -> tuple[int, int]:
    x, y = cell_center(cell)''', '''def cell_to_engine(cell: int, mirror: bool, grid: str = "floor") -> tuple[int, int]:
    x, y = cell_center(cell, grid)'''),
('''    return model, {"epoch": ck.get("epoch"), "n_params": ck.get("n_params"), "deck": ck.get("deck"),''',
 '''    return model, {"epoch": ck.get("epoch"), "n_params": ck.get("n_params"), "deck": ck.get("deck"),
                   "grid": args.get("grid", "floor"),'''),
('''                x, y = cell_center(d["cell"])
                X, Y = cell_to_engine(d["cell"], mirror)''',
 '''                x, y = cell_center(d["cell"], grid)
                X, Y = cell_to_engine(d["cell"], mirror, grid)'''),
])
print("patched")
