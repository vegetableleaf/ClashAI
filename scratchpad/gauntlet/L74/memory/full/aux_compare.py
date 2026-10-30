"""MEM-RETRAIN gate 4 (MEM_FULL.md section 4): aux metrics of the OLD encoder (B0's, e_max 128, no snapshot) vs a NEW one
(train_memory --e-max 256 --snap) on the SAME held-out rows, split by the row's history length: (a) <= 128 events,
(b) > 128 events (the rows the old window truncated).

    python scratchpad/gauntlet/L74/memory/full/aux_compare.py --init RAW.pt --old B0.pt --new mem_best.pt \
        --tables TABLES.npz --data DATA.npz --out OUT.json [--val-sample 0] [--bs 512] [--device cuda]

Both use the NEW run's label_stats (the same normalisation) and the same val rows (split 1, rows with a table). The old
encoder reads the snap tables through mem_full(128, snap): zero new columns = its own output (MEM_FULL section 4).
A row's history length = its event count at e_max 256 (memory mask), exact below the cap (max 229 pro, section 1)."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))
from pipeline import match_memory as MM  # noqa: E402
from pipeline.dataset import load as load_ds  # noqa: E402
from pipeline.dataset_gen import checkpoint_gid, load_memory_tables  # noqa: E402
from pipeline.model_gen import load_model  # noqa: E402
from pipeline.train_gen import GenRows as Rows  # noqa: E402
from pipeline.train_memory import AUX_HEADS, AuxLabels, aux_eval, table_val_rows  # noqa: E402


def history_lengths(packed, row_tab, tick, deck, ids, gid, e_max=256, bs=4096) -> np.ndarray:
    out = np.zeros(len(ids), np.int32)
    for s in range(0, len(ids), bs):
        m = MM.rows_features(packed, row_tab, tick, deck, ids[s:s + bs], "v2", gid, e_max=e_max)
        out[s:s + bs] = m["mem_mask"].astype(bool).sum(-1)
    return out


def brief(ev: dict) -> dict:
    res = {"loss": ev["loss"]}
    for k in AUX_HEADS:
        r = ev.get(k) or {}
        res[k] = {m: r[m] for m in ("n", "r2", "auc", "acc", "trivial_acc", "queue_acc", "queue_trivial_acc") if r.get(m) is not None}
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ("init", "old", "new", "tables", "out"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--data", type=Path, default=REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz")
    ap.add_argument("--val-sample", type=int, default=0)
    ap.add_argument("--bs", type=int, default=512)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    t0 = time.time()
    dev = torch.device(a.device)
    arrs, meta = load_ds(a.data)
    packed, row_tab, _ = load_memory_tables(a.tables)
    n = len(arrs["y_gate"])
    row_tab = row_tab[:n]
    gid = checkpoint_gid(meta["card_vocab"])
    new_ck = torch.load(a.new, map_location="cpu", weights_only=False)
    st = new_ck["s3"]["label_stats"]
    tr_tab = (packed, row_tab, arrs["tick"])
    base = load_model(a.init, dev)[0].eval()
    new = load_model(a.new, dev)[0].eval()
    old = load_model(a.old, dev)[0].eval()
    old.mem_full(128, True)                  # zero new columns: reads the 70-wide rows with the 46-wide weights
    if float(old.mem.ev_in.weight[:, 46:].abs().max()) != 0:
        raise SystemExit("old encoder: snapshot columns are not zero")
    grid = str(new_ck["args"].get("grid", "lattice"))
    va = table_val_rows(arrs, row_tab, a.val_sample)
    hl = history_lengths(packed, row_tab, arrs["tick"], arrs["deck_card"], va, gid)
    rows = Rows(arrs, va, dev)
    rows.memory, rows.grid = tr_tab, grid
    rows.memory_version, rows.memory_gid = "v2", gid
    lab = AuxLabels(arrs, packed, row_tab, gid, base.n_cards)
    res = {"new": str(a.new), "new_step": new_ck["s3"].get("step"), "old": str(a.old), "val_rows": int(len(va)),
           "hist_len_p50": float(np.median(hl)), "hist_len_max": int(hl.max()), "groups": {}}
    for name, ids in (("all", va), ("le128", va[hl <= 128]), ("gt128", va[hl > 128])):
        g = {"rows": int(len(ids))}
        if len(ids):
            v = rows.view(ids)
            for tag, model, em in (("old", old, 128), ("new", new, new.mem.e_max)):
                v.memory_e_max, v.memory_n_f = em, model.mem.ev_in.in_features
                with torch.no_grad():
                    g[tag] = brief(aux_eval(model, base, v, lab, st, bs=a.bs))
        res["groups"][name] = g
        if g.get("new"):
            print(name, g["rows"], "loss old", round(g["old"]["loss"], 4), "new", round(g["new"]["loss"], 4), flush=True)
    res["seconds"] = round(time.time() - t0, 1)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
