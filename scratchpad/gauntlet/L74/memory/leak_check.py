"""S3 target-leak check: for PLAY rows of the pro dataset, does the row's memory already contain the play being predicted?

Leak = a visible (vis <= t) own play event with tick >= the row tick t, or a visible own play of the SAME card within 2 ticks
before t at the label's tile (the row's own play logged slightly earlier than its play frame).
Usage: python leak_check.py <dataset.npz> <memory_tables.npz> [n_rows]"""
import sys
import zipfile

import numpy as np

sys.path.insert(0, __file__.rsplit("scratchpad", 1)[0])
from pipeline import match_memory as M  # noqa: E402


def arr(path, keys):
    with zipfile.ZipFile(path) as zf:
        return {k: np.load(zf.open(k + ".npy"), allow_pickle=False) for k in keys}


def main():
    ds, mem = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    d = arr(ds, ("tick", "y_gate"))
    z = np.load(mem)
    packed = {k[4:]: z[k] for k in z.files if k.startswith("tab_")}
    row_tab = z["row_tab"]
    rows = np.flatnonzero((d["y_gate"] == 1) & (row_tab >= 0))
    rows = np.random.default_rng(0).choice(rows, min(n, len(rows)), replace=False)
    mine_c, play_c = M._COL["mine"], M._COL["is_play"]
    late = same2 = vis_own = 0
    gaps = []
    for s in range(0, len(rows), 4096):
        ids = rows[s:s + 4096]
        E = M.gather_rows(packed, row_tab[ids])
        t = d["tick"][ids].astype(np.int64)[:, None]
        own = (E["vals"][..., mine_c] > 0) & (E["vals"][..., play_c] > 0)
        vis = E["vis"] <= t
        ov = own & vis
        vis_own += int(ov.any(1).sum())
        late += int((ov & (E["tick"] >= t)).any(1).sum())
        same2 += int((ov & (E["tick"] >= t - 2)).any(1).sum())
        newest = np.where(ov, E["tick"], -10 ** 9).max(1)
        gaps.append((t[:, 0] - newest)[newest > -10 ** 9])
    g = np.concatenate(gaps)
    print(f"play rows checked {len(rows)}; with a visible own play {vis_own}")
    print(f"visible own play with tick >= row tick (LEAK): {late}")
    print(f"visible own play within 2 ticks before the row: {same2}")
    print(f"row tick - newest visible own play tick: min {g.min()}, p1 {np.percentile(g, 1):.0f}, median {np.median(g):.0f}")
    assert late == 0, "target leak"


if __name__ == "__main__":
    main()
