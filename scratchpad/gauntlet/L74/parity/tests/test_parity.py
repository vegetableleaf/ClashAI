import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import core as c, driver as d


def body(cid=1, side=0, key='a', x=1000, y=1000, hp=100, tower=False):
    return dict(card_id=cid, side=side, key=key, x=x, y=y, hp=hp, max_hp=hp, tower=tower)


def raw(cid, side, key, x=1000, y=1000, hp=100):
    b = body(cid, side, key, x, y, hp)
    b['address'] = b.pop('key'); b.pop('tower')
    return b


def fixture_data():
    cat, names = c.ps.load_catalog()
    knight = names['Knight']['card_id']
    ds = []
    for tick, bs in [(100, []), (120, [raw(knight, 0, 'one')]),
                     (130, [raw(knight, 0, 'one'), raw(knight, 0, 'two', x=1500)]),
                     (200, [raw(knight, 0, 'aftergap', x=4000)])]:
        ds.append(dict(tick=tick, side=1, bodies=bs, hand=[], elixir=5, projectiles=[]))
    return dict(decisions=ds, plays=[dict(tick=110, name='Knight', xy=[.25, .75]),
                                    dict(tick=170, name='Knight', xy=[.5, .7])],
                confirmations=[dict(tick=140, name='Knight', spawn=[[.25, .75]])],
                abilities=[], sha256='fixture', errors=0), cat, names


def test_public_play_extraction_grouping_gaps_and_confirmation():
    data, cat, _ = fixture_data()
    _, names = c.ps.load_catalog()
    plays = c.extract_plays(data, cat, names)
    assert len(plays) == 2
    own, enemy = plays
    assert (own['tick'], own['side'], own['x'], own['y']) == (110, 1, 13500, 24000)
    assert (enemy['tick'], enemy['previous_tick'], enemy['side'], enemy['x'], enemy['y'], enemy['bodies']) == (120, 100, 0, 1000, 1000, 2)


@pytest.mark.parametrize('side,expected', [(1, (13500, 24000)), (0, (4500, 8000))])
def test_play_coordinate_seats(side, expected):
    data, cat, names = fixture_data()
    for dec in data['decisions']:
        dec['side'] = side; dec['bodies'] = []
    own = c.extract_plays(data, cat, names)[0]
    assert (own['x'], own['y']) == expected


def test_synthetic_log_selection_public_only():
    import uuid
    tmp_path = ROOT/'scratchpad/gauntlet/L74/parity/output'/('test_'+uuid.uuid4().hex)
    tmp_path.mkdir(parents=True)
    towers = [raw(-1, side, str((side, x)), x=x, y=y, hp=hp)
              for side in (0, 1) for x,y,hp in [(9000, 3000 if side==0 else 29000,7032),
                                               (3500,6500 if side==0 else 25500,4424),
                                               (14500,6500 if side==0 else 25500,4424)]]
    path = tmp_path/'live_play_20261008_000000.jsonl'
    rows = [dict(event='start', dry_run=False)]
    for tick in (100, 2500):
        rows.append(dict(event='decision', tick=tick, public=dict(observer_side=1,
                    raw_bodies=towers, own_hand=[dict(name='Xbow',form=0)], own_elixir_raw=6,
                    opponent_hand='SECRET', opponent_elixir='SECRET', opponent_deck='SECRET')))
    rows += [dict(event='play', tick=110, name='Xbow', xy=[.25,.75]),
             dict(event='confirmed', tick=130, name='Xbow', spawn=[[.25,.75]]), dict(event='end')]
    path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    data, reason = c.ps.read_live(path)
    assert reason is None
    assert 'SECRET' not in json.dumps(data)
    cat, names = c.ps.load_catalog()
    prepared = c.prepare(path, data, cat, names)
    assert len(prepared['plays']) == 1
    assert prepared['plays'][0]['x'] == 13500
    assert 'card_and_tower_levels_unobserved_supply_explicit_assumed_level' in prepared['blocks']
    assert 'SECRET' not in json.dumps(prepared)
    rows[1]['public']['raw_bodies'][3]['max_hp'] = 999
    path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    assert c.ps.read_live(path)[1] == 'other_account_tower_signature'


