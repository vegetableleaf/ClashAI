"""HEROIW contracts without importing either engine or running a battle."""
import ast
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

from pipeline import royale_heroiw as h
from pipeline.reader_identity_aliases import HERO_ICE_WIZARD_NAMES, extend_forms, extend_names

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'scratchpad/gauntlet/L74/heroiw'


def source_methods():
    """Compile actual production methods with a fake protocol; no engine import."""
    tree = ast.parse((ROOT/'pipeline/royale_env.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RoyalePoolEnv')
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('_setup', '_scan', 'raw', '_v2_gate')]
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), cls], type_ignores=[])
    ns = dict(heroiw=h, MatchSetup=lambda **kw: NS(**kw), ShuffleMode=NS(NONE=0),
              DeployCommand=lambda *args: args, DeployStatus=NS(OK=0), HAND_SIZE=4, EMPTY_CARD=-1,
              SCALE=18, EntityKind=NS(KING_TOWER=1, PRINCESS_TOWER=2), V2_KEYS={}, UnsupportedDeck=ValueError)
    exec(compile(ast.fix_missing_locations(module), '<production methods>', 'exec'), ns)
    return ns['RoyalePoolEnv']


@pytest.mark.parametrize('runtime,version,table', [('', None, False), ('20261006', None, False),
    ('20261006-linux', None, False), ('20261012', '0.1.33', True), ('20261012-linux', '0.1.33', True)])
def test_runtime_selection_without_sim(runtime, version, table):
    script = '''
import json, sys
from pipeline import royale_runtime as r
from pipeline import royale_heroiw as h
m=json.loads(r.MANIFEST.read_text())
assert 'royalesim' not in sys.modules and 'royalegym' not in sys.modules
print(json.dumps(dict(id=r.RUNTIME_ID, manifest=str(r.MANIFEST), runtime=str(r.RUNTIME),
                     manifest_data=m, options=h.engine_options())))
'''
    p = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=dict(os.environ, ROYALE_RUNTIME=runtime),
                       check=True, text=True, capture_output=True)
    out = json.loads(p.stdout)
    assert out['id'] == (runtime or None)
    assert bool(out['options']) == table
    if version:
        assert out['manifest_data']['versions'] == {'royalesim': version, 'royalegym': '0.1.23'}
        assert out['options']['calibration_overrides']['cards.CARD_TABLE'] == h.CARD_TABLE
    else:
        relative = ('scratchpad/gauntlet/L73/royale_update_20261006/build_manifest.json' if runtime
                    else 'scratchpad/gauntlet/L71/royale_update_20261005/build_manifest.json')
        assert out['manifest_data'] == json.loads((ROOT/relative).read_text())
        assert Path(out['manifest']) == ROOT/relative


def test_old_selection_matches_pre_ticket_source():
    # Independent old source is HEAD, not a copied set of constants from the implementation.
    before = subprocess.check_output(['git', 'show', 'HEAD:pipeline/royale_runtime.py'], cwd=ROOT, text=True)
    for value in ('', '20261006', '20261006-linux'):
        script = '''
import json, pathlib, sys
ns={'__file__':str(pathlib.Path('pipeline/royale_runtime.py').resolve())}
exec(sys.stdin.read(), ns)
print(json.dumps([str(ns[k]) for k in ('RUNTIME_ID','MANIFEST','RUNTIME')]))
'''
        env = dict(os.environ, ROYALE_RUNTIME=value)
        a = subprocess.check_output([sys.executable, '-c', script], input=before, env=env, cwd=ROOT, text=True)
        b = subprocess.check_output([sys.executable, '-c', script], input=(ROOT/'pipeline/royale_runtime.py').read_text(),
                                    env=env, cwd=ROOT, text=True)
        assert a == b


@pytest.mark.parametrize('enabled', [False, True])
def test_deck_form_and_fail_closed(monkeypatch, enabled):
    monkeypatch.setattr(h, 'ENABLED', enabled)
    names = ['Tornado', 'Tesla', 'IceWizard', 'Xbow', 'Rocket', 'Knight', 'Log', 'Skeletons']
    forms = [0, 1, 0, 0, 0, 1, 0, 0]
    mapped = h.deck_forms(names, forms)
    assert mapped[2] == (2 if enabled else 0)
    assert forms[2] == 0
    assert h.deck_forms(['IceWizard', 'Giant'], [0, 0]) == [0, 0]
    env = source_methods()()
    env.forms_mode = 'deck'
    env.deck_ids = {0: list(range(8)), 1: list(range(8))}
    env.names = dict(enumerate(names))
    env._form_loads = lambda *args: True
    order = {0: list(reversed(range(8))), 1: list(range(8))}
    result = env._setup(env.deck_ids, order, {0: forms, 1: forms})
    assert result.forms[0] == list(reversed(mapped)) and result.forms[1] == mapped
    assert env.loaded_forms[0] == mapped and env.form_fallbacks == []
    if enabled:
        env._form_loads = lambda side, cid, form: cid != 2
        with pytest.raises(ValueError, match='refused form 2'):
            env._setup(env.deck_ids, order, {0: forms, 1: forms})


