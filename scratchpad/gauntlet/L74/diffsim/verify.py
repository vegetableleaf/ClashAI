"""Run engine-free acceptance tests and write a source-bound receipt."""
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def main():
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(str(HERE / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    forbidden = sorted(n for n in sys.modules if n == "royalesim" or n.startswith("royalesim.")
                       or n == "royalegym" or n.startswith("royalegym."))
    receipt = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   skipped=len(result.skipped), engine_imports=forbidden,
                   wall_seconds=time.perf_counter()-started,
                   sources={str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(HERE.rglob("*.py")) if "test-output" not in p.parts},
                   native_vm_tested=False, fork_wheel_tested=False)
    (HERE / "VERIFICATION.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.wasSuccessful() and not forbidden:
        print("DIFFSIM_VERIFIED")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
