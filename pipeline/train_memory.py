"""Imitation of public replay decisions with ONLY history.* trainable and a base-policy KL anchor."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import time

import numpy as np
import torch
from torch.nn import functional as F

from .model_gen import load_model
from .eval_gen import GenRows
from .train_gen import losses


def freeze_base(model):
    if not hasattr(model, 'history'):
        raise ValueError('convert checkpoint with add_memory first')
    for name, p in model.named_parameters():
        p.requires_grad_(name.startswith('history.'))
    # Keep the frozen trunk deterministic. Gradients still flow through it.
    model.eval()
    return [p for p in model.parameters() if p.requires_grad]


def policy_kl(student, teacher):
    """KL(base || learner), with padding excluded before log_softmax (no 0*-inf)."""
    terms = []
    for key in ('card', 'wait', 'cell', 'value'):
        a, b = student[key], teacher[key].detach()
        valid = torch.isfinite(b)
        a, b = a.masked_fill(~valid, -1e9), b.masked_fill(~valid, -1e9)
        terms.append((b.softmax(-1)*(b.log_softmax(-1)-a.log_softmax(-1))).sum(-1).mean())
    a, b = student['gate'], teacher['gate'].detach()
    p = b.sigmoid()
    terms.append((p*(F.logsigmoid(b)-F.logsigmoid(a)) +
                  (1-p)*(F.logsigmoid(-b)-F.logsigmoid(-a))).mean())
    return sum(terms)


def anchored_loss(model, base, batch, kl_weight, grid='lattice'):
    if kl_weight <= 0:
        raise ValueError('positive KL anchor is mandatory')
    imitation, _ = losses(model, batch, mirror=False, grid=grid)
    with torch.no_grad():
        reference = base(batch, card=batch['card'], form=batch['form'])
    output = model(batch, card=batch['card'], form=batch['form'])
    kl = policy_kl(output, reference)
    return imitation + kl_weight*kl, imitation.detach(), kl.detach()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--init', type=Path, required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--epochs', type=int, default=3)
    p.add_argument('--bs', type=int, default=128)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--kl', type=float, default=1.0)
    p.add_argument('--seed', type=int, default=74)
    p.add_argument('--device', default='cuda')
    p.add_argument('--limit-rows', type=int, default=0)
    p.add_argument('--val-rows', type=int, default=10000)
    a = p.parse_args(argv)
    if min(a.epochs, a.bs, a.lr, a.kl, a.val_rows) <= 0:
        raise ValueError('positive training budgets and KL required')
    torch.manual_seed(a.seed)
    model, checkpoint = load_model(a.init, torch.device(a.device))
    params = freeze_base(model)
    base = copy.deepcopy(model)
    del base.history
    for param in base.parameters():
        param.requires_grad_(False)
    from .dataset_spool import load_mapped
    a.out.parent.mkdir(parents=True, exist_ok=True)
    arrs, meta = load_mapped(a.data, a.out.parent / f'dataset_cache_{time.time_ns()}')
    if (not meta.get('history_events') or meta['history_cap'] != model.history.cap or
            meta['card_vocab'] != checkpoint['card_vocab'] or
            meta['feature_version'] not in (model.feature_version, 5 if model.feature_version == 6 else model.feature_version)):
        raise ValueError('dataset/history/vocabulary/feature schema mismatch')
    train = np.flatnonzero(arrs['split'] == 0)
    val = np.flatnonzero(arrs['split'] == 1)
    rng = np.random.default_rng(a.seed)
    if a.limit_rows and len(train) > a.limit_rows:
        train = rng.choice(train, a.limit_rows, replace=False)
    if len(val) > a.val_rows:
        val = rng.choice(val, a.val_rows, replace=False)
    if not len(train) or not len(val):
        raise ValueError('nonempty replay-disjoint train and validation splits required')
    rows = GenRows(arrs, train, a.device)
    opt = torch.optim.AdamW(params, lr=a.lr)
    initial = {k: v.detach().cpu().clone() for k, v in model.state_dict().items() if not k.startswith('history.')}
    metrics, best = [], float('inf')
    for epoch in range(a.epochs):
        total = 0.0
        for start in range(0, len(train), a.bs):
            if start == 0:
                order = rng.permutation(train)
            b = rows.batch(order[start:start+a.bs])
            opt.zero_grad(set_to_none=True)
            loss, _, _ = anchored_loss(model, base, b, a.kl, checkpoint['args'].get('grid', 'lattice'))
            if not torch.isfinite(loss):
                raise ValueError('nonfinite memory loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0, error_if_nonfinite=True)
            opt.step()
            total += float(loss.detach())*len(b['gate'])
        score = anchor = 0.0
        with torch.no_grad():
            for start in range(0, len(val), a.bs):
                b = rows.batch(val[start:start+a.bs])
                loss, _, kl = anchored_loss(model, base, b, a.kl, checkpoint['args'].get('grid', 'lattice'))
                score += float(loss)*len(b['gate'])
                anchor += float(kl)*len(b['gate'])
        score /= len(val)
        if not all(torch.equal(initial[k], v.cpu()) for k, v in model.state_dict().items() if k in initial):
            raise AssertionError('frozen base changed')
        metrics.append(dict(epoch=epoch+1, train_loss=total/len(train), val_loss=score, val_kl=anchor/len(val)))
        if score < best:
            best = score
            out = {k: v for k, v in checkpoint.items() if k != 'rl'}
            out.update(model={k: v.cpu() for k, v in model.state_dict().items()}, memory_pretrain=dict(
                parameters='history.* only', kl_weight=a.kl, epoch=epoch+1, seed=a.seed, val_loss=score))
            torch.save(out, a.out)
        a.out.with_suffix('.metrics.json').write_text(json.dumps(metrics, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(metrics[-1]), flush=True)


if __name__ == '__main__':
    main()