@pytest.mark.parametrize('name', [*HERO_ICE_WIZARD_NAMES, 'IceWizard_hero'])
def test_public_identity_and_aliases(monkeypatch, name):
    monkeypatch.setattr(h, 'ENABLED', True)
    assert h.public_identity(name) == 203000023
    assert h.public_identity('IceWizard') is None
    names = {26000023: 'IceWizard'}
    forms = {26000023: ('IceWizard', 0)}
    assert extend_names(names)[203000023] == 'IceWizard'
    assert extend_forms(forms)[203000023] == ('IceWizard', 2)
    assert len(names) == len(forms) == 1
    monkeypatch.setattr(h, 'ENABLED', False)
    assert h.public_identity(name) is None


def test_cube_observed_as_live_identity_not_controller_flag(monkeypatch):
    from pipeline.public_observation import public_frame
    from pipeline.obs_contract import entity_form
    monkeypatch.setattr(h, 'ENABLED', True)
    env = source_methods()()
    env.deck_ids, env.names, env.feature_version = {0: [0], 1: [0]}, {0: 'IceWizard'}, 3
    e = NS(kind=3, team=0, x=63000, y=240000, hp=100, max_hp=100, card_id=0, uid=77,
           status_flags=0, deploy_ticks=0, unit_type=0)
    st = NS(tick=120, players=[NS(team=s, hand=[0], elixir_milli=5000, next_card=0) for s in (0, 1)], entities=[e], spells=[])
    env.core = NS(state=lambda: st, unit_types=lambda: ['IceWizardHero_IceCube'])
    raw = env.raw()
    assert raw['entities'][0]['status_flags'] == 0
    assert entity_form(raw['entities'][0]) == 2
    public = public_frame(raw, source='sim')
    assert public['entities'][0]['card_id'] == 203000023
    assert 'players' not in public
    from pipeline.obs_contract import from_engine, load_deck
    from pipeline import vocab
    board = from_engine(raw, 0, load_deck('icebow'), feature_version=5)
    assert len(board.units) == 1
    assert board.units[0].cls == vocab.unit_id('ice_wizard') and board.units[0].form == 2
    monkeypatch.setattr(h, 'ENABLED', False)
    assert 'public_card_id' not in env.raw()['entities'][0]


def test_button_uses_engine_cost_readiness_and_hero_body(monkeypatch):
    monkeypatch.setattr(h, 'ENABLED', True)
    env = source_methods()()
    hero = NS(team=0, card_id=0, hp=600, max_hp=600, uid=3, status_flags=16)
    cube = NS(team=0, card_id=0, hp=100, max_hp=100, uid=4, status_flags=0)
    champion = NS(team=0, card_id=1, hp=1000, max_hp=1000, uid=5, status_flags=0)
    player = NS(abilities=[(0, 1, 2, 0), (1, 1, 1, 1)], elixir_milli=2000)
    st = NS(players=[player], entities=[hero, cube, champion])
    env.core = NS(state=lambda: st, check_deploy=lambda cmd: 0)
    env._hero_ids, env._champ_ids = {0: [0, 1]}, {0: {1}}
    env._hero_costs, env._ability_pending = {0: 99}, []
    assert env._scan(0, lambda *args: True) == [(0, 0, 3), (1, 1, 5)]
    player.elixir_milli = 1999
    assert env._scan(0, lambda *args: True) == [(1, 1, 5)]
    env.core.check_deploy = lambda cmd: 99
    assert env._scan(0, lambda *args: True) == []
    assert not h.controller_body(0) and h.controller_body(0, champion=True)
    monkeypatch.setattr(h, 'ENABLED', False)
    assert not h.controller_body(0, champion=True)


