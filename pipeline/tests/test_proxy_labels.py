import importlib.util
from pathlib import Path
import sys
import pytest

path=Path(__file__).resolve().parents[2]/'scratchpad/gauntlet/L70/gen_v31/proxy_labels.py'
sys.path.insert(0,str(path.parent))
spec=importlib.util.spec_from_file_location('proxy_labels',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def pair():
    tower=dict(tag='a',play_index=1,side=0,tick=10,targets=[dict(hp_drop_around_flight=0,distance_tiles=3)])
    troop=dict(tag='a',play_index=1,enemy_units_last_flight=[{}],last_flight_tick=11,flight_ambiguous=False,target_half='own',combos=[],compatible_hp_changes=[])
    return tower,troop


def test_proxies_do_not_become_causal_truth_or_zero_missing():
    a,b=pair();r=m.rocket_label(a,b)
    assert r['proxy_defensive_rocket'] and r['proxy_tower_rocket']
    assert r['audit_tower_all_observed_nonpositive'] and r['audit_tower_edge_only']
    assert r['causal_tower_hit'] is None and r['actual_elixir_value_hit'] is None
    b['flight_ambiguous']=True
    assert m.rocket_label(a,b)['proxy_troop_rocket'] is None
    a['targets'][0]['hp_drop_around_flight']=None
    assert not m.rocket_label(a,b)['audit_tower_hp_change_observed']


def test_combo_orders_are_separate_and_event_ids_checked():
    a,b=pair();b['combos']=[dict(order='rocket_then_tornado',cast_window_prior=True)]
    r=m.rocket_label(a,b)
    assert r['proxy_rocket_then_tornado'] and not r['proxy_tornado_then_rocket']
    b['tag']='wrong'
    with pytest.raises(ValueError):m.rocket_label(a,b)


def test_missing_flight_is_unknown_not_a_negative_troop_label():
    a,b=pair();b['last_flight_tick']=None;b['enemy_units_last_flight']=[]
    r=m.rocket_label(a,b)
    assert r['proxy_troop_rocket'] is None and r['proxy_defensive_rocket'] is None
