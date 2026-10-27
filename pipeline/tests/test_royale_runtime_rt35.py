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


def test_fin15_selection():
    """W8 10-20: fin15-linux = the parity fork fin15 in /workspace/venvf15 (parity/fin15/setup_fin15.sh), Hero IW adapter on."""
    out = probe('fin15-linux')
    assert out['id'] == 'fin15-linux' and out['heroiw'] is True
    assert out['manifest'] == 'scratchpad/gauntlet/L74/parity/fin15/build_manifest_fin15.json'
    assert out['options'] == {'calibration_overrides': {'cards.CARD_TABLE': 'client160402017_20261006'}}


def test_fin16_selection():
    """A1 10-27: fin16-linux = fin15 + the client-dated 10-19 card table in /workspace/venvf16 (parity/fin16/setup_fin16.sh),
    Hero IW adapter on, the battle on the 10-19 table."""
    out = probe('fin16-linux')
    assert out['id'] == 'fin16-linux' and out['heroiw'] is True
    assert out['manifest'] == 'scratchpad/gauntlet/L74/parity/fin16/build_manifest_fin16.json'
    assert out['options'] == {'calibration_overrides': {'cards.CARD_TABLE': 'client160402017_20261019'}}
    m = json.loads((ROOT/out['manifest']).read_text())
    assert m['pins']['RoyaleSim'] == '3f5676076fa7293de5355fa7c76275ddfbf4322c' and m['card_table'] == 'client160402017_20261019'


@pytest.mark.parametrize('runtime', ['', '20261006', '20261006-linux', '20261012', '20261012-linux', '20261016-linux',
                                     'fork36-linux', 'fin13-linux', 'fin15-linux', 'fork', 'unpinned-linux'])
def test_ids_unchanged_by_fin16(runtime):
    now, before = probe(runtime), probe(runtime, '0f2d82f5541a96bb40fae430b6cc8dd8472b73fa')   # the commit before fin16-linux
    assert (ROOT/now.pop('runtime')).resolve() == (ROOT/before.pop('runtime')).resolve() and now == before


CUE_PROBE = '''
import json, types
from pipeline import sim_unit_state as s
tab = lambda v: json.dumps(dict(towers=[], cards=[dict(name=v)], evolutions=[], hero_forms=[], buffs={}, projectiles={}))
both = types.SimpleNamespace(EMBEDDED_CARDS_160402017_JSON=tab('t1006'), EMBEDDED_CARDS_160402017_20261019_JSON=tab('t1019'))
old = types.SimpleNamespace(EMBEDDED_CARDS_160402017_JSON=tab('t1006'))
print(json.dumps([list(s._tbl(both)['cards']), list(s._tbl(old)['cards'])]))
'''


@pytest.mark.parametrize('runtime, want', [('fin16-linux', 't1019'), ('fin15-linux', 't1006'), ('', 't1006')])
def test_cue_table_follows_fin16(runtime, want):
    """sim_unit_state reads the battle's table: the 10-19 one only under fin16-linux; a module without the 10-19 text
    (older wheels, live_unit_state's namespace) always the 10-06 one."""
    p = subprocess.run([sys.executable, '-c', CUE_PROBE], cwd=ROOT, env=dict(os.environ, ROYALE_RUNTIME=runtime, PYTHONPATH=str(ROOT)),
                       text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout) == [[want], ['t1006']]


@pytest.mark.parametrize('runtime', ['fork36-linux', 'fin13-linux'])
def test_fork_ids_unchanged_by_fin15(runtime):
    now, before = probe(runtime), probe(runtime, '3f727662229e36ed4f890b5deb0a5a39a523acc2')   # the last selector commit before fin15
    assert (ROOT/now.pop('runtime')).resolve() == (ROOT/before.pop('runtime')).resolve() and now == before   # runtime: repo-relative or absolute
