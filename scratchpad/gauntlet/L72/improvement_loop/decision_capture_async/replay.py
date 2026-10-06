"""One fresh replay verifies each new record and its identical frozen old record."""
import copy
import json
import time

import numpy as np
import torch

from common import HERE, OLD, original, sha, save_json, source_bindings, manifest, load_old
from capture import load_record, CaptureError

r = load_old('replay')


def main():
    assert not (HERE / 'replay_started.json').exists()
    torch.set_num_threads(4)
    q = json.loads((HERE / 'qualified.json').read_text())
    old = json.loads((OLD / 'qualified.json').read_text())
    assert q['latency_pass'] and q['sources'] == source_bindings()
    assert q['original_qualified_sha256'] == sha(OLD / 'qualified.json')
    assert original.execution_environment() == json.loads((HERE / 'started.json').read_text())['environment']
    assert sha(OLD / 'reference_heads.npz') == q['reference_sha256'] == old['reference_sha256']
    save_json(HERE / 'replay_started.json', dict(time=time.time(), sources=source_bindings()))
    pilot = original.make_pilot()
    assert original.manifest(pilot) == old['manifest']
    m = manifest(pilot)
    assert m == q['manifest']
    controls, heads, details = 0, 0, []
    reference = np.load(OLD / 'reference_heads.npz', allow_pickle=False)
    for case in q['cases']:
        i = case['case']
        meta, arrays = load_record(HERE / 'records' / case['record'], m)
        oldmeta, oldarrays = load_record(OLD / 'records' / old['cases'][i]['record'], old['manifest'])
        assert set(arrays) == set(oldarrays)
        assert all(r.equal_bytes(arrays[k], oldarrays[k]) for k in arrays)
        assert all(meta[k] == oldmeta[k] for k in ('row', 'frame', 'decision', 'forwards', 'model_eval'))
        for j, forward in enumerate(meta['forwards']):
            batch = {k: torch.from_numpy(arrays[f'f{j}__input__{k}'].copy()) for k in forward['inputs']}
            kwargs = {k: torch.from_numpy(arrays[f'f{j}__kwarg__{k}'].copy()) for k in forward['kwargs']}
            with torch.no_grad():
                out = pilot.model(batch, **kwargs)
            assert set(out) == set(forward['outputs'])
            for name, tensor in out.items():
                saved = arrays[f'f{j}__output__{name}']
                assert r.equal_bytes(tensor.numpy(), saved), ('fresh', i, j, name)
                assert r.equal_bytes(saved, reference[f'r{i}__f{j}__{name}'])
                heads += 1
        decision = r.reconstruct(meta, arrays, m['settings'])
        assert decision == meta['decision']
        details.append(dict(case=i, forwards=len(meta['forwards']), play=decision['play'], no_affordable=decision['no_affordable']))
        time.sleep(.15)
    reference.close()
    path = HERE / 'records' / q['cases'][0]['record']
    for field in ('schema', 'checkpoint_sha256', 'sources'):
        bad = copy.deepcopy(m)
        bad[field] = 999 if field == 'schema' else ('0' * 64 if field == 'checkpoint_sha256' else {'bad.py': '0' * 64})
        try:
            load_record(path, bad)
        except CaptureError:
            controls += 1
        else:
            raise AssertionError(field)
    save_json(HERE / 'replayed.json', dict(schema=1, cases=len(details), details=details,
        heads_exact=heads, manifest_corruptions_rejected=controls, sources=source_bindings(),
        qualified_sha256=sha(HERE / 'qualified.json'), original_latency_pass=False,
        original_saved_records_exact_replay=True,
        records={c['record']:sha(HERE / 'records' / c['record']) for c in q['cases']}))
    print('ASYNC_CAPTURE_REPLAYED', len(details), heads, controls)


if __name__ == '__main__':
    main()
