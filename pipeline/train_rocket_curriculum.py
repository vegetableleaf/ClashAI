"""Explicit, checkpoint-compatible expert curriculum fine-tuning experiment.

No new model inputs, heads, rewards or runtime action rules. Paired arms differ
only in row sampling. --smoke-one-batch is CPU-only and never saves a checkpoint.
"""
from __future__ import annotations

import argparse
import ctypes
import json
from pathlib import Path
import time
import zipfile

import numpy as np
import torch

from .eval_gen import GenRows, evaluate
from .model_gen import load_model
from .rocket_teaching import load_curriculum, sampling_probabilities, sha
from .train_gen import losses


def take(archive, name, ids):
    """Stream selected sorted rows with <=16MiB source chunks."""
    with archive.open(name + '.npy') as f:
        version = np.lib.format.read_magic(f)
        shape, fortran, dtype = (np.lib.format.read_array_header_1_0(f) if version == (1, 0)
                                 else np.lib.format.read_array_header_2_0(f))
        if fortran or dtype.hasobject:
            raise ValueError('Unsupported array layout')
        width = int(np.prod(shape[1:], dtype=np.int64)) * dtype.itemsize
        out = np.empty((len(ids),) + shape[1:], dtype)
        step = max(1, (16 << 20) // max(width, 1))
        for lo in range(0, shape[0], step):
            count = min(step, shape[0] - lo)
            buf = bytearray()
            while len(buf) < count * width:
                part = f.read(count * width - len(buf))
                if not part:
                    raise EOFError(name)
                buf += part
            a, b = np.searchsorted(ids, [lo, lo + count])
            if b > a:
                out[a:b] = np.frombuffer(buf, dtype).reshape((count,) + shape[1:])[ids[a:b] - lo]
        return out


def load_subset(path, ids):
    if len(ids) == 0 or np.any(np.diff(ids) <= 0):
        raise ValueError('Need sorted unique nonempty row ids')
    keys = ('sc hand_card hand_form next_card next_form deck_card deck_form past y_gate y_card '
            'y_hand_pos y_xy y_wait_card y_crowns tick side rep split deck_id opp_past opp_cycle '
            'projectiles effects own_ability y_cell').split()
    with np.load(path, allow_pickle=False) as z, zipfile.ZipFile(path) as archive:
        meta = json.loads(str(z['meta']))
        sub = {k: take(archive, k, ids) for k in keys}
        offsets = z['off']
        lengths = offsets[ids + 1] - offsets[ids]
        gather = np.concatenate([np.arange(offsets[i], offsets[i + 1]) for i in ids])
        sub['tok'] = take(archive, 'tok', gather)
        sub['unit_form'] = take(archive, 'unit_form', gather)
        sub['off'] = np.r_[0, np.cumsum(lengths)].astype(np.int64)
    return sub, meta


def train_step(model, batch, optimizer, mirror, grid):
    model.train()
    loss, parts = losses(model, batch, mirror=mirror, grid=grid)
    if not torch.isfinite(loss):
        raise ValueError('Nonfinite curriculum loss')
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    if not all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()):
        raise ValueError('Nonfinite curriculum gradients')
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    return float(loss.detach()), parts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--curriculum', type=Path, required=True)
    ap.add_argument('--init-ckpt', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--arm', choices=('uniform', 'curriculum'), required=True)
    ap.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    ap.add_argument('--steps', type=int, default=1000)
    ap.add_argument('--bs', type=int, default=128)
    ap.add_argument('--lr', type=float, default=1e-5)
    ap.add_argument('--seed', type=int, default=20261004)
    ap.add_argument('--smoke-one-batch', action='store_true')
    a = ap.parse_args(argv)
    if a.steps < 1 or a.bs < 1 or not np.isfinite(a.lr) or a.lr <= 0:
        raise ValueError('Invalid training parameters')
    if a.smoke_one_batch and a.device != 'cpu':
        raise ValueError('Smoke must be CPU-only')
    torch.set_num_threads(1)
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except AttributeError:
        pass
    with np.load(a.data, allow_pickle=False) as z:
        split, rep = z['split'], z['rep']
    cohorts, manifest = load_curriculum(a.curriculum, a.data, split)
    pool = cohorts['pool']
    train_reps = set(rep[pool & (split == 0)])
    if train_reps & set(rep[pool & (split != 0)]):
        raise ValueError('Replay leakage between train and held-out')
    ids = np.flatnonzero(pool)
    if a.smoke_one_batch:
        ids = np.unique(np.concatenate([np.flatnonzero(pool & (split == 0))[:16],
                                        np.flatnonzero(cohorts['opportunity'] & (split == 0))[:8],
                                        np.flatnonzero(cohorts['sequence'] & (split == 0))[:8]]))
    sub, meta = load_subset(a.data, ids)
    model, st = load_model(a.init_ckpt, a.device)
    if st['card_vocab'] != meta['card_vocab'] or int(st['args'].get('feature_version', 1)) != 4:
        raise ValueError('Requires vocabulary-identical public-v4 checkpoint')
    grid = st['args']['grid']
    if grid != meta['grid']:
        raise ValueError('Checkpoint/dataset grid mismatch')
    probability = sampling_probabilities(pool[ids], cohorts['opportunity'][ids], cohorts['sequence'][ids],
                                         split[ids], uniform=a.arm == 'uniform')
    rows = GenRows(sub, np.arange(len(ids)), a.device)
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=.01)
    a.out.mkdir(parents=True, exist_ok=False)
    config = dict(args={k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()},
                  dataset_sha256=manifest['dataset_sha256'], curriculum_sha256=sha(a.curriculum/'manifest.json'),
                  initial_checkpoint_sha256=sha(a.init_ckpt), trainer_sha256=sha(__file__),
                  runtime_rules_added=False, targets='unchanged expert card/cell/gate/wait/value',
                  model_architecture_unchanged=True, heldout_used_for_sampling=False,
                  selection='fixed final step; no test-set checkpoint selection')
    (a.out/'run.json').write_text(json.dumps(config, indent=2))
    seen = {k: 0 for k in cohorts}
    started = time.time()
    steps = 1 if a.smoke_one_batch else a.steps
    with (a.out/'train.jsonl').open('w') as log:
        for step in range(steps):
            chosen = rng.choice(len(ids), size=a.bs, p=probability)
            batch = rows.batch(chosen)
            loss, parts = train_step(model, batch, opt, bool(rng.random() < .5), grid)
            for name, mask in cohorts.items():
                seen[name] += int(mask[ids[chosen]].sum())
            record = dict(step=step+1, loss=loss, parts=parts, seconds=round(time.time()-started, 1))
            log.write(json.dumps(record)+'\n')
            if (step+1) % 100 == 0 or a.smoke_one_batch:
                log.flush()
                print(json.dumps(record), flush=True)
    if a.smoke_one_batch:
        (a.out/'smoke.json').write_text(json.dumps(dict(status='ROCKET_TRAIN_SMOKE_PASS', loss=loss,
                                                     sampled_cohorts=seen, deployment_evidence=False), indent=2))
        print('ROCKET_TRAIN_SMOKE_PASS')
        return 0
    checkpoint = dict(st, model=model.state_dict(), rocket_curriculum=config)
    checkpoint['val'] = evaluate(model, rows.view(np.flatnonzero(split[ids] != 0)), grid=grid)
    torch.save(checkpoint, a.out/'candidate.pt')
    result = dict(val=checkpoint['val'], sampled_cohorts=seen,
                  checkpoint_sha256=sha(a.out/'candidate.pt'), deployment_accepted=False)
    (a.out/'result.json').write_text(json.dumps(result, indent=2))
    print('ROCKET_TRAINING_FINISHED_REQUIRES_ACCEPTANCE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
