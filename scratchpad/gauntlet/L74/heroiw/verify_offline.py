"""Run requested pytest coverage and prove no engine package was imported."""
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import pytest


class LocalTemp:
    @pytest.fixture
    def tmp_path(self):
        # Same managed-Windows workaround as LIVECAL/conftest.py: normal mkdir,
        # not pytest/tempfile mode 0700, which produces unreadable directories here.
        work = Path(__file__).resolve().parent/'.test_work'
        path = work/uuid.uuid4().hex
        assert path.resolve().parent == work.resolve()
        path.mkdir(parents=True)
        return path

if __name__ == '__main__':
    paths = ['pipeline/tests/test_heroiw.py', 'pipeline/tests/test_reader_identity_aliases.py',
             'pipeline/tests/test_own_ability_hero_iw.py', 'pipeline/tests/test_identity_fv5.py']
    rc = pytest.main(['-q', '-p', 'no:cacheprovider', *[str(ROOT/p) for p in paths]], plugins=[LocalTemp()])
    if rc:
        raise SystemExit(rc)
    assert not any(n.split('.')[0] in ('royalesim', 'royalegym') for n in sys.modules), 'SIM import in offline tests'
    print('HEROIW_OFFLINE_OK')
