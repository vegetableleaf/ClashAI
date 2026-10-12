"""Bounded no-SIM verification with success-only markers and recorded evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tests', action='store_true')
    ap.add_argument('--contract', action='store_true')
    a = ap.parse_args()
    evidence = {}
    if a.tests:
        cmd = [sys.executable, '-m', 'pytest', str(HERE/'tests'), '-q', '-p', 'no:cacheprovider']
        r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        print(r.stdout); print(r.stderr, file=sys.stderr)
        if r.returncode:
            return r.returncode
        assert re.search(r'\d+ passed', r.stdout)
        evidence['tests'] = dict(command=cmd, cwd=str(ROOT), exit_code=r.returncode,
                                 output_sha256=hashlib.sha256((r.stdout+r.stderr).encode()).hexdigest(),
                                 summary=r.stdout.strip().splitlines()[-1])
        print('PRO2_TESTS_PASS')
    if a.contract:
        text = (HERE/'README.md').read_text(encoding='utf-8')
        block = text.split('## Current format chain (10 lines)', 1)[1].split('**Runtime distinction:**',1)[0]
        assert len(re.findall(r'^\d+\. ',block,re.M)) == 10
        for name in ('convert.py','build_rows.py','audit.py','verify.py'):
            compile((HERE/name).read_text(encoding='utf-8'), name, 'exec')
        # Static review only; this does not claim to parse or execute Bash.
        sh = (HERE/'build_rows.sh').read_text(encoding='utf-8')
        assert sh.index('exit 0') < sh.index('"$PYTHON"')
        assert '/workspace/results/PRO2' in sh and 'set -euo pipefail' in sh
        assert 'unit_missing=None' in (HERE/'build_rows.py').read_text(encoding='utf-8')
        evidence['contract'] = dict(format_chain_lines=10, python_compile=True,
                                    bash_execution='UNAVAILABLE_WINDOWS_ACCESS_DENIED',
                                    simulator_execution='NOT_RUN')
        print('PRO2_CONTRACT_PASS')
    receipt = HERE/'verification.json'
    old = json.loads(receipt.read_text()) if receipt.exists() else {}
    old.update(evidence, platform=os.name, interpreter=sys.executable)
    receipt.write_text(json.dumps(old,indent=2)+'\n',encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
