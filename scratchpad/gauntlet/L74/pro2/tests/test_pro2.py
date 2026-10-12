import copy
import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.pro2 import convert as c
from scratchpad.gauntlet.L74.pro2 import build_rows as b

HERE = Path(__file__).resolve().parent


def fixture(name):
    return json.loads((HERE/(name+'.json')).read_text(encoding='utf-8'))


@pytest.mark.parametrize('name,card,tick,xy,side', [
    ('raw2', 'skeletons', 202, (8.5, 22.5), 1),
    ('bait', 'wall-breakers', 143, (8.5, 17.5), 1),
])
def test_real_page(name, card, tick, xy, side):
    r = c.parse_page(fixture(name))
    assert len(r['plays']) == 4
    assert [len(r['decks'][s]) for s in ('0','1')] == [8,8]
    p = r['plays'][0]
    assert (p['card'], p['tick'], p['side']) == (card, tick, side)
    assert (p['x'], p['y']) == xy
    assert r['plays'][1]['side'] == 0
    assert r['plays'][-1]['ability'] and r['plays'][-1]['x'] is None
    assert not r['blocks']
    assert 'names' not in r and 'tags' not in r
    assert r['battle_time'] is None


@pytest.mark.parametrize('seat', ['0', '1'])
@pytest.mark.parametrize('xy', [(0,0), (18,32), (3.499,24.499), (9,16)])
def test_frame_roundtrip(seat, xy):
    assert c.canonical_xy(*c.canonical_xy(*xy, seat), seat) == pytest.approx(xy)


def test_frame_rejects_unknown_seat_and_nan():
    with pytest.raises(ValueError): c.canonical_xy(1,2,None)
    with pytest.raises(ValueError): c.canonical_xy(float('nan'),2,'0')


def test_dedupe_id_time_decks_seat_order_and_no_capture_time():
    r = c.parse_page(fixture('raw2'))
    r['battle_time'] = '20261001T123456.000Z'
    d = c.Dedupe(c.identity_keys(r))
    assert d.add(r) == 'existing_corpus'
    other = copy.deepcopy(r); other['tag'] = 'OTHER'
    other['decks'] = {'0': list(reversed(r['decks']['1'])), '1': r['decks']['0']}
    assert d.add(other) == 'existing_corpus'
    other['battle_time'] = '20261002T123456.000Z'
    assert c.Dedupe(c.identity_keys(r)).add(other) is None
    d = c.Dedupe(); assert d.add(r) is None; assert d.add(r) == 'input_duplicate'
    r.pop('battle_time'); r['captured_at'] = '20261001T123456.000Z'
    assert all(not k.startswith('time-decks:') for k in c.identity_keys(r))


def test_missing_commands_and_result_fail_closed():
    doc = fixture('raw2')
    doc['payload']['html'] = doc['payload']['html'].replace('data-t="202" data-s="blue"', 'data-t="203" data-s="blue"')
    # Attribute order isn't part of the API; make a definite unmatched timeline.
    doc['payload']['html'] += '<img data-card="rocket" data-t="999" data-s="blue" data-ability="0">'
    with pytest.raises(ValueError): c.parse_page(doc)
    doc = fixture('raw2'); doc['request_url'] = '/replay?tag=FIXTURE_RAW2'
    assert 'result_unavailable' in c.parse_page(doc)['blocks']


def test_visible_forms_are_flagged_not_inferred():
    doc = fixture('raw2')
    r = c.parse_page(doc)
    assert not any(p['evolution_visible'] or p['hero_visible'] for p in r['plays'])
    doc['payload']['html'] = doc['payload']['html'].replace('skeletons', 'skeletons-ev1')
    assert c.parse_page(doc)['plays'][0]['evolution_visible']


def test_csv_is_canonical_once_and_dedupe_uses_only_members(tmp_path):
    inputs = tmp_path/'in'; inputs.mkdir()
    for name in ('raw2','bait'):
        (inputs/(name+'.json')).write_text(json.dumps(fixture(name)))
    (inputs/'duplicate.json').write_text(json.dumps(fixture('raw2')))
    corpus = tmp_path/'corpus'; corpus.mkdir()
    (corpus/'replay_FIXTURE_BAIT.json').write_text('{}')
    summary = c.convert([inputs], tmp_path/'out', [corpus], [])
    assert summary['counts']['input_files'] == 3
    assert summary['counts']['existing_corpus'] == 1
    assert summary['counts']['input_duplicate'] == 1
    assert summary['counts']['new_replays'] == 1
    with (tmp_path/'out/plays_ext.csv').open() as f: rows=list(csv.DictReader(f))
    assert (rows[0]['x_units'], rows[0]['y_units'], rows[0]['attr_i']) == ('8500','22500','0')
    # The existing loader's rotation is now a no-op; ability coordinates stay empty.
    assert rows[-1]['x_units'] == '' and rows[-1]['attr_ability'] == '1'
    with pytest.raises(ValueError): c.convert([inputs], tmp_path/'out', [corpus], [])


