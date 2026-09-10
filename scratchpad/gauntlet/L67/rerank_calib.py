"""L67n: CALIBRATE the reranker's play/wait threshold before any sim run -- and grade it on an untouched fold.

Found by the 1-match smoke run: at margin 0 the v1 head played 3 times and waited 226 (tower -2.59), i.e. it
became the never-play arm, which was the worst arm measured (0/12 wins, -2.40). The cause is the target, not a
bug: 89.6% of training candidates have NEGATIVE advantage over WAIT (only 10.4% beat it), so a regressor learns to
predict "worse than waiting" nearly everywhere (median predicted advantage -0.062) and a fixed 0 threshold almost
never trips. Offline balanced accuracy (0.62) did not reveal how rarely it would act in closed loop.

Calibration, not retraining: on the SELECT fold, choose the margin whose play rate equals the SEARCH's own play
rate there (the share of decisions whose best candidate beats WAIT). Then report regret on the REPORT fold, which
neither training nor this calibration touched, at margin 0 and at the calibrated margin, beside the baselines.

usage: python scratchpad/gauntlet/L67/rerank_calib.py --ckpt <v6lat_s0.pt> --shards rr_0..2.npz --heads h1.pt h2.pt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rerank_train import encode_all, grade, load_head, load_shards      # noqa: E402


def per_decision_max(pred, coff, dec_ids):
    return np.array([float(pred[coff[i]:coff[i + 1]].max()) for i in dec_ids if coff[i + 1] > coff[i]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--shards", type=Path, nargs="+", required=True)
    ap.add_argument("--heads", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, default=Path("scratchpad/gauntlet/L67/rerank/calib.json"))
    a = ap.parse_args()

    from pipeline.model_v3 import S1Model

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = load_shards(a.shards)
    st = torch.load(a.ckpt, map_location=dev)
    args = dict(st.get("args", {}) or {})
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(dev)
    model.load_state_dict(st["model"]); model.eval()
    G, CP = encode_all(model, data, dev)

    coff = data["cand_off"]
    dec_of = np.repeat(np.arange(len(G)), np.diff(coff))
    adv = (data["cand_score"] - data["wait_score"][dec_of]).astype(np.float32)
    fold = data["fold"]
    sel_dec = [i for i in np.flatnonzero(fold == 0) if coff[i + 1] > coff[i]]
    rep_dec = [i for i in np.flatnonzero(fold == 1) if coff[i + 1] > coff[i]]
    search_rate_sel = float(np.mean(per_decision_max(adv, coff, sel_dec) > 0))
    search_rate_rep = float(np.mean(per_decision_max(adv, coff, rep_dec) > 0))
    print(f"search play rate: select fold {search_rate_sel:.3f}, report fold {search_rate_rep:.3f}", flush=True)

    Gt = torch.from_numpy(G); CPt = torch.from_numpy(CP)
    slot_t = torch.from_numpy(data["cand_slot"].astype(np.int64))
    cell_t = torch.from_numpy(data["cand_cell"].astype(np.int64))
    dec_t = torch.from_numpy(dec_of)

    rows = []
    for hp in a.heads:
        head, hst = load_head(hp)
        pred = np.zeros_like(adv)
        with torch.no_grad():
            for s0 in range(0, len(adv), 16384):
                ii = torch.arange(s0, min(len(adv), s0 + 16384))
                pred[s0:s0 + len(ii)] = head(Gt[dec_t[ii]], CPt[ii], slot_t[ii], cell_t[ii]).numpy()
        mx_sel = per_decision_max(pred, coff, sel_dec)
        margin = float(np.quantile(mx_sel, 1.0 - search_rate_sel))            # play rate on SELECT = search's
        mx_rep = per_decision_max(pred, coff, rep_dec)
        r0 = grade(pred, adv, coff, rep_dec, 0.0, np.random.default_rng(0))
        rc = grade(pred, adv, coff, rep_dec, margin, np.random.default_rng(0))
        rec = {"head": hp.name, "epoch": hst.get("epoch"), "hidden": hst.get("hidden", 256),
               "dropout": hst.get("dropout", 0.0), "calibrated_margin": round(margin, 4),
               "report_corr": round(float(np.corrcoef(pred[np.isin(dec_of, rep_dec)], adv[np.isin(dec_of, rep_dec)])[0, 1]), 4),
               "report_play_rate_margin0": round(float(np.mean(mx_rep > 0.0)), 4),
               "report_play_rate_calibrated": round(float(np.mean(mx_rep > margin)), 4),
               "report_regret_margin0": r0["rerank"], "report_regret_calibrated": rc["rerank"],
               "report_bal_acc_calibrated": rc["play_bal_acc"],
               "report_top1_when_play_is_right": rc["top1_when_play_is_right"],
               "baseline_always_wait": rc["always_wait"], "baseline_student_top": rc["student_top"],
               "baseline_random": rc["random_cand"], "search_play_rate_report": round(search_rate_rep, 4)}
        rows.append(rec)
        print(json.dumps(rec), flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
