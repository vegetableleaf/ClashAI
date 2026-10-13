"""IWDIAG contracts: public fixtures only; never import an engine package."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from pipeline import royale_heroiw as H
from pipeline import royale_iw_policy as P

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT/'scratchpad/gauntlet/L74/heroiw/diag'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def env_methods(*names):
    tree = ast.parse((ROOT/'pipeline/royale_env.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RoyalePoolEnv')
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    tree = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), cls], type_ignores=[])
    ns = dict(heroiw=H, V2_KEYS={'Knight': 'knight-hero'})
    exec(compile(ast.fix_missing_locations(tree), '<production>', 'exec'), ns)
    return ns['RoyalePoolEnv']


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('mode', [None, 'hero', 'normal'])
def test_forms_opt_in(monkeypatch, enabled, mode):
    monkeypatch.setattr(H, 'ENABLED', enabled)
    monkeypatch.delenv('ROYALE_HEROIW_FORM', raising=False)
    if mode is not None:
        monkeypatch.setenv('ROYALE_HEROIW_FORM', mode)
    deck = ['Tornado', 'Tesla', 'IceWizard', 'Xbow', 'Rocket', 'Knight', 'Log', 'Skeletons']
    forms = [0, 1, 0, 0, 0, 1, 0, 0]
    wanted = list(forms)
    if enabled and mode != 'normal':
        wanted[2] = 2
    assert H.deck_forms(deck, forms) == wanted
    assert forms == [0, 1, 0, 0, 0, 1, 0, 0]
    assert H.deck_forms(['Giant', 'IceWizard'], [0, 2]) == [0, 2]
    assert H.deck_forms(list(reversed(deck)), list(reversed(forms))) == list(reversed(wanted))


def test_press_opt_in_and_invalid_flags(monkeypatch):
    monkeypatch.delenv('ROYALE_HEROIW_PRESS', raising=False)
    assert not H.live_press_enabled()
    monkeypatch.setattr(H, 'ENABLED', True)
    monkeypatch.setenv('ROYALE_HEROIW_PRESS', 'live')
    assert H.live_press_enabled()
    monkeypatch.setenv('ROYALE_HEROIW_PRESS', 'never')
    assert H.press_mode() == 'never' and not H.live_press_enabled()
    monkeypatch.setattr(H, 'ENABLED', False)
    with pytest.raises(ValueError, match='runtime'):
        H.press_mode()
    monkeypatch.setenv('ROYALE_HEROIW_PRESS', 'live')
    with pytest.raises(ValueError, match='runtime'):
        H.live_press_enabled()
    monkeypatch.setenv('ROYALE_HEROIW_PRESS', 'typo')
    with pytest.raises(ValueError):
        H.live_press_enabled()
    monkeypatch.setattr(H, 'ENABLED', True)
    monkeypatch.setenv('ROYALE_HEROIW_FORM', 'typo')
    with pytest.raises(ValueError):
        H.deck_forms(list(H.ICEBOW), [0]*8)


def test_production_routing_default_and_live():
    env = env_methods('_v2_gate', '_v2_recheck')()
    env.names = {0: 'IceWizard', 1: 'UnknownHero', 2: 'Knight'}
    env._near = lambda *args: 'old fallback'
    assert env._v2_gate(0, 0, None, None) == 'old fallback'
    assert env._v2_recheck(0, 0, None, None) == 'old fallback'
    env._iw_policy = NS(gate=lambda *args: 'live rule')
    assert env._v2_gate(0, 0, None, None) == 'live rule'
    assert env._v2_gate(0, 1, None, None) == 'old fallback'
    assert env._v2_recheck(0, 0, None, None) is True
    assert env._v2_recheck(0, 2, None, None) is True


def live_geometry():
    tree = ast.parse((P.LIVE/'hero_button.py').read_text())
    wanted = {'IW_RANGE', 'FREEZE_R', 'TESLA_COST', 'CLUMP_BODIES_MIN', 'CLUMP_VALUE_MIN', 'UNKNOWN_UNIT_VALUE',
              'WINCONS', 'BUILDINGS'}
    nodes = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name == 'ice_wizard_should_press')
             or (isinstance(n, ast.Assign) and any(isinstance(v, ast.Name) and v.id in wanted
                 for t in n.targets for v in ast.walk(t)))]
    ns = dict(unit_values=P.unit_values)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<live pure geometry>', 'exec'), ns)
    for name in wanted:
        assert ns[name] == getattr(P, name)
    return ns['ice_wizard_should_press']


@pytest.mark.parametrize('side', [0, 1])
def test_geometry_matches_live_fixtures(side):
    live = live_geometry()
    names = {0: 'IceWizard', 1: 'Knight', 2: 'HogRider', 3: 'Tesla', 4: 'Skeletons', 5: 'Unknown', 6: 'Cannon'}
    rng = random.Random(17)
    for _ in range(300):
        hero = dict(side=side, x=rng.randrange(18000), y=rng.randrange(32000), card_id=0)
        foes = [dict(side=1-side, x=hero['x']+rng.randrange(-5501, 5502),
                     y=hero['y']+rng.randrange(-5501, 5502), card_id=rng.randrange(1, 7)) for _ in range(8)]
        frame = dict(entities=[hero]+foes, players=[dict(side=side, deck_card_ids=[0, 3],
                      hand_deck_indices=[rng.choice([-1, 0, 1])], elixir_raw=rng.choice([20000, 39999, 40000, 90000]))])
        assert P.geometry(frame, side, hero, names) == live(frame, side, hero, names)[0]
    assert not P.geometry(frame, side, None, names)


def test_geometry_decisive_clump_and_tesla_boundaries():
    hero = dict(side=0, x=9000, y=10000, card_id=0)
    hog = dict(side=1, x=9000, y=14000, card_id=1)
    me = dict(side=0, deck_card_ids=[2], hand_deck_indices=[0], elixir_raw=40000)
    f = dict(entities=[hero, hog], players=[me])
    names = {0: 'IceWizard', 1: 'HogRider', 2: 'Tesla', 3: 'Knight', 4: 'Skeletons'}
    assert not P.geometry(f, 0, hero, names)
    me['elixir_raw'] = 39999
    assert P.geometry(f, 0, hero, names)
    me['elixir_raw'] = 40000
    f['entities'] = [hero, dict(hog, card_id=3), dict(hog, x=10000, card_id=3)]
    assert P.geometry(f, 0, hero, names)
    f['entities'] = [hero]+[dict(hog, card_id=4, x=9000+i) for i in range(3)]
    assert not P.geometry(f, 0, hero, names)
    f['entities'] = [hero, dict(hog, y=15501)]
    assert not P.geometry(f, 0, hero, names)


def test_hazard_threshold_geometry_and_whole_second_grid(monkeypatch):
    hazard = P.hazard_module()
    grids = []
    monkeypatch.setattr(hazard, 'live_features', lambda *a, **kw: grids.append(kw['tick']) or {})
    monkeypatch.setattr(hazard, 'frosty_fella_press_probability', lambda f: .03)
    for tick in (120, 121, 139):
        assert hazard.should_press_pro(None, {'game_tick': tick}, 0, 100, True, v_min=4, p_star=P.P_STAR)[0]
    assert grids == [120, 120, 120]
    assert not hazard.should_press_pro(None, {'game_tick': 139}, 0, 100, False, v_min=4, p_star=P.P_STAR)[0]
    monkeypatch.setattr(hazard, 'frosty_fella_press_probability', lambda f: .029999)
    assert not hazard.should_press_pro(None, {'game_tick': 139}, 0, 100, True, v_min=4, p_star=P.P_STAR)[0]


def test_adapter_only_own_state_and_public_counter(monkeypatch):
    import pipeline.public_observation as public
    from pipeline import obs_contract
    policy = P.LiveIWPolicy()
    raw = dict(tick=139, entities=[dict(side=0, x=9000, y=10000, hp=700, max_hp=700, card_id=0,
                                       public_card_id=203000023, name='IceWizard', entity_id=42)], effects=[])
    own = [dict(card='IceWizard', side=0, tick=100, accepted=True),
           dict(card='Rocket', side=1, tick=90, accepted=True)]
    class Observer:
        def __init__(self, *a, **kw):
            self.plays = []
        def update(self, frame, *, source):
            assert frame is raw and source == 'sim'
        def estimate_at(self, tick):
            return 6.25
    monkeypatch.setattr(public, 'PublicObserver', Observer)
    env = NS(feature_version=4, raw=lambda: raw, public_plays=own, elixir_regen_schedule=(),
             tick=139, deck_ids={0: [0, 1]}, names={0: 'IceWizard', 1: 'Tesla'})
    policy.observe(env, 0)
    assert policy.observers[0].own_events == [dict(own[0], card='ice-wizard')]
    class OwnPlayers:
        def __getitem__(self, side):
            assert side == 0, 'opponent private state was read'
            return NS(hand=[1], elixir_milli=5000)
    st = NS(players=OwnPlayers())
    monkeypatch.setattr(P, 'geometry', lambda f, side, hero, names: hero['address'] == (0, 42))
    got = []
    def decide(pilot, frame, side, deploy, **kwargs):
        got.append((pilot.public.estimate_at(frame['game_tick']), deploy, kwargs, frame['players']))
        return True, 'fixture'
    monkeypatch.setattr(P.hazard_module(), 'should_press_pro', decide)
    assert policy.gate(env, NS(team=0, uid=42), st)
    assert got[0][:3] == (6.25, 100, dict(geometry_ok=True, v_min=4.0, p_star=.03))
    assert got[0][3][0]['deck_card_ids'] == [26000023, 27000006]
    policy.reset()
    assert not policy.observers and not policy.frames


def test_no_engine_imports_and_default_behavior_subprocess():
    script = '''
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, *a):
  if fullname.split('.')[0] in ('royalesim','royalegym'): raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from pipeline import royale_heroiw as h, royale_iw_policy as p
assert not h.live_press_enabled()
assert p.hazard_module().load_model()['feature_names']
assert not any(n.split('.')[0] in ('royalesim','royalegym') for n in sys.modules)
'''
    env = dict(os.environ, ROYALE_HEROIW_PRESS='off')
    subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env, check=True)


def test_public_damage_estimate_and_mixed_damage_are_explicit():
    M = module('iwdiag_metrics_test', DIAG/'metrics.py')
    rec = M.Recorder(0, 7, 28800)
    before = dict(tick=100, towers={(1, 0, 100000): 1000}, shots=[(0, 'Xbow', 0, 80000, 0, 100000)],
                  bodies=[], spells=[])
    after = dict(before, tick=101, towers={(1, 0, 100000): 939}, shots=[])
    rec.observe(before, after)
    assert rec.result()['xbow_impact_hp_loss'] == 61
    assert rec.result()['xbow_tower_damage_exact'] is None
    assert rec.result()['xbow_contested_hp_loss'] == 0
    rec.observe(dict(before, spells=[(0, 0, 0)]), after)
    assert rec.result()['xbow_contested_hp_loss'] == 61
    rec.observe(dict(before, tick=6000), dict(after, tick=6001))
    rec.observe(before, dict(after, tick=102))
    rec.observe(dict(before, shots=[]), after)
    assert rec.result()['xbow_impact_hp_loss'] == 122


def test_exact_press_accounting_and_zero_attempt_rate():
    M = module('iwdiag_metrics_accounting', DIAG/'metrics.py')
    state = NS(tick=100, players=[NS(elixir_milli=5000, abilities=[(0, 1, 2, 0)])])
    def step(commands, ticks):
        return []
    def act(**kw):
        if kw.get('ability_button') is not None:
            state.players[0].elixir_milli -= 2000
        return dict(accepted=True, result_code=0)
    env = NS(core=NS(state=lambda: copy.deepcopy(state), step=step), eng=NS(act=act),
             queue_abilities=lambda *a: None, ids={'Xbow': 1}, names={0: 'IceWizard', 1: 'Xbow'},
             deck_ids={0: [0, 1]}, _ability_pending=[])
    rec, restore = M.instrument(env, 0, 28800, (1, 2))
    assert rec.result()['iw_success_rate'] is None
    env.queue_abilities(0, [(0, 0, 9), (0, 0, 9)], 26)
    env.eng.act(side=0, ability_button=0)
    env.eng.act(side=0, deck_index=1)
    result = rec.result()
    assert result['iw_scheduled'] == result['iw_attempts'] == result['iw_accepted'] == 1
    assert result['iw_elixir'] == 2 and result['iw_success_rate'] == 1
    assert result['xbow_placements'] == 1
    restore()
    assert env.core.step is step and env.eng.act is act


def fixture_rows(arm, k=8):
    D = module('iwdiag_driver_fixture', DIAG/'iwdiag.py')
    hero = arm in ('N0', 'N2')
    return [dict(census=census, seed=seed, learner_side=seed % 2, opp_deck=['Giant'],
                 opp_gen_sha256='same', outcome='win' if arm == 'N1' else 'loss', searched=0, wall_truncated=False,
                 ability_presses={str(seed % 2): {'IceWizard': int(hero)}},
                 iwdiag=dict(arm=arm, runtime={'runtime_id': D.ARMS[arm][0]}, form=D.ARMS[arm][1], press=D.ARMS[arm][2],
                             loaded_forms={str(seed % 2): [0, 1, 2 if arm in ('N0', 'N2', 'N3') else 0, 0, 0, 1, 0, 0]},
                             iw_table_cost=2 if arm != 'O0' else None,
                             press_receipts=[dict(accepted=True, spent=2)] if hero else [],
                             iw_scheduled=2*int(hero), iw_attempts=int(hero), iw_accepted=int(hero), iw_elixir=2*int(hero), xbow_placements=3,
                             xbow_impact_hp_loss=61, xbow_contested_hp_loss=0, xbow_impact_windows=1))
            for census in ('evo', 'lad') for seed in range(741200, 741200+k//2)]


def test_paired_summary_and_rejection_controls():
    D = module('iwdiag_driver_summary', DIAG/'iwdiag.py')
    data = {arm: fixture_rows(arm) for arm in D.ARMS}
    report, text = D.summarize(data, 25, expected=8)
    assert report['N1']['paired']['delta_pp'] == 100
    assert report['N1']['paired']['ci95_pp'] == [100, 100]
    assert report['N0']['paired']['ci95_pp'] == [0, 0]
    assert 'NOT exact' in text and '2.0000' in text
    bad = copy.deepcopy(data)
    bad['N2'][0]['opp_deck'] = ['Knight']
    with pytest.raises(ValueError, match='pairing mismatch'):
        D.summarize(bad, 25, expected=8)
    bad = copy.deepcopy(data)
    bad['N2'][0]['iwdiag']['press'] = 'off'
    with pytest.raises(ValueError, match='provenance'):
        D.summarize(bad, 25, expected=8)
    with pytest.raises(ValueError):
        D.summarize({**data, 'N2': data['N2'][:-1]}, 25, expected=8)
    bad = copy.deepcopy(data)
    bad['N2'][0]['iwdiag']['iw_elixir'] = float('nan')
    with pytest.raises(ValueError, match='invalid metric'):
        D.summarize(bad, 25, expected=8)
    bad = copy.deepcopy(data)
    bad['N0'][0]['iwdiag']['press_receipts'] = []
    with pytest.raises(ValueError, match='incomplete press'):
        D.summarize(bad, 25, expected=8)
    bad = copy.deepcopy(data)
    bad['N3'][0]['iwdiag']['iw_scheduled'] = 1          # N3 = never press
    with pytest.raises(ValueError, match='unexpectedly pressed'):
        D.summarize(bad, 25, expected=8)
    report, _ = D.summarize({a: data[a] for a in ('N0', 'N1', 'N3')}, 25, expected=8)   # --arms subset
    assert set(report) == {'N0', 'N1', 'N3'}
    with pytest.raises(ValueError, match='N0'):
        D.summarize({a: data[a] for a in ('N1', 'N3')}, 25, expected=8)


def test_schedule_and_exact_one_change_per_new_arm():
    D = module('iwdiag_driver_plan', DIAG/'iwdiag.py')
    import livecal
    m = D.read(D.LIVE/'manifest.json')
    m['groups'] = [g for g in m['groups'] if g['family'] == 'old' and not g['fast']]
    plan = livecal.schedule(m, k=480, seed_start=741200, pools='P1')
    assert plan['games'] == 480 and len(plan['jobs']) == 40
    for arm, key in [('N1', 'ROYALE_HEROIW_FORM'), ('N2', 'ROYALE_HEROIW_PRESS')]:
        baseline, changed = D.arm_env('N0'), D.arm_env(arm)
        assert {k for k in baseline if baseline[k] != changed[k]} == {key, 'IWDIAG_ARM'}
    job = plan['jobs'][0]
    cmd = D.command(job, Path('census.json'), Path('out'), 'python')
    assert cmd[1] == str(DIAG/'iwdiag.py') and cmd[2] == '--worker'
    assert '--hero-abilities' in cmd and cmd[cmd.index('--ability-policy')+1] == 'v2'
    assert cmd[cmd.index('--workers')+1] == '1' and cmd[cmd.index('--arms')+1] == 'plain'


@pytest.mark.parametrize('workers', [0, 26, -1])
def test_worker_cap_rejects_before_any_dispatch(workers):
    D = module('iwdiag_driver_worker_cap', DIAG/'iwdiag.py')
    with pytest.raises(ValueError, match='workers'):
        D.run(NS(workers=workers))


@pytest.mark.parametrize('corrupt', [False, True])
def test_arm_dispatch_collects_receipts_and_fails_closed(monkeypatch, corrupt):
    D = module('iwdiag_driver_dispatch', DIAG/'iwdiag.py')
    import livecal
    directory = DIAG/'offline'/('test_'+uuid4().hex)
    directory.mkdir(parents=True)
    monkeypatch.setattr(livecal, 'validate_files', lambda *args: None)
    data = fixture_rows('N0')
    plan = dict(files=[dict(path='checkpoint', sha256='learner'), dict(path=livecal.E4, sha256='same')],
                censuses={c: dict(path=c+'.json') for c in ('evo', 'lad')},
                jobs=[dict(census=c, group='old', pool='P1', checkpoint='checkpoint', fast=False,
                           opponent=dict(path=livecal.E4, temperature=.1), seeds=list(range(741200, 741204)))
                      for c in ('evo', 'lad')])
    def fake_worker(cmd, **kwargs):
        assert kwargs['env']['IWDIAG_ARM'] == 'N0'
        assert kwargs['env']['ROYALE_HEROIW_PRESS'] == 'off'
        dest = Path(cmd[cmd.index('--out')+1])
        dest.mkdir()
        D.dump(dest/'run.json', dict(gen_sha256='bad' if corrupt else 'learner', opp_gen_sha256='same'))
        census = Path(cmd[cmd.index('--census')+1]).stem
        records = [dict(r, arm='plain') for r in data if r['census'] == census]
        (dest/'matches.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    monkeypatch.setattr(D.subprocess, 'run', fake_worker)
    out = directory/'N0'
    if corrupt:
        with pytest.raises(ValueError, match='checkpoint receipt'):
            D.run_arm('N0', 'fake-python', plan, directory, out, 2)
        assert not (out/'DONE').exists()
    else:
        D.run_arm('N0', 'fake-python', plan, directory, out, 2)
        assert len(D.rows(out/'matches.jsonl')) == 8
        assert (out/'DONE').read_text() == 'exit_code=0\n'


def test_device_evidence_matches_local_sources():
    C = module('iwdiag_cost_test', DIAG/'cost_evidence.py')
    assert C.evidence() == json.loads((DIAG/'device_cost.json').read_text())


def test_source_scripts_compile_and_shell_constraints():
    for p in DIAG.glob('*.py'):
        compile(p.read_text(), str(p), 'exec')
    shell = (DIAG/'run_iwdiag.sh').read_text()
    assert '\r' not in (DIAG/'run_iwdiag.sh').read_bytes().decode()
    assert 'flock 9' in shell and 'WORKERS <= 25' in shell and 'trap finish EXIT' in shell
    assert shell.index('flock 9') < shell.index('mkdir "$OUT"') < shell.index('trap finish EXIT')
    assert 'pip install' not in shell and 'ssh ' not in shell and 'curl ' not in shell
