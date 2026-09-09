"""L67h: grade a distilled student on BOTH instruments -- teacher agreement and pro agreement.

The distillation spec's own gate (HANDOFF 6-PRIORITY-B): the teacher sees ENGINE GROUND TRUTH while the
student sees the degraded observation, so if the targets depend on information the student cannot see,
distillation cannot reproduce them and the run caps out early. "Cheapest test: hold out a slice of the corpus
and check the student's top-1 agreement with the teacher on states it never trained on, BEFORE committing."

The corpus is split BY MATCH, so held-out states come from matches the model never saw.

Second instrument, and the reason this script reports two: a checkpoint that wins in the sim while its PRO
agreement collapses has learned the sim, not the game. The sim is a scripted-opponent model of Clash Royale,
and this project has a history of engine results that did not transfer. Pro agreement is the closest thing to
an outside check we have, so it is reported for every arm whether or not it moved.

usage: python scratchpad/gauntlet/L67/distill_grade.py --ckpt <pt> [--ckpt <pt> ...] \
           --teacher <teacher_corpus.npz> --pro <s1_dataset_v6.npz> --out <json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def load_model(ckpt, torch, S1Model, dev):
    st = torch.load(ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    m = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    m.load_state_dict(st["model"])
    m.eval()
    return m, str(args.get("grid", "floor")), st.get("epoch")


def teacher_agreement(model, grid, arrs, idx, torch, tau, Rows, cell_label, hand_mask_from_sc, dev):
    """Top-1 agreement with the TEACHER's action on states the model never trained on."""
    rows = Rows(arrs, idx, dev)
    y_gate = arrs["y_gate"][idx].astype(int)
    y_slot = arrs["y_slot"][idx].astype(int)
    y_cell = cell_label(torch.from_numpy(arrs["y_xy"][idx]), grid).numpy()
    gate_hit = card_hit = cell_hit = n_play = 0
    tp = fp = tn = fn = 0
    p_all = []
    with torch.no_grad():
        for s0 in range(0, len(idx), 512):
            sl = idx[s0:s0 + 512]
            b = rows.batch(sl)
            enc = model.encode(b["tok"], b["mask"], b["sc"], b["past"])
            h = model.heads(enc, hand_mask_from_sc(b["sc"]))
            p = torch.sigmoid(h["gate"]).cpu().numpy()
            p_all.append(p)
            lo, hi = s0, s0 + len(sl)
            pred = (p > tau).astype(int)
            truth = y_gate[lo:hi]
            gate_hit += int((pred == truth).sum())
            tp += int(((pred == 1) & (truth == 1)).sum()); fp += int(((pred == 1) & (truth == 0)).sum())
            tn += int(((pred == 0) & (truth == 0)).sum()); fn += int(((pred == 0) & (truth == 1)).sum())
            play = y_gate[lo:hi] == 1
            if play.any():
                card = h["card"].argmax(-1).cpu().numpy()
                card_hit += int((card[play] == y_slot[lo:hi][play]).sum())
                true_slot = torch.from_numpy(y_slot[lo:hi]).clamp(min=0).to(dev)
                cell = model.cell_logits(enc, true_slot).argmax(-1).cpu().numpy()
                cell_hit += int((cell[play] == y_cell[lo:hi][play]).sum())
                n_play += int(play.sum())
    p = np.concatenate(p_all)
    # BALANCED accuracy and the always-WAIT baseline, because the teacher plays only ~24% of decisions:
    # a model that never plays scores ~76% raw accuracy, so raw gate agreement alone means nothing here.
    rec_pos = tp / max(tp + fn, 1)
    rec_neg = tn / max(tn + fp, 1)
    return {"n": int(len(idx)), "n_play": n_play,
            "gate_bal_acc": round(0.5 * (rec_pos + rec_neg), 4),
            "gate_recall_play": round(rec_pos, 4), "gate_recall_wait": round(rec_neg, 4),
            "always_wait_acc": round(float(1.0 - y_gate.mean()), 4),
            "gate_agree_pct": round(100.0 * gate_hit / max(len(idx), 1), 2),
            "card_agree_pct": round(100.0 * card_hit / max(n_play, 1), 2),
            "cell_agree_pct": round(100.0 * cell_hit / max(n_play, 1), 2),
            "teacher_play_rate": round(float(y_gate.mean()), 4),
            "model_play_rate_at_tau": round(float((p > tau).mean()), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, action="append", required=True)
    ap.add_argument("--teacher", type=Path, required=True)
    ap.add_argument("--pro", type=Path, default=None)
    ap.add_argument("--tau", type=float, default=0.27)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    import torch
    from pipeline.dataset import load as load_ds
    from pipeline.model_v3 import S1Model, cell_label, hand_mask_from_sc
    from pipeline.train_s1 import Rows, evaluate

    dev = torch.device("cpu")
    t_arrs, _ = load_ds(a.teacher)
    t_idx = np.flatnonzero(t_arrs["split"] == 1)          # held-out MATCHES
    pro_arrs = pro_idx = None
    if a.pro is not None:
        pro_arrs, _ = load_ds(a.pro)
        pro_idx = np.flatnonzero(pro_arrs["split"] == 1)

    out = []
    for ck in a.ckpt:
        model, grid, epoch = load_model(ck, torch, S1Model, dev)
        rec = {"ckpt": ck.name, "epoch": epoch, "grid": grid,
               "teacher_heldout": teacher_agreement(model, grid, t_arrs, t_idx, torch, a.tau,
                                                    Rows, cell_label, hand_mask_from_sc, dev)}
        if pro_arrs is not None:
            m = evaluate(model, Rows(pro_arrs, pro_idx, dev), grid=grid)
            rec["pro_val"] = {"cell_half_top1": round(float(m["cell_half_top1"]), 4),
                              "card_top1": round(float(m["card_top1"]), 4),
                              "place_dist": round(float(m["place_dist"]), 4),
                              "gate_acc": round(float(m["gate_acc"]), 4)}
        out.append(rec)
        print(json.dumps(rec), flush=True)
    if a.out:
        a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