def test_matching_spawn_order_not_nearest_neighbour():
    a, b = c.Tracks(), c.Tracks()
    x = a.assign(0, [body(key='a', x=1000), body(key='b', x=2000)])
    y = b.assign(0, [body(key='x', x=1100), body(key='y', x=2100)])
    assert list(x) == list(y)
    x = a.assign(20, [body(key='a', x=3000), body(key='b', x=500)])
    y = b.assign(20, [body(key='x', x=3100), body(key='y', x=600)])
    assert all(r['position_error_tiles'] == pytest.approx(.1) for r in c.compare(x,y))
    assert next(iter(a.assign(100, [body(key='a')]))) == 'unit:1:0:3'


def test_same_id_opposite_side_and_missing_not_zero_hp():
    a = c.Tracks().assign(0, [body(side=0), body(side=1)])
    b = c.Tracks().assign(0, [body(side=1)])
    rows = c.compare(a,b)
    assert rows[0]['missing'] == 'sim'
    assert rows[0]['hp_error'] is None
    assert rows[0]['unmatched_visible_hp'] == 100
    assert not rows[1]['mismatch']


def test_metrics_position_hp_tower_thresholds():
    a = {'unit': body(), 'tower': body(-1, tower=True)}
    b = {'unit': body(x=4000,y=5000,hp=70), 'tower': body(-1,hp=40,tower=True)}
    rows = c.compare(a,b)
    unit = next(r for r in rows if not r['tower'])
    assert unit['position_error_tiles'] == 5
    assert unit['hp_error'] == 30
    assert next(r for r in rows if r['tower'])['hp_error'] == 60
    assert not c.compare({'a':body()}, {'a':body(x=1500)})[0]['mismatch']


def test_ranking_frequency_and_impacts_not_swarm_multiplied():
    cat = {1:dict(display_name='Tesla',type='building'), 2:dict(display_name='Knight',type='troop')}
    def sample(cid, hp, count=1):
        a = {str(i):body(cid,key=str(i)) for i in range(count)}
        b = {str(i):body(cid,key=str(i),hp=100-hp) for i in range(count)}
        return dict(match='m',tick=1,rows=c.compare(a,b),recent_plays=[])
    rows = c.rank([sample(1,50,5),sample(2,1)],cat)
    assert rows[0]['group'] == 'Tesla deploy'
    assert rows[0]['frequency'] == rows[0]['exposures'] == 1
    assert rows[0]['mean_unit_hp_error'] == 50
    assert rows[0]['attribution'] == 'association_only'


def test_summary_pairs_same_completed_matches_and_nulls():
    def result(rt, match):
        return dict(runtime=rt,match=match,samples=[],commands=[],divergence_seconds=None,divergence_tick=None)
    r = d.summarize([{},{}], [result('old','a'),result('old','b'),result('new','a')], ['old','new'])
    assert r['paired_matches'] == ['a']
    assert r['runtimes']['old']['completed'] == 2
    assert r['runtimes']['old']['paired'] == 1
    assert r['runtimes']['new']['unit_hp_mae'] is None
    assert d.summarize([{}], [], ['old','new'])['status'] == 'NO_PAIRED_MEASUREMENTS'


def test_spell_context_ranks_unit_displacement_and_hp_errors():
    cat = {1:dict(display_name='Knight',type='troop'), 2:dict(display_name='Tornado',type='spell')}
    rows = c.compare({'u':body(1)}, {'u':body(1,x=4000,hp=50)})
    ranked = c.rank([dict(match='m',rows=rows,recent_plays=[dict(card_id=2,name='Tornado')])],cat)
    tornado = next(r for r in ranked if r['group']=='Tornado pull')
    assert tornado['frequency'] == 1
    assert tornado['mean_position_error_tiles'] == 3
    assert tornado['mean_unit_hp_error'] == 50
    assert tornado['attribution'] == 'association_only'


