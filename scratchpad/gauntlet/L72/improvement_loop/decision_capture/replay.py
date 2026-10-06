"""Fresh CPU4 exact forward and independent scalar decision reconstruction."""
import copy
import json
import time

import numpy as np
import torch

from support import HERE, CKPT, CHECKPOINT_SHA, sources, sha, save_json, manifest, execution_environment, make_pilot
from capture import load_record, CaptureError


def equal_bytes(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def reconstruct(meta, arrays, settings):
    row = meta['row']
    hand = row['hand']
    affordable = [int(pair[0]) > 0 and float(c) <= float(row['el_int']) + 1e-6
                  for pair, c in zip(hand, row['costs'])]
    assert affordable == row['allowed']
    p = float(torch.sigmoid(torch.from_numpy(arrays['f0__output__gate']))[0])
    if not any(affordable):
        assert len(meta['forwards']) == 1
        return dict(play=False, no_affordable=True, p_play=p, hand_pos=-1,
                    deck_index=-1, card=0, form=3, name=None, el_int=row['el_int'])
    logits = arrays['f0__output__card'][0]
    # Python max preserves original first-slot tie behavior.
    pos = max((i for i, ok in enumerate(affordable) if ok), key=lambda i: float(logits[i]))
    card, form = hand[pos]
    assert len(meta['forwards']) == 2
    assert arrays['f1__kwarg__card'].tolist() == [card]
    assert arrays['f1__kwarg__form'].tolist() == [form]
    assert equal_bytes(arrays['f0__input__hand_card'], np.array([[h[0] for h in hand]], dtype=np.int64))
    cell = int(np.argmax(arrays['f1__output__cell'][0]))
    offset = .5 if settings['grid'] == 'floor' else 0.
    return dict(play=bool(p > settings['gate_tau'] and card > 0), no_affordable=False,
                p_play=p, hand_pos=pos, deck_index=row['hand_deck_indices'][pos], card=card,
                form=form, name=row['names'][row['hand_deck_indices'][pos]],
                xy=[(cell % 36 + offset) / 36, (cell // 36 + offset) / 64])


def main():
    assert not (HERE / 'replay_started.json').exists(), 'fresh replay required'
    torch.set_num_threads(4)
    q = json.loads((HERE / 'qualified.json').read_text())
    assert q['latency_pass'] and q['sources'] == sources()
    assert sha(CKPT) == CHECKPOINT_SHA
    assert execution_environment() == json.loads((HERE / 'started.json').read_text())['environment']
    save_json(HERE / 'replay_started.json', dict(time=time.time(), sources=sources()))
    pilot = make_pilot()
    expected_manifest = manifest(pilot)
    assert expected_manifest == q['manifest']
    reference = np.load(HERE / 'reference_heads.npz', allow_pickle=False)
    details = []
    heads = 0
    for case in q['cases']:
        i = case['case']
        meta, arrays = load_record(HERE / 'records' / case['record'], expected_manifest)
        for j, forward in enumerate(meta['forwards']):
            prefix = f'f{j}__'
            batch = {k[len(prefix + 'input__'):]: torch.from_numpy(v.copy()) for k, v in arrays.items()
                     if k.startswith(prefix + 'input__')}
            kwargs = {k[len(prefix + 'kwarg__'):]: torch.from_numpy(v.copy()) for k, v in arrays.items()
                      if k.startswith(prefix + 'kwarg__')}
            for group, values in (('input', batch), ('kwarg', kwargs)):
                for key, tensor in values.items():
                    assert equal_bytes(tensor.numpy(), reference[f'r{i}__f{j}__{group}__{key}'])
            with torch.no_grad():
                output = pilot.model(batch, **kwargs)
            assert set(output) == set(forward['outputs'])
            for name, tensor in output.items():
                got = tensor.numpy()
                saved = arrays[prefix + 'output__' + name]
                assert equal_bytes(got, saved), ('replay', i, j, name)
                assert equal_bytes(saved, reference[f'r{i}__f{j}__{name}']), ('baseline', i, j, name)
                heads += 1
        decision = reconstruct(meta, arrays, expected_manifest['settings'])
        assert decision == meta['decision'], ('decision', i)
        # Actual metadata values, not a producer's copied totals.
        details.append(dict(case=i, record_id=meta['record_id'], forwards=len(meta['forwards']),
                            play=decision['play'], no_affordable=decision['no_affordable']))
        time.sleep(.15)
    reference.close()
    path = HERE / 'records' / q['cases'][0]['record']
    controls = 0
    for field in ('schema', 'checkpoint_sha256', 'sources'):
        bad = copy.deepcopy(expected_manifest)
        bad[field] = 999 if field == 'schema' else ('0' * 64 if field == 'checkpoint_sha256' else {'wrong.py': '0' * 64})
        try:
            load_record(path, bad)
        except CaptureError:
            controls += 1
        else:
            raise AssertionError(field)
    # Signed-zero must be distinct in the exact byte oracle.
    assert not equal_bytes(np.array([0.], np.float32), np.array([-0.], np.float32))
    assert equal_bytes(np.array([0.], np.float32), np.array([0.], np.float32))
    save_json(HERE / 'replayed.json', dict(schema=1, details=details, heads_exact=heads,
        cases=len(details), manifest_corruptions_rejected=controls, sources=sources(),
        checkpoint_sha256=sha(CKPT), records= {c['record']: sha(HERE / 'records' / c['record']) for c in q['cases']},
        qualified_sha256=sha(HERE / 'qualified.json')))
    print('DECISION_CAPTURE_REPLAYED', len(details), heads, controls)


if __name__ == '__main__':
    main()
