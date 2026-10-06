"""New capture mechanism versus the already saved OFF controls; no OFF inference."""
import json
import time

import numpy as np
import torch

from common import HERE, OLD, original, sha, save_json, source_bindings, manifest, load_old
from async_capture import AsyncCaptureStore
from capture import load_record

old_qualification = load_old('qualify')


def main():
    assert not (HERE / 'started.json').exists()
    torch.set_num_threads(4)
    registration = json.loads((HERE / 'registration.json').read_text())
    assert registration['sources'] == source_bindings()
    old = json.loads((OLD / 'qualified.json').read_text())
    assert sha(OLD / 'qualified.json') == registration['original_qualified_sha256']
    assert not old['latency_pass'] and old['sources'] == original.sources()
    assert sha(OLD / 'reference_heads.npz') == old['reference_sha256']
    save_json(HERE / 'started.json', dict(time=time.time(), sources=source_bindings(),
                                        environment=original.execution_environment()))
    pilot = original.make_pilot()
    assert original.manifest(pilot) == old['manifest']
    initial = original.weight_hash(pilot.model)
    assert initial == old['initial_final_weight_sha256']
    frames = original.fixed_frames()
    assert old_qualification.digest(frames) == old['fixture_sha256']
    for f in frames[:4]:
        original.prepare_case(pilot, f)
        pilot.decide(f)
    m = manifest(pilot)
    store = AsyncCaptureStore(HERE / 'records', m)
    reference = np.load(OLD / 'reference_heads.npz', allow_pickle=False)
    cases, flush_ms, flush_results = [], [], []
    try:
        for i, f in enumerate(frames):
            original.prepare_case(pilot, f)
            before_rng = old_qualification.rng()
            before_frame = old_qualification.digest(f)
            start = time.perf_counter()
            d = store.decide(pilot, f)
            decision_ms = (time.perf_counter() - start) * 1000
            assert old_qualification.digest(d) == old['cases'][i]['decision_digest'], ('decision', i)
            assert old_qualification.observer(pilot) == old['cases'][i]['observer_digest'], ('observer', i)
            assert old_qualification.rng() == before_rng and old_qualification.digest(f) == before_frame
            start = time.perf_counter()
            flushed = store.flush(timeout=10)
            assert flushed['ok'] and not flushed['timed_out'], ('bounded flush failed', flushed)
            flush_results.append(dict(flushed))
            flush_ms.append((time.perf_counter() - start) * 1000)
            assert not store.disabled_reason, store.disabled_reason
            paths = sorted((HERE / 'records').glob('*.npz'))
            assert len(paths) == i + 1
            meta, arrays = load_record(paths[-1], m)
            assert len(meta['forwards']) == old['cases'][i]['forward_count']
            for j, forward in enumerate(meta['forwards']):
                for group, names in (('input', forward['inputs']), ('kwarg', forward['kwargs']), ('output', forward['outputs'])):
                    for name in names:
                        expected_key = f'r{i}__f{j}__{name}' if group == 'output' else f'r{i}__f{j}__{group}__{name}'
                        expected, actual = reference[expected_key], arrays[f'f{j}__{group}__{name}']
                        assert expected.dtype == actual.dtype and expected.shape == actual.shape and expected.tobytes() == actual.tobytes(), (i, j, group, name)
            cases.append(dict(case=i, record=paths[-1].name, forward_count=len(meta['forwards']),
                              play=d['play'], no_affordable=d['no_affordable'], decision_ms=decision_ms,
                              decision_digest=old_qualification.digest(d), observer_digest=old_qualification.observer(pilot)))
            time.sleep(.15)
    finally:
        reference.close()
        closed = store.close(timeout=10)
    assert closed['ok'] and not closed['timed_out'] and not closed['writer_alive'] and not store.disabled_reason
    assert original.weight_hash(pilot.model) == initial
    assert all(p.grad is None for p in pilot.model.parameters())
    assert 'row' not in pilot.__dict__ and not pilot.model._forward_hooks and not pilot.model._forward_pre_hooks
    values = np.array([t['total_ms'] for t in store.timings])
    perf = dict(median=float(np.median(values)), p95=float(np.quantile(values, .95)), maximum=float(values.max()))
    qualified = perf['median'] <= 2 and perf['p95'] <= 5 and perf['maximum'] <= 20
    result = dict(schema=1, cases=cases, manifest=m, timings=store.timings,
        flush_ms=flush_ms, flush_results=flush_results, close_result=dict(closed),
        writer_timings=store.writer_timings, overhead_ms=perf, latency_pass=qualified,
        initial_final_weight_sha256=initial, original_qualified_sha256=sha(OLD / 'qualified.json'),
        reference_sha256=old['reference_sha256'], fixture_sha256=old['fixture_sha256'], sources=source_bindings())
    save_json(HERE / 'qualified.json', result)
    assert qualified, ('unchanged overhead budget failed', perf)
    print('ASYNC_CAPTURE_QUALIFIED', len(cases), json.dumps(perf))


if __name__ == '__main__':
    main()
