"""Generalist evaluator: ``GenModel`` checkpoint + ``dataset_gen`` npz -> S1-comparable metrics.

    icebow/.venv/Scripts/python.exe -m pipeline.eval_gen --ckpt DIR/gen_s0.pt --data icebow/data/pipeline/gen_dataset_starter.npz

``evaluate`` is ``train_s1.evaluate`` line for line; the only differences are the model call (identity inputs, the
cell head teacher-forced on the pro's card IDENTITY instead of its deck slot) and what "card" indexes: S1's argmax is
over the 8 deck slots masked to the hand, ours over the 4 hand positions. A hand holds 4 DISTINCT cards (the 8 deck
cards are distinct; asserted on the starter data), so "argmax hand position == pro's hand position" is the same event
as S1's "argmax slot == pro's slot". pipeline/tests/test_model_gen.py checks the two functions return identical
numbers on an S1-equivalent toy case. Reported on (a) the v3val rows (icebow sides of S1's v3 VAL replays, directly
comparable to S1 checkpoints), (b) per deck vs that deck's TRAIN row count, (c) all val rows, each beside board-blind
baselines on the same rows.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

from .dataset import load as load_ds
from .model_gen import IDENT, GenModel, card_form_of
from .model_v3 import GRID_X, GRID_Y, cell_index, cell_label, tile_of_cell
from .train_s1 import Rows

DECK_ID_NOTE = ("deck_id is keyed on the 8 BASE card keys (dataset_gen): evo/hero variants of one card list share a "
                "deck_id, so a 'deck' here merges its form variants")


class GenRows(Rows):
    """``train_s1.Rows`` over a dataset_gen npz: ``slot`` = the pro's HAND POSITION (-1 on wait rows), ``wait`` = the
    DECK POSITION of the card played next (-1 if absent), plus the identity arrays, ``y_card`` and its decked form."""

    def __init__(self, arrs: dict, idx: np.ndarray, device):
        dc, wc = arrs["deck_card"], arrs["y_wait_card"]
        hit = dc == wc[:, None]
        wait = np.where(hit.any(1) & (wc > 0), hit.argmax(1), -1)
        super().__init__(dict(arrs, y_slot=arrs["y_hand_pos"], y_wait_slot=wait), idx, device)
        self.ident = {k: torch.from_numpy(arrs[k].astype(np.int64)).to(device) for k in IDENT}
        self.card = torch.from_numpy(arrs["y_card"].astype(np.int64)).to(device)
        self.form = card_form_of(self.ident["deck_card"], self.ident["deck_form"], self.card)

    def view(self, idx: np.ndarray) -> "GenRows":
        """Same device arrays, another index set (the arrays are not copied again)."""
        v = copy.copy(self)
        v.idx = np.asarray(idx)
        return v

    def batch(self, ids: np.ndarray) -> dict:
        b = super().batch(ids)
        t = torch.from_numpy(np.asarray(ids)).to(self.dev)
        b.update({k: v[t] for k, v in self.ident.items()})
        b["card"], b["form"] = self.card[t], self.form[t]
        return b


@torch.no_grad()
def evaluate(model: GenModel, rows: GenRows, bs: int = 512, grid: str = "floor", rowlog: list | None = None) -> dict:
    """``train_s1.evaluate`` for GenModel. ``rowlog``: if a list, gets (row ids, cell_half_ok, cell_tile_ok, card_ok)
    per batch for the PLAY rows (per-deck grouping)."""
    model.eval()
    n = len(rows.idx)
    agg = {"cell_half": 0, "cell_tile": 0, "card": 0, "joint": 0, "n_play": 0, "gate_tp": 0, "gate_tn": 0,
           "n_pos": 0, "n_neg": 0, "wait": 0, "n_wait": 0, "value": 0, "cell_nll": 0.0,
           "place_hit": 0, "place_1t": 0, "place_dist": 0.0}
    off = 0.5 if grid == "floor" else 0.0
    gs = []
    for s in range(0, n, bs):
        ids = rows.idx[s:s + bs]
        b = rows.batch(ids)
        out = model(b, card=b["card"], form=b["form"])
        play = b["gate"] > 0.5
        if play.any():
            logits = out["cell"][play]
            xy = b["xy"][play]
            t_half = cell_label(xy, grid)
            pred = logits.argmax(-1)
            half_ok = pred == t_half
            agg["cell_half"] += int(half_ok.sum())
            px = (pred % GRID_X).float() + off; py = (pred // GRID_X).float() + off
            dist = torch.sqrt(((px / GRID_X - xy[:, 0]) * (GRID_X / 2)) ** 2 + ((py / GRID_Y - xy[:, 1]) * (GRID_Y / 2)) ** 2)
            agg["place_hit"] += int((dist <= 0.3).sum()); agg["place_1t"] += int((dist <= 1.0).sum())
            agg["place_dist"] += float(dist.sum())
            agg["cell_nll"] += float(Fn.cross_entropy(logits, t_half, reduction="sum"))
            p = logits.softmax(-1).view(-1, GRID_Y // 2, 2, GRID_X // 2, 2).sum((2, 4)).flatten(1)
            t_tile = cell_index(xy, GRID_X // 2, GRID_Y // 2) if grid == "floor" else tile_of_cell(t_half)
            tile_ok = p.argmax(-1) == t_tile
            agg["cell_tile"] += int(tile_ok.sum())
            card_ok = out["card"][play].argmax(-1) == b["slot"][play]
            agg["card"] += int(card_ok.sum())
            agg["joint"] += int((card_ok & tile_ok).sum())
            agg["n_play"] += int(play.sum())
            if rowlog is not None:
                rowlog.append((np.asarray(ids)[play.cpu().numpy()], half_ok.cpu().numpy(), tile_ok.cpu().numpy(),
                               card_ok.cpu().numpy()))
        g_pred = out["gate"] > 0
        agg["gate_tp"] += int((g_pred & play).sum()); agg["gate_tn"] += int((~g_pred & ~play).sum())
        agg["n_pos"] += int(play.sum()); agg["n_neg"] += int((~play).sum())
        if (~play).any():
            agg["wait"] += int((out["wait"][~play].argmax(-1) == b["wait"][~play]).sum()); agg["n_wait"] += int((~play).sum())
        agg["value"] += int((out["value"].argmax(-1) == b["value"]).sum())
        if len(gs) < 4:
            gs.append(out["g"])
    g = torch.cat(gs)[:512]
    g = Fn.normalize(g, dim=-1)
    cos = (g @ g.t())
    spread = float((cos.sum() - cos.diag().sum()) / max(len(g) * (len(g) - 1), 1))
    np_ = max(agg["n_play"], 1)
    return {"cell_half_top1": agg["cell_half"] / np_, "cell_tile_top1": agg["cell_tile"] / np_,
            "card_top1": agg["card"] / np_, "joint_top1": agg["joint"] / np_, "cell_nll": agg["cell_nll"] / np_,
            "gate_acc": (agg["gate_tp"] + agg["gate_tn"]) / max(n, 1),
            "gate_bal_acc": 0.5 * (agg["gate_tp"] / max(agg["n_pos"], 1) + agg["gate_tn"] / max(agg["n_neg"], 1)),
            "wait_top1": agg["wait"] / max(agg["n_wait"], 1), "value_acc": agg["value"] / max(n, 1),
            "place_hit": agg["place_hit"] / np_, "place_1t": agg["place_1t"] / np_, "place_dist": agg["place_dist"] / np_,
            "emb_cosine": spread, "n_play": agg["n_play"], "n": n}


def baseline(arrs: dict, eval_idx: np.ndarray, grid: str = "lattice") -> dict:
    """Board-blind baselines on the PLAY rows of ``eval_idx``, fitted on TRAIN play rows (split 0): train_s1.baseline
    with the card IDENTITY in place of the deck slot. cell_*_percard = the card's most common train cell (a card
    never seen in train -> the overall most common cell); cell_*_global = the overall most common cell; card_top1 =
    the hand card with the highest train play frequency."""
    tr = (arrs["split"] == 0) & (arrs["y_gate"] == 1)
    ev = np.zeros(len(arrs["split"]), bool); ev[eval_idx] = True
    ev &= arrs["y_gate"] == 1
    xy = torch.from_numpy(arrs["y_xy"].astype(np.float32)); card = arrs["y_card"].astype(np.int64)
    res = {}
    for name, gx, gy in (("half", GRID_X, GRID_Y), ("tile", GRID_X // 2, GRID_Y // 2)):
        c = (cell_index(xy, gx, gy) if grid == "floor" else
             (cell_label(xy, grid) if name == "half" else tile_of_cell(cell_label(xy, grid)))).numpy()
        glob = np.bincount(c[tr], minlength=gx * gy).argmax()
        best = {k: np.bincount(c[tr & (card == k)], minlength=gx * gy).argmax() for k in np.unique(card[tr])}
        pred = np.array([best.get(k, glob) for k in card[ev]])
        res[f"cell_{name}_percard"] = float((pred == c[ev]).mean()) if ev.any() else 0.0
        res[f"cell_{name}_global"] = float((c[ev] == glob).mean()) if ev.any() else 0.0
    freq = np.bincount(card[tr], minlength=int(arrs["hand_card"].max()) + 1).astype(float)
    freq[0] = -1.0                                               # pad never
    hand = arrs["hand_card"][ev].astype(np.int64)
    res["card_top1_handfreq"] = float((freq[hand].argmax(1) == arrs["y_hand_pos"][ev]).mean()) if ev.any() else 0.0
    res["n_play"] = int(ev.sum())
    return res


def per_deck(arrs: dict, rowlog: list) -> dict:
    """Val PLAY-row agreement per deck_id vs that deck's TRAIN row count; buckets by train rows + the 25 decks with
    the most val play rows."""
    ids = np.concatenate([r[0] for r in rowlog]); half = np.concatenate([r[1] for r in rowlog])
    tile = np.concatenate([r[2] for r in rowlog]); card = np.concatenate([r[3] for r in rowlog])
    did = arrs["deck_id"][ids]
    n_dk = int(arrs["deck_id"].max()) + 1
    tr_rows = np.bincount(arrs["deck_id"][arrs["split"] == 0], minlength=n_dk)
    cnt = np.bincount(did, minlength=n_dk)

    def agg(m):
        return {"decks": int(len(np.unique(did[m]))), "n_play": int(m.sum()), "cell_half_top1": float(half[m].mean()),
                "cell_tile_top1": float(tile[m].mean()), "card_top1": float(card[m].mean())}

    buckets = {}
    tr_of_row = tr_rows[did]
    for lo, hi in ((0, 1), (1, 1_000), (1_000, 10_000), (10_000, 100_000), (100_000, 10 ** 9)):
        m = (tr_of_row >= lo) & (tr_of_row < hi)
        if m.any():
            buckets[f"train_rows[{lo},{hi})"] = agg(m)
    top = []
    for d in np.argsort(-cnt)[:25]:
        if cnt[d]:
            top.append({"deck_id": int(d), "train_rows": int(tr_rows[d]), **agg(did == d)})
    rho = None
    ok = cnt >= 20                                               # decks with >= 20 val play rows
    if ok.sum() >= 3:
        acc = np.bincount(did, weights=half, minlength=n_dk)[ok] / cnt[ok]
        r1, r2 = np.argsort(np.argsort(tr_rows[ok])), np.argsort(np.argsort(acc))
        rho = float(np.corrcoef(r1, r2)[0, 1])
    return {"note": DECK_ID_NOTE, "buckets_by_train_rows": buckets, "top_decks_by_val_rows": top,
            "spearman_trainrows_vs_cell_half(decks>=20 val play)": rho, "n_decks_ge20": int(ok.sum())}


def load_model(ckpt: Path, device) -> tuple[GenModel, dict]:
    st = torch.load(ckpt, map_location=device)
    if not st.get("gen"):
        raise SystemExit(f"{ckpt} is not a generalist checkpoint (no 'gen' key)")
    a = st["args"]
    model = GenModel(d=int(a["d"]), layers=int(a["layers"]), d_c=int(st["d_c"]), n_cards=len(st["card_vocab"])).to(device)
    model.load_state_dict(st["model"])
    return model, st


def run(model: GenModel, arrs: dict, rows: GenRows, grid: str, bs: int = 512) -> dict:
    v3 = np.where(arrs["v3val"] == 1)[0]
    va = np.where(arrs["split"] == 1)[0]
    log: list = []
    res = {"v3val": {"model": evaluate(model, rows.view(v3), bs, grid), "baseline": baseline(arrs, v3, grid)},
           "val_all": {"model": evaluate(model, rows.view(va), bs, grid, rowlog=log), "baseline": baseline(arrs, va, grid)}}
    res["per_deck_val"] = per_deck(arrs, log)
    res["s1_reference_v3val"] = {"v6lat_s0": {"cell_half_top1": 0.2097, "card_top1": 0.6546, "gate_bal_acc": 0.766},
                                 "v6lat_3seed": {"cell_half_top1": "0.2104 +- 0.0022", "card_top1": "0.6499 +- 0.0057"},
                                 "v6aug_s1": {"cell_half_top1": 0.2073, "card_top1": 0.6394, "gate_bal_acc": 0.7636}}
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None, help="json path (default: <ckpt>.eval.json)")
    ap.add_argument("--bs", type=int, default=512)
    a = ap.parse_args(argv)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, st = load_model(a.ckpt, dev)
    arrs, meta = load_ds(a.data)
    if meta["card_vocab"] != st["card_vocab"]:
        raise SystemExit("card_vocab of the data differs from the checkpoint's: ids would mean other cards")
    grid = st["args"]["grid"]
    rows = GenRows(arrs, np.where(arrs["split"] == 1)[0], dev)
    res = {"ckpt": str(a.ckpt), "data": str(a.data), "epoch": st.get("epoch"), "grid": grid, **run(model, arrs, rows, grid, a.bs)}
    out = a.out or a.ckpt.with_suffix(".eval.json")
    out.write_text(json.dumps(res, indent=1))
    keys = ("cell_half_top1", "cell_tile_top1", "card_top1", "joint_top1", "place_dist", "cell_nll", "gate_acc",
            "gate_bal_acc", "n_play", "n")
    for part in ("v3val", "val_all"):
        print(json.dumps({part: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res[part]["model"].items() if k in keys},
                          "baseline": res[part]["baseline"]}))
    print(json.dumps({"per_deck_buckets": res["per_deck_val"]["buckets_by_train_rows"],
                      "spearman": res["per_deck_val"]["spearman_trainrows_vs_cell_half(decks>=20 val play)"],
                      "note": DECK_ID_NOTE}))
    print(json.dumps({"written": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
