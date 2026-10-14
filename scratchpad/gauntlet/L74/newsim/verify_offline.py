"""Run pytest without SIM. Cached pytest may live in .test_deps (no download)."""
import os
from pathlib import Path
import sys
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE / '.test_deps'), str(ROOT)]
os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode = True
os.chdir(ROOT)

if os.name == 'nt':
    def inherited_temp(suffix=None, prefix=None, dir=None):
        path = Path(dir or HERE / '.test_work') / (str(prefix or 'tmp') + uuid.uuid4().hex + str(suffix or ''))
        path.mkdir(parents=True)
        return str(path)
    tempfile.mkdtemp = inherited_temp

import pytest


class LocalTemp:
    @pytest.fixture
    def tmp_path(self):
        return Path(tempfile.mkdtemp())


if __name__ == '__main__':
    args = sys.argv[1:] or ['pipeline/tests']
    rc = pytest.main(['-q', '-p', 'no:cacheprovider', *args], plugins=[LocalTemp()])
    assert not any(n.split('.')[0] in ('royalesim', 'royalegym') for n in sys.modules), 'SIM imported'
    if not rc:
        print('NEWSIM_OFFLINE_OK')
    raise SystemExit(rc)
