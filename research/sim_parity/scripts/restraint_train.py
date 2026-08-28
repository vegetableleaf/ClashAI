"""RESTRAINT HEAD: given that the policy wants to play, is this a play the teacher would make?

§5i measured the signal with a LINEAR probe on the board crushed to 24 numbers: held-out AUC 0.667.
This trains the real thing -- a conv over the full 96x64x12 observation plus the same tabular state
the policy reads -- and reports held-out AUC by MATCH.

WHY THIS IS NOT THE GATE DISTILLATION THAT FAILED (§8, 0.5892 -> 0.6012 against an always-WAIT
floor of 0.7756): that fit the gate as a 2-way classifier over ALL decisions, 79% of which are
waits, so a model scored 0.776 by never playing and the loss barely rewarded learning WHEN. This
conditions on `pol_gate == 1` -- the policy already wants to play -- and asks only whether THIS play
is one the teacher endorses. Different question, and §5i showed the answer is separable.

WHY A VETO AND NOT A GRADIENT: every gradient-side intervention this project has measured moved the
mechanism and not the outcome (clip sign flip at 34 sigma -> no change in P(play); card distillation
at +4.2 sigma -> no change in winrate). A veto acts at DECISION TIME, which is where rollout search
gets 37.0% -> 85.7% out of the same frozen weights.

/!\ ACCURACY IS THE WRONG METRIC. The class is ~74/26, so "always call it an over-play" scores
~0.74. Judge on AUC, and on the operating point actually chosen.

    python restraint_train.py --corpus <npz> [--epochs 30] [--out head.pt]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank AUC. Positive = a play the TEACHER ALSO MAKES."""
    order = np.argsort(scores)
    t = labels[order]
    pos, neg = t.sum(), len(t) - t.sum()
    if pos == 0 or neg == 0:
        return float("nan")
    return float(np.cumsum(1 - t)[t == 1].sum() / (pos * neg))


class RestraintHead(nn.Module):
    """Small conv over the board + the tabular state the policy also reads."""

    def __init__(self, in_ch: int, tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, 16, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(32, 32, 3, stride=2, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Sequential(
            nn.Linear(32 + tab, 64), nn.ReLU(), nn.Dropout(0.3), nn.Linear(64, 1))

    def forward(self, obs, tab):
        z = self.conv(obs).flatten(1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--holdout", type=float, default=0.2)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("export PYTHONHASHSEED=0 first")
    torch.manual_seed(0)

    z = np.load(a.corpus, allow_pickle=False)
    pg = np.asarray(z["pol_gate"]).astype(int)
    tg = np.asarray(z["teach_gate"]).astype(int)
    match = np.asarray(z["match"]).astype(int)

    sel = np.nonzero(pg == 1)[0]                     # the policy wanted to play
    y = (tg[sel] == 1).astype(np.float32)            # 1 = teacher agrees, 0 = OVER-PLAY
    m = match[sel]
    print(f"policy-play decisions {len(sel)} | teacher agrees {y.mean():.4f} "
          f"| OVER-PLAYS {1 - y.mean():.4f}")

    obs = z["obs"][sel]                              # keep uint8; cast per batch
    tab = np.concatenate([z["hand"][sel], z["nxt"][sel], z["elx"][sel], z["thr"][sel]],
                         axis=1).astype(np.float32)

    # SPLIT BY MATCH. Consecutive decisions share a board; a row split leaks the answer.
    um = np.unique(m)
    rng = np.random.RandomState(0)
    rng.shuffle(um)
    te_m = set(um[: max(1, int(len(um) * a.holdout))].tolist())
    tr = np.array([i for i, v in enumerate(m) if v not in te_m])
    te = np.array([i for i, v in enumerate(m) if v in te_m])
    mu, sd = tab[tr].mean(0), tab[tr].std(0) + 1e-6
    tab = (tab - mu) / sd
    print(f"train {len(tr)} rows / test {len(te)} rows "
          f"({len(um) - len(te_m)} vs {len(te_m)} matches)")

    dev = torch.device("cpu")
    net = RestraintHead(obs.shape[3], tab.shape[1]).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr, weight_decay=1e-4)
    # CLASS WEIGHT: the positives (good plays) are the ~26% minority, so without this the loss is
    # minimised by calling everything an over-play -- which is the 0.74 baseline, not a model.
    pos_w = torch.tensor([(1.0 - y[tr].mean()) / max(1e-6, y[tr].mean())], device=dev)
    lossf = nn.BCEWithLogitsLoss(pos_weight=pos_w)
    print(f"pos_weight {float(pos_w):.3f}\n")

    def batches(idx, shuffle):
        idx = idx.copy()
        if shuffle:
            rng.shuffle(idx)
        for s in range(0, len(idx), a.batch):
            j = idx[s:s + a.batch]
            ob = torch.from_numpy(obs[j].astype(np.float32)).permute(0, 3, 1, 2).to(dev) / 255.0
            yield ob, torch.from_numpy(tab[j]).to(dev), torch.from_numpy(y[j]).to(dev)

    best = (0.0, -1)
    for ep in range(1, a.epochs + 1):
        net.train()
        for ob, tb, yy in batches(tr, True):
            opt.zero_grad()
            lossf(net(ob, tb), yy).backward()
            opt.step()
        net.eval()
        S = []
        with torch.no_grad():
            for ob, tb, _ in batches(te, False):
                S.append(net(ob, tb).cpu().numpy())
        s = np.concatenate(S)
        A = auc(s, y[te])
        if A > best[0]:
            best = (A, ep)
            if a.out:
                torch.save({"model": net.state_dict(), "mu": mu, "sd": sd,
                            "in_ch": int(obs.shape[3]), "tab": int(tab.shape[1]),
                            "auc": A, "epoch": ep}, a.out)
        if ep % 5 == 0 or ep == 1:
            print(f"  epoch {ep:3d}  held-out AUC {A:.4f}")
    print(f"\nBEST held-out AUC {best[0]:.4f} at epoch {best[1]}")
    print(f"  linear-probe baseline (§5i, crushed board): 0.6675")
    print(f"  chance: 0.5000")
    if a.out:
        print(f"  saved -> {a.out}")


if __name__ == "__main__":
    main()
