"""Checks a slot re-drive output (slot_redrive.py): sidecar alignment and the slot-label invariants.
usage: python check_slot.py OUT [max_shards]"""
import collections
import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

out = Path(sys.argv[1])
files = sorted((out / "rows").glob("*.parquet"))[: int(sys.argv[2]) if len(sys.argv) > 2 else None]
c = collections.Counter()
for f in files:
    t = pq.read_table(f, columns=["y_gate", "y_wait_dt", "tick", "side", "tag", "tier", "hand_inferred", "own_ability"])
    sc = np.load(f.with_suffix(".slot.npz"))
    g = np.asarray(t.column("y_gate")); wdt = np.asarray(t.column("y_wait_dt")); tick = np.asarray(t.column("tick"))
    gap, ab, pl = sc["frame_gap"], sc["ab_dt"], sc["play_dt"]
    assert len(gap) == len(g)
    w = g == 0
    c["rows"] += len(g); c["play"] += int((g == 1).sum()); c["wait"] += int(w.sum())
    c["wait_playdt_eq_waitdt"] += int((pl[w] == np.round(wdt[w] * 20)).sum())
    c["play_playdt_0"] += int((pl[g == 1] == 0).sum())
    for k, v in collections.Counter(gap[w].tolist()).items():
        c[f"wait_gap:{k}"] += v
    c["wait_tick_mod10_0"] += int((tick[w] % 10 == 0).sum())
    # slots = the 10-tick grid: a grid frame is a wait row, or this side's play row when it plays ON the grid tick.
    # (frames also sit on every play tick of either side, so frame_gap < 10 marks a play inside the slot)
    on = (g == 1) & (tick % 10 == 0)
    c["play_on_grid"] += int(on.sum())
    slot = (tick % 10 == 0)
    tg = np.asarray(t.column("tag")).astype(str); sd = np.asarray(t.column("side"))
    for key in set(zip(tg[slot], sd[slot])):
        tk = np.sort(tick[slot & (tg == key[0]) & (sd == key[1])])
        c["grid_holes"] += int(((np.diff(tk) // 10) - 1).sum()); c["grid_sides"] += 1
        c["grid_dup"] += int((np.diff(tk) == 0).sum())
    c["slot_rows"] += int(slot.sum())
    ev = slot & (pl >= 0) & (pl < 10)
    c["slot_events"] += int(ev.sum())
    c["slot_rows_ab_ok"] += int((slot & (np.asarray(t.column("own_ability").combine_chunks().flatten()).reshape(len(g), -1)[:, 0::7] > 0).any(1)).sum())
    c["ab_events"] += int((slot & (ab >= 0) & (ab < 10)).sum())
    c["hand_inferred"] += int(np.asarray(t.column("hand_inferred")).sum())
    mem = out / "mem" / (f.name[:-len(".parquet")] + ".npz")
    if mem.exists():
        z = np.load(mem)
        c["mem_rows"] += len(z["row_tab"]); c["mem_rows_with_table"] += int((z["row_tab"] >= 0).sum())
print(json.dumps(dict(c), indent=1))
w = c["wait"]
print("wait rows: play_dt == wait_dt*20:", c["wait_playdt_eq_waitdt"] / max(w, 1), "| gap 10:", c["wait_gap:10"] / max(w, 1),
      "| tick%10==0:", c["wait_tick_mod10_0"] / max(w, 1))
print("slot event rate:", c["slot_events"] / max(c["slot_rows"], 1), "| play rows on the grid:",
      c["play_on_grid"] / max(c["play"], 1), "| holes per side:", c["grid_holes"] / max(c["grid_sides"], 1))
