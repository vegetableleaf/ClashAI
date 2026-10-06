"""Serial successor qualification with common lock spanning subprocess gaps."""
import json
import msvcrt
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PY = ROOT / 'research/ext/Royale/.venv/Scripts/python.exe'
CHECK = ROOT / 'scratchpad/gauntlet/L71/integration/run_check.py'


def main():
    assert not (HERE / 'chain_started.json').exists()
    with (ROOT / 'icebow/data/bench/development_iteration_1_20261005/chain.lock').open('r+b') as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        (HERE / 'chain_started.json').write_text(json.dumps(dict(time=time.time(), pid=os.getpid())))
        jobs = [('unit', 'passed', ['-m', 'pytest', str(HERE / 'test_async.py'), '-q']),
                ('qualify', 'ASYNC_CAPTURE_QUALIFIED', [str(HERE / 'qualify.py')]),
                ('replay', 'ASYNC_CAPTURE_REPLAYED', [str(HERE / 'replay.py')]),
                ('entry', 'LIVE_CHECK_PASS', [str(HERE / 'entry.py'), '--check', '--capture-character-identity',
                    '--capture-dir', str(HERE / 'check_unused'), '--device', 'cpu', '--tau', '.35', '--no-anti-leak',
                    '--ckpt', str(ROOT / 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt')])]
        for stage, token, args in jobs:
            name = 'l72-decision-capture-async-' + stage
            p = subprocess.run([str(PY), str(CHECK), '--name', name, '--expect', token, '--', str(PY), *args], cwd=ROOT)
            if p.returncode:
                (HERE / 'chain_failed.json').write_text(json.dumps(dict(time=time.time(), stage=stage, code=p.returncode)))
                raise SystemExit(p.returncode)
        (HERE / 'chain_complete.json').write_text(json.dumps(dict(time=time.time(), stages=[j[0] for j in jobs])))


if __name__ == '__main__':
    main()
