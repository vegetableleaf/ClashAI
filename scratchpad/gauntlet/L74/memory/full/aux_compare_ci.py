"""MEM-RETRAIN gate 4 WITH bootstrap 95% CIs (MEM_FULL.md section 4 / 5). Same models, same held-out rows as aux_compare.py, but:
every labelled element keeps its own loss / prediction, and a PAIRED bootstrap over MATCHES (the dataset's `rep` = one replay)
gives a CI for each metric of each variant AND for the difference between two variants (same resampled matches).

    python scratchpad/gauntlet/L74/memory/full/aux_compare_ci.py --init RAW.pt --old B0.pt --new mem_best.pt \
        --tables TABLES.npz --data DATA.npz --out OUT.json [--val-sample 0] [--bs 128] [--boot 1000] [--auc-boot 300]

Variants: old (B0 encoder, 128 events), old256 (same weights, full history), new (retrained, 256 + snapshot), new128 (the
retrained encoder fed only the newest 128 events: separates "trained" from "sees more history"). Groups by the row's history
length: all / le128 / gt128 (the rows the 128 window truncated).
Metric definitions (pooled over the group's labelled elements, NOT the batch mean of aux_eval): REG head loss = mean of the
standardised squared error, r2 = 1 - SSE/sum z^2; BIN loss = BCE / H, auc (weighted Mann-Whitney, ties broken by order),
acc; CLS loss = CE / H, acc, cyc queue_acc. sum_all = the 12 head losses added; sum_main drops the two sparse heads
(rk_dmg, xb_lock: a few hundred labelled elements). "better" = lower loss, higher r2 / auc / acc / queue_acc."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aux_compare as AC  # noqa: E402  (puts the repo on sys.path)
from pipeline import match_memory as MM  # noqa: E402
from pipeline.dataset import load as load_ds  # noqa: E402
from pipeline.dataset_gen import checkpoint_gid, load_memory_tables  # noqa: E402
from pipeline.model_gen import load_model  # noqa: E402
from pipeline.train_gen import GenRows as Rows  # noqa: E402
from pipeline.train_memory import (AUX_HEADS, BIN, CLS, REG, AuxLabels, _mask, _pred, aux_forward,  # noqa: E402
                                   table_val_rows)

SPARSE = ("rk_dmg", "xb_lock")
NN = {}                       # (group, head) -> (labelled elements, matches they come from): a CI over < ~20 matches is not a CI
GROUPS = ("all", "le128", "gt128")


@torch.no_grad()
def collect(models: dict, base, v, lab, st, bs: int) -> dict:
    """models: tag -> model (one feature batch is shared by every model of the same e_max, set on ``v`` by the caller).
    -> {tag: {head: {pos, loss, ...}}}, pos = position of the element's row in v.idx."""
    acc = {t: {k: [] for k in AUX_HEADS} for t in models}
    for s in range(0, len(v.idx), bs):
        ids = v.idx[s:s + bs]
        b = v.batch(ids)
        b.update(lab.batch(ids, v.dev))
        dc = b["deck_card"]
        qmat = ~((dc.unsqueeze(-1) == b["hand_card"].unsqueeze(1)).any(-1) | (dc == b["next_card"].unsqueeze(-1)))
        for tag, model in models.items():
            p = _pred(aux_forward(model, base, b), b)
            for k in AUX_HEADS:
                m = _mask(b, k)
                if not m.any():
                    continue
                y, q = b["aux_" + k][m], p[k][m].float()
                e = {"pos": (m.nonzero()[:, 0] + s).cpu().numpy().astype(np.int64)}
                if k in REG:
                    z = (y - st[k]["mean"]) / st[k]["std"]
                    e["loss"], e["zz"] = (q - z) ** 2, z ** 2
                elif k in BIN:
                    e["loss"] = Fn.binary_cross_entropy_with_logits(q, y.float(), reduction="none") / st[k]["H"]
                    e["acc"], e["score"], e["y"] = ((q > 0) == (y > 0.5)).float(), q, (y > 0.5).float()
                else:
                    e["loss"] = Fn.cross_entropy(q, y, reduction="none") / st[k]["H"]
                    e["acc"] = (q.argmax(-1) == y).float()
                    if k == "cyc":
                        e["queue"] = qmat[m].float()
                acc[tag][k].append({n: (x if isinstance(x, np.ndarray) else x.cpu().numpy()) for n, x in e.items()})
    out = {}
    for tag in models:
        out[tag] = {}
        for k in AUX_HEADS:
            if acc[tag][k]:
                out[tag][k] = {n: np.concatenate([c[n] for c in acc[tag][k]]) for n in acc[tag][k][0]}
    return out


