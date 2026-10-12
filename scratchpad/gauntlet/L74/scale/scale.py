"""Offline SCALE experiment. All writes stay in --out; no deployment or network code."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import torch
from pipeline.model_gen import GenModel
from pipeline.train_gen import GenRows, losses
from features import add_richer_inputs, public_area_timeline, align_area_age, bridge_events, bridge_mask
from metrics import METRICS, phase, row_metrics, summarize, group_masks, paired_ci, helps

ETA = 'Estimate: 12-24 hours on one L40, including native preparation; unmeasured until first epoch. 20-epoch cap, patience 3.'
ICEBOW = {'ice-wizard', 'knight', 'skeletons', 'tesla', 'the-log', 'tornado', 'rocket', 'x-bow'}


@dataclasses.dataclass(frozen=True)
class Arm:
    name: str
    d: int
    layers: int
    richer_inputs: bool = False


def arm_configs(include_richer=True):
    return [Arm('A', 128, 4), Arm('B', 256, 4), Arm('C', 128, 6)] + ([Arm('D', 128, 4, True)] if include_richer else [])


def construct(arm, n_cards):
    model = GenModel(d=arm.d, layers=arm.layers, n_cards=n_cards, feature_version=5)
    if arm.richer_inputs:
        old = model.effect_in[0]
        extended = torch.nn.Linear(old.in_features+2, old.out_features)
        with torch.no_grad():
            extended.weight[:, :-2].copy_(old.weight)
            extended.weight[:, -2:].zero_()
            extended.bias.copy_(old.bias)
        model.effect_in[0] = extended
    return model


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def mapped_dataset(path, cache, only=None):
    """Fresh private NPZ extraction, CRC-checked by zipfile; never alter source data."""
    cache.mkdir(parents=True, exist_ok=False)
    arrays = {}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names):
            raise ValueError('Duplicate NPZ member')
        for name in names:
            if Path(name).name != name or not name.endswith('.npy'):
                raise ValueError('Unsafe NPZ member')
            key = name[:-4]
            if only is not None and key not in only | {'meta'}:
                continue
            with archive.open(name) as src, (cache/name).open('xb') as dst:
                shutil.copyfileobj(src, dst, 1024*1024)
            arrays[key] = np.load(cache/name, mmap_mode='c', allow_pickle=False)
    meta = json.loads(str(arrays.pop('meta')))
    if meta.get('feature_version') != 5 or meta.get('grid') != 'lattice':
        raise ValueError('SCALE requires the specified fv5 lattice dataset')
    return arrays, meta


def partitions(arrays):
    """Original train remains intact; hash each held-out replay into select/test."""
    tags = arrays['tags']
    holdout_bucket = np.array([hashlib.sha256(str(t).encode()).digest()[0] % 2 for t in tags])
    split, rep = arrays['split'], arrays['rep']
    if not np.isin(split, [0, 1]).all():
        raise ValueError('Unexpected dataset split')
    for r in np.unique(rep):
        # Dataset is replay-contiguous; validate this once in prepare().
        lo, hi = np.searchsorted(rep, [r, r+1])
        if np.unique(split[lo:hi]).size != 1:
            raise ValueError('Replay crosses dataset split')
    tr = np.flatnonzero(split == 0)
    select = np.flatnonzero((split == 1) & (holdout_bucket[rep] == 0))
    test = np.flatnonzero((split == 1) & (holdout_bucket[rep] == 1))
    if not len(tr) or not len(select) or not len(test):
        raise ValueError('Empty train/selection/test partition')
    return tr, select, test


def corpus_files(meta, overrides=None):
    roots = [Path(p) for p in overrides] if overrides else [ROOT / p.replace('\\', '/') for p in meta['corpora']]
    found = {}
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError(f'Required native corpus absent: {root}')
        for p in sorted(list(root.glob('replay_*.json'))+list(root.glob('j*/replay_*.json'))):
            found.setdefault(p.stem.removeprefix('replay_'), p)
    return roots, found


def inspect_schema(rec):
    schema = {}
    for f in rec.get('frames', []) + rec.get('play_frames', []):
        for key, items in [('entities', f.get('entities', [])), ('effects', f.get('effects', [])),
                           ('projectiles', f.get('projectiles', [])),
                           ('public_area_effects', f.get('public_objects', {}).get('area_effects', [])),
                           ('public_projectiles', f.get('public_objects', {}).get('projectiles', []))]:
            for item in items or []:
                shape = ','.join(sorted(item)) if isinstance(item, dict) else 'compact_'+str(len(item))
                schema.setdefault(key, set()).add(shape)
    return {k: sorted(v) for k, v in schema.items()}


def prepare(arrays, meta, out, corpora=None, audit_only=False):
    roots, paths = corpus_files(meta, corpora)
    if (np.diff(arrays['rep']) < 0).any():
        raise ValueError('Expected replay-contiguous dataset')
    tags = [str(t) for t in arrays['tags']]
    missing = sorted(set(tags)-set(paths))
    if missing:
        raise FileNotFoundError(f'{len(missing)} dataset replays absent from native corpus; first={missing[:3]}')
    selected = list(range(len(tags)))
    if audit_only:
        # One real dataset replay from EACH source root; explicit bounded audit.
        selected = []
        for root in roots:
            candidates = [i for i, t in enumerate(tags) if paths[t].is_relative_to(root)]
            if candidates:
                selected.append(candidates[len(candidates)//2])
    n = len(arrays['tick'])
    age = None if audit_only else np.lib.format.open_memmap(out/'area_age.npy', mode='w+', dtype=np.float32, shape=(n, 32, 2))
    bridge = None if audit_only else np.lib.format.open_memmap(out/'bridge.npy', mode='w+', dtype=bool, shape=(n,))
    gid = {k: i for i, k in enumerate(meta['card_vocab'])}
    audit = {'scope': 'six-corpus bounded sample' if audit_only else 'all dataset replays',
             'replays': 0, 'rows': 0, 'area_tokens': 0, 'age_known': 0, 'age_nonzero': 0, 'bridge_rows': 0,
             'sources': [], 'schemas': {}, 'feature': 'continuous visible area age / 30 seconds, clipped at 1; known mask',
             'source_timers_used': False, 'opponent_private_fields_used': False}
    manifest = out/'native_manifest.jsonl'
    with manifest.open('w', encoding='utf-8') as mf:
        for number, rep in enumerate(selected):
            p = paths[tags[rep]]
            raw = p.read_bytes()
            rec = json.loads(raw)
            if rec.get('record_native') is not True or str(rec['tag']) != tags[rep]:
                raise ValueError('Native identity/schema mismatch')
            lo, hi = np.searchsorted(arrays['rep'], [rep, rep+1])
            ticks, sides, effects = arrays['tick'][lo:hi], arrays['side'][lo:hi], arrays['effects'][lo:hi]
            timeline = public_area_timeline(rec['frames'], gid)
            extra = align_area_age(timeline, ticks, sides, effects)
            crossing = bridge_mask(bridge_events(rec['frames']), ticks, sides)
            if age is not None:
                age[lo:hi], bridge[lo:hi] = extra, crossing
            for k, v in inspect_schema(rec).items():
                audit['schemas'][k] = sorted(set(audit['schemas'].get(k, [])) | set(v))
            audit['replays'] += 1
            audit['rows'] += int(hi-lo)
            audit['area_tokens'] += int((effects[..., 0] > 0).sum())
            audit['age_known'] += int(extra[..., 1].sum())
            audit['age_nonzero'] += int((extra[..., 0] > 0).sum())
            audit['bridge_rows'] += int(crossing.sum())
            entry = {'rep': rep, 'tag': tags[rep], 'path': str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                     'sha256': hashlib.sha256(raw).hexdigest(), 'rows': int(hi-lo)}
            mf.write(json.dumps(entry)+'\n')
            if audit_only:
                audit['sources'].append(entry)
            if number % 100 == 0:
                print(json.dumps({'prepare_replays': number+1, 'of': len(selected)}), flush=True)
    if age is not None:
        age.flush(); bridge.flush()
    dump(out/'field_audit.json', audit)
    if not audit['age_nonzero']:
        raise ValueError('No nonzero observable area ages: D cannot be evaluated')
    return age, bridge, audit


def batch(rows, ids, device, age=None, richer_inputs=False):
    b = {k: v.to(device) for k, v in rows.batch(ids).items()}
    extra = torch.from_numpy(np.asarray(age[ids])) if richer_inputs else None
    return add_richer_inputs(b, extra, richer_inputs=richer_inputs)


@torch.inference_mode()
def evaluate(model, rows, ids, device, age, rich, bs):
    model.eval()
    parts = {}
    for start in range(0, len(ids), bs):
        b = batch(rows, ids[start:start+bs], device, age, rich)
        out = model(b, card=b['card'], form=b['form'])
        for k, v in row_metrics(out, b).items():
            parts.setdefault(k, []).append(v)
    return {k: np.concatenate(v) for k, v in parts.items()}


def train_arm(arm, rows, meta, age, tr, select, a, out):
    torch.manual_seed(a.seed)
    np.random.seed(a.seed)
    rng = np.random.default_rng(a.seed)
    model = construct(arm, len(meta['card_vocab'])).to(a.device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=.01)
    steps = len(tr)//a.bs
    if steps < 1:
        raise ValueError('Insufficient training rows for a batch')
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-4, total_steps=a.epochs*steps, pct_start=.05)
    best, stale, history = math.inf, 0, []
    path = out/f'{arm.name}.pt'
    started = time.monotonic()
    with (out/f'{arm.name}.jsonl').open('w', encoding='utf-8') as log:
        for epoch in range(a.epochs):
            model.train()
            perm, total = rng.permutation(tr), 0.
            t0 = time.monotonic()
            for step in range(steps):
                ids = perm[step*a.bs:(step+1)*a.bs]
                b = batch(rows, ids, a.device, age, arm.richer_inputs)
                with torch.autocast('cuda', dtype=torch.bfloat16, enabled=a.amp == 'bf16'):
                    loss, _ = losses(model, b, mirror=rng.random() < .5, grid='lattice')
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite training loss')
                opt.zero_grad(set_to_none=True)
                loss.backward()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
                opt.step(); sched.step()
                total += float(loss.detach())
                if (step+1) % 200 == 0:
                    record = {'arm': arm.name, 'epoch': epoch+1, 'step': step+1, 'steps': steps,
                              'rows_per_s': (step+1)*a.bs/(time.monotonic()-t0)}
                    print(json.dumps(record), flush=True); log.write(json.dumps(record)+'\n'); log.flush()
            stats = evaluate(model, rows, select, a.device, age, arm.richer_inputs, a.eval_bs)
            ev = summarize(stats, np.ones(len(select), bool))
            record = {'arm': arm.name, 'epoch': epoch+1, 'optimization_loss': total/steps, 'selection': ev,
                      'epoch_seconds': time.monotonic()-t0, 'elapsed_seconds': time.monotonic()-started,
                      'remaining_cap_hours': (a.epochs-epoch-1)*(time.monotonic()-t0)/3600}
            history.append(record)
            print(json.dumps(record), flush=True); log.write(json.dumps(record)+'\n'); log.flush()
            if ev['loss'] < best-a.min_delta:
                best, stale = ev['loss'], 0
                torch.save({'model': model.state_dict(), 'args': dict(d=arm.d, layers=arm.layers, d_c=64,
                            feature_version=5, richer_inputs=arm.richer_inputs, seed=a.seed, grid='lattice'),
                            'architecture': 'scale_area_observed_age_v1' if arm.richer_inputs else None,
                            'gen': True, 'deck': 'generalist', 'd_c': 64, 'card_vocab': meta['card_vocab'],
                            'epoch': epoch+1, 'selection': ev, 'deployment_authorized': False,
                            'n_params': sum(p.numel() for p in model.parameters())}, path)
            else:
                stale += 1
            if epoch+1 >= a.min_epochs and stale >= a.patience:
                break
    state = torch.load(path, map_location=a.device, weights_only=False)
    model.load_state_dict(state['model'])
    dump(out/f'{arm.name}_history.json', history)
    return model, {'epochs_run': len(history), 'best_epoch': state['epoch'], 'parameter_count': state['n_params'],
                   'training_seconds': time.monotonic()-started, 'checkpoint_sha256': digest(path)}


@torch.inference_mode()
def latency(model, b, device, iterations=200):
    """Full deterministic decision: encoder, gate/card heads, chosen-card cell head."""
    model = model.to(device).eval()
    b = {k: v.to(device) for k, v in b.items()}
    def decision():
        enc = model.encode_gen(b)
        heads = model.heads_gen(enc, b)
        slot = heads['card'].argmax(-1, keepdim=True)
        card = b['hand_card'].gather(1, slot).squeeze(1)
        form = b['hand_form'].gather(1, slot).squeeze(1)
        cell = model.cell_logits_gen(enc, card, form).argmax(-1)
        return heads['gate'] > 0, slot, cell
    for _ in range(20):
        decision()
    if device.startswith('cuda'):
        torch.cuda.synchronize()
    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        decision()
        if device.startswith('cuda'):
            torch.cuda.synchronize()
        times.append((time.perf_counter()-t0)*1000)
    return {'mean_ms': float(np.mean(times)), 'p50_ms': float(np.median(times)), 'p95_ms': float(np.quantile(times, .95)),
            'batch': 1, 'warmup': 20, 'iterations': iterations, 'cpu_threads': torch.get_num_threads(),
            'precision': 'fp32', 'includes': 'encode, gate/card/wait/value heads and chosen-card cell argmax; no I/O or feature build'}


def reports(stats, arrays, ids, bridge, icebow):
    masks = group_masks(phase(arrays['tick'][ids]), bridge[ids], icebow[ids])
    return {key: summarize(stats, mask) for key, mask in masks.items()}


def compare(predictions, arrays, test, bridge, icebow, draws):
    result = {}
    if 'A' not in predictions:
        return result
    masks = group_masks(phase(arrays['tick'][test]), bridge[test], icebow[test])
    for arm in ('B', 'C', 'D'):
        if arm not in predictions:
            continue
        result[arm] = {}
        for group, mask in masks.items():
            result[arm][group] = {k: paired_ci(predictions['A'][k][mask], predictions[arm][k][mask],
                arrays['rep'][test][mask], draws=draws, confidence=.975 if arm in ('B', 'C') else .95) for k in METRICS}
    return result


def render_summary(out, results, comparisons, status, error=None):
    capacity = status == 'SUCCESS' and any(helps(comparisons[k]['icebow/overall']) for k in ('B', 'C') if k in comparisons)
    richer = status == 'SUCCESS' and 'D' in comparisons and helps(comparisons['D']['icebow/overall'])
    lines = [f"Verdict: capacity {'helps' if capacity else 'no evidence'}; richer inputs {'help' if richer else 'no evidence'}.",
             'ETA: '+ETA, 'Status: '+status, 'Measurement only. No deployment.',
             'Primary verdict: untouched icebow test replays, card AND half-tile cell top-1 lower paired CI > 0.',
             'Capacity CIs are 97.5% (two-arm Bonferroni); D CIs are 95%. Replay-cluster bootstrap, paired rows.',
             'Cells are teacher-forced on the pro card; card metrics use PLAY rows, gate uses all rows.',
             'Train gaps use a fixed unaugmented train sample at the selected checkpoint; selection is separate.',
             'Single training seed: CIs measure replay sampling uncertainty, not training-seed uncertainty.']
    if error:
        lines += ['Failure: '+error]
    def number(value, percent=False):
        return 'unavailable' if value is None else f'{value * (100 if percent else 1):.4f}' + ('%' if percent else '')
    for arm, result in results.items():
        lines += ['', f"Arm {arm}: {result['parameter_count']} parameters; best epoch {result['best_epoch']}; epochs run {result['epochs_run']}."]
        for device in ('cpu', 'gpu'):
            lat = result['latency'].get(device)
            lines.append(device.upper()+' latency: '+(f"mean {lat['mean_ms']:.3f}, median {lat['p50_ms']:.3f}, p95 {lat['p95_ms']:.3f} ms/decision, batch 1, FP32." if lat else 'unavailable'))
        for group, held in result['held_out'].items():
            train = result['train'][group]
            lines.append(f"{group}: rows={held['rows']}, card rows={held['card_top1_n']}, cell rows={held['cell_top1_n']}; held-out loss={number(held['loss'])}; " +
                         ', '.join(f'{k}={number(held[k], True)}' for k in METRICS))
            lines.append('  train: loss='+number(train['loss'])+'; '+', '.join(f'{k}={number(train[k], True)}' for k in METRICS))
            lines.append('  gap (train minus held-out agreement; held-out minus train loss): '+
                         ', '.join(k+'='+number(v, k != 'loss_held_minus_train') for k,v in result['gap'][group].items()))
    lines += ['', 'Paired changes in percentage points (B/C/D minus A):']
    for arm, groups in comparisons.items():
        for group, values in groups.items():
            text = []
            for metric, ci in values.items():
                fmt = lambda x: 'unavailable' if x is None else f'{100*x:+.3f}'
                text.append(f"{metric} {fmt(ci['delta'])} [{fmt(ci['lo'])}, {fmt(ci['hi'])}], {ci['replays']} replays")
            lines.append(arm+' versus A, '+group+': '+'; '.join(text))
    lines += [
              '', 'Raw results: report.json; per-arm predictions NPZ, checkpoints PT, and training JSONL.',
              'DONE marks termination; check Status above. No IL result establishes live performance.']
    (out/'SUMMARY.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def parser():
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, default=ROOT/'icebow/data/pipeline/gen_dataset_v32_fv5.npz')
    p.add_argument('--out', type=Path, default=Path('/workspace/results/SCALE'))
    p.add_argument('--corpus', action='append', help='All six roots, in original order; repeat for relocated data')
    p.add_argument('--audit-only', action='store_true')
    p.add_argument('--epochs', type=int, default=20)
    p.add_argument('--min-epochs', type=int, default=5)
    p.add_argument('--patience', type=int, default=3)
    p.add_argument('--min-delta', type=float, default=1e-4)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--bs', type=int, default=256)
    p.add_argument('--eval-bs', type=int, default=256)
    p.add_argument('--selection-sample', type=int, default=30000)
    p.add_argument('--train-sample', type=int, default=30000)
    p.add_argument('--bootstrap-draws', type=int, default=4000)
    p.add_argument('--amp', choices=['bf16', 'none'], default='bf16')
    p.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    p.add_argument('--allow-cpu-smoke', action='store_true', help='Synthetic tests only; report is explicitly SMOKE')
    return p


def execute(a):
    out = a.out
    out.mkdir(parents=True, exist_ok=True)
    if (out/'DONE').exists() or (out/'report.json').exists():
        raise FileExistsError('Refusing to overwrite previous results; use a fresh --out')
    if a.audit_only:
        arrays, meta = mapped_dataset(a.data, out/'audit_cache', {'tags', 'rep', 'tick', 'side', 'effects'})
        _, _, audit = prepare(arrays, meta, out, a.corpus, audit_only=True)
        print('SCALE_AUDIT_PASS '+json.dumps(audit), flush=True)
        return 0
    results, comparisons, status, error = {}, {}, 'FAILED', None
    try:
        render_summary(out, results, comparisons, 'RUNNING')
        if a.epochs < 1 or a.bs < 1 or a.patience < 1 or a.min_epochs < 1 or a.bootstrap_draws < 100:
            raise ValueError('Invalid common training/CI configuration')
        if a.device == 'cpu' and not a.allow_cpu_smoke:
            raise ValueError('CPU training is restricted to explicit synthetic smoke')
        if a.device == 'cuda' and (not torch.cuda.is_available() or torch.cuda.device_count() != 1 or 'L40' not in torch.cuda.get_device_name(0)):
            raise RuntimeError('Exactly one visible L40 is required; no silent GPU/CPU fallback')
        if a.device == 'cpu' and a.amp != 'none':
            raise ValueError('CPU smoke requires --amp none')
        torch.set_num_threads(1)
        torch.backends.cuda.matmul.allow_tf32 = a.amp == 'bf16'
        torch.backends.cudnn.allow_tf32 = a.amp == 'bf16'
        arrays, meta = mapped_dataset(a.data, out/'dataset_cache')
        if a.allow_cpu_smoke:
            if a.device != 'cpu' or len(arrays['tick']) > 4096:
                raise ValueError('CPU smoke is limited to <=4096 synthetic rows')
        else:
            from pipeline.projectile_observation import require_complete_training
            require_complete_training(meta, allow_causal_tti_unknowns=True)
        age, bridge, audit = prepare(arrays, meta, out, a.corpus)
        tr, select, test = partitions(arrays)
        rng = np.random.default_rng(0)
        if a.selection_sample and len(select) > a.selection_sample:
            select = np.sort(rng.choice(select, a.selection_sample, replace=False))
        train_eval = np.sort(np.random.default_rng(1).choice(tr, min(a.train_sample, len(tr)), replace=False))
        np.savez(out/'split_rows.npz', train=tr, selection=select, test=test, train_evaluation=train_eval)
        vocab = meta['card_vocab']
        # Accept the repository's canonical underscored or hyphenated spellings.
        canonical = lambda k: str(k).replace('_', '-').replace('the-log', 'log').replace('x-bow', 'xbow')
        ids = {i for i, k in enumerate(vocab) if canonical(k) in {canonical(x) for x in ICEBOW}}
        if len(ids) != 8:
            raise ValueError(f'Icebow vocabulary mismatch: {ids}')
        icebow = np.isin(arrays['deck_card'], list(ids)).all(1)
        if not (icebow[test] & (arrays['y_gate'][test] == 1)).any():
            raise ValueError('No held-out icebow plays')
        sources = list(Path(__file__).parent.glob('*.py')) + [ROOT/'pipeline'/n for n in
            ('train_gen.py', 'eval_gen.py', 'model_gen.py', 'model_v3.py', 'obs_contract.py', 'projectile_observation.py')]
        dump(out/'manifest.json', {'dataset_sha256': digest(a.data), 'configuration': {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()},
             'arms': [dataclasses.asdict(arm) for arm in arm_configs()], 'sources': {str(p.relative_to(ROOT)): digest(p) for p in sources},
             'torch': torch.__version__, 'numpy': np.__version__, 'gpu': torch.cuda.get_device_name(0) if a.device == 'cuda' else None,
             'cpu': __import__('platform').processor(), 'cpu_threads': 1, 'eta': ETA,
             'split_rows_sha256': digest(out/'split_rows.npz'), 'native_manifest_sha256': digest(out/'native_manifest.jsonl')})
        rows = GenRows(arrays, tr, torch.device('cpu'))
        predictions = {}
        for arm in arm_configs():
            model, result = train_arm(arm, rows, meta, age, tr, select, a, out)
            held = evaluate(model, rows, test, a.device, age, arm.richer_inputs, a.eval_bs)
            train = evaluate(model, rows, train_eval, a.device, age, arm.richer_inputs, a.eval_bs)
            np.savez_compressed(out/f'{arm.name}_held_out.npz', row=test, rep=arrays['rep'][test], **held)
            np.savez_compressed(out/f'{arm.name}_train.npz', row=train_eval, **train)
            predictions[arm.name] = {k: held[k] for k in METRICS}
            result['held_out'] = reports(held, arrays, test, bridge, icebow)
            result['train'] = reports(train, arrays, train_eval, bridge, icebow)
            result['gap'] = {}
            for group, ev in result['held_out'].items():
                tv = result['train'][group]
                result['gap'][group] = {k+'_train_minus_held': tv[k]-ev[k] if tv[k] is not None and ev[k] is not None else None for k in METRICS}
                result['gap'][group]['loss_held_minus_train'] = ev['loss']-tv['loss'] if ev['loss'] is not None and tv['loss'] is not None else None
            # Same representative, median-unit-count icebow test row for every arm.
            candidates = test[icebow[test]]
            lengths = arrays['off'][candidates+1]-arrays['off'][candidates]
            chosen = candidates[np.argsort(lengths, kind='stable')[len(candidates)//2]]
            b = batch(rows, np.asarray([chosen]), a.device, age, arm.richer_inputs)
            result['latency'] = {'row': int(chosen), 'units': int(arrays['off'][chosen+1]-arrays['off'][chosen])}
            # Force fp32 for BOTH CPU and GPU latency independently of training AMP.
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            if a.device == 'cuda':
                result['latency']['gpu'] = latency(model, b, 'cuda')
            result['latency']['cpu'] = latency(model, b, 'cpu')
            torch.backends.cuda.matmul.allow_tf32 = a.amp == 'bf16'
            torch.backends.cudnn.allow_tf32 = a.amp == 'bf16'
            results[arm.name] = result
            dump(out/f'{arm.name}_metrics.json', result)
            del model, held, train
            if a.device == 'cuda':
                torch.cuda.empty_cache()
            render_summary(out, results, comparisons, 'RUNNING')
        comparisons = compare(predictions, arrays, test, bridge, icebow, a.bootstrap_draws)
        status = 'SMOKE ONLY' if a.allow_cpu_smoke else 'SUCCESS'
    except BaseException as exc:
        error = f'{type(exc).__name__}: {exc}'
        (out/'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
        print(traceback.format_exc(), flush=True)
    finally:
        dump(out/'report.json', {'status': status, 'error': error, 'arms': results, 'comparisons': comparisons})
        render_summary(out, results, comparisons, status, error)
        (out/'DONE').write_text(status+'\n', encoding='utf-8')
    return 0 if status in ('SUCCESS', 'SMOKE ONLY') else 1


if __name__ == '__main__':
    raise SystemExit(execute(parser().parse_args()))