def test_v2_hero_iw_uses_existing_fallback(monkeypatch):
    monkeypatch.setattr(h, 'ENABLED', True)
    env = source_methods()()
    env.names = {0: 'IceWizard'}
    env._near = lambda *args: 'existing public range gate'
    assert env._v2_gate(0, 0, None, None) == 'existing public range gate'


def test_own_ability_tokens_use_selected_engine_spec(monkeypatch):
    from pipeline import own_ability as own, royale_runtime
    monkeypatch.setattr(h, 'ENABLED', True)
    monkeypatch.setattr(royale_runtime, 'activate', lambda: {})
    spec = dict(mana_cost=2, max_charges=1, cooldown_ms=None)
    monkeypatch.setattr(h, 'selected_card_data', lambda: dict(cards=[], hero_forms=[
        dict(name='IceWizard_hero', form_of='IceWizard', ability=spec, deploy_time_ms=1000)]))
    own.catalog.cache_clear()
    try:
        assert own.catalog()['ice-wizard', 2] == dict(spec, deploy_ms=1000)
        rows = [('ice-wizard', 2, 1, -1., 0.)]
        events = [dict(card='IceWizard', tick=100, accepted=True)]
        ready = own.tokens(rows, {'ice-wizard': 62}, events, 121)[0]
        assert list(ready) == [62, 2, 1, 1, 1, 1, 0]
        events.append(dict(card='IceWizard', tick=122, accepted=True, ability=True))
        spent = own.tokens(rows, {'ice-wizard': 62}, events, 123)[0]
        assert list(spent) == [62, 2, 1, 0, 1, 0, 0]
    finally:
        own.catalog.cache_clear()


def driver():
    spec = importlib.util.spec_from_file_location('heroiw_validate', HERE/'validate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paired_ci_and_failure_controls():
    mod = driver()
    base = [dict(census='evo' if i < 4 else 'lad', seed=i, learner_side=i % 2, opp_deck=['Giant'],
                 opp_gen_sha256='same', outcome='loss', searched=0) for i in range(8)]
    new = [dict(r, outcome='win') for r in base]
    report = mod.paired_drift(base, new, expected=8)
    assert report['delta_pp'] == 100 and report['ci95_pp'] == [100, 100]
    assert mod.paired_drift(base, base, expected=8)['ci95_pp'] == [0, 0]
    with pytest.raises(ValueError, match='incomplete'):
        mod.paired_drift(base, new[:-1], expected=8)
    with pytest.raises(ValueError, match='pairing mismatch'):
        mod.paired_drift(base, [dict(r, opp_deck=['Knight']) for r in new], expected=8)
    with pytest.raises(ValueError, match='duplicate'):
        mod.paired_drift(base, new+[new[0]], expected=8)


def test_source_manifest_and_scripts_compile():
    manifest = json.loads((HERE/'build_manifest.json').read_text())
    assert manifest['pins']['RoyaleSim'] == 'cacb7005f0e441797c533e91ab4f44820f9919d4'
    assert manifest['pins']['RoyaleGym'] == 'a7deb6e48c3580fe2cd7d856b7c7d19ce67f02f9'
    assert 'royalegym/rust_engine.py' in manifest['files']
    for path in HERE.glob('*.py'):
        compile(path.read_text(), str(path), 'exec')
    shell = (HERE/'run_heroiw.sh').read_text()
    assert b'\r' not in (HERE/'run_heroiw.sh').read_bytes()
    assert 'flock 9' in shell and 'WORKERS <= 25' in shell and 'trap finish EXIT' in shell
    assert '/workspace/venv33' in shell and 'royalesim==0.1.33 royalegym==0.1.23' in shell


def test_drift_and_livecal_schedules_keep_pairing():
    mod = driver()
    import livecal
    manifest = json.loads((mod.LIVE/'manifest.json').read_text())
    old = [g for g in manifest['groups'] if g['family'] == 'old' and not g['fast']]
    plan = livecal.schedule({**manifest, 'groups': old}, k=480, seed_start=741200, pools='P1')
    assert len(old) == 1 and sum(len(j['seeds']) for j in plan['jobs']) == 480
    assert all(j['opponent'] == dict(path=livecal.E4, temperature=.1) and not j['fast'] for j in plan['jobs'])
    keys = [(j['census'], s) for j in plan['jobs'] for s in j['seeds']]
    assert len(set(keys)) == 480
    live = livecal.schedule(manifest, k=480, pools='P1,P2,P5')
    assert {j['pool'] for j in live['jobs']} == {'P1', 'P2', 'P5'}
    assert live['games'] == len(manifest['groups'])*3*480
