"""Bool mask over a rows dir: rows in (t_x, t_x + 200] after an enemy reach X-Bow (siege_a.windows, groups 1-2).
CB=... python make_mask.py ROWS_DIR MEM.npz OUT.npy"""
import json, os, sys
from pathlib import Path
import numpy as np
sys.path[:0] = [os.environ["CB"], str(Path(__file__).resolve().parent)]
from pipeline.dataset_gen import load_memory_tables  # noqa: E402
import siege_a as SA                                  # noqa: E402
tick = np.load(Path(sys.argv[1]) / "tick.npy", mmap_mode="r")
split = np.load(Path(sys.argv[1]) / "split.npy", mmap_mode="r")
packed, row_tab, _ = load_memory_tables(Path(sys.argv[2]))
grp, _, W = SA.windows(packed, np.asarray(row_tab), np.asarray(tick))
m = grp >= 1
np.save(sys.argv[3], m)
print(json.dumps({"rows": int(len(m)), "window_rows": int(m.sum()), "train_window_rows": int((m & (split == 0)).sum()),
                  "train_rows": int((split == 0).sum()), "windows": len(W)}))
