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
feature under the candidate cell, card embedding, cell embedding] -> predicted advantage. Card and cell
embeddings are initialised from the student's own and fine-tuned.

Graded on HELD-OUT MATCHES (split by match, never by row) with the metric that matters for play -- REGRET: the
rollout value left on the table versus the best choice available at that decision (0 for an oracle). Baselines
on the same decisions: always WAIT, always play the student's TOP candidate, play a RANDOM candidate.

usage: python scratchpad/gauntlet/L67/rerank_train.py --ckpt <v6lat_s0.pt> --shards rr_0.npz rr_1.npz rr_2.npz
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


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
    out["split"] = ((out["rep"] % 5) == 0).astype(np.int8)          # 1 in 5 MATCHES held out
    assert int(out["off"][-1]) == len(out["tok"]) and int(out["cand_off"][-1]) == len(out["cand_score"])
    return out


def encode_all(model, data, torch, dev, bs=256, max_units=64):
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
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--bs", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()

    import torch
    import torch.nn as nn
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
    G, CP = encode_all(model, data, torch, dev)
    print(f"encoded {len(G)} decisions / {len(CP)} candidates in {time.time() - t0:.0f}s", flush=True)

    coff = data["cand_off"]
    dec_of = np.repeat(np.arange(len(G)), np.diff(coff))               # candidate -> decision
    adv = (data["cand_score"] - data["wait_score"][dec_of]).astype(np.float32)
    val_dec = np.flatnonzero(data["split"] == 1)
    tr_dec = np.flatnonzero(data["split"] == 0)
    tr_c = np.flatnonzero(data["split"][dec_of] == 0)
    va_c = np.flatnonzero(data["split"][dec_of] == 1)
    print(f"train decisions {len(tr_dec)} / candidates {len(tr_c)}; held-out {len(val_dec)} / {len(va_c)}", flush=True)

    d = model.d

    class Head(nn.Module):
        def __init__(self):
            super().__init__()
            self.card = nn.Embedding.from_pretrained(model.card_emb.weight.detach().clone(), freeze=False)
            self.cell = nn.Embedding.from_pretrained(model.cell_emb.detach().clone(), freeze=False)
            self.mlp = nn.Sequential(nn.Linear(4 * d, 256), nn.GELU(), nn.Linear(256, 256), nn.GELU(), nn.Linear(256, 1))

        def forward(self, g, cp, slot, cell):
            return self.mlp(torch.cat([g, cp, self.card(slot), self.cell(cell)], -1)).squeeze(-1)

    head = Head().to(dev)
    opt = torch.optim.AdamW(head.parameters(), lr=a.lr, weight_decay=1e-4)
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

    rng = np.random.default_rng(0)
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
        pred[va_c] = predict(va_c)
        g_val = grade(pred, adv, coff, val_dec, 0.0, rng)
        corr = float(np.corrcoef(pred[va_c], adv[va_c])[0, 1])
        rec = {"epoch": ep, "train_loss": round(tot / max(nb, 1), 5), "val_corr": round(corr, 4), **g_val}
        hist.append(rec)
        print(json.dumps(rec), flush=True)
        if best is None or rec["rerank"] < best["rerank"]:
            best = rec
            torch.save({"head": head.state_dict(), "encoder_ckpt": str(a.ckpt), "d": d, "epoch": ep, "val": rec},
                       a.out_dir / f"rerank_head_s{a.seed}.pt")
    (a.out_dir / f"hist_s{a.seed}.json").write_text(json.dumps({"best": best, "hist": hist}, indent=1), encoding="utf-8")
    print("BEST " + json.dumps(best), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
