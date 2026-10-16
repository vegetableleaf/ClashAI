"""20261016-linux (royalesim 0.1.35) selection without importing either engine; old ids unchanged vs 9fa94c3."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
BEFORE = '9fa94c3'   # last commit before the 20261016-linux id
PROBE = '''
import json, sys
from pipeline import royale_runtime as r
from pipeline import royale_heroiw as h
assert 'royalesim' not in sys.modules and 'royalegym' not in sys.modules
print(json.dumps(dict(id=r.RUNTIME_ID, manifest=str(r.MANIFEST), runtime=str(r.RUNTIME), heroiw=h.ENABLED,
                      options=h.engine_options())))
'''


def probe(runtime, source_rev=None):
    """Run PROBE against the working tree, or against royale_runtime/royale_heroiw as of source_rev."""
    cwd = ROOT
    if source_rev:
        import tempfile
        cwd = Path(tempfile.mkdtemp())
        (cwd/'pipeline').mkdir()
        for name in ('__init__.py', 'royale_runtime.py', 'royale_heroiw.py', 'reader_identity_aliases.py'):
            (cwd/'pipeline'/name).write_bytes(subprocess.check_output(['git', 'show', f'{source_rev}:pipeline/{name}'], cwd=ROOT))
    p = subprocess.run([sys.executable, '-c', PROBE], cwd=cwd, env=dict(os.environ, ROYALE_RUNTIME=runtime, PYTHONPATH=str(cwd)),
                       text=True, capture_output=True)
    if p.returncode:
        return dict(error=p.stderr.strip().splitlines()[-1])
    out = json.loads(p.stdout)
    for k in ('manifest', 'runtime'):   # compare repo-relative
        path = Path(out[k])
        repo_path = any(path.is_relative_to(cwd/d) for d in ('scratchpad', 'research'))   # not a venv inside the repo
        out[k] = path.relative_to(cwd).as_posix() if repo_path else path.as_posix()
    return out


def test_rt35_selection():
    out = probe('20261016-linux')
    assert out['id'] == '20261016-linux' and out['heroiw'] is True
    assert out['manifest'] == 'scratchpad/gauntlet/L74/rt35/build_manifest.json'
    assert out['options'] == {'calibration_overrides': {'cards.CARD_TABLE': 'client160402017_20261006'}}
    import sysconfig
    assert ROOT/out['runtime'] == Path(sysconfig.get_paths()['purelib'])   # ROOT/abs = abs
    m = json.loads((ROOT/out['manifest']).read_text())
    assert m['versions'] == {'royalesim': '0.1.35', 'royalegym': '0.1.23'}
    assert m['pins']['RoyaleSim'] == '4fd4d54cdcbf6469aff4e4d87cb0dba523d295bc'


@pytest.mark.parametrize('runtime', ['', '20261006', '20261006-linux', '20261012', '20261012-linux', 'fork', 'unpinned-linux'])
def test_old_ids_unchanged(runtime):
    assert probe(runtime) == probe(runtime, BEFORE)


@pytest.mark.parametrize('runtime', ['20261016', '20261016-Linux', 'rt35'])
def test_unknown_still_raises(runtime):
    assert 'Unknown ROYALE_RUNTIME' in probe(runtime)['error']