def auc_draws(score, y, mid, cnt, n):
    """Weighted Mann-Whitney AUC per bootstrap draw (weights = the draw's match multiplicities); the elements are sorted
    ONCE; ties broken by sort order (negligible for logits). -> array[len(cnt)], draws >= n are NaN."""
    o = np.argsort(score, kind="stable")
    yy, mo = y[o] > 0.5, mid[o]
    out = np.full(len(cnt), np.nan)
    for i in range(min(n, len(cnt))):
        w = cnt[i][mo]
        wp, wn = w * yy, w * ~yy
        if wp.sum() > 0 and wn.sum() > 0:
            out[i] = (wp * (np.cumsum(wn) - wn)).sum() / (wp.sum() * wn.sum())
    return out


def bootstrap(models_out, hl, rep, boot, auc_boot, seed=0):
    """-> {(group, head, metric, tag): array[boot]} ; draw 0 is the point estimate (all matches once)."""
    um, mid_row = np.unique(rep, return_inverse=True)
    M = len(um)
    rng = np.random.default_rng(seed)
    cnt = np.vstack([np.ones(M)] + [np.bincount(rng.integers(0, M, M), minlength=M) for _ in range(boot)]).astype(np.float64)
    rowgrp = {"all": np.ones(len(hl), bool), "le128": hl <= 128, "gt128": hl > 128}
    res = {}
    for tag, heads in models_out.items():
        for g in GROUPS:
            for k, e in heads.items():
                sel = rowgrp[g][e["pos"]]
                if not sel.any():
                    continue
                mid = mid_row[e["pos"][sel]]

                def per(x):
                    return np.bincount(mid, weights=np.asarray(x, np.float64)[sel], minlength=M)
                n = per(np.ones(len(sel)))
                NN[(g, k)] = (int(sel.sum()), int((n > 0).sum()))
                L = per(e["loss"])
                with np.errstate(invalid="ignore", divide="ignore"):
                    res[(g, k, "loss", tag)] = (cnt @ L) / (cnt @ n)
                    if k in REG:
                        res[(g, k, "r2", tag)] = 1 - (cnt @ L) / (cnt @ per(e["zz"]))
                    else:
                        res[(g, k, "acc", tag)] = (cnt @ per(e["acc"])) / (cnt @ n)
                    if k == "cyc":
                        qn, qa = per(e["queue"]), per(e["acc"] * e["queue"])
                        res[(g, k, "queue_acc", tag)] = (cnt @ qa) / (cnt @ qn)
                    if k in BIN:
                        res[(g, k, "auc", tag)] = auc_draws(e["score"][sel], e["y"][sel], mid, cnt, 1 + auc_boot)
            for name, drop in (("sum_all", ()), ("sum_main", SPARSE)):
                ks = [k for k in AUX_HEADS if k not in drop and (g, k, "loss", tag) in res]
                if ks:
                    res[(g, name, "loss", tag)] = np.sum([res[(g, k, "loss", tag)] for k in ks], 0)
    return res


def ci(x):
    x = x[1:]
    x = x[np.isfinite(x)]
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) > 20 else [None, None]


