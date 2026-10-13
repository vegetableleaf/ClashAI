"""Offline test/provenance receipt, using the interpreter the caller selected."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def main():
    for path in [*HERE.glob('*.py'), * (HERE/'tests').glob('*.py')]:
        ast.parse(path.read_text(encoding='utf8'),filename=str(path))
    cmd=[sys.executable,'-m','pytest',str(HERE/'tests'),'-q','-p','no:cacheprovider','-p','no:tmpdir']
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    output=result.stdout+result.stderr
    print(output)
    files=[*HERE.glob('*.py'),* (HERE/'tests').glob('*.py'),HERE/'run_parity.sh',HERE/'TRIAGE.md']
    receipt=dict(command=cmd,cwd=str(ROOT),shell='direct subprocess from PowerShell',
                 exit_code=result.returncode,success=result.returncode==0 and 'passed' in output,
                 output=output,output_sha256=hashlib.sha256(output.encode()).hexdigest(),
                 file_sha256={p.relative_to(HERE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                 validation_scope='synthetic and offline only; no real-engine replay or pod launch')
    (HERE/'triage/verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    if not receipt['success']:return 1
    print('PARITY_TRIAGE_TESTS_PASS')
    return 0


if __name__=='__main__':raise SystemExit(main())
