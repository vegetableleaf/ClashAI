"""CPU acceptance only. Does not import or run a simulator runtime."""
import os
from pathlib import Path
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
if os.name == 'nt':
    original = tempfile.mkdtemp

    def inherited_temp(suffix=None, prefix=None, dir=None):
        if dir is not None:
            return original(suffix=suffix, prefix=prefix, dir=dir)
        path = ROOT/'scratchpad'/((prefix or 'memory_test_')+uuid.uuid4().hex+(suffix or ''))
        path.mkdir(mode=0o777)
        return str(path)

    tempfile.mkdtemp = inherited_temp

import pytest
args = ['-q', '-p', 'no:cacheprovider']
if len(sys.argv) > 1:
    args += sys.argv[1:]
else:
    args += ['pipeline/tests/'+name for name in (
        'test_match_memory.py', 'test_memory_model.py', 'test_memory_training.py', 'test_memory_driver.py',
        'test_model_gen.py', 'test_rl_royale.py', 'test_league.py', 'test_adaptive_opponents.py')]
    if os.name == 'nt':
        # Windows named pipes are blocked; this unrelated lifecycle test uses them.
        args += ['-k', 'not TestActorExitWithUnreadPut']
rc = pytest.main(args)
if rc == 0:
    print('MEMORY_OFFLINE_ACCEPTANCE_PASSED')
raise SystemExit(rc)
