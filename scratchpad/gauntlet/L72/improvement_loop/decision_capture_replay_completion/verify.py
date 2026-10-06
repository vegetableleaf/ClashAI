"""One fresh replay of two frozen capture sets; both latency failures persist."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OLD = HERE.parent / 'decision_capture'
ASYNC = HERE.parent / 'decision_capture_async'
CHECKS = ROOT / 'scratchpad/gauntlet/L71/integration/checks'
PY = ROOT / 'research/ext/Royale/.venv/Scripts/python.exe'
CKPT = ROOT / 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt'
CHECKPOINT_SHA = '76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd'
NAMES = ('l72-decision-capture-unit', 'l72-decision-capture-qualify',
         'l72-decision-capture-async-unit', 'l72-decision-capture-async-qualify')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def registration_bindings():
    """Read/hash only: the parent freezes this map before any execution."""
    paths = {HERE / n for n in ('PLAN.md', 'METRICS.md', 'verify.py')}
    paths.update({CKPT, OLD / 'reference_heads.npz'})
    for leaf in (OLD, ASYNC):
        q = read(leaf / 'qualified.json')
        paths.update(ROOT / n for n in q['sources'])
        paths.update(leaf / n for n in ('registration.json', 'started.json',
                                       'qualified.json', 'chain_failed.json'))
        paths.update({leaf / 'records/manifest.json', leaf / 'records/index.json'})
        paths.update(leaf / 'records' / c['record'] for c in q['cases'])
    paths.update(CHECKS / (name + suffix) for name in NAMES for suffix in ('.json', '.out'))
    return {relative(p): sha(p) for p in sorted(paths)}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def replay_helpers(np, torch):
    """Compile only unchanged pure helper definitions, excluding imports/main."""
    source = OLD / 'replay.py'
    tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
             and n.name in ('equal_bytes', 'reconstruct')]
    assert [n.name for n in nodes] == ['equal_bytes', 'reconstruct']
    namespace = {'np': np, 'torch': torch}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['equal_bytes'], namespace['reconstruct']


def receipts():
    commands = (
        [str(PY), '-m', 'pytest', str(OLD / 'test_capture.py'), str(OLD / 'test_entry_capture.py'), '-q'],
        [str(PY), str(OLD / 'qualify.py')],
        [str(PY), '-m', 'pytest', str(ASYNC / 'test_async.py'), '-q'],
        [str(PY), str(ASYNC / 'qualify.py')],
    )
    expected = ('passed', 'DECISION_CAPTURE_QUALIFIED', 'passed', 'ASYNC_CAPTURE_QUALIFIED')
    details = []
    for i, name in enumerate(NAMES):
        p = CHECKS / (name + '.json')
        receipt = read(p)
        output = (CHECKS / (name + '.out')).read_text(encoding='utf-8')
        assert receipt['command'] == commands[i] and receipt['cwd'] == str(ROOT)
        assert receipt['shell'] == 'none; subprocess argument vector'
        assert receipt['expected'] == expected[i]
        assert receipt['exit_code'] == i % 2 and receipt['matched'] is (i % 2 == 0)
        assert hashlib.sha256(output.encode('utf-8')).hexdigest() == receipt['output_sha256']
        if i % 2:
            marker = 'capture overhead budget failed' if i == 1 else 'unchanged overhead budget failed'
            assert output.count('Traceback (most recent call last):') == 1
            assert output.rstrip().splitlines()[-1].startswith("AssertionError: ('" + marker + "',")
        else:
            assert ('42 passed' if i == 0 else '12 passed') in output
        details.append(dict(name=name, receipt_sha256=sha(p), **receipt))
    return details


def run_locked(registration, registration_sha):
    import numpy as np
    import torch

    torch.set_num_threads(4)
    old, new = (read(leaf / 'qualified.json') for leaf in (OLD, ASYNC))
    assert old['latency_pass'] is False and new['latency_pass'] is False
    assert new['original_qualified_sha256'] == sha(OLD / 'qualified.json')
    assert old['fixture_sha256'] == new['fixture_sha256']
    assert sha(OLD / 'reference_heads.npz') == old['reference_sha256'] == new['reference_sha256']
    assert sha(CKPT) == CHECKPOINT_SHA
    for leaf, q in ((OLD, old), (ASYNC, new)):
        assert q['sources'] == read(leaf / 'started.json')['sources'] == read(leaf / 'registration.json')['sources']
        assert q['manifest']['sources'] == q['sources']
        assert all(sha(ROOT / name) == value for name, value in q['sources'].items())
        assert [c['case'] for c in q['cases']] == list(range(24))
        expected_records = [f'record_{i:06d}.npz' for i in range(24)]
        assert [c['record'] for c in q['cases']] == expected_records
        assert sorted(p.name for p in (leaf / 'records').glob('*.npz')) == expected_records
        assert read(leaf / 'records/manifest.json') == q['manifest']
        assert len(read(leaf / 'records/index.json')['records']) == 24
    assert all(r['complete'] is True and r['ok'] is True and r['pending'] == 0
               for r in new['flush_results']) and len(new['flush_results']) == 24
    close = new['close_result']
    assert close['complete'] is True and close['ok'] is True and close['closed'] is True
    assert close['submitted'] == close['committed'] == 24 and close['pending'] == 0
    assert close['disabled_reason'] is None and close['excluded_ids'] == []
    assert close['writer_failed'] is False and close['writer_alive'] is False
    prior_receipts = receipts()
    original = load_module('capture_replay_completion_support', OLD / 'support.py')
    decoder = load_module('capture_replay_completion_decoder', OLD / 'capture.py')
    equal_bytes, reconstruct = replay_helpers(np, torch)
    environment = original.execution_environment()
    assert environment == read(OLD / 'started.json')['environment'] == read(ASYNC / 'started.json')['environment']
    save(HERE / 'started.json', dict(schema=1, time=time.time(), pid=os.getpid(),
        registration_sha256=registration_sha, bindings=registration['bindings'], environment=environment,
        original_latency_pass=False, async_latency_pass=False, live_eligible=False))
    pilot = original.make_pilot()
    model = pilot.model
    manifest = original.manifest(pilot)
    assert manifest == old['manifest']
    async_manifest = copy.deepcopy(manifest)
    async_manifest.update(sources=new['sources'], capture_id='public-decision-capture-async-20261006')
    assert async_manifest == new['manifest']
    assert torch.get_num_threads() == 4 and str(pilot.dev) == 'cpu'
    assert all(not m.training for m in model.modules())
    initial = original.weight_hash(model)
    assert initial == old['initial_final_weight_sha256'] == new['initial_final_weight_sha256']
    assert all(p.grad is None for p in model.parameters())
    rng = (random.getstate(), np.random.get_state(), torch.get_rng_state().clone())
    details, calls, heads, input_arrays = [], 0, 0, 0
    positive = set()
    reference_keys = set()
    with np.load(OLD / 'reference_heads.npz', allow_pickle=False) as reference:
        for i, (a, b) in enumerate(zip(old['cases'], new['cases'])):
            meta, arrays = decoder.load_record(OLD / 'records' / a['record'], manifest)
            newmeta, newarrays = decoder.load_record(ASYNC / 'records' / b['record'], async_manifest)
            assert set(meta) == set(newmeta) and set(arrays) == set(newarrays)
            assert all(meta[k] == newmeta[k] for k in meta if k != 'manifest_sha256')
            assert all(equal_bytes(arrays[k], newarrays[k]) for k in arrays)
            assert meta['record_id'] == i
            for key in ('case', 'record', 'forward_count', 'play', 'no_affordable', 'decision_digest', 'observer_digest'):
                assert a[key] == b[key], (i, key)
            assert len(meta['forwards']) == a['forward_count']
            for j, forward in enumerate(meta['forwards']):
                batch = {k: torch.from_numpy(arrays[f'f{j}__input__{k}'].copy()) for k in forward['inputs']}
                kwargs = {k: torch.from_numpy(arrays[f'f{j}__kwarg__{k}'].copy()) for k in forward['kwargs']}
                for group, tensors in (('input', batch), ('kwarg', kwargs)):
                    for k, tensor in tensors.items():
                        refkey = f'r{i}__f{j}__{group}__{k}'
                        assert equal_bytes(tensor.numpy(), reference[refkey]), refkey
                        reference_keys.add(refkey)
                        input_arrays += 1
                kwargs.update({k: None for k in forward['null_kwargs']})
                assert calls < 42
                with torch.no_grad():
                    output = model(batch, **kwargs)
                calls += 1
                assert set(output) == set(forward['outputs'])
                for name, tensor in output.items():
                    saved = arrays[f'f{j}__output__{name}']
                    assert equal_bytes(tensor.detach().cpu().numpy(), saved), ('fresh', i, j, name)
                    assert equal_bytes(saved, newarrays[f'f{j}__output__{name}'])
                    refkey = f'r{i}__f{j}__{name}'
                    assert equal_bytes(saved, reference[refkey]), ('reference', i, j, name)
                    reference_keys.add(refkey)
                    heads += 1
                for group, tensors in (('input', batch), ('kwarg', kwargs)):
                    for k, tensor in tensors.items():
                        if tensor is not None:
                            assert equal_bytes(tensor.numpy(), arrays[f'f{j}__{group}__{k}'])
            decision = reconstruct(meta, arrays, manifest['settings'])
            assert decision == meta['decision'] == newmeta['decision']
            assert reconstruct(newmeta, newarrays, async_manifest['settings']) == decision
            assert decision['play'] == a['play'] and decision['no_affordable'] == a['no_affordable']
            positive.add('no_affordable_WAIT' if decision['no_affordable'] else
                         ('PLAY' if decision['play'] else 'affordable_WAIT'))
            details.append(dict(case=i, records=[a['record'], b['record']], forwards=len(meta['forwards']), decision=decision))
            save(HERE / 'progress.json', dict(cases=i + 1, fresh_forwards=calls, heads=heads))
            time.sleep(.15)
        assert reference_keys == set(reference.files)
    assert calls == 42 and len(details) == 24
    assert positive == {'no_affordable_WAIT', 'affordable_WAIT', 'PLAY'}
    assert sum(d['decision']['no_affordable'] for d in details) == 6
    assert sum(d['decision']['play'] for d in details) == 6
    rejected = []
    path = ASYNC / 'records' / new['cases'][0]['record']
    for field in ('schema', 'checkpoint_sha256', 'sources'):
        bad = copy.deepcopy(async_manifest)
        bad[field] = 999 if field == 'schema' else ('0' * 64 if field == 'checkpoint_sha256' else {'wrong.py': '0' * 64})
        try:
            decoder.load_record(path, bad)
        except decoder.CaptureError:
            rejected.append(field)
        else:
            raise AssertionError(('unrejected manifest corruption', field))
    assert not equal_bytes(np.array([0.], np.float32), np.array([-0.], np.float32))
    assert equal_bytes(np.array([0.], np.float32), np.array([0.], np.float32))
    assert random.getstate() == rng[0] and torch.equal(torch.get_rng_state(), rng[2])
    now = np.random.get_state()
    assert now[0] == rng[1][0] and equal_bytes(now[1], rng[1][1]) and now[2:] == rng[1][2:]
    assert all(p.grad is None for p in model.parameters()) and all(not m.training for m in model.modules())
    assert original.weight_hash(model) == initial and sha(CKPT) == CHECKPOINT_SHA
    assert registration_bindings() == registration['bindings'] and sha(HERE / 'registration.json') == registration_sha
    save(HERE / 'verified.json', dict(schema=1, time=time.time(), registration_sha256=registration_sha,
        bindings=registration['bindings'], prior_receipts=prior_receipts, cases=24, saved_records=48,
        fresh_forwards=calls, heads_exact=heads, saved_head_comparisons=2 * heads,
        input_conditioning_arrays_exact=input_arrays, reference_arrays_exact=len(reference_keys), details=details,
        positive_controls=sorted(positive), positive_control_count=3,
        manifest_corruptions_rejected=rejected, manifest_negative_count=3, signed_zero_negative_count=1,
        initial_final_weight_sha256=initial, checkpoint_sha256=CHECKPOINT_SHA,
        rng_unchanged=True, gradients_empty=True, zero_optimizer=True, new_model=False,
        environment=environment, original_latency_pass=False, async_latency_pass=False, live_eligible=False,
        original_overhead_ms=old['overhead_ms'], async_overhead_ms=new['overhead_ms'],
        fixture_limitations='Training Camp deck; no Rocket/Log/Tornado/Tesla/X-Bow; 16 Hero, 8 no-Hero, '
                            '6 incoming Barrel; friendly Knight in all cases; no enemy troop push. '
                            'No Icebow spending, defense value, ladder or model-strength conclusion.'))
    print('DECISION_CAPTURE_REPLAY_COMPLETED', 24, 48, calls, heads, 3, 3, 1)


def main():
    import msvcrt

    assert not (HERE / 'started.json').exists() and not (HERE / 'verified.json').exists(), 'fresh completion required'
    registration = read(HERE / 'registration.json')
    assert registration['status'] == 'REGISTERED_UNEXECUTED'
    assert registration['bindings'] == registration_bindings()
    registration_sha = sha(HERE / 'registration.json')
    with (ROOT / 'icebow/data/bench/development_iteration_1_20261005/chain.lock').open('r+b') as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            run_locked(registration, registration_sha)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()
