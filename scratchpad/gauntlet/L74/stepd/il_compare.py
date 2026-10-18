"""Step d IL gate: held-out action agreement of imitation checkpoints on the SAME rows, paired, CI by MATCH.

    python scratchpad/gauntlet/L74/stepd/il_compare.py --data gen_dataset_v32_fv5.npz --cue-data v32_cue.npz \
        --ckpt cue=il_cue/gen_cue_s0.pt --ckpt v32=icebow/data/pipeline/gen_v32_s0/gen_s0.pt --ckpt nocue1=... \
        --pairs cue:v32 nocue1:v32 [--grid lattice] [--draws 2000] [--out il_compare.json]

Rows: the val split (split 1 = 10% of replays by tag hash, never trained on). Subsets: all val rows; val rows whose cue
sidecar status is 'attached' (the only rows where cues can matter); v3val (the icebow S1 instrument). Per row: play rows
-> cell NLL, cell tile top-1, card top-1 (eval_gen.evaluate's definitions); every row -> gate decision (bal. accuracy)
and gate NLL; wait rows -> wait top-1. A pair A:B = A - B with a 95% bootstrap CI over val REPLAYS (rows of one match
move together). Every model gets the cue rows; a model without a cue layer ignores them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

METRICS = ("card_top1", "cell_tile_top1", "cell_nll", "gate_bal_acc", "gate_nll", "wait_top1")


@torch.no_grad()
def per_row(model, rows, ids: np.ndarray, grid: str, bs: int = 512) -> dict:
    from pipeline.model_v3 import cell_label, tile_of_cell, GRID_X, GRID_Y, cell_index
    model.eval()
    n = len(ids)
    out = {k: np.full(n, np.nan, np.float32) for k in ("cell_nll", "tile", "card", "gate_nll", "gate_ok", "wait")}
    play_all = np.zeros(n, bool)
    for s in range(0, n, bs):
        b = rows.batch(ids[s:s + bs])
        o = model(b, card=b["card"], form=b["form"])
        play = (b["gate"] > 0.5).cpu().numpy()
        sl = slice(s, s + len(play))
        play_all[sl] = play
        pt = torch.from_numpy(play).to(b["gate"].device)
        out["gate_nll"][sl] = Fn.binary_cross_entropy_with_logits(o["gate"], b["gate"], reduction="none").cpu().numpy()
        out["gate_ok"][sl] = ((o["gate"] > 0).cpu().numpy() == play).astype(np.float32)
        if play.any():
            lg, xy = o["cell"][pt], b["xy"][pt]
            t_half = cell_label(xy, grid)
            p = lg.softmax(-1).view(-1, GRID_Y // 2, 2, GRID_X // 2, 2).sum((2, 4)).flatten(1)
            t_tile = cell_index(xy, GRID_X // 2, GRID_Y // 2) if grid == "floor" else tile_of_cell(t_half)
            idx = np.flatnonzero(play) + s
            out["cell_nll"][idx] = Fn.cross_entropy(lg, t_half, reduction="none").cpu().numpy()
            out["tile"][idx] = (p.argmax(-1) == t_tile).float().cpu().numpy()
            out["card"][idx] = (o["card"][pt].argmax(-1) == b["slot"][pt]).float().cpu().numpy()
        if (~play).any():
            wt = ~pt
            idx = np.flatnonzero(~play) + s
            ok = (o["wait"][wt].argmax(-1) == b["wait"][wt]).float()
            ok[b["wait"][wt] < 0] = float("nan")             # no valid target: excluded (eval_gen's max(n, 1) rule)
            out["wait"][idx] = ok.cpu().numpy()
    out["play"] = play_all
    return out


def replay_sums(r: dict, rep: np.ndarray) -> tuple[np.ndarray, list]:
    """Per-replay sums -> [n_rep, k] and the column names; the metrics are ratios of these sums."""
    reps, inv = np.unique(rep, return_inverse=True)
    play = r["play"]
    cols = {
        "n_play": play.astype(float), "card": np.nan_to_num(r["card"]), "tile": np.nan_to_num(r["tile"]),
        "cell_nll": np.nan_to_num(r["cell_nll"]), "tp": (r["gate_ok"] * play), "n_pos": play.astype(float),
        "tn": (r["gate_ok"] * ~play), "n_neg": (~play).astype(float), "gate_nll": r["gate_nll"], "n": np.ones(len(play)),
        "wait": np.nan_to_num(r["wait"]), "n_wait": np.isfinite(r["wait"]).astype(float)}
    names = list(cols)
    m = np.zeros((len(reps), len(names)))
    for k, name in enumerate(names):
        np.add.at(m[:, k], inv, cols[name])
    return m, names


def metrics(s: np.ndarray, names: list) -> dict:
    c = {n: s[..., i] for i, n in enumerate(names)}
    d = lambda a, b: a / np.maximum(b, 1e-9)                   # noqa: E731
    return {"card_top1": d(c["card"], c["n_play"]), "cell_tile_top1": d(c["tile"], c["n_play"]),
            "cell_nll": d(c["cell_nll"], c["n_play"]),
            "gate_bal_acc": 0.5 * (d(c["tp"], c["n_pos"]) + d(c["tn"], c["n_neg"])),
            "gate_nll": d(c["gate_nll"], c["n"]), "wait_top1": d(c["wait"], c["n_wait"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--cue-data", type=Path, required=True)
    ap.add_argument("--ckpt", action="append", required=True, help="NAME=PATH")
    ap.add_argument("--pairs", nargs="*", default=[], help="A:B (A - B)")
    ap.add_argument("--grid", default="lattice")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    from pipeline.dataset import load as load_ds
    from pipeline.eval_gen import GenRows, load_model
    arrs, meta = load_ds(a.data)
    with np.load(a.cue_data, allow_pickle=False) as cz:
        if cz["cue"].shape[0] != len(arrs["tok"]):
            raise SystemExit("--cue-data does not belong to --data")
        arrs["cue"], status = cz["cue"], cz["status"]
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    va = np.flatnonzero(arrs["split"] == 1)
    subsets = {"val_all": va, "val_cue_attached": va[status[va] == 4], "v3val": np.flatnonzero(arrs["v3val"] == 1)}
    rows = GenRows(arrs, va, dev)
    res = {"rows": {k: int(len(v)) for k, v in subsets.items()}, "models": {}, "pairs": {}}
    per = {}
    for spec in a.ckpt:
        name, path = spec.split("=", 1)
        model, _ = load_model(Path(path), dev)
        per[name] = {k: per_row(model, rows, ids, a.grid) for k, ids in subsets.items() if len(ids)}
        res["models"][name] = {k: {m: round(float(v), 5) for m, v in metrics(replay_sums(r, arrs["rep"][subsets[k]])[0].sum(0),
                                                                           replay_sums(r, arrs["rep"][subsets[k]])[1]).items()}
                               for k, r in per[name].items()}
        res["models"][name]["has_cue_layer"] = getattr(model, "cue_in", None) is not None
    rng = np.random.default_rng(0)
    for pair in a.pairs:
        A, B = pair.split(":")
        res["pairs"][pair] = {}
        for k, ids in subsets.items():
            if k not in per[A]:
                continue
            sa, names = replay_sums(per[A][k], arrs["rep"][ids])
            sb, _ = replay_sums(per[B][k], arrs["rep"][ids])
            w = rng.multinomial(len(sa), np.full(len(sa), 1 / len(sa)), size=a.draws).astype(float)   # replay bootstrap
            da, db = metrics(w @ sa, names), metrics(w @ sb, names)
            pa, pb = metrics(sa.sum(0), names), metrics(sb.sum(0), names)
            res["pairs"][pair][k] = {m: dict(diff=round(float(pa[m] - pb[m]), 5),
                                             ci=[round(float(np.quantile(da[m] - db[m], q)), 5) for q in (0.025, 0.975)])
                                     for m in METRICS}
    print("IL_COMPARE", json.dumps(res, indent=1))
    if a.out:
        a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
