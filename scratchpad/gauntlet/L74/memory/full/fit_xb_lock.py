"""MEM-RETRAIN-2 iteration: re-fit ONLY the xb_lock output row of mem_aux.glob (encoder, hidden layer and every other row frozen).
The row sees h = GELU(glob[0](z, ctx)) (128 wide), so h is computed once per labelled train row and the row is a logistic
regression on h. Variants: (A) refit row (w, b) from the current values, Adam, early stop on a held-in TRAIN split (rep % 5 == 0;
the held-out val rows are never used for fitting or stopping); (B) temperature: logit / T, one scalar fit on the whole train
split. Writes CKPT_xbfit.pt (A) and CKPT_xbtemp.pt (B) next to the input and prints train-holdout and val BCE/H of old / current /
A / B.   python fit_xb_lock.py --init RAW.pt --old B0.pt --ck mem_best.pt --tables T.npz --data D.npz"""
import argparse
import copy
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aux_compare as AC  # noqa: E402
from pipeline.dataset import load as load_ds  # noqa: E402
from pipeline.dataset_gen import checkpoint_gid, load_memory_tables  # noqa: E402
from pipeline.model_gen import AUX_GLOB, load_model  # noqa: E402
from pipeline.train_gen import GenRows as Rows  # noqa: E402
from pipeline.train_memory import AuxLabels, aux_forward  # noqa: E402


@torch.no_grad()
def hidden(model, base, rows, lab, ids, bs=128):
    hs, ys, lo = [], [], []
    cap = []
    h = model.mem_aux.glob[1].register_forward_hook(lambda m, i, o: cap.append(o.detach().float().cpu()))
    for s in range(0, len(ids), bs):
        c = ids[s:s + bs]
        b = rows.batch(c)
        b.update(lab.batch(c, rows.dev))
        out = aux_forward(model, base, b)
        hs.append(cap.pop())
        ys.append(b["aux_xb_lock"].float().cpu())
        lo.append(out["xb_lock"].float().cpu())
    h.remove()
    return torch.cat(hs), torch.cat(ys), torch.cat(lo)


def bce(logit, y, H):
    return float(Fn.binary_cross_entropy_with_logits(logit, y) / H)


def main():
    ap = argparse.ArgumentParser()
    for k in ("init", "old", "ck", "tables"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--data", type=Path, default=AC.REPO / "icebow/data/pipeline/gen_dataset_v32_fv5.npz")
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=30)
    ap.add_argument("--wd", type=float, default=1e-2)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    dev = torch.device(a.device)
    arrs, meta = load_ds(a.data)
    packed, row_tab, _ = load_memory_tables(a.tables)
    row_tab = row_tab[:len(arrs["y_gate"])]
    gid = checkpoint_gid(meta["card_vocab"])
    ck = torch.load(a.ck, map_location="cpu", weights_only=False)
    st = ck["s3"]["label_stats"]["xb_lock"]
    H = st["H"]
    base = load_model(a.init, dev)[0].eval()
    new = load_model(a.ck, dev)[0].eval()
    old = load_model(a.old, dev)[0].eval()
    old.mem_full(128, True)
    lab = AuxLabels(arrs, packed, row_tab, gid, base.n_cards)
    fin = np.isfinite(lab.xb_lock)
    tr = np.where((arrs["split"] == 0) & (row_tab >= 0) & fin)[0]
    va = np.where((arrs["split"] == 1) & (row_tab >= 0) & fin)[0]
    print("xb_lock labelled rows: train", len(tr), "val", len(va), flush=True)
    rows = Rows(arrs, tr, dev)
    rows.memory, rows.grid = (packed, row_tab, arrs["tick"]), "lattice"
    rows.memory_version, rows.memory_gid, rows.memory_n_f = "v2", gid, 70
    rows.memory_e_max = 256
    htr, ytr, ltr = hidden(new, base, rows, lab, tr)
    rows.idx = va
    hva, yva, lva = hidden(new, base, rows, lab, va)
    rows.memory_e_max = 128
    _, _, lva_old = hidden(old, base, rows, lab, va)           # old encoder, 128 events, its own head
    row = AUX_GLOB.index("xb_lock") + base.n_cards
    W0 = new.mem_aux.glob[2].weight[row].detach().float().cpu().clone()
    b0 = new.mem_aux.glob[2].bias[row].detach().float().cpu().clone()
    assert torch.allclose(htr @ W0 + b0, ltr, atol=1e-3), "hidden * row does not reproduce the logit"
    rep = np.asarray(arrs["rep"])[tr]
    hold = torch.from_numpy(rep % 5 == 0)
    res = {"current": (bce(ltr[hold], ytr[hold], H), bce(lva, yva, H)), "old": (None, bce(lva_old, yva, H))}
    # (A) refit the row
    w, b = W0.clone().requires_grad_(True), b0.clone().requires_grad_(True)
    opt = torch.optim.AdamW([w, b], lr=a.lr, weight_decay=a.wd)
    best, bw, bb, bad = 1e9, W0.clone(), b0.clone(), 0
    for ep in range(a.epochs):
        perm = torch.randperm(int((~hold).sum()))
        hh, yy = htr[~hold][perm], ytr[~hold][perm]
        for s in range(0, len(hh), 256):
            opt.zero_grad()
            Fn.binary_cross_entropy_with_logits(hh[s:s + 256] @ w + b, yy[s:s + 256]).backward()
            opt.step()
        v = bce(htr[hold] @ w + b, ytr[hold], H)
        if v < best - 1e-5:
            best, bw, bb, bad = v, w.detach().clone(), b.detach().clone(), 0
        else:
            bad += 1
            if bad >= a.patience:
                break
    print("A stopped at epoch", ep + 1, "best holdout", round(best, 4), flush=True)
    res["A_refit"] = (best, bce(hva @ bw + bb, yva, H))
    # (B) temperature on the whole train split
    lt = torch.zeros((), requires_grad=True)                     # logit / exp(lt)
    o2 = torch.optim.LBFGS([lt], lr=0.5, max_iter=100)

    def clo():
        o2.zero_grad()
        l = Fn.binary_cross_entropy_with_logits(ltr / lt.exp(), ytr)
        l.backward()
        return l
    o2.step(clo)
    T = float(lt.exp())
    res["B_temp"] = (bce(ltr[hold] / T, ytr[hold], H), bce(lva / T, yva, H))
    print(f"T = {T:.4f}")
    print("BCE/H (train-holdout, val):", {k: tuple(None if x is None else round(x, 4) for x in v) for k, v in res.items()}, flush=True)
    for tag, (rw, rb) in (("xbfit", (bw, bb)), ("xbtemp", (W0 / T, b0 / T))):
        c = copy.deepcopy(ck)
        c["model"]["mem_aux.glob.2.weight"][row] = rw.to(c["model"]["mem_aux.glob.2.weight"].dtype)
        c["model"]["mem_aux.glob.2.bias"][row] = rb.to(c["model"]["mem_aux.glob.2.bias"].dtype)
        c["xb_lock_refit"] = {"variant": tag, "T": T if tag == "xbtemp" else None, "from": str(a.ck), "bce_val": res["A_refit" if tag == "xbfit" else "B_temp"][1]}
        p = a.ck.with_name(a.ck.stem + "_" + tag + ".pt")
        torch.save(c, p)
        print("saved", p, flush=True)


if __name__ == "__main__":
    main()
