"""Receipt/source closeout only; no model construction, forwards or check reruns."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
LEAF = BASE / 'decision_capture_replay_completion'
CHECKS = ROOT / 'scratchpad/gauntlet/L71/integration/checks'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    assert not (LEAF / 'reviewed.json').exists()
    spec = importlib.util.spec_from_file_location('capture_completion_review_source', LEAF / 'verify.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registration = read(LEAF / 'registration.json')
    report = read(LEAF / 'verified.json')
    assert module.registration_bindings() == registration['bindings'] == report['bindings']
    assert report['registration_sha256'] == sha(LEAF / 'registration.json')
    assert report['cases'] == 24 and report['saved_records'] == 48 and report['fresh_forwards'] == 42
    assert report['heads_exact'] == 228 and report['saved_head_comparisons'] == 456
    assert report['input_conditioning_arrays_exact'] == 708 and report['reference_arrays_exact'] == 936
    assert report['positive_control_count'] == 3 and report['manifest_negative_count'] == 3
    assert report['signed_zero_negative_count'] == 1
    for name in ('original_latency_pass', 'async_latency_pass', 'live_eligible', 'new_model'):
        assert report[name] is False
    for name in ('rng_unchanged', 'gradients_empty', 'zero_optimizer'):
        assert report[name] is True
    receipt_path = CHECKS / 'l72-decision-capture-replay-completion.json'
    receipt = read(receipt_path)
    expected = ['research/ext/Royale/.venv/Scripts/python.exe',
                'scratchpad/gauntlet/L72/improvement_loop/decision_capture_replay_completion/verify.py']
    assert receipt['command'] == expected and receipt['cwd'] == str(ROOT)
    assert receipt['exit_code'] == 0 and receipt['matched'] is True
    assert receipt['expected'] == 'DECISION_CAPTURE_REPLAY_COMPLETED'
    output = (CHECKS / 'l72-decision-capture-replay-completion.out').read_text(encoding='utf-8')
    assert hashlib.sha256(output.encode()).hexdigest() == receipt['output_sha256']
    assert 'DECISION_CAPTURE_REPLAY_COMPLETED 24 48 42 228 3 3 1' in output
    assert len(report['prior_receipts']) == 4
    for previous in report['prior_receipts']:
        path = CHECKS / (previous['name'] + '.json')
        assert sha(path) == previous['receipt_sha256']
        assert all(read(path)[key] == value for key, value in previous.items()
                   if key not in ('name', 'receipt_sha256'))
    preserved_failures = {p['name']: p['exit_code'] for p in report['prior_receipts'] if p['exit_code']}
    assert set(preserved_failures) == {'l72-decision-capture-qualify', 'l72-decision-capture-async-qualify'}
    result = dict(schema=1, time=time.time(), reviewer_source_sha256=sha(__file__),
        verified_sha256=sha(LEAF / 'verified.json'), registration_sha256=sha(LEAF / 'registration.json'),
        completion_receipt_sha256=sha(receipt_path), receipt=receipt,
        preserved_failures=preserved_failures, prior_receipts=report['prior_receipts'],
        cases=24, saved_records=48, fresh_forwards=42, heads_exact=228,
        input_conditioning_arrays_exact=708, reference_arrays_exact=936,
        original_latency_pass=False, async_latency_pass=False, live_eligible=False, new_model=False,
        scope=report['fixture_limitations'])
    (LEAF / 'reviewed.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('DECISION_CAPTURE_REVIEWED', 24, 48, 42, 228)


if __name__ == '__main__':
    main()
