"""O2 (pod): fine-tune the pro-imitation net gen_v32_s0 on O1's OPPONENT-seat live rows; time-ordered holdout.
Run from a pod checkout root (imports pipeline.*), any CUDA torch venv:

    python scratchpad/gauntlet/L74/opp_model/pod/o2_finetune.py --init icebow/data/pipeline/gen_v32_s0/gen_s0.pt \
        --train o1_train_v32.npz --val o1_holdout_v32.npz --out-dir o2_out --seed 0 [--epochs 8] [--lr 3e-5]

Only rows with opp_mask == 1 train / validate (our own seat's rows are the live model's play, never targets). Losses, batching,
mirror augmentation and metrics are pipeline.train_gen's / eval_gen's unchanged (card CE over the hand, cell CE, gate BCE,
0.5 x wait CE, 0.5 x crown CE). Epoch 0 = the untouched gen_v32_s0 scored on the same holdout (the baseline the acceptance
compares with). The best epoch by --select (default: holdout card_top1 + cell_tile_top1 + gate_bal_acc) is saved in
train_gen's checkpoint layout, so it loads wherever gen_v32_s0 loads (gap.py --opp-ckpt, rl_royale inits / league opponents).
No pipeline file is modified."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sys

import numpy as np
import torch

_up = Path(__file__).resolve().parents
if len(_up) > 5 and (_up[5] / 'pipeline').is_dir():                 # run from a checkout (scratchpad/gauntlet/L74/opp_model/pod/..)
    sys.path.insert(0, str(_up[5]))                                  # else: PYTHONPATH names the checkout (o2_pod.sh)
from pipeline.dataset import load as load_ds
from pipeline.eval_gen import evaluate
from pipeline.model_gen import GenModel
from pipeline.train_gen import GenRows, losses


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def score(ev):
    return ev['card_top1'] + ev['cell_tile_top1'] + ev['gate_bal_acc']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--init', type=Path, required=True)
    ap.add_argument('--train', type=Path, required=True)
    ap.add_argument('--val', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--epochs', type=int, default=8)
    ap.add_argument('--lr', type=float, default=3e-5)
    ap.add_argument('--bs', type=int, default=256)
    ap.add_argument('--grid', default='lattice')
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    st = torch.load(a.init, map_location='cpu', weights_only=False)
    args = st['args']
    tr, mtr = load_ds(a.train)
    va, mva = load_ds(a.val)
    for m in (mtr, mva):
        if m['card_vocab'] != st['card_vocab']:
            raise SystemExit('O1 rows are not in the init checkpoint card vocabulary (run o1_finalize.py remap)')
    fv = int(args.get('feature_version') or mtr.get('feature_version'))
    model = GenModel(d=args['d'], layers=args['layers'], d_c=args['d_c'], n_cards=len(st['card_vocab']), feature_version=fv).to(dev)
    model.load_state_dict(st['model'])
    tr_idx = np.where(tr['opp_mask'] == 1)[0]
    va_idx = np.where(va['opp_mask'] == 1)[0]
    rows, vrows = GenRows(tr, tr_idx, dev), GenRows(va, va_idx, dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    tag = f'live_s{a.seed}'
    ckpt = a.out_dir / f'gen_{tag}.pt'
    hist = []
    model.eval()
    ev0 = evaluate(model, vrows, grid=a.grid)
    ev0.update(epoch=0, note='untouched init')
    hist.append(ev0)
    best = score(ev0)
    print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in ev0.items()}), flush=True)
    t0 = time.time()
    for ep in range(1, a.epochs + 1):
        model.train()
        perm = rng.permutation(tr_idx)
        tot = nb = 0
        for s in range(0, len(perm) - a.bs + 1, a.bs):
            b = rows.batch(perm[s:s + a.bs])
            loss, _ = losses(model, b, mirror=rng.random() < 0.5, grid=a.grid)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tot += float(loss.detach()); nb += 1
        model.eval()
        ev = evaluate(model, vrows, grid=a.grid)
        ev.update(epoch=ep, train_loss=tot / max(nb, 1), seconds=round(time.time() - t0))
        hist.append(ev)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in ev.items()}), flush=True)
        if score(ev) > best:
            best = score(ev)
            torch.save({'model': model.state_dict(), 'args': {**args, 'o2_finetune': {k: str(v) for k, v in vars(a).items()}},
                        'deck': 'generalist', 'epoch': ep, 'val': ev, 'n_params': st.get('n_params'), 'gen': True,
                        'card_vocab': st['card_vocab'], 'd_c': st['d_c'],
                        'o2': dict(init=str(a.init), init_sha256=sha(a.init), train_sha256=sha(a.train), val_sha256=sha(a.val),
                                   train_rows=int(len(tr_idx)), val_rows=int(len(va_idx)))}, ckpt)
    (a.out_dir / f'hist_{tag}.json').write_text(json.dumps(dict(seed=a.seed, train_rows=int(len(tr_idx)), val_rows=int(len(va_idx)),
                                                               hist=hist, best_score=best, saved=ckpt.exists()), indent=1))
    print(json.dumps({'FINAL': tag, 'best_score': round(best, 4), 'base_score': round(score(ev0), 4), 'saved': ckpt.exists()}))


if __name__ == '__main__':
    main()
