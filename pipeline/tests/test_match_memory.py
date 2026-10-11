"""Public synthetic frame adapters only: no simulator runtime."""
import copy
import numpy as np
import pytest

from pipeline.match_memory import PublicHistory, PLAY, TOWER_HP, TOWER_DEATH, SPELL_LANDING, ABILITY, COLS
from pipeline.public_observation import PublicObserver, recording_observers
from pipeline.native_recording import tag_native_recording
from pipeline.tests.memory_fixtures import tmp_path
IDS = {('knight', 0): 100, ('knight', 1): 101, ('musketeer', 0): 102, ('poison', 0): 103}
NAMES = {100: ('Knight', 0), 101: ('Knight', 1), 102: ('Musketeer', 0), 103: ('Poison', 0)}

@pytest.fixture(autouse=True)
def synthetic_catalog(monkeypatch):
    # Small catalog fixture only: production detectors/adapters run unmodified.
    from pipeline import public_observation, obs_contract, native_recording, own_ability, projectile_observation, opp_elixir_count
    for module in (public_observation, obs_contract, native_recording, own_ability, projectile_observation, opp_elixir_count):
        if hasattr(module, 'catalog_card_form'):
            monkeypatch.setattr(module, 'catalog_card_form', lambda cid: NAMES.get(cid, (None, 0)))
    monkeypatch.setattr(public_observation, '_native_ids', lambda: IDS)
    monkeypatch.setattr(opp_elixir_count, '_catalog_names', lambda: {k: v[0] for k, v in NAMES.items()})
    monkeypatch.setattr(projectile_observation, 'unavailable_area_timers', lambda: set())

def body(key='knight', eid=1, side=1, form=0):
    return dict(side=side, x=3000, y=25000, hp=1000, max_hp=1000, card_id=IDS[key, form], address=str(eid), category=eid, kind=15)

def spell(key='poison'):
    return dict(side=1, x=3500, y=6500, card_id=IDS[key, 0])

def frame(tick=10, bodies=(), effects=()):
    return dict(game_tick=tick, entities=list(bodies), projectiles=[], effects=list(effects))


def streams():
    readers, natives, sims = [], [], []
    for tick, hp in ((10, 3000), (30, 2000), (60, 0)):
        bodies = [body('knight', 1, side=0, form=1), body('musketeer', 2, side=1)]
        tower = dict(side=1, x=3500, y=25500, hp=hp, max_hp=3000, type='princess')
        effect = spell('poison') if tick >= 30 else None
        r = frame(tick, bodies, effects=[effect] if effect else [])
        # Reader has visible crown-tower entities, not engine episode blocks.
        r['entities'].append(dict(tower, card_id=-1, kind=13, address='tower', category=0))
        readers.append(r)
        native = dict(tick=tick,
            entities=[[e['side'], e['x'], e['y'], name, e['hp'], e['max_hp'], 15, e['card_id'], i]
                      for i, (e, name) in enumerate(zip(bodies, ('Knight', 'Musketeer')))],
            towers=[[1, 'princess', 'L', 3500, 25500, hp, 3000]],
            projectiles=[], area_effects=[[1, 3500, 6500, 'Poison']] if effect else [])
        natives.append(native)
        sims.append(dict(tick=tick, entities=[dict(side=e['side'], x=e['x'], y=e['y'], hp=e['hp'], max_hp=e['max_hp'],
            entity_id=i, name=name, status_flags=8 if e['side']==0 else 0)
            for i, (e, name) in enumerate(zip(bodies, ('Knight', 'Musketeer')))],
            episode=dict(crown_towers=[tower]), effects=[dict(side=1, x=3500, y=6500, name='Poison')] if effect else []))
    rec = tag_native_recording(dict(record_native=True, record_full=True, frames=natives), {})
    return readers, rec, sims


@pytest.mark.parametrize('side', [0, 1])
def test_adapters_identical_public_history(side):
    readers, rec, sims = streams()
    live, sim = PublicObserver(side, history_events=True), PublicObserver(side, history_events=True)
    for r, s in zip(readers, sims):
        live.update(r, source='reader')
        sim.update(s, source='sim')
    dataset = recording_observers(rec, history_events=True)[side]
    gid = {'knight': 1, 'musketeer': 2, 'poison': 3}
    expected = live.history_tokens(61, gid)
    np.testing.assert_array_equal(expected, sim.history_tokens(61, gid))
    np.testing.assert_array_equal(expected, dataset.history_tokens(61, gid))
    assert (expected[:, 0] == PLAY).sum() == 3
    assert (expected[:, 0] == TOWER_HP).sum() == 3
    assert (expected[:, 0] == TOWER_DEATH).sum() == 1
    assert (expected[:, 0] == SPELL_LANDING).sum() == 1
    assert set(expected[expected[:, 0] == PLAY, 1]) == {0, 1}
    assert np.all(np.diff(expected[expected[:, 0] > 0, 6]) >= 0)


def test_cap_causality_duplicates_and_same_tick_boundary():
    h = PublicHistory()
    for tick in range(300):
        h.add(PLAY, tick=tick, side=tick%2, card='knight', x=3000, y=6000)
        h.add(PLAY, tick=tick, side=tick%2, card='knight', x=3000, y=6000)
    t = h.tokens(300, 0, {'knight': 1})
    assert t.shape == (256, len(COLS))
    assert t[0, 6] == pytest.approx(44*.05)
    assert t[-1, 6] == pytest.approx(299*.05)
    assert h.tokens(100, 0, {}, 3)[-1, 6] == pytest.approx(99*.05)
    assert not h.tokens(0, 0, {}).any()
    with pytest.raises(ValueError):
        h.tokens(1, 0, {}, 0)
    a, b = PublicHistory(), PublicHistory()
    for s in (0, 1):
        a.add(PLAY, tick=1, side=s)
        b.add(PLAY, tick=1, side=1-s)
    np.testing.assert_array_equal(a.tokens(2, 0, {}, 1), b.tokens(2, 0, {}, 1))


