"""PARITY v2 receipt writer. Offline tests and frozen-cohort planning; no SIM."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    for name in ('tests', 'planning', 'contract'):
        ap.add_argument('--'+name, action='store_true')
    args = ap.parse_args()
    receipt_path = HERE/'verification_v2.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}

    def record(key, command):
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        output = p.stdout+p.stderr
        print(output)
        receipt[key] = dict(command=[str(s) for s in command], shell='PowerShell (direct subprocess)',
                            cwd=str(ROOT), exit_code=p.returncode,
                            output_sha256=hashlib.sha256(output.encode()).hexdigest(), output=output)
        receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')
        if p.returncode:
            raise SystemExit(p.returncode)

    if args.tests:
        record('tests', [sys.executable, '-m', 'pytest', str(HERE/'tests'), '-q', '-p', 'no:cacheprovider', '-p', 'no:tmpdir'])
        print('PARITY_V2_TESTS_PASS')
    if args.planning:
        out = HERE/'output'/('cohort100_v2_'+uuid.uuid4().hex[:8])
        frozen = HERE/'output/cohort100/sources'
        record('planning', [sys.executable, str(HERE/'driver.py'), 'plan', '--mechanics-replay',
                            '--cohort', str(frozen), '--out', str(out)])
        report = json.loads((out/'planning.json').read_text())
        selected = json.loads((out/'selection.json').read_text())
        original = [json.loads(p.read_text()) for p in sorted(frozen.glob('*.json'))]
        assert {r['match']:r['sha256'] for r in original} == {r['match']:r['sha256'] for r in report['matches']}
        assert report['selected'] == len(original)
        assert report['usable_matches'] + sum(not r['usable'] for r in report['matches']) == report['selected']
        for row in report['matches']:
            counts = row['counts']
            assert counts['plays_used'] + sum(s['kind']=='play' for s in row['skips']) == counts['plays_total']
            assert counts['decisions_used'] + sum(s['kind']=='decision' for s in row['skips']) == counts['decisions_total']
        report['frozen_cohort'] = 'scratchpad/gauntlet/L74/parity/output/cohort100/sources'
        report['hydrated_cohort'] = (out/'sources').relative_to(ROOT).as_posix()
        report['harness_hashes'] = selected['harness_hashes']
        (HERE/'planning_v2.json').write_text(json.dumps(report, indent=2)+'\n')
        receipt['planning']['report'] = {k:v for k,v in report.items() if k != 'matches'}
        print('PARITY_V2_PLANNING_PASS')
    if args.contract:
        for p in [*HERE.glob('*.py'), * (HERE/'tests').glob('*.py')]:
            ast.parse(p.read_text(), filename=str(p))
        # Both checked source versions must expose the adapter's APIs and exact
        # guarded rehash diagnostic. The rebuilt hash retry does not swallow errors.
        engine_paths = [ROOT/'research/ext/Royale/RoyaleSim', ROOT/'research/ext/Royale-20261006/RoyaleSim']
        evidence = {}
        for engine in engine_paths:
            py_path=engine/'crates/royalesim/src/py.rs'; state_path=engine/'crates/royalesim/src/state.rs'
            py=py_path.read_text();state=state_path.read_text()
            assert all(s in py for s in ('fn save<', 'fn load(', 'fn reset(', 'fn step('))
            assert 'snapshot self-check failed: saved hash {:#x}, rebuilt {got:#x}{what}' in state
            assert 'serde_json::to_vec(&snap)' in state and 'pub const NO_CARD: u16 = u16::MAX' in state
            evidence[str(engine.relative_to(ROOT))] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (py_path,state_path)}
        driver=(HERE/'driver.py').read_text(); run=(HERE/'run_parity.sh').read_text()
        assert 'mechanics_replay=False' in driver and "action='store_true'" in driver
        assert 'MECHANICS_REPLAY:-0' in run and '--mechanics-replay' in run
        assert 'new_fork_unsupported_old' in driver and 'ranking=rank(samples, catalog)' in driver
        doc=(HERE/'V2.md').read_text()
        assert all(s in doc for s in ('MECHANICS_REPLAY=1', 'planning_v2.json', 'snapshot', 'No SIM', 'next card'))
        receipt['contract'] = dict(engine_source=evidence, default_off=True, python_syntax='passed',
                                   files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in HERE.iterdir() if p.suffix in ('.py','.sh')})
        print('PARITY_V2_CONTRACT_PASS')
    assert not any(n.split('.')[0] in ('royalesim','royalegym') for n in sys.modules)
    receipt_path.write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()
