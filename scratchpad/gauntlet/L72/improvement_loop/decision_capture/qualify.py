"""Fixed offline engineering comparison. Does not start native/live matches."""
import copy
import dataclasses
import hashlib
import json
import random
import time
from collections import deque
from pathlib import Path

import numpy as np
import torch

from support import HERE, ROOT, CKPT, CHECKPOINT_SHA, sha, sources, manifest, execution_environment
from support import fixed_frames, prepare_case, save_json, weight_hash, make_pilot
from capture import CaptureStore, load_record


def canonical(x):
    if isinstance(x, torch.Tensor):
        x = x.detach().cpu().contiguous().numpy()
    if isinstance(x, np.ndarray):
        return {'dtype': x.dtype.str, 'shape': list(x.shape), 'bytes': x.tobytes().hex()}
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, dict):
        return [[canonical(k), canonical(v)] for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))]
    if isinstance(x, (list, tuple, deque)):
        return [canonical(a) for a in x]
    if isinstance(x, (set, frozenset)):
        return sorted([canonical(a) for a in x], key=str)
    if isinstance(x, Path):
        return str(x)
    if dataclasses.is_dataclass(x):
        return canonical(dataclasses.asdict(x))
    if x is None or isinstance(x, (str, int, float, bool)):
        return x
    if hasattr(x, '__dict__'):
        return {'class': type(x).__module__ + '.' + type(x).__name__, 'data': canonical(vars(x))}
    raise TypeError(type(x))


def digest(x):
    return hashlib.sha256(json.dumps(canonical(x), sort_keys=True).encode()).hexdigest()


def observer(p):
    return digest({k: getattr(p, k) for k in ('past', 'history', 'frames', 'public', 'public_battle',
                   'opp', 'opp_est', 'match_index', 'match_seed')} | {'rng': p.rng_decisions.bit_generator.state})


def rng():
    return digest((random.getstate(), np.random.get_state(), torch.get_rng_state()))


def heads_recorder(target):
    def hook(model, args, kwargs, out):
        target.append({k: v.detach().cpu().contiguous().numpy().copy() for k, v in out.items()})
    return hook


def inputs_recorder(target):
    def hook(model, args, kwargs):
        target.append({'input': {k: v.detach().cpu().contiguous().numpy().copy() for k, v in args[0].items()},
                       'kwarg': {k: v.detach().cpu().contiguous().numpy().copy() for k, v in kwargs.items()}})
    return hook


