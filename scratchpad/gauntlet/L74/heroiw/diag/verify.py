"""No-SIM acceptance checks; logs/receipts remain beside this script."""
import argparse
import hashlib
import importlib.abc
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))


class NoSim(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in ('royalesim', 'royalegym'):
            raise AssertionError(f'No SIM allowed in offline verification: {fullname}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tests', action='store_true')
    args = ap.parse_args()
    if args.tests:
        # In-process pytest retains the import guard (unlike a child process).
        sys.meta_path.insert(0, NoSim())
        import pytest
        code = pytest.main(['-q', '-p', 'no:cacheprovider', str(ROOT/'pipeline/tests/test_iwdiag.py'),
                            str(ROOT/'pipeline/tests/test_heroiw.py')])
        if code:
            raise SystemExit(code)
        print('IWDIAG_TESTS_OK')
        return
    sys.meta_path.insert(0, NoSim())
    import iwdiag as D
    from cost_evidence import evidence
    assert evidence() == D.read(HERE/'device_cost.json')
    for path in [ROOT/'pipeline/royale_heroiw.py', ROOT/'pipeline/royale_iw_policy.py',
                 ROOT/'pipeline/royale_env.py', *HERE.glob('*.py')]:
        compile(path.read_text(encoding='utf8'), str(path), 'exec')
    # Normal inherited ACLs; tempfile's owner-only Windows directory mode is
    # inaccessible under this managed workspace. Preserve the small input receipt.
    directory = HERE/'offline'/uuid4().hex
    directory.mkdir(parents=True)
    plan = D.prepare(directory/'inputs')
    assert plan['games'] == 480
    assert len({(j['census'], s) for j in plan['jobs'] for s in j['seeds']}) == 480
    assert all(not j['fast'] for j in plan['jobs'])
    archive = Path('C:/Users/benpe/pod_backup_weekend/podB/x_HEROIW/results/HEROIW/DRIFT_NEW/plan.json')
    if archive.is_file():
        old = D.read(archive)
        for key in ('groups', 'pools', 'jobs', 'k', 'seed_start', 'censuses'):
            assert plan[key] == old[key], f'HEROIW design mismatch: {key}'
    assert not subprocess.check_output(['git', 'diff', '--name-only', '--',
                                        'scratchpad/gauntlet/L68/live_reader'], cwd=ROOT).strip()
    shell = (HERE/'run_iwdiag.sh').read_text()
    assert 'flock 9' in shell and 'WORKERS <= 25' in shell
    assert 'pip install' not in shell and 'curl ' not in shell and 'ssh ' not in shell
    assert b'\r' not in (HERE/'run_iwdiag.sh').read_bytes()
    receipt = dict(status='offline checks passed; no SIM executed', games_per_arm=480, arms=4,
                   total_games=1920, workers_cap=25, eta=D.eta(25),
                   device_cost_evidence='device_cost.json',
                   shell_parse='Git Bash -n attempted; blocked by Windows sandbox CreateFileMapping error 5. Static launcher assertions passed.',
                   sources={str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in [ROOT/'pipeline/royale_heroiw.py', ROOT/'pipeline/royale_env.py',
                                      ROOT/'pipeline/royale_iw_policy.py', ROOT/'pipeline/tests/test_iwdiag.py',
                                      *HERE.glob('*.py'), HERE/'run_iwdiag.sh', HERE/'device_cost.json']})
    D.dump(HERE/'verification.json', receipt)
    print('IWDIAG_OFFLINE_OK')


if __name__ == '__main__':
    main()