def summarise(res):
    """-> list of rows: group, head, metric, per-variant point + CI, and paired differences."""
    rows = []
    keys = sorted({k[:3] for k in res})
    pairs = (("new", "old"), ("old256", "old"), ("new", "old256"), ("new", "new128"), ("new128", "old"))
    for g, h, m in keys:
        r = {"group": g, "head": h, "metric": m, "n": NN.get((g, h), (None, None))[0], "matches": NN.get((g, h), (None, None))[1]}
        for t in ("old", "old256", "new128", "new"):
            if (g, h, m, t) in res:
                r[t] = {"point": float(res[(g, h, m, t)][0]), "ci": ci(res[(g, h, m, t)])}
        for a, b in pairs:
            if (g, h, m, a) in res and (g, h, m, b) in res:
                d = res[(g, h, m, a)] - res[(g, h, m, b)]
                sign = -1.0 if m == "loss" else 1.0           # +: a better than b
                good = sign * d[1:]
                good = good[np.isfinite(good)]
                r[f"{a}-{b}"] = {"point": float(d[0]), "ci": ci(d), "p_better": float((good > 0).mean()) if len(good) else None}
        rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    for k in ("init", "old", "new", "tables", "out"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--data", type=Path, default=AC.REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz")
    ap.add_argument("--val-sample", type=int, default=0)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--auc-boot", type=int, default=300)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    t0 = time.time()
    dev = torch.device(a.device)
    arrs, meta = load_ds(a.data)
    packed, row_tab, _ = load_memory_tables(a.tables)
    row_tab = row_tab[:len(arrs["y_gate"])]
    gid = checkpoint_gid(meta["card_vocab"])
    new_ck = torch.load(a.new, map_location="cpu", weights_only=False)
    st = new_ck["s3"]["label_stats"]
    base = load_model(a.init, dev)[0].eval()
    new = load_model(a.new, dev)[0].eval()
    old = load_model(a.old, dev)[0].eval()
    old.mem_full(128, True)
    if float(old.mem.ev_in.weight[:, 46:].abs().max()) != 0:
        raise SystemExit("old encoder: snapshot columns are not zero")
    va = table_val_rows(arrs, row_tab, a.val_sample)
    hl = AC.history_lengths(packed, row_tab, arrs["tick"], arrs["deck_card"], va, gid)
    rep = np.asarray(arrs["rep"])[va]
    rows = Rows(arrs, va, dev)
    rows.memory, rows.grid = (packed, row_tab, arrs["tick"]), str(new_ck["args"].get("grid", "lattice"))
    rows.memory_version, rows.memory_gid = "v2", gid
    lab = AuxLabels(arrs, packed, row_tab, gid, base.n_cards)
    print(f"val rows {len(va)} matches {len(np.unique(rep))} gt128 {(hl > 128).sum()} setup {time.time() - t0:.0f}s", flush=True)
    out = {}
    for em, models in ((128, {"old": old, "new128": new}), (256, {"old256": old, "new": new})):
        rows.memory_e_max, rows.memory_n_f = em, 70
        out.update(collect(models, base, rows, lab, st, a.bs))
        print(f"collected e_max {em} {time.time() - t0:.0f}s", flush=True)
    res = bootstrap(out, hl, rep, a.boot, min(a.auc_boot, a.boot))
    summary = summarise(res)
    n_el = {t: {k: int(len(e["pos"])) for k, e in h.items()} for t, h in out.items()}
    js = {"new": str(a.new), "new_step": new_ck["s3"].get("step"), "val_rows": int(len(va)), "matches": int(len(np.unique(rep))),
          "rows": {"all": int(len(va)), "le128": int((hl <= 128).sum()), "gt128": int((hl > 128).sum())},
          "boot": a.boot, "auc_boot": a.auc_boot, "elements_new": n_el["new"], "summary": summary,
          "seconds": round(time.time() - t0, 1)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(js, indent=1, default=float), encoding="utf-8")
    print("wrote", a.out, js["seconds"], "s", flush=True)


if __name__ == "__main__":
    main()