def main():
    assert not (HERE / 'started.json').exists(), 'fresh qualification required'
    torch.set_num_threads(4)
    registration = json.loads((HERE / 'registration.json').read_text())
    assert registration['sources'] == sources()
    assert sha(CKPT) == CHECKPOINT_SHA
    save_json(HERE / 'started.json', dict(time=time.time(), sources=sources(), checkpoint_sha256=sha(CKPT),
                                         environment=execution_environment()))
    off = make_pilot()
    on = make_pilot()
    assert off.feature_version == on.feature_version == 4
    initial = weight_hash(off.model)
    assert weight_hash(on.model) == initial
    frozen_manifest = manifest(on)
    session = CaptureStore(HERE / 'records', frozen_manifest)
    fixture_frames = fixed_frames()
    # Warm both models on the same first four cases, without capture.
    for f in fixture_frames[:4]:
        for p in (off, on):
            prepare_case(p, f)
            p.decide(f)
    counts = {'off': 0, 'on': 0}
    raw_heads = []
    raw_inputs = []
    off_pre = off.model.register_forward_pre_hook(inputs_recorder(raw_inputs), with_kwargs=True)
    off_hook = off.model.register_forward_hook(heads_recorder(raw_heads), with_kwargs=True)
    on_hook = on.model.register_forward_hook(lambda m, a, k, o: counts.__setitem__('on', counts['on'] + 1), with_kwargs=True)
    results = []
    reference = {}
    try:
        for i, f in enumerate(fixture_frames):
            prepare_case(off, f)
            prepare_case(on, f)
            before_rng = rng()
            before_frame = digest(f)
            raw_heads.clear()
            raw_inputs.clear()
            out = {}
            for mode in (('off', 'on') if i % 2 == 0 else ('on', 'off')):
                start = time.perf_counter()
                out[mode] = off.decide(f) if mode == 'off' else session.decide(on, f)
                out[mode + '_ms'] = (time.perf_counter() - start) * 1000
            assert digest(out['off']) == digest(out['on']), ('decision', i)
            assert observer(off) == observer(on), ('observer', i)
            assert rng() == before_rng and digest(f) == before_frame
            assert not session.disabled_reason, session.disabled_reason
            records = sorted((HERE / 'records').glob('*.npz'))
            assert len(records) == i + 1
            meta, arrays = load_record(records[-1], frozen_manifest)
            assert len(meta['forwards']) == len(raw_heads)
            for j, heads in enumerate(raw_heads):
                for group, values in raw_inputs[j].items():
                    for key, arr in values.items():
                        got = arrays[f'f{j}__{group}__{key}']
                        assert got.dtype == arr.dtype and got.shape == arr.shape and got.tobytes() == arr.tobytes(), (i, j, group, key)
                        reference[f'r{i}__f{j}__{group}__{key}'] = arr
                for key, arr in heads.items():
                    got = arrays[f'f{j}__output__{key}']
                    assert got.dtype == arr.dtype and got.shape == arr.shape and got.tobytes() == arr.tobytes(), (i, j, key)
                    reference[f'r{i}__f{j}__{key}'] = arr
            counts['off'] += len(raw_heads)
            results.append(dict(case=i, record=records[-1].name, forward_count=len(raw_heads),
                play=out['off']['play'], no_affordable=out['off']['no_affordable'],
                raw_hero_objects=sum(e.get('card_id') == 203000023 for e in f['entities']),
                excluded_roles=[x['role'] for x in on._public_audit_snapshot.get('excluded_public_objects', [])],
                decision_digest=digest(out['off']), observer_digest=observer(on),
                off_ms=out['off_ms'], on_ms=out['on_ms'], delta_ms=out['on_ms'] - out['off_ms']))
            time.sleep(.15)
    finally:
        off_pre.remove()
        off_hook.remove()
        on_hook.remove()
    assert counts['off'] == counts['on']
    assert sum(r['raw_hero_objects'] == 3 for r in results) == 16
    assert sum(len(r['excluded_roles']) for r in results) == 32
    assert 'row' not in on.__dict__ and not on.model._forward_hooks and not on.model._forward_pre_hooks
    assert weight_hash(off.model) == weight_hash(on.model) == initial
    assert all(p.grad is None for p in off.model.parameters()) and all(p.grad is None for p in on.model.parameters())
    np.savez(HERE / 'reference_heads.npz', **reference)
    timings = session.timings
    added = np.array([t['total_ms'] for t in timings], dtype=np.float64)
    perf = dict(median=float(np.median(added)), p95=float(np.quantile(added, .95)), maximum=float(added.max()))
    qualified = perf['median'] <= 2 and perf['p95'] <= 5 and perf['maximum'] <= 20
    report = dict(schema=1, cases=results, counts=counts, timings=timings, overhead_ms=perf,
                  latency_pass=qualified, manifest=frozen_manifest, fixture_sha256=digest(fixture_frames),
                  reference_sha256=sha(HERE / 'reference_heads.npz'),
                  initial_final_weight_sha256=initial, sources=sources(), zero_optimizer=True,
                  actual_play_cases=sum(r['play'] for r in results),
                  timing_note='OFF paired timing includes reference input/output copy hooks; budget uses separately measured capture overhead.',
                  no_affordable_cases=sum(r['no_affordable'] for r in results))
    save_json(HERE / 'qualified.json', report)
    assert qualified, ('capture overhead budget failed', perf)
    print('DECISION_CAPTURE_QUALIFIED', json.dumps(dict(cases=len(results), **perf)))


if __name__ == '__main__':
    main()
