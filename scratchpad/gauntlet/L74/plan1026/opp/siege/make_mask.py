"""Bool mask over a rows dir: rows in (t_x, t_x + 200] after an enemy reach X-Bow (siege_a.windows, groups 1-2).
CB=... python make_mask.py ROWS_DIR MEM.npz OUT.npy
OPP-SIEGE2 fix 2 (opt-in env; unset = the mask above, unchanged): MASK_WALL=600 -> windows (t_x, t_x + 600] (the lock rule's
30 s); MASK_FAILED=1 -> only windows of enemy X-Bows that did NOT lock (the human's defence held)."""
import json, os, sys
from pathlib import Path
import numpy as np
sys.path[:0] = [os.environ["CB"], str(Path(__file__).resolve().parent)]
from pipeline.dataset_gen import load_memory_tables  # noqa: E402
import siege_a as SA                                  # noqa: E402
if os.environ.get("MASK_WALL"):
    SA.W_ALL = int(os.environ["MASK_WALL"])
tick = np.load(Path(sys.argv[1]) / "tick.npy", mmap_mode="r")
split = np.load(Path(sys.argv[1]) / "split.npy", mmap_mode="r")
packed, row_tab, _ = load_memory_tables(Path(sys.argv[2]))
grp, wid, W = SA.windows(packed, np.asarray(row_tab), np.asarray(tick))
m = grp >= 1
if os.environ.get("MASK_FAILED"):
    failed = np.array([lk == 0 for _, _, lk in W] + [False])      # index -1 (no window) -> False
    m &= failed[wid]
np.save(sys.argv[3], m)
print(json.dumps({"rows": int(len(m)), "window_rows": int(m.sum()), "train_window_rows": int((m & (split == 0)).sum()),
                  "train_rows": int((split == 0).sum()), "windows": len(W), "failed_windows": int(sum(lk == 0 for _, _, lk in W)),
                  "w_all": SA.W_ALL, "failed_only": bool(os.environ.get("MASK_FAILED"))}))
