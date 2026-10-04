import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scratchpad/gauntlet/L70/gen_v31'))
from mine_rocket_tornado import mine, summarize, troops


def sample():
    rocket = dict(side=0, card='rocket', tick=100, engine_tick=100, play_index=1,
                  x=3500, y=12000, accepted=True)
    nado = dict(rocket, card='tornado', play_index=2, tick=120, engine_tick=120)
    entity = [1, 3500, 12000, 'Knight', 1000, 1000, 26000000, 99]
    frames = [dict(tick=100, entities=[entity], projectiles=[]),
              dict(tick=120, entities=[entity], projectiles=[[0, 3500, 10000, 3500, 12000, 'Rocket']]),
              dict(tick=140, entities=[list(entity)], projectiles=[])]
    frames[-1]['entities'][0][4] = 500
    rec = dict(tag='t', record_native=True, frames=frames, log=[rocket, nado])
    old = [dict(play_index=1, targets=[], phase='single', own_elixir_before=9)]
    values = {26000000:dict(card='Knight', kind='troop', nominal_base_cost_per_body=3)}
    return rec, old, values


def test_rocket_then_tornado_requires_exact_flight_and_retains_damage_unknown():
    rec, old, values = sample(); rows, n = mine(rec, old, values)
    r = rows[0]; c = r['combos'][0]
    assert n == 1 and c['order'] == 'rocket_then_tornado'
    assert c['exact_observed_rocket_in_flight_at_tornado'] is True
    assert c['cast_window_prior'] and c['cast_gap_s'] == 1
    assert c['disappearance_gap_after_tornado_s'] == [0, 1]
    assert r['target_half'] == 'own' and r['compatible_hp_changes'][0]['hp_drop'] == 500
    assert r['confirmed_troop_hits'] is None and r['elixir_value_hit'] is None


def test_tornado_then_rocket_is_distinct_and_landing_not_invented():
    rec, old, values = sample(); rec['log'][1].update(tick=80, engine_tick=80, play_index=0)
    r = mine(rec, old, values)[0][0]; c = r['combos'][0]
    assert c['order'] == 'tornado_then_rocket' and c['cast_gap_s'] == 1
    assert not c['exact_observed_rocket_in_flight_at_tornado']
    assert c['disappearance_gap_after_tornado_s'] == [2, 3]
    assert summarize([r])['orders']['tornado_then_rocket']['disappearance_bracket_upper_within_2_5s'] == 0


def test_opponent_tornado_and_distant_or_old_pairs_do_not_pass_prior():
    rec, old, values = sample()
    rec['log'] += [dict(rec['log'][1], side=1, play_index=3),
                   dict(rec['log'][1], x=18000, play_index=4),
                   dict(rec['log'][1], tick=201, engine_tick=201, play_index=5)]
    rows, n = mine(rec, old, values)
    assert n == 4 and len(rows[0]['combos']) == 2
    assert sum(c['cast_window_prior'] for c in rows[0]['combos']) == 1


def test_opponent_hidden_mutations_leave_all_public_evidence_identical():
    rec, old, values = sample(); expected = mine(rec, old, values)
    for f in rec['frames']:
        f['players'] = [dict(side=1, hand=['private'], elixir=1234, next='private')]
    rec['decks'] = {'1':['private']*8}
    assert mine(rec, old, values) == expected


def test_missing_and_ambiguous_flight_cannot_be_claimed_exact():
    rec, old, values = sample(); rec['frames'][1]['projectiles'] *= 2
    assert not mine(rec, old, values)[0][0]['combos'][0]['exact_observed_rocket_in_flight_at_tornado']
    rec, old, values = sample(); rec['frames'][0]['projectiles'] = rec['frames'][1]['projectiles']
    assert mine(rec, old, values)[0][0]['flight_ambiguous']
    rec, old, values = sample()
    for f in rec['frames']:
        f.pop('projectiles')
    r = mine(rec, old, values)[0][0]
    assert r['last_flight_tick'] is None and r['enemy_units_last_flight'] is None


def test_nominal_body_cost_does_not_multiply_full_squad_cost_or_infer_hits():
    rec, old, values = sample()
    values[26000000]['nominal_base_cost_per_body'] = 1/3
    f = rec['frames'][0]; f['entities'].append(list(f['entities'][0])); f['entities'][-1][-1] = 100
    out = troops(f, 0, 3500, 12000, values)
    assert sum(u['nominal_base_cost_per_body'] for u in out) == 2/3
    assert troops(None, 0, 3500, 12000, values) is None
    assert troops(f, 0, 3500, 12000, {})[0]['nominal_base_cost_per_body'] is None


def test_prior_boundary_and_both_orders_are_counted_separately():
    rec, old, values = sample(); rec['log'][1].update(tick=150, engine_tick=150)
    rec['log'].append(dict(rec['log'][1], tick=50, engine_tick=50, play_index=0))
    rows, _ = mine(rec, old, values); summary = summarize(rows)
    assert summary['orders']['rocket_then_tornado']['cast_window_prior_rate']['count'] == 1
    assert summary['orders']['tornado_then_rocket']['cast_window_prior_rate']['count'] == 1
    assert summary['orders']['rocket_then_tornado']['sensitivity']['1']['0.11'] == 0


def test_policy_prior_matches_both_directions_and_accepted_time():
    from rocket_tornado_baselines import vector, metrics
    row = dict(end_tick=3600, plays=[
        dict(card='tornado', cell=100, tick=0, land_tick=50, accepted=True),
        dict(card='rocket', cell=100, tick=50, land_tick=100, accepted=True),
        dict(card='tornado', cell=100, tick=100, land_tick=150, accepted=True),
        dict(card='rocket', cell=100, tick=50, land_tick=100, accepted=False)])
    for grid in ('floor', 'lattice'):
        v = vector(row, grid)
        assert v.tolist() == [3, 3, 1, 1, 1]
        assert metrics(v[None]).tolist() == [1, 100/3, 100, 100]