def test_deck_categories():
    assert c.deck_type(list(c.ICEBOW)[:5]) == 'icebow-like'
    assert c.deck_type(['x-bow','archers']) == 'other X-Bow'
    assert c.deck_type(['goblin-barrel','dart-goblin']) == 'Log Bait'
    assert c.deck_type(['goblin-barrel']) == 'other'


def test_snapshot_and_existing_fv5_builder_without_sim(tmp_path):
    """Synthetic states verify adapter/schema, never claim SIM runtime fidelity."""
    from pipeline.dataset_gen import replay_rows
    catalog = b.card_catalog()
    deck = ['Skeletons','Knight','Tesla','Xbow','Rocket','Log','Tornado','IceWizard']
    raw = dict(tick=100, entities=[dict(side=0,x=3500,y=10000,name='Skeletons',hp=81,max_hp=81,
                 kind=1,card_id=123,entity_id=7,status_flags=0)],
               players=[dict(side=s,elixir_exact=8,hand=[dict(name=n) for n in deck[:4]],next_deck_index=4) for s in (0,1)],
               episode={'crown_towers':[dict(side=s,type='princess',x=3500,y=6500 if s==0 else 25500,hp=3052,max_hp=3052) for s in (0,1)]},
               projectiles=[], effects=[])
    snap = b.snapshot(raw, catalog)
    assert snap['entities'][0][-2] == catalog['skeletons']['card_id'] != 123
    rec = dict(tag='SCHEMA_TEST',record_native=True,record_full=True,record_every=10,
               recording_origin='royalesim', final_decks={'0':deck,'1':deck},
               expected={'crowns_by_side':{'0':1,'1':0}},
               frames=[dict(snap,tick=t) for t in range(0,201,10)],
               play_frames=[dict(snap,tick=100,play_index=0),dict(snap,tick=180,play_index=1)],
               log=[dict(tick=100,side=0,card='skeletons',x=3500,y=10000,play_index=0,accepted=True,hand_before=deck[:4]),
                    dict(tick=180,side=1,card='knight',x=3500,y=25000,play_index=1,accepted=True,hand_before=deck[:4])])
    p=tmp_path/'replay_SCHEMA_TEST.json';p.write_text(json.dumps(rec))
    rows=replay_rows(str(p),feature_version=5)
    assert 'error' not in rows, rows.get('error')
    assert rows['stats']['play_rows'] == 2 and rows['stats']['wait_rows'] > 0
    assert set(rows['side']) == {0,1}


def test_unknown_forms_block_before_runtime_import(tmp_path):
    result=subprocess.run([sys.executable,str(b.__file__),'--source',str(tmp_path/'missing'),
                           '--out',str(tmp_path/'out')],capture_output=True,text=True)
    assert result.returncode != 0 and 'Pages do not establish deck forms' in result.stderr
    assert not (tmp_path/'out/DONE').exists()


def test_fixtures_are_allowlisted():
    for name in ('raw2','bait'):
        text=(HERE/(name+'.json')).read_text()
        assert not any(s in text for s in ('team_tags','opponent_tags','player','http','referrer','src=','<h5'))
        assert len(text)<6000


def test_row_phase_and_fidelity_report(tmp_path):
    import numpy as np
    path=tmp_path/'rows.npz'
    meta={'decks':[dict(cards=list(c.ICEBOW),rows=4)]}
    np.savez(path, tags=np.array(['A','B']), rep=np.array([0,0,1,1]),
             tick=np.array([2399,2400,4800,6000]),meta=json.dumps(meta))
    path.with_suffix('.json').write_text(json.dumps(meta))
    b.stamp_dataset(path, {'test':'schema-only'})
    report=b.summarize_rows(path, {'A':dict(first_command_divergence_tick=2400,crowns_match=True),
                                  'B':dict(first_command_divergence_tick=None,crowns_match=False)},tmp_path)
    assert report['row_phases']=={'1x':1,'2x':1,'3x':1,'postgame':1}
    assert report['rows_after_command_divergence']==1
    assert report['rows_with_outcome_divergence']==2
    assert report['rows_unit_missing'] is None and report['rows_unit_out_of_place'] is None
    with np.load(path) as z:
        assert json.loads(str(z['pro2_provenance']))['recording_origin']=='royalesim'
    with np.load(tmp_path/'row_fidelity.npz') as z:
        assert z['command_diverged'].tolist()==[False,True,False,False]
        assert not z['body_fidelity_known'].any()
