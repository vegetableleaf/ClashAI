"""Explicit-only pro fine-tune: card pointer (optional cell head), ordinary KL.

No RL, gate loss, trunk updates, deployment or runtime policy hooks. Candidate
epochs must improve held-out pending CE and keep ordinary top-card drift <1%.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

import numpy as np
import torch
from torch.nn import functional as F

from .eval_gen import GenRows
from .model_gen import load_model
from .model_v3 import cell_label
from .pending_states import digest


def head_parameter(name, train_cell=False):
    # Identity embeddings and tower-refinement features are shared: freeze them.
    return name.startswith(('card_q.', 'card_b.')) or (train_cell and
           (name.startswith(('query.', 'cell_key.')) or name == 'cell_bias'))


def freeze_heads(model, train_cell=False):
    for name, param in model.named_parameters():
        param.requires_grad_(head_parameter(name, train_cell))
    model.eval()  # frozen dropout/buffers cannot drift
    params = [p for p in model.parameters() if p.requires_grad]
    if not params:
        raise ValueError('no supported generalist head parameters')
    return params


def top_card_drift(student, teacher):
    """Fraction of valid-hand rows whose top hand position changes (ties: first)."""
    valid = torch.isfinite(teacher).any(-1)
    if not valid.any():
        raise ValueError('no valid ordinary hands')
    return (student[valid].argmax(-1) != teacher[valid].argmax(-1)).float().mean()


def head_kl(student, teacher):
    teacher = teacher.detach()
    valid = torch.isfinite(teacher)
    rows = valid.any(-1)
    if not rows.any():
        raise ValueError('no valid anchor logits')
    a = student[rows].masked_fill(~valid[rows], -1e9)
    b = teacher[rows].masked_fill(~valid[rows], -1e9)
    return (b.softmax(-1) * (b.log_softmax(-1) - a.log_softmax(-1))).sum(-1).mean()


def forward(model, batch, train_cell):
    return model(batch, card=batch['card'], form=batch['form']) if train_cell else model(batch)


def pro_loss(output, batch, grid, train_cell):
    loss = F.cross_entropy(output['card'], batch['slot'])
    if train_cell:
        loss = loss + F.cross_entropy(output['cell'], cell_label(batch['xy'], grid))
    return loss


def anchored_loss(model, base, pending, ordinary, kl_weight=100., grid='lattice', train_cell=False):
    if not np.isfinite(kl_weight) or kl_weight <= 0:
        raise ValueError('a positive ordinary-state KL anchor is mandatory')
    imitation = pro_loss(forward(model, pending, train_cell), pending, grid, train_cell)
    # For WAIT anchors the cell anchor is conditioned on the base's top card,
    # not pad card 0. Card-only training never evaluates a cell head.
    with torch.no_grad():
        ref_card = base(ordinary)['card']
        pos = ref_card.argmax(-1, keepdim=True)
        ordinary = dict(ordinary, card=ordinary['hand_card'].gather(1, pos).squeeze(1),
                        form=ordinary['hand_form'].gather(1, pos).squeeze(1))
        reference = forward(base, ordinary, train_cell)
    output = forward(model, ordinary, train_cell)
    kl = head_kl(output['card'], reference['card'])
    if train_cell:
        kl = kl + head_kl(output['cell'], reference['cell'])
    return imitation + kl_weight * kl, imitation.detach(), kl.detach()


def eligible(drift, pending_ce, starting_ce, max_drift=.01):
    return np.isfinite(drift) and drift < max_drift and pending_ce < starting_ce


@torch.no_grad()
def measure(model, base, batch, pending, ordinary, bs, grid, train_cell):
    ce = changed = count = 0
    for start in range(0, len(pending), bs):
        b = batch(pending[start:start+bs])
        ce += float(pro_loss(forward(model, b, train_cell), b, grid, train_cell)) * len(b['gate'])
    for start in range(0, len(ordinary), bs):
        b = batch(ordinary[start:start+bs])
        a, ref = model(b)['card'], base(b)['card']
        valid = torch.isfinite(ref).any(-1)
        changed += int((a[valid].argmax(-1) != ref[valid].argmax(-1)).sum())
        count += int(valid.sum())
    if not count or not len(pending):
        raise ValueError('empty validation sample')
    return dict(pending_ce=ce/len(pending), ordinary_top_card_drift=changed/count,
                ordinary_changed=changed, ordinary_n=count)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--init', type=Path, required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--pending', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=5)
    p.add_argument('--bs', type=int, default=256)
    p.add_argument('--lr', type=float, default=1e-4)
    p.add_argument('--kl', type=float, default=100.)
    p.add_argument('--ordinary-rows', type=int, default=100000)
    p.add_argument('--val-rows', type=int, default=30000)
    p.add_argument('--max-drift', type=float, default=.01)
    p.add_argument('--train-cell', action='store_true')
    p.add_argument('--seed', type=int, default=74)
    p.add_argument('--device', default='cuda')
    a = p.parse_args(argv)
    if min(a.epochs, a.bs, a.lr, a.kl, a.ordinary_rows, a.val_rows, a.max_drift) <= 0 or a.max_drift > .01:
        raise ValueError('positive budgets required; max drift must be <= .01')
    if a.out.exists() or a.out.with_suffix('.metrics.json').exists():
        raise FileExistsError(a.out)
    with np.load(a.pending, allow_pickle=False) as z:
        index_meta = json.loads(str(z['meta']))
        pending, ordinary = z['pending'], z['ordinary']
    if digest(a.data) != index_meta['source_sha256']:
        raise ValueError('pending indexes do not match source corpus')
    torch.manual_seed(a.seed)
    model, checkpoint = load_model(a.init, torch.device(a.device))
    params = freeze_heads(model, a.train_cell)
    base = copy.deepcopy(model)
    for param in base.parameters():
        param.requires_grad_(False)
    from .dataset_spool import load_mapped
    a.out.parent.mkdir(parents=True, exist_ok=True)
    arrays, meta = load_mapped(a.data, a.out.parent / f'dataset_cache_{time.time_ns()}')
    fv = model.feature_version
    if (meta['card_vocab'] != checkpoint['card_vocab'] or meta['grid'] != checkpoint['args'].get('grid', 'lattice')
            or meta['feature_version'] not in (fv, 5 if fv == 6 else fv)
            or (hasattr(model, 'history') and (not meta.get('history_events') or meta.get('history_cap') != model.history.cap))):
        raise ValueError('dataset/checkpoint schema mismatch')
    train = pending[arrays['split'][pending] == 0]
    val = pending[arrays['split'][pending] == 1]
    rng = np.random.default_rng(a.seed)
    def sample(ids, n):
        return np.sort(rng.choice(ids, min(n, len(ids)), replace=False))
    anchor = sample(ordinary[arrays['split'][ordinary] == 0], a.ordinary_rows)
    heldout = sample(ordinary[arrays['split'][ordinary] == 1], a.val_rows)
    if any(len(ids) == 0 for ids in (train, val, anchor, heldout)):
        raise ValueError('nonempty replay-disjoint pending and ordinary splits required')
    # Keep full corpus on CPU, transfer only this batch (including public rows).
    rows = GenRows(arrays, train, 'cpu')
    def batch(ids):
        return {k: v.to(a.device) for k, v in rows.batch(ids).items()}
    np.savez_compressed(a.out.with_suffix('.samples.npz'), pending_train=train, pending_val=val,
                        ordinary_train=anchor, ordinary_val=heldout)
    initial = {k: v.detach().cpu().clone() for k, v in model.state_dict().items() if not head_parameter(k, a.train_cell)}
    grid = meta['grid']
    baseline = measure(model, base, batch, val, heldout, a.bs, grid, a.train_cell)
    history = [dict(epoch=0, **baseline)]
    best = baseline['pending_ce']
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.)
    for epoch in range(1, a.epochs+1):
        order, anchors = rng.permutation(train), rng.permutation(anchor)
        # Every sampled ordinary row participates each epoch. Pending rows cycle
        # when the anchor corpus is larger; no ordinary imitation loss is used.
        totals = np.zeros(3)
        steps = (max(len(order), len(anchors)) + a.bs - 1) // a.bs
        for step in range(steps):
            ix = np.arange(step*a.bs, (step+1)*a.bs)
            b, ordinary_b = batch(order[ix % len(order)]), batch(anchors[ix % len(anchors)])
            opt.zero_grad(set_to_none=True)
            loss, ce, kl = anchored_loss(model, base, b, ordinary_b, a.kl, grid, a.train_cell)
            if not torch.isfinite(loss):
                raise ValueError('nonfinite pending loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1., error_if_nonfinite=True)
            opt.step()
            totals += [float(loss.detach()), float(ce), float(kl)]
        metrics = measure(model, base, batch, val, heldout, a.bs, grid, a.train_cell)
        ok = eligible(metrics['ordinary_top_card_drift'], metrics['pending_ce'], baseline['pending_ce'], a.max_drift)
        if not all(torch.equal(initial[k], v.cpu()) for k, v in model.state_dict().items() if k in initial):
            raise AssertionError('frozen parameters or buffers changed')
        history.append(dict(epoch=epoch, **metrics, eligible=bool(ok),
                            train_loss=totals[0]/steps, train_ce=totals[1]/steps, train_kl=totals[2]/steps))
        if ok and metrics['pending_ce'] < best:
            best = metrics['pending_ce']
            out = {k: v for k, v in checkpoint.items() if k not in ('model', 'rl')}
            out.update(model={k: v.detach().cpu() for k, v in model.state_dict().items()},
                       pending_pretrain=dict(epoch=epoch, **metrics, init_sha256=digest(a.init),
                           source_sha256=index_meta['source_sha256'], kl=a.kl, seed=a.seed,
                           train_cell=a.train_cell, trainable=[n for n, p in model.named_parameters() if p.requires_grad]))
            torch.save(out, a.out)
        a.out.with_suffix('.metrics.json').write_text(json.dumps(history, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(history[-1]), flush=True)
    if not a.out.exists():
        raise RuntimeError('no epoch improved pending validation within the ordinary drift bound; no checkpoint saved')


if __name__ == '__main__':
    main()
