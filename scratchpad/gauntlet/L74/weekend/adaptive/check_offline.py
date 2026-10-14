"""Run offline acceptance tests (no SIM). Windows temp dirs inherit workspace ACLs.

The unrelated process-exit regression needs named pipes unavailable in the
restricted Windows host. It is excluded on Windows, run normally on Linux.
"""
import os
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

if os.name == "nt":
    original_mkdtemp = tempfile.mkdtemp

    def inherited_temp(suffix=None, prefix=None, dir=None):
        # Python 3.13 mkdir(0700) sets an ACL excluding the restricted token.
        # Only test artifacts under this workspace get inherited permissions.
        if dir is not None:
            return original_mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        path = ROOT / "scratchpad" / (str(prefix or "adaptive_test_") + uuid.uuid4().hex + str(suffix or ""))
        path.mkdir(mode=0o777)
        return str(path)

    tempfile.mkdtemp = inherited_temp

import pytest

args = ["-q", "-p", "no:cacheprovider", "pipeline/tests/test_adaptive_opponents.py",
        "pipeline/tests/test_league.py", "pipeline/tests/test_rl_royale.py"]
if os.name == "nt":
    args += ["-k", "not TestActorExitWithUnreadPut"]
rc = pytest.main(args)
if rc == 0:
    print("ADAPTIVE_OFFLINE_ACCEPTANCE_PASSED")
raise SystemExit(rc)
