"""L67n: VALUE RERANKER -- learn the search's RANKING of the student's own shortlist, not its action.

Why this and not the thing already tried (HANDOFF 5cs.99 P): cloning the search's ACTIONS succeeded as imitation
(balanced gate agreement 0.576 -> 0.653) and made play WORSE (sim tower -0.54 / -0.39 paired, pro card agreement
63.4% -> 48.9%). The student learned the search's marginal play rate without the per-decision evaluation behind
it. What the search actually contributes is a SCORE per candidate, and the rollout search itself replicates
(+1.714 / +1.460 paired, 5cs.99 N) -- so this keeps the evaluate-then-choose structure and learns the evaluation.

Corpus (student_search.py --dump-rerank, N=1, degraded view, 120 matches): per searched decision the state,
WAIT's rollout score, and every candidate's (deck slot, lattice cell, rollout score). Target = candidate score
minus WAIT's score, i.e. the ADVANTAGE of playing that card there over waiting.

Model: the S1 encoder is FROZEN (v6lat_s0) and run once; a small head reads [board summary g, the encoder's patch
feature under the candidate cell, card embedding, cell embedding] -> predicted advantage.

v2 (after the first run): the first head's best held-out regret came at EPOCH 1 and decayed after (val corr
0.417 -> 0.334, regret 0.058 -> 0.077), and that epoch was selected on the SAME fold it was reported on -- an
optimistic number. So matches are now split into three folds by match id: fold 0 SELECTS the epoch, fold 1 is
REPORTED and never used for selection, the rest train. Dropout, weight decay and frozen embeddings are exposed
because 92k candidates come from only ~16k correlated decisions in ~96 matches.

Graded by REGRET: the rollout value left on the table versus the best choice available at that decision (0 for
an oracle). Baselines on the same decisions: always WAIT, always play the student's TOP candidate, a RANDOM one.

usage: python scratchpad/gauntlet/L67/rerank_train.py --ckpt <v6lat_s0.pt> --shards rr_0.npz rr_1.npz rr_2.npz \
           [--hidden 128 --dropout 0.3 --wd 1e-2 --freeze-emb --lr 3e-4 --tag A]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


class Head(nn.Module):
    """[g, patch-under-cell, card emb, cell emb] -> predicted advantage over WAIT.

    Module-level so the sim actor loads the exact same architecture. With dropout 0 the layer indices match the
    first (v1) head file, so it still loads.
    """

    def __init__(self, d: int, n_slots: int, n_cells: int, hidden: int = 256, dropout: float = 0.0,
                 card_w=None, cell_w=None, freeze_emb: bool = False):
        super().__init__()
        self.card = nn.Embedding(n_slots, d)
        self.cell = nn.Embedding(n_cells, d)
        if card_w is not None:
            self.card.weight.data.copy_(card_w)
        if cell_w is not None:
            self.cell.weight.data.copy_(cell_w)
        self.card.weight.requires_grad_(not freeze_emb)
        self.cell.weight.requires_grad_(not freeze_emb)
        layers = [nn.Linear(4 * d, hidden), nn.GELU()]
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        layers += [nn.Linear(hidden, hidden), nn.GELU()]
        if dropout > 0:
            layers.append(nn.Dropout(dropout))
        layers.append(nn.Linear(hidden, 1))
        self.mlp = nn.Sequential(*layers)

    def forward(self, g, cp, slot, cell):
        return self.mlp(torch.cat([g, cp, self.card(slot), self.cell(cell)], -1)).squeeze(-1)


def load_head(path, device="cpu"):
    st = torch.load(path, map_location=device)
    d = int(st.get("d", 128))
    sd = st["head"]
    h = Head(d, sd["card.weight"].shape[0], sd["cell.weight"].shape[0], hidden=int(st.get("hidden", 256)),
             dropout=float(st.get("dropout", 0.0)))
    h.load_state_dict(sd)
    h.eval()
    return h, st


def load_shards(paths):
    """Concatenate ragged shards, shifting token offsets, candidate offsets and match ids."""
    keys = ("sc", "past", "wait_score", "cand_slot", "cand_cell", "cand_score")
    acc = {k: [] for k in keys}
    toks, offs, coffs, reps = [], [], [], []
    tb = cb = rb = 0
    for p in paths:
        z = np.load(p)
        d = {k: np.array(z[k]) for k in z.files}
        toks.append(d["tok"]); offs.append(d["off"][1:] + tb)
        coffs.append(d["cand_off"][1:] + cb); reps.append(d["rep"].astype(np.int64) + rb)
        for k in keys:
            acc[k].append(d[k])
        tb += int(d["off"][-1]); cb += int(d["cand_off"][-1]); rb += int(d["rep"].max()) + 1
    out = {k: np.concatenate(v) for k, v in acc.items()}
    out["tok"] = np.concatenate(toks)
    out["off"] = np.concatenate([[0], np.concatenate(offs)]).astype(np.int64)
    out["cand_off"] = np.concatenate([[0], np.concatenate(coffs)]).astype(np.int64)
    out["rep"] = np.concatenate(reps)
    out["fold"] = (out["rep"] % 5).astype(np.int8)                # by MATCH: 0 select, 1 report, 2-4 train
    assert int(out["off"][-1]) == len(out["tok"]) and int(out["cand_off"][-1]) == len(out["cand_score"])
    return out


def encode_all(model, data, dev, bs=256, max_units=64):
    """Frozen encoder, run ONCE: per decision g [d]; per candidate the patch feature under its cell [d]."""
    n = len(data["sc"])
    G = np.zeros((n, model.d), np.float32)
    CP = np.zeros((len(data["cand_score"]), model.d), np.float32)
    off, coff = data["off"], data["cand_off"]
    cell_patch = model.cell_patch.cpu().numpy()
    with torch.no_grad():
        for s0 in range(0, n, bs):
            ids = range(s0, min(n, s0 + bs))
            U = max(1, min(max_units, max(int(off[i + 1] - off[i]) for i in ids)))
            tok = np.zeros((len(ids), U, data["tok"].shape[1]), np.float32)
            mask = np.zeros((len(ids), U), bool)
            for j, i in enumerate(ids):
                t = data["tok"][off[i]:off[i + 1]][:U]
                tok[j, :len(t)] = t
                mask[j, :len(t)] = True
            enc = model.encode(torch.from_numpy(tok).to(dev), torch.from_numpy(mask).to(dev),
                               torch.from_numpy(data["sc"][s0:s0 + len(ids)]).to(dev),
                               torch.from_numpy(data["past"][s0:s0 + len(ids)]).to(dev))
            g = enc["g"].cpu().numpy(); p = enc["p"].cpu().numpy()
            G[s0:s0 + len(ids)] = g
            for j, i in enumerate(ids):
                a, b = int(coff[i]), int(coff[i + 1])
                if b > a:
                    CP[a:b] = p[j, cell_patch[data["cand_cell"][a:b]]]
    return G, CP


def grade(pred, adv, coff, dec_ids, margin, rng):
    """Regret and ranking on a set of decisions. pred/adv are per candidate."""
    reg = {"rerank": [], "always_wait": [], "student_top": [], "random_cand": []}
    top1_hits = top1_n = 0
    tp = fp = tn = fn = 0
    for i in dec_ids:
        a, b = int(coff[i]), int(coff[i + 1])
        if b <= a:
            continue
        av, pv = adv[a:b], pred[a:b]
        best = max(0.0, float(av.max()))
        k = int(np.argmax(pv))
        chose = float(av[k]) if float(pv[k]) > margin else 0.0
        reg["rerank"].append(best - chose)
        reg["always_wait"].append(best)
        reg["student_top"].append(best - float(av[0]))             # candidate 0 = student's top card x top cell
        reg["random_cand"].append(best - float(av[rng.integers(0, b - a)]))
        truth_play, pred_play = float(av.max()) > 0, float(pv[k]) > margin
        tp += truth_play and pred_play; fn += truth_play and not pred_play
        fp += (not truth_play) and pred_play; tn += (not truth_play) and not pred_play
        if truth_play:
            top1_n += 1
            top1_hits += int(k == int(np.argmax(av)))
    out = {k: round(float(np.mean(v)), 4) for k, v in reg.items()}
    out["play_bal_acc"] = round(0.5 * (tp / max(tp + fn, 1) + tn / max(tn + fp, 1)), 4)
    out["top1_when_play_is_right"] = round(top1_hits / max(top1_n, 1), 4)
    out["n_decisions"] = len(reg["rerank"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--shards", type=Path, nargs="+", required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("scratchpad/gauntlet/L67/rerank"))
    ap.add_argument("--tag", default="v2")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--wd", type=float, default=1e-2)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--dropout", type=float, default=0.3)
    ap.add_argument("--freeze-emb", action="store_true")
    ap.add_argument("--bs", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()

    import torch.nn.functional as Fn
    from pipeline.model_v3 import S1Model

    torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device(a.device if (a.device == "cpu" or torch.cuda.is_available()) else "cpu")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    data = load_shards(a.shards)
    st = torch.load(a.ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"]); model.eval()
    for q in model.parameters():
        q.requires_grad_(False)

    t0 = time.time()
    G, CP = encode_all(model, data, dev)
    print(f"encoded {len(G)} decisions / {len(CP)} candidates in {time.time() - t0:.0f}s", flush=True)

    coff = data["cand_off"]
    dec_of = np.repeat(np.arange(len(G)), np.diff(coff))
    adv = (data["cand_score"] - data["wait_score"][dec_of]).astype(np.float32)
    fold = data["fold"]
    sel_dec, rep_dec = np.flatnonzero(fold == 0), np.flatnonzero(fold == 1)
    tr_c = np.flatnonzero(fold[dec_of] >= 2)
    sel_c = np.flatnonzero(fold[dec_of] == 0)
    rep_c = np.flatnonzero(fold[dec_of] == 1)
    print(f"train candidates {len(tr_c)} | select-fold decisions {len(sel_dec)} | report-fold decisions {len(rep_dec)}",
          flush=True)

    d = model.d
    head = Head(d, model.card_emb.weight.shape[0], model.cell_emb.shape[0], hidden=a.hidden, dropout=a.dropout,
                card_w=model.card_emb.weight.detach(), cell_w=model.cell_emb.detach(), freeze_emb=a.freeze_emb).to(dev)
    opt = torch.optim.AdamW([q for q in head.parameters() if q.requires_grad], lr=a.lr, weight_decay=a.wd)
    Gt = torch.from_numpy(G).to(dev); CPt = torch.from_numpy(CP).to(dev)
    slot_t = torch.from_numpy(data["cand_slot"].astype(np.int64)).to(dev)
    cell_t = torch.from_numpy(data["cand_cell"].astype(np.int64)).to(dev)
    dec_t = torch.from_numpy(dec_of).to(dev)
    adv_t = torch.from_numpy(adv).to(dev)

    def predict(idx):
        out = []
        with torch.no_grad():
            for s0 in range(0, len(idx), 8192):
                ii = torch.from_numpy(idx[s0:s0 + 8192]).to(dev)
                out.append(head(Gt[dec_t[ii]], CPt[ii], slot_t[ii], cell_t[ii]).cpu().numpy())
        return np.concatenate(out) if out else np.zeros(0, np.float32)

    best, hist = None, []
    for ep in range(1, a.epochs + 1):
        head.train()
        perm = np.random.permutation(tr_c)
        tot = nb = 0
        for s0 in range(0, len(perm), a.bs):
            ii = torch.from_numpy(perm[s0:s0 + a.bs]).to(dev)
            loss = Fn.smooth_l1_loss(head(Gt[dec_t[ii]], CPt[ii], slot_t[ii], cell_t[ii]), adv_t[ii], beta=0.1)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss.detach()); nb += 1
        head.eval()
        pred = np.zeros_like(adv)
        pred[sel_c] = predict(sel_c)
        pred[rep_c] = predict(rep_c)
        g_sel = grade(pred, adv, coff, sel_dec, 0.0, np.random.default_rng(0))
        g_rep = grade(pred, adv, coff, rep_dec, 0.0, np.random.default_rng(0))
        rec = {"epoch": ep, "train_loss": round(tot / max(nb, 1), 5),
               "select_corr": round(float(np.corrcoef(pred[sel_c], adv[sel_c])[0, 1]), 4),
               "select": g_sel,
               "report_corr": round(float(np.corrcoef(pred[rep_c], adv[rep_c])[0, 1]), 4),
               "report": g_rep}
        hist.append(rec)
        print(json.dumps(rec), flush=True)
        if best is None or g_sel["rerank"] < best["select"]["rerank"]:     # SELECT on fold 0 only
            best = rec
            torch.save({"head": head.state_dict(), "encoder_ckpt": str(a.ckpt), "d": d, "hidden": a.hidden,
                        "dropout": a.dropout, "epoch": ep, "val": rec},
                       a.out_dir / f"rerank_head_{a.tag}_s{a.seed}.pt")
    (a.out_dir / f"hist_{a.tag}_s{a.seed}.json").write_text(json.dumps({"args": vars(a) | {"ckpt": str(a.ckpt),
                                                                          "shards": [str(s) for s in a.shards],
                                                                          "out_dir": str(a.out_dir)},
                                                                 "best": best, "hist": hist}, indent=1),
                                                        encoding="utf-8")
    print("BEST " + json.dumps(best), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