def test_hidden_mutation_cannot_change_history_and_reset():
    readers, _, _ = streams()
    a, b = [PublicObserver(0, history_events=True) for _ in range(2)]
    for f in readers:
        hidden = dict(copy.deepcopy(f), players=[dict(side=1, hand=['rocket'], next='secret', deck=['zap'], elixir=99)],
                      log=[dict(tick=1, side=1, card='rocket', accepted=True)], final_decks={'1': ['secret']})
        a.update(f, source='reader')
        b.update(hidden, source='reader')
    np.testing.assert_array_equal(a.history_tokens(61, {}), b.history_tokens(61, {}))
    assert all(len(e) == len(COLS) for e in b.history.events)
    assert not {'hand', 'next', 'deck', 'elixir'} & set(COLS)
    with pytest.raises(TypeError):
        a.history.add(PLAY, tick=1, side=1, elixir=3)
    prior = a.history_tokens(11, {})
    assert (prior[:, 0] == TOWER_HP).sum() == 1  # later HP changes absent
    a.update(frame(1), source='reader')
    assert not a.history_tokens(2, {}).any()


def test_only_confirmed_observed_abilities_no_future_or_attempts():
    o = PublicObserver(0, history_events=True)
    o.own_events = [dict(tick=t, side=0, card='knight', ability=True, accepted=ok)
                    for t, ok in ((5, True), (6, False), (100, True))]
    o.update(frame(10), source='reader')
    t = o.history_tokens(11, {'knight': 1})
    assert (t[:, 0] == ABILITY).sum() == 1
    assert t[0, 6] == .25
    assert not o.history_tokens(5, {}).any()


def test_off_observer_has_no_history_and_old_features():
    o = PublicObserver(0)
    o.update(frame(10, [body()]), source='reader')
    assert o.history is None
    assert 'history_events' not in o.features(11, {'knight': 1})


def test_multiword_identity_uses_model_vocabulary():
    h = PublicHistory()
    h.add(PLAY, tick=10, side=1, card='goblin_barrel')
    assert h.tokens(11, 0, {'goblin-barrel': 7})[0, 2] == 7


def test_tower_disappearance_and_unreadable_hp():
    h = PublicHistory()
    tower = dict(side=1, type='princess', x=3500, y=25500, hp=3000, max_hp=3000)
    def frame_hp(t, rows):
        h.frame(dict(tick=t, episode={'crown_towers': rows}), source='sim', tick=t)
    frame_hp(1, [tower])
    frame_hp(2, [dict(tower, hp=-1, max_hp=-1)])
    assert not (h.tokens(3, 0, {})[:, 0] == TOWER_DEATH).any()
    frame_hp(3, [])
    frame_hp(4, [])
    tokens = h.tokens(5, 0, {})
    assert (tokens[:, 0] == TOWER_DEATH).sum() == 1
    assert tokens[tokens[:, 0] == TOWER_HP][-1, 8] == -1


def test_dataset_build_persists_global_vocab_histories(tmp_path, monkeypatch):
    import json
    from pipeline import dataset_gen as D
    from pipeline.tests.test_model_gen import toy
    _, rec, _ = streams()
    observers = recording_observers(rec, history_events=True)
    g = toy(n=4)['gen']
    keys = ['knight', 'musketeer', 'poison', 'rocket', 'goblins', 'giant', 'zap', 'arrows']
    r = dict(path='synthetic', tag='synthetic', keys=keys, stats={}, deck_keys={s:keys for s in (0,1)},
             icebow_sides=[0], history_archive=[o.history for o in observers], actual_plays=[],
             n_tok=np.diff(g['off']), tok=g['tok'], sc=g['sc'], tick=np.array([11, 31, 61, 61]),
             side=np.array([0, 1, 0, 1]), unit_form=np.zeros(len(g['tok']), np.int64),
             past_card=g['past'][...,0].astype(int)-1, past_form=g['past'][...,1], past_xydt=g['past'][...,2:],
             y_gate=g['y_gate'], y_hand_pos=g['y_hand_pos'], y_xy=g['y_xy'], y_wait_dt=np.zeros(4), y_crowns=g['y_crowns'],
             projectiles=np.zeros((4,64,8),np.float32), effects=np.zeros((4,32,6),np.float32), own_ability=np.zeros((4,8,7),np.float32))
    for name in ('hand_card','next_card','deck_card','y_card','y_wait_card'):
        r[name] = g[name]-1
    for name in ('hand_form','next_form','deck_form'):
        r[name] = g[name]
    (tmp_path/'replay_test.json').write_text('{}')
    monkeypatch.setattr(D, '_job', lambda job: r)
    monkeypatch.setattr(D, 'evolution_cycles', lambda: {})  # catalog-only fixture, no engine assets
    out = tmp_path/'history.npz'
    D.build([tmp_path], out, workers=1, feature_version=4, history_events=True, history_cap=4,
            v3val_npz=tmp_path/'absent.npz', log=None)
    with np.load(out) as arrs:
        meta = json.loads(str(arrs['meta']))
        assert meta['history_events'] and meta['history_cap'] == 4
        gid = {k:i for i,k in enumerate(meta['card_vocab'])}
        for i, (tick, side) in enumerate(zip(r['tick'],r['side'])):
            np.testing.assert_array_equal(arrs['history_events'][i], observers[side].history_tokens(tick,gid,4))
