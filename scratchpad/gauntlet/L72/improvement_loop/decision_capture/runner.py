"""One serial qualification chain; common lock covers subprocess gaps."""
import json
import msvcrt
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PY = ROOT / 'research/ext/Royale/.venv/Scripts/python.exe'
CHECK = ROOT / 'scratchpad/gauntlet/L71/integration/run_check.py'


def main():
    assert not (HERE / 'chain_started.json').exists()
    lock_path = ROOT / 'icebow/data/bench/development_iteration_1_20261005/chain.lock'
    with lock_path.open('r+b') as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        (HERE / 'chain_started.json').write_text(json.dumps(dict(time=time.time(), pid=__import__('os').getpid())))
        jobs = [('l72-decision-capture-unit', 'passed', ['-m', 'pytest', str(HERE / 'test_capture.py'), str(HERE / 'test_entry_capture.py'), '-q']),
                ('l72-decision-capture-qualify', 'DECISION_CAPTURE_QUALIFIED', [str(HERE / 'qualify.py')]),
                ('l72-decision-capture-replay', 'DECISION_CAPTURE_REPLAYED', [str(HERE / 'replay.py')]),
                ('l72-decision-capture-entry', 'LIVE_CHECK_PASS', [str(HERE / 'entry.py'), '--check',
                    '--capture-character-identity', '--capture-dir', str(HERE / 'check_unused'),
                    '--ckpt', str(ROOT / 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt'),
                    '--device', 'cpu', '--tau', '0.35', '--no-anti-leak'])]
        for name, token, command in jobs:
            result = subprocess.run([str(PY), str(CHECK), '--name', name, '--expect', token, '--', str(PY), *command], cwd=ROOT)
            if result.returncode:
                (HERE / 'chain_failed.json').write_text(json.dumps(dict(time=time.time(), job=name, code=result.returncode)))
                raise SystemExit(result.returncode)
        (HERE / 'chain_complete.json').write_text(json.dumps(dict(time=time.time(), jobs=[x[0] for x in jobs])))


if __name__ == '__main__':
    main()
