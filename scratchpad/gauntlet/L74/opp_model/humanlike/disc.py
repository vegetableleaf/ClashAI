"""P2-SCORE level C: a FRESH match-level discriminator per evaluation (plan1026 Pillar 2 / REPORT_opponents section 4).

A 2-layer transformer over one match's event stream: the opponent's plays (card, tick, x, y, cost, spell) plus our plays (tick
only: our deck is the same in every match), CLS token -> P(model).  Deck conditioning comes only from the cards PLAYED (a "seen
cards" input would separate live (seen) from SIM (full deck) by construction).  Trained on 70% of the matches of each class
(match-level split), held-out AUC on the other 30% with a bootstrap 90% CI.  Pass (THRESHOLDS C): upper CI <= 0.55 overall and
<= 0.58 per archetype with n per class >= n_per_class_min; below that n the level FAILS (sufficiency rule).

    python -I disc.py selftest --hf data/hf_ref_bec5811a.json.gz     # human vs human halves, planted bugs
Card keys pass through weekend/archetypes.canon (one spelling for the detector, engine and HF slugs)."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / 'weekend')]
MAXLEN = 160
NUM = 9          # t, x, y, cost, spell, valid, dt since any / same-side / other-side event (s / 10, cap 10 s)


def _spell(k):
    import card as C
    return C._spell(k)


def encode(recs, vocab):
    import archetypes as A
    X = np.zeros((len(recs), MAXLEN, NUM), np.float32)
    C = np.zeros((len(recs), MAXLEN), np.int64)            # 0 pad, 1 our play, 2.. opponent card
    for i, r in enumerate(recs):
        ev = [(p[0], vocab.setdefault(A.canon(p[1]), len(vocab) + 2), p[3] / 18, p[4] / 32, (p[2] or 0) / 10, float(_spell(p[1])))
              for p in r['plays']] + [(t, 1, 0.0, 0.0, 0.0, 0.0) for t in r['mine']]
        ev.sort(key=lambda e: e[0])
        last = {0: None, 1: None}                          # relative timing made explicit: a 1 s tempo shift is 0.003 of t / 6000
        prev = None
        for j, (t, c, x, y, cost, sp) in enumerate(ev[:MAXLEN]):
            mine = int(c == 1)
            da = min(10.0, (t - prev) / 20) / 10 if prev is not None else 1.0
            ds = min(10.0, (t - last[mine]) / 20) / 10 if last[mine] is not None else 1.0
            do = min(10.0, (t - last[1 - mine]) / 20) / 10 if last[1 - mine] is not None else 1.0
            prev, last[mine] = t, t
            C[i, j] = c
            X[i, j] = (t / 6000, x, y, cost, sp, 1.0, da, ds, do)
    return C, X


def auc(y, p):
    o = np.argsort(p)
    r = np.empty(len(p))
    r[o] = np.arange(1, len(p) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float('nan')


def train_eval(H, M, seed=0, epochs=12, device=None, threads=4):
    """H human records, M model records -> dict(auc, ci, n_h, n_m, test predictions)."""
    import torch
    import torch.nn as nn
    import os
    device = device or os.environ.get('DISC_DEVICE', 'cpu')
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    rng = random.Random(seed)
    vocab = {}
    ch, xh = encode(H, vocab)
    cm, xm = encode(M, vocab)
    C = np.concatenate([ch, cm])
    X = np.concatenate([xh, xm])
    y = np.concatenate([np.zeros(len(H)), np.ones(len(M))]).astype(np.float32)
    idx = list(range(len(y)))
    rng.shuffle(idx)
    cut = int(0.7 * len(idx))
    tr, te = np.array(idx[:cut]), np.array(idx[cut:])

    class Net(nn.Module):
        def __init__(s, nv, d=64):
            super().__init__()
            s.emb = nn.Embedding(nv, d, padding_idx=0)
            s.num = nn.Linear(NUM, d)
            s.cls = nn.Parameter(torch.zeros(1, 1, d))
            s.enc = nn.TransformerEncoder(nn.TransformerEncoderLayer(d, 4, 128, 0.1, batch_first=True), 2)
            s.out = nn.Linear(d, 1)

        def forward(s, c, x):
            h = s.emb(c) + s.num(x)
            h = torch.cat([s.cls.expand(len(c), 1, -1), h], 1)
            pad = torch.cat([torch.zeros(len(c), 1, dtype=torch.bool, device=c.device), c == 0], 1)
            return s.out(s.enc(h, src_key_padding_mask=pad)[:, 0]).squeeze(1)

    net = Net(len(vocab) + 3).to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-2)
    Ct, Xt, yt = (torch.tensor(a) for a in (C, X, y))
    w = torch.tensor([len(y) / (2 * max(1, (y == 0).sum())), len(y) / (2 * max(1, (y == 1).sum()))])   # class balance
    for _ in range(epochs):
        net.train()
        perm = np.random.RandomState(seed + _).permutation(tr)
        for k in range(0, len(perm), 128):
            b = perm[k:k + 128]
            yb = yt[b].to(device)
            loss = (nn.functional.binary_cross_entropy_with_logits(net(Ct[b].to(device), Xt[b].to(device)), yb, reduction='none')
                    * w[yb.long().cpu()].to(device)).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    net.eval()
    with torch.no_grad():
        p = np.concatenate([torch.sigmoid(net(Ct[te[k:k + 512]].to(device), Xt[te[k:k + 512]].to(device))).cpu().numpy()
                            for k in range(0, len(te), 512)])
    yte = y[te]
    a = auc(yte, p)
    bs = []
    r2 = np.random.RandomState(seed)
    for _ in range(400):
        s = r2.randint(0, len(te), len(te))
        bs.append(auc(yte[s], p[s]))
    bs = sorted(x for x in bs if x == x)
    return dict(auc=a, ci=(bs[int(.05 * len(bs))], bs[int(.95 * len(bs)) - 1]), n_h=len(H), n_m=len(M), te=te, p=p, y=yte)


def level_c(H, M, th, tag='', seed=0):
    C = th['C']
    r = train_eval(H, M, seed)
    arch = {}
    allrec = H + M
    for a in sorted({x['arch'] for x in allrec}):
        sel = np.array([allrec[i]['arch'] == a for i in r['te']])
        if sel.sum() >= 40 and 0 < r['y'][sel].sum() < sel.sum():
            arch[a] = (int(sel.sum()), auc(r['y'][sel], r['p'][sel]))
    enough = min(len(H), len(M)) >= C['n_per_class_min']
    ok = enough and r['ci'][1] <= C['auc_upper_ci_max_overall']
    return dict(auc=r['auc'], ci=r['ci'], n_h=len(H), n_m=len(M), enough=bool(enough), arch=arch, passed=bool(ok))


def fmt(c):
    if 'auc' not in c:
        return f'FAIL -- {c.get("why")}'
    return (f'AUC {c["auc"]:.3f} 90% CI [{c["ci"][0]:.3f}, {c["ci"][1]:.3f}] (human {c["n_h"]}, model {c["n_m"]}; need >= 5,000 per class: '
            f'{c["enough"]}) per arch (held-out n, AUC): ' + ', '.join(f'{a} {n} {v:.2f}' for a, (n, v) in c['arch'].items())
            + f' => {"PASS" if c["passed"] else "FAIL"}')


def selftest(hf, out=None):
    import card as CD
    th, _ = CD.SC.load_thresholds()
    lines = []
    L = CD.live_records('calibration')
    a, b = CD.halves(L, 0)
    r = train_eval(a, b, 0)
    lines.append(f'live calibration halves ({len(a)} / {len(b)}): AUC {r["auc"]:.3f} [{r["ci"][0]:.3f}, {r["ci"][1]:.3f}]')
    bad = [dict(x, plays=[[p[0] + 20] + p[1:] for p in x['plays']]) for x in b]
    r = train_eval(a, bad, 0)
    lines.append(f'planted: half B plays 1 s later: AUC {r["auc"]:.3f} [{r["ci"][0]:.3f}, {r["ci"][1]:.3f}]')
    if hf:
        H, _ = CD.hf_records(hf)
        tags = sorted({x['tag'] for x in H})
        ta, tb = CD.halves(tags, 0)
        ta, tb = set(ta[:5000]), set(tb[:5000])
        xa = [x for x in H if x['tag'] in ta and x['side'] == 0]
        xb = [x for x in H if x['tag'] in tb and x['side'] == 0]
        r = train_eval(xa, xb, 0)
        lines.append(f'HF human halves (5,000 matches each, side 0): AUC {r["auc"]:.3f} [{r["ci"][0]:.3f}, {r["ci"][1]:.3f}]')
        sh = [dict(x, plays=[[p[0] + 20] + p[1:] for p in x['plays']]) for x in xb]
        r = train_eval(xa, sh, 0)
        lines.append(f'planted HF: half B plays 1 s later: AUC {r["auc"]:.3f} [{r["ci"][0]:.3f}, {r["ci"][1]:.3f}]')
        r = train_eval(xa[:len(L)], L, 0)
        lines.append(f'HF humans vs live humans (instrument + population gap, {len(L)} each): AUC {r["auc"]:.3f} [{r["ci"][0]:.3f}, {r["ci"][1]:.3f}]')
    txt = '\n'.join(lines)
    print(txt)
    if out:
        Path(out).write_text(txt + '\n', encoding='utf-8')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('selftest',))
    ap.add_argument('--hf', default=None)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    selftest(a.hf, a.out)
