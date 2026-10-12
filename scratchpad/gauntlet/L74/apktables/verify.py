"""Run the authorized synthetic checks and record a private receipt."""
from __future__ import annotations
import datetime
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True


def main():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(HERE/'tests'))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    output = stream.getvalue()
    print(output, end='')
    receipt = dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   skipped=len(result.skipped), success=result.wasSuccessful(),
                   python=sys.version, cwd=str(Path.cwd()), shell='caller shell',
                   output_sha256=hashlib.sha256(output.encode()).hexdigest(),
                   sources={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in [*HERE.glob('*.py'), *HERE.glob('tests/*.py')]})
    (HERE/'out').mkdir(exist_ok=True)
    (HERE/'out/test_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    if result.wasSuccessful() and not result.skipped:
        print('APKTABLES_SYNTHETIC_PASS')
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