@pytest.mark.parametrize('selection', ['', '20261006', '20261012', 'fork'])
def test_runtime_selector_no_sim_default_preserved(monkeypatch, selection):
    monkeypatch.setenv('ROYALE_RUNTIME',selection)
    spec = importlib.util.spec_from_file_location('runtime_test', ROOT/'pipeline/royale_runtime.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    expected = {'':'Royale-20261005', '20261006':'Royale-20261006', '20261012':'Royale-20261012', 'fork':'Royale-fork'}
    assert mod.RUNTIME == ROOT/'research/ext'/expected[selection]/'runtime'
    if selection == 'fork':
        assert mod.MANIFEST == mod.RUNTIME.parent/'build_manifest.json'
        monkeypatch.setattr(mod,'MANIFEST',ROOT/'parity_missing_manifest.json')
        with pytest.raises(RuntimeError, match='manifest missing'):
            mod.activate()


def test_sim_snapshot_mapping_and_unit_scale_without_sim():
    _, names = c.ps.load_catalog()
    fields = ['uid','team','card_id','x','y','hp','max_hp','status_flags']
    raw_state = dict(tick=100, players=[dict(team=1, elixir_milli=5000)],
                     entities=[[7,0,0,18000,36000,90,100,0], [8,0,-1,162000,54000,7032,7032,0]])
    sim = SimpleNamespace(ENTITY_FIELDS=fields)
    battle = SimpleNamespace(state_json=lambda: json.dumps(raw_state))
    state, bodies, elixir = d.snapshot(sim,battle,names,['Knight'],1)
    assert bodies[0]['card_id'] == names['Knight']['card_id']
    assert (bodies[0]['x'],bodies[0]['y']) == (1000,2000)
    assert bodies[1]['tower'] and elixir == 5


def test_no_engine_imported():
    assert not any(n.split('.')[0] in ('royalesim','royalegym') for n in sys.modules)


def test_worker_both_sides_ticks_levels_refusals_and_terminal(monkeypatch):
    """Adapter integration against a deterministic contract fake, not a SIM test."""
    from importlib import metadata
    _, native = c.ps.load_catalog()
    names = list(c.ps.OWN_COST)
    fields = ['uid','team','card_id','x','y','hp','max_hp','status_flags']
    class Battle:
        instance = None
        def __init__(self, card_names, slots, **kw):
            Battle.instance = self
            assert card_names is None and slots == [[0,1,2],[0,2,1]]
            self.tick = 0; self.calls = []; self.entities = []
        def catalogue_json(self): return json.dumps([[n] for n in names])
        def reset(self, seed, decks, shuffle, tick, elixir, hp, spawns, **kw):
            self.decks = decks
            assert kw['levels'] == [[15]*8,[15]*8]
            assert kw['tower_levels'] == [15,15]
        def state_json(self):
            return json.dumps(dict(tick=self.tick, entities=self.entities,
                players=[dict(team=s,hand=list(range(4)),elixir_milli=5000) for s in (0,1)]))
        def step(self, commands, ticks):
            self.tick = min(150, self.tick+ticks)
            rows=[]
            for side, slot, x, y in commands:
                self.calls.append((self.tick,side,x,y))
                rows.append((slot,0 if side==0 else 4,self.tick,x,y))
            return rows
    sim = SimpleNamespace(Battle=Battle, ENTITY_FIELDS=fields, CATALOGUE_FIELDS=['name'],
                          DEPLOY_REASONS=['OK','BAD_TEAM','BAD_SLOT','EMPTY_SLOT','NOT_ENOUGH_ELIXIR'])
    runtime = SimpleNamespace(activate=lambda: {'test':'fake'}, RUNTIME=ROOT)
    monkeypatch.setitem(sys.modules,'royalesim',sim)
    monkeypatch.setitem(sys.modules,'pipeline.royale_runtime',runtime)
    from research.sandbox_tools.replay_drive import infer_deals
    # Real existing solver, with its deterministic first solution on both sides.
    monkeypatch.setattr(metadata,'distributions',lambda **kw: [SimpleNamespace(metadata={'Name':'royalesim'},version='0.1.17')])
    decks = {str(s):[dict(name=n,card_id=native[n]['card_id'],level=15,form=0) for n in names] for s in (0,1)}
    plays = [dict(tick=t,side=s,name=names[0],card_id=native[names[0]]['card_id'],x=1500,y=3000)
             for s,t in ((0,100),(1,110))]
    source=dict(match='fake',decks=decks,plays=plays,tower_levels=[15,15],observer_side=0,quality={},sha256='fake',
                frames=[dict(tick=t,bodies=[],own_elixir=5) for t in (90,100,120,160)])
    out=d.drive(source,'old')
    assert Battle.instance.calls == [(100,0,27000,54000),(110,1,27000,54000)]
    assert len(out['samples']) == 4
    assert out['commands'][1]['reason'] == 'NOT_ENOUGH_ELIXIR'
    assert out['divergence_tick'] == 120 and out['first_rejected_command_tick'] == 110
    assert out['samples'][-1]['unavailable'] == 'sim_terminated'
