"""L60 kNN-vs-BC: three ways of predicting the PRO's placement cell, scored on the same 1,004 val rows.

Subcommands (cwd icebow, PYTHONPATH=src):
  baseline   A. c2r_best cell head, masked, on the val split (should agree with meta.csv ck_hit1/ck_hit5)
  knn        B. retrieval over TRAIN rows of the same card: learned embedding (z / fmap) and raw-obs PCA-256
  bc         C. cell-head cross-entropy on the pro cell; --mode head (trunk frozen) or --mode ft (trunk lr 1e-4)
Every subcommand writes a json under data/bc_pro/models/ with the numbers.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ICEBOW = Path("C:/Users/benpe/ClashBot/icebow")
DATA = ICEBOW / "data" / "bc_pro"
MODELS = DATA / "models"
CKPT = ICEBOW / "data" / "bench" / "c2r_best_36k_backup.pt"
sys.path.insert(0, str(ICEBOW / "src"))

from clashrl.model import PolicyNet          # noqa: E402
from clashrl.config import Config            # noqa: E402
from clashrl.actions import ActionSpace      # noqa: E402

TOP_CARDS = ["skeletons", "ice_wizard", "the_log", "knight", "tesla", "x_bow", "tornado", "rocket"]
BUCKETS = [(0, 60), (60, 120), (120, 180), (180, 10 ** 9)]
GW, GH = 18, 24


# ----------------------------------------------------------------------------------------------- data
def load_all(device):
    d = np.load(DATA / "dataset.npz", allow_pickle=True)
    obs = torch.from_numpy(d["obs"])                       # uint8 [N,96,64,12] -- stays uint8
    acts = torch.from_numpy(d["acts"]).long()
    hands = torch.from_numpy(d["hands"]).float()
    nexts = torch.from_numpy(d["nexts"]).float()
    elx = torch.from_numpy(d["elixirs"]).float()
    thr = torch.from_numpy(d["threats"]).float()
    deck = [str(s) for s in d["deck"]]
    cell = acts[:, 2] * GW + acts[:, 1]
    rows = list(csv.DictReader(open(DATA / "meta.csv", newline="")))
    assert len(rows) == len(obs)
    meta = {
        "seconds": np.array([float(r["seconds"]) for r in rows]),
        "anywhere": np.array([int(r["anywhere"]) for r in rows]),
        "pocket": np.array([int(r["pocket_code"]) for r in rows]),
        "card_key": np.array([r["card_key"] for r in rows]),
        "ck_hit1": np.array([int(r["ck_hit1"]) for r in rows]),
        "ck_hit5": np.array([int(r["ck_hit5"]) for r in rows]),
        "cell": np.array([int(r["cell"]) for r in rows]),
    }
    assert (meta["cell"] == cell.numpy()).all()
    sp = json.load(open(DATA / "split.json"))
    tr, va = np.array(sp["train_rows"]), np.array(sp["val_rows"])
    assert len(tr) == 5918 and len(va) == 1004 and not set(tr) & set(va)
    cfg = Config.load(ICEBOW / "config" / "config.yaml")
    A = ActionSpace(cfg)
    masks = torch.zeros(2, 4, GW * GH, dtype=torch.bool)
    for a in (0, 1):
        for pk in range(4):
            masks[a, pk] = torch.tensor(A.deployable_mask(bool(a), (bool(pk & 2), bool(pk & 1))))
    row_mask = masks[torch.from_numpy(meta["anywhere"]), torch.from_numpy(meta["pocket"])]   # [N,432] bool
    T = dict(obs=obs.to(device), hands=hands.to(device), nexts=nexts.to(device), elx=elx.to(device),
             thr=thr.to(device), card=acts[:, 0].to(device), cell=cell.to(device), mask=row_mask.to(device))
    return T, meta, deck, tr, va


def load_net(device):
    ck = torch.load(CKPT, map_location="cpu")
    net = PolicyNet(in_ch=int(ck["in_ch"]), n_cards=int(ck["n_cards"]), n_cells=int(ck["n_cells"]),
                    threat_dim=int(ck["threat_dim"]))
    net.load_state_dict(ck["model"])
    return net.to(device).eval(), ck


def batch_x(T, idx):
    return T["obs"][idx].float().permute(0, 3, 1, 2) / 255.0


@torch.no_grad()
def forward_all(net, T, idx, bs=128, want=("cells",)):
    """Returns dict of concatenated outputs over rows idx: cells = pro card's MASKED cell logits [n,432]
    (still tanh-capped like the policy), z = 328-d embed, fmap = flattened pre-pool feature map."""
    out = {k: [] for k in want}
    for i0 in range(0, len(idx), bs):
        sl = torch.as_tensor(idx[i0:i0 + bs], device=T["obs"].device)
        x = batch_x(T, sl)
        fmap = net.features(x)
        z = net._embed(fmap, T["hands"][sl], T["nexts"][sl], T["elx"][sl], T["thr"][sl])
        if "cells" in want:
            cells = 8.0 * torch.tanh(net._cell_logits(fmap, z) / 8.0)
            sel = cells[torch.arange(len(sl)), T["card"][sl]]
            out["cells"].append(sel.masked_fill(~T["mask"][sl], float("-inf")))
        if "z" in want:
            out["z"].append(z)
        if "fmap" in want:
            out["fmap"].append(fmap.flatten(1))
    return {k: torch.cat(v) for k, v in out.items()}


# ----------------------------------------------------------------------------------------------- scoring
def score(scores: torch.Tensor, target: torch.Tensor, meta, idx, name):
    """scores [n,432] with -inf outside the mask. Returns dict overall / per card / per time bucket."""
    top5 = torch.topk(scores, 5, dim=1).indices
    hit1 = (top5[:, 0] == target).cpu().numpy()
    hit5 = (top5 == target[:, None]).any(1).cpu().numpy()
    res = {"name": name, "n": int(len(idx)), "top1": float(hit1.mean() * 100), "top5": float(hit5.mean() * 100),
           "per_card": {}, "per_time": {}}
    ck = meta["card_key"][idx]
    for c in TOP_CARDS:
        m = ck == c
        if m.any():
            res["per_card"][c] = [int(m.sum()), float(hit1[m].mean() * 100), float(hit5[m].mean() * 100)]
    sec = meta["seconds"][idx]
    for lo, hi in BUCKETS:
        m = (sec >= lo) & (sec < hi)
        key = f"{lo}-{hi}" if hi < 10 ** 8 else f"{lo}+"
        res["per_time"][key] = [int(m.sum()), float(hit1[m].mean() * 100), float(hit5[m].mean() * 100)]
    return res, hit1, hit5


def fmt(res):
    s = f"{res['name']}: n {res['n']} top1 {res['top1']:.2f} top5 {res['top5']:.2f}"
    s += " | cards " + " ".join(f"{c}:{v[1]:.1f}/{v[2]:.1f}({v[0]})" for c, v in res["per_card"].items())
    s += " | time " + " ".join(f"{k}:{v[1]:.1f}/{v[2]:.1f}({v[0]})" for k, v in res["per_time"].items())
    return s


def masked_entropy(logits):
    p = torch.softmax(logits, dim=1)
    return float((-(p * torch.log(p.clamp_min(1e-30))).sum(1)).mean())


# ----------------------------------------------------------------------------------------------- A
def cmd_baseline(args):
    dev = torch.device(args.device)
    T, meta, deck, tr, va = load_all(dev)
    net, ck = load_net(dev)
    out = forward_all(net, T, va, want=("cells",))
    res, h1, h5 = score(out["cells"], T["cell"][va], meta, va, "A_baseline_val")
    res["entropy_nats"] = masked_entropy(out["cells"])
    res["agree_meta_hit1"] = int((h1 == meta["ck_hit1"][va]).sum())
    res["agree_meta_hit5"] = int((h5 == meta["ck_hit5"][va]).sum())
    res["top1_hist"] = {int(k): int(v) for k, v in
                        zip(*np.unique(torch.topk(out["cells"], 1).indices.cpu().numpy(), return_counts=True))}
    res["top1_hist"] = dict(sorted(res["top1_hist"].items(), key=lambda kv: -kv[1])[:6])
    # train-split numbers too, for the kNN "train prior" comparison
    outt = forward_all(net, T, tr, want=("cells",))
    rest, _, _ = score(outt["cells"], T["cell"][tr], meta, tr, "A_baseline_train")
    res["train"] = {"top1": rest["top1"], "top5": rest["top5"]}
    print(fmt(res)); print("entropy", res["entropy_nats"], "agree", res["agree_meta_hit1"], res["agree_meta_hit5"],
                           "hist", res["top1_hist"], "train", res["train"])
    json.dump(res, open(MODELS / "A_baseline.json", "w"), indent=1)


# ----------------------------------------------------------------------------------------------- B
def gauss_kernel(sigma=1.0):
    """[432,432] cell-to-cell Gaussian weights on the 18x24 grid (sigma in cells)."""
    gx = torch.arange(GW * GH) % GW
    gy = torch.arange(GW * GH) // GW
    d2 = (gx[:, None] - gx[None]) ** 2 + (gy[:, None] - gy[None]) ** 2
    return torch.exp(-d2.float() / (2 * sigma ** 2))


def knn_eval(E_tr, E_va, T, meta, tr, va, tag, ks=(1, 5, 15, 50, 150), sigma=1.0):
    """E_* are L2-normalised embeddings. Same-card neighbours only."""
    dev = E_tr.device
    S = E_va @ E_tr.T                                                       # cosine [nva, ntr]
    same = T["card"][va][:, None] == T["card"][tr][None]
    S_masked = S.masked_fill(~same, -2.0)
    K = gauss_kernel(sigma).to(dev)
    results = []
    # coverage: NN cosine (same card) per val row, and any-card
    nn_same = S_masked.max(1).values.cpu().numpy()
    nn_any = S.max(1).values.cpu().numpy()
    cov = {"same_card_nn_cos": [float(np.median(nn_same)), float(np.percentile(nn_same, 10)), float(np.percentile(nn_same, 90))],
           "any_card_nn_cos": [float(np.median(nn_any)), float(np.percentile(nn_any, 10)), float(np.percentile(nn_any, 90))]}
    # also train-to-train (leave-one-out, same card) so the val statistic has a reference
    Stt = (E_tr @ E_tr.T).fill_diagonal_(-2.0)
    same_tt = T["card"][tr][:, None] == T["card"][tr][None]
    nn_tt = Stt.masked_fill(~same_tt, -2.0).max(1).values.cpu().numpy()
    cov["train_loo_same_card_nn_cos"] = [float(np.median(nn_tt)), float(np.percentile(nn_tt, 10)), float(np.percentile(nn_tt, 90))]
    print(f"[{tag}] coverage {cov}")
    cells_tr = T["cell"][tr]
    for k in ks:
        top = torch.topk(S_masked, k, dim=1)
        nb_cells = cells_tr[top.indices]                                    # [nva,k]
        votes = torch.zeros(len(va), GW * GH, device=dev)
        votes.scatter_add_(1, nb_cells, torch.ones_like(nb_cells, dtype=torch.float))
        smooth = votes @ K
        for variant, sc in (("hard", votes + 1e-3 * smooth), ("gauss", smooth)):
            sc = sc.masked_fill(~T["mask"][va], float("-inf"))
            res, _, _ = score(sc, T["cell"][va], meta, va, f"B_{tag}_k{k}_{variant}")
            print(fmt(res)); results.append(res)
    return results, cov


def cmd_knn(args):
    dev = torch.device(args.device)
    T, meta, deck, tr, va = load_all(dev)
    net, ck = load_net(dev)
    all_res, covs = [], {}
    feats = forward_all(net, T, np.concatenate([tr, va]), want=("z", "fmap"))
    ntr = len(tr)
    for name in ("z", "fmap"):
        E = F.normalize(feats[name], dim=1)
        r, cov = knn_eval(E[:ntr], E[ntr:], T, meta, tr, va, name)
        all_res += r; covs[name] = cov
    del feats
    # raw obs: cosine on the flattened uint8 image (no PCA) and PCA-256 fitted on train rows, via Gram matrices
    N = len(T["obs"]); idx_all = np.concatenate([tr, va]); n = len(idx_all)
    D = 96 * 64 * 12
    mean = torch.zeros(D, device=dev)
    for i0 in range(0, ntr, 256):
        sl = torch.as_tensor(tr[i0:i0 + 256], device=dev)
        mean += T["obs"][sl].float().flatten(1).sum(0) / 255.0
    mean /= ntr
    G_raw = torch.zeros(n, n, device=dev); G_c = torch.zeros(n, n, device=dev)
    ch = 512
    chunks = [(i0, torch.as_tensor(idx_all[i0:i0 + ch], device=dev)) for i0 in range(0, n, ch)]
    for i0, si in chunks:
        Xi = T["obs"][si].float().flatten(1) / 255.0
        Xic = Xi - mean
        for j0, sj in chunks:
            if j0 < i0:
                continue
            Xj = T["obs"][sj].float().flatten(1) / 255.0
            g = Xi @ Xj.T; gc = Xic @ (Xj - mean).T
            G_raw[i0:i0 + len(si), j0:j0 + len(sj)] = g; G_raw[j0:j0 + len(sj), i0:i0 + len(si)] = g.T
            G_c[i0:i0 + len(si), j0:j0 + len(sj)] = gc; G_c[j0:j0 + len(sj), i0:i0 + len(si)] = gc.T
            del Xj, g, gc
        del Xi, Xic
    # raw cosine: normalise the Gram
    nrm = torch.sqrt(torch.diag(G_raw)).clamp_min(1e-8)
    C_raw = G_raw / nrm[:, None] / nrm[None]
    # PCA-256 from the train Gram: G_tr = U L U^T ; train scores = U sqrt(L) ; val scores = G_va,tr U / sqrt(L)
    Gtr = G_c[:ntr, :ntr].double()
    evals, evecs = torch.linalg.eigh(Gtr)
    order = torch.argsort(evals, descending=True)[:256]
    L, U = evals[order].clamp_min(1e-8), evecs[:, order]
    P_tr = U * torch.sqrt(L)[None]
    P_va = G_c[ntr:, :ntr].double() @ U / torch.sqrt(L)[None]
    expl = float(L.sum() / evals.clamp_min(0).sum())
    print(f"[pca] 256 comps explain {expl*100:.1f}% of train variance")
    E_tr, E_va = F.normalize(P_tr.float(), dim=1), F.normalize(P_va.float(), dim=1)
    r, cov = knn_eval(E_tr, E_va, T, meta, tr, va, "rawpca256")
    cov["explained_var"] = expl
    all_res += r; covs["rawpca256"] = cov
    # raw cosine without PCA: reuse knn_eval by passing precomputed similarities -> simplest is a fake embedding
    # via the Gram itself: C_raw = E E^T with E = eigen-embedding of C_raw (exact, all comps). n=6922 -> [n,n] fine.
    ev2, U2 = torch.linalg.eigh(C_raw.double())
    E_full = (U2 * torch.sqrt(ev2.clamp_min(0))[None]).float()
    E_full = F.normalize(E_full, dim=1)
    r, cov = knn_eval(E_full[:ntr], E_full[ntr:], T, meta, tr, va, "rawcos")
    all_res += r; covs["rawcos"] = cov
    json.dump({"results": all_res, "coverage": covs}, open(MODELS / "B_knn.json", "w"), indent=1)


# ----------------------------------------------------------------------------------------------- control
def cmd_prior(args):
    """Per-card cell histogram on TRAIN rows (= kNN with k -> all same-card rows). If kNN does not beat this, the
    neighbours carry no state information beyond 'which card'."""
    dev = torch.device(args.device)
    T, meta, deck, tr, va = load_all(dev)
    K = gauss_kernel(1.0).to(dev)
    hist = torch.zeros(10, GW * GH, device=dev)
    hist.index_put_((T["card"][tr], T["cell"][tr]), torch.ones(len(tr), device=dev), accumulate=True)
    out = []
    for variant, H in (("hard", hist + 1e-3 * (hist @ K)), ("gauss", hist @ K), ("laplace1", hist + 1.0)):
        sc = H[T["card"][va]].masked_fill(~T["mask"][va], float("-inf"))
        res, _, _ = score(sc, T["cell"][va], meta, va, f"prior_card_hist_{variant}")
        p = torch.softmax(torch.log(H[T["card"][va]].clamp_min(1e-9)).masked_fill(~T["mask"][va], float("-inf")), 1)
        res["entropy_nats"] = float((-(p * torch.log(p.clamp_min(1e-30))).sum(1)).mean())
        okv = T["mask"][va][torch.arange(len(va)), T["cell"][va]]
        res["val_ce_reachable"] = float(F.nll_loss(torch.log(p.clamp_min(1e-30))[okv], T["cell"][va][okv]))
        print(fmt(res), "H", res["entropy_nats"], "val_ce", res["val_ce_reachable"]); out.append(res)
    # global (card-agnostic) train cell histogram
    g = torch.zeros(GW * GH, device=dev).index_put_((T["cell"][tr],), torch.ones(len(tr), device=dev), accumulate=True)
    sc = (g + 1e-3 * (g @ K))[None].expand(len(va), -1).masked_fill(~T["mask"][va], float("-inf"))
    res, _, _ = score(sc, T["cell"][va], meta, va, "prior_global_hist"); print(fmt(res)); out.append(res)
    json.dump(out, open(MODELS / "control_prior.json", "w"), indent=1)


# ----------------------------------------------------------------------------------------------- C
def cmd_bc(args):
    dev = torch.device(args.device)
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    T, meta, deck, tr, va = load_all(dev)
    net, ck = load_net(dev)
    rescale = None
    if args.rescale_p99 > 0:
        # RAIL REPAIR (measured 2026-09-05): c2r_best's raw cell logits are far past the +/-8 tanh cap (92.4% of masked
        # val logits |raw|>8, mean -23.6, min -112), where d tanh ~ 0, so a cross-entropy on the head barely moves it.
        # A LINEAR rescale of the last 1x1 conv (weight AND bias) keeps every ranking (top-1/top-5 unchanged) and puts
        # the p99 |raw| at args.rescale_p99 (inside the cap). Same idea as tools/repair_card_head.py, for the cell head.
        with torch.no_grad():
            raws = []
            for i0 in range(0, len(tr), 256):
                sl = torch.as_tensor(tr[i0:i0 + 256], device=dev)
                fmap = net.features(batch_x(T, sl))
                z = net._embed(fmap, T["hands"][sl], T["nexts"][sl], T["elx"][sl], T["thr"][sl])
                sel = net._cell_logits(fmap, z)[torch.arange(len(sl)), T["card"][sl]]
                raws.append(sel[T["mask"][sl]].abs())
            p99 = float(torch.quantile(torch.cat(raws), 0.99))
            rescale = p99 / args.rescale_p99
            net.cell_conv[4].weight.div_(rescale); net.cell_conv[4].bias.div_(rescale)
        print(f"[rescale] p99 |raw masked cell logit| on train {p99:.2f} -> divided cell_conv.4 by {rescale:.2f}")
    head_params = list(net.cell_ctx.parameters()) + list(net.cell_conv.parameters())
    head_ids = {id(p) for p in head_params}
    rest = [p for p in net.parameters() if id(p) not in head_ids]
    if args.mode == "head":
        for p in rest:
            p.requires_grad_(False)
        opt = torch.optim.Adam(head_params, lr=args.head_lr)
    else:
        opt = torch.optim.Adam([{"params": head_params, "lr": args.head_lr}, {"params": rest, "lr": args.trunk_lr}])
    gen = torch.Generator(device="cpu").manual_seed(args.seed)
    va_t = torch.as_tensor(va, device=dev)

    def evaluate():
        net.eval()
        out = forward_all(net, T, va, want=("cells",))
        res, _, _ = score(out["cells"], T["cell"][va], meta, va, f"C_{args.mode}_s{args.seed}")
        res["entropy_nats"] = masked_entropy(out["cells"])
        okv = T["mask"][va][torch.arange(len(va)), T["cell"][va]]
        res["val_ce"] = float(F.cross_entropy(out["cells"][okv], T["cell"][va][okv]))   # over the 974 reachable val rows
        return res

    r0 = evaluate()
    curve = [(0, r0["top1"], r0["top5"], r0["val_ce"], r0["entropy_nats"])]
    best, best_state, bad = r0["top1"], {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}, 0
    best_ep = 0
    if args.stop_on == "ce":
        best = -r0["val_ce"]
    if args.skip_epoch0:                      # do not let the untouched source checkpoint win the early-stop race
        best = -1e9
    for ep in range(1, args.epochs + 1):
        net.train()
        perm = torch.randperm(len(tr), generator=gen).numpy()
        tot, n = 0.0, 0
        for i0 in range(0, len(tr), args.bs):
            sl = torch.as_tensor(tr[perm[i0:i0 + args.bs]], device=dev)
            x = batch_x(T, sl)
            _, cells = net(x, T["hands"][sl], T["nexts"][sl], T["elx"][sl], T["thr"][sl])
            sel = cells[torch.arange(len(sl)), T["card"][sl]].masked_fill(~T["mask"][sl], float("-inf"))
            ok = T["mask"][sl][torch.arange(len(sl)), T["cell"][sl]]     # 300 train rows have the pro cell OUTSIDE the mask
            loss = F.cross_entropy(sel[ok], T["cell"][sl][ok])            # (own-tower footprints); -inf target -> skip
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(sl); n += len(sl)
        r = evaluate()
        curve.append((ep, r["top1"], r["top5"], r["val_ce"], r["entropy_nats"]))
        print(f"ep {ep} train_ce {tot/n:.3f} val top1 {r['top1']:.2f} top5 {r['top5']:.2f} ce {r['val_ce']:.3f} H {r['entropy_nats']:.2f}", flush=True)
        crit = r["top1"] if args.stop_on == "top1" else -r["val_ce"]
        if crit > best + 1e-9:
            best, bad, best_ep = crit, 0, ep
            best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= args.patience and ep >= args.min_epochs:
                print(f"early stop at ep {ep}, best ep {best_ep} top1 {best:.2f}")
                break
    net.load_state_dict(best_state)
    rb = evaluate(); rb["best_epoch"] = best_ep; rb["curve"] = curve
    print("BEST", fmt(rb), "entropy", rb["entropy_nats"])
    outp = MODELS / (args.out or f"bc_{args.mode}_s{args.seed}.pt")
    jname = args.json or f"C_{args.mode}_s{args.seed}.json"
    ck2 = dict(ck); ck2["model"] = {k: v.clone() for k, v in best_state.items()}
    ck2["bc_pro"] = {"mode": args.mode, "seed": args.seed, "best_epoch": best_ep, "val_top1": best, "source": str(CKPT),
                     "head_rescale_div": rescale, "epoch0": curve[0]}
    torch.save(ck2, outp)
    # verify: reload through PolicyNet strict + the ppo resume keys
    ck3 = torch.load(outp, map_location="cpu")
    net2 = PolicyNet(in_ch=int(ck3["in_ch"]), n_cards=int(ck3["n_cards"]), n_cells=int(ck3["n_cells"]), threat_dim=int(ck3["threat_dim"]))
    net2.load_state_dict(ck3["model"])                       # strict
    import torch.nn as nn
    for key, shape in (("gate", 2), ("value", 1), ("value_d", 1)):
        nn.Linear(net2.embed_dim, shape).load_state_dict(ck3[key])
    assert set(ck3["model"]) == set(ck["model"]) and all(ck3["model"][k].shape == ck["model"][k].shape for k in ck["model"])
    net2 = net2.to(dev).eval()
    out2 = forward_all(net2, T, va, want=("cells",))
    r2, _, _ = score(out2["cells"], T["cell"][va], meta, va, "reload")
    assert abs(r2["top1"] - rb["top1"]) < 1e-6, (r2["top1"], rb["top1"])
    rb["saved"] = str(outp); rb["reload_ok"] = True
    print("saved+reloaded", outp, "top1", r2["top1"])
    json.dump(rb, open(MODELS / jname, "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["baseline", "knn", "bc", "prior"])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--mode", default="head", choices=["head", "ft"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--bs", type=int, default=128)
    ap.add_argument("--out", default=None)
    ap.add_argument("--min_epochs", type=int, default=0)
    ap.add_argument("--json", default=None)
    ap.add_argument("--rescale_p99", type=float, default=0.0)
    ap.add_argument("--stop_on", default="top1", choices=["top1", "ce"])
    ap.add_argument("--skip_epoch0", action="store_true")
    ap.add_argument("--head_lr", type=float, default=1e-3)
    ap.add_argument("--trunk_lr", type=float, default=1e-4)
    a = ap.parse_args()
    torch.set_num_threads(2)
    MODELS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    {"baseline": cmd_baseline, "knn": cmd_knn, "bc": cmd_bc, "prior": cmd_prior}[a.cmd](a)
    print(f"done {time.time()-t0:.0f}s")
