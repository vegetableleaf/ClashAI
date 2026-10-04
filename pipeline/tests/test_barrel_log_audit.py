import copy
import importlib.util
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[2]/'scratchpad/gauntlet/L70/gen_v31/mine_barrel_logs.py'
spec=importlib.util.spec_from_file_location('barrel_audit',path)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


def sample():
    barrel=dict(play_index=0,tick=10,side=1,card='goblin-barrel',accepted=True,x=3000,y=5000)
    log=dict(play_index=1,tick=20,side=0,card='the-log',accepted=True)
    q=[1,8000,15000,3000,5000,'GoblinBarrel']
    return dict(tag='a',log=[barrel,log],frames=[dict(tick=10,projectiles=[]),dict(tick=20,projectiles=[q])])


def test_same_tick_flight_is_a_lower_bound_not_a_landing_claim():
    r=M.mine(sample());assert r['counts']['certain_in_flight']==1
    a=M.aggregate([r]);assert a['descriptive_bounds']==[1,1]
    assert a['full_metric_value'] is None
    assert a['bound_endpoint_ci95'] is None


def test_missing_frame_and_skeleton_evidence_stay_unknown():
    r=sample();r['log'][1]['tick']=21
    assert M.mine(r)['counts']['certain_in_flight']==0
    assert M.aggregate([M.mine(r)])['descriptive_bounds']==[0,1]
    r['log'][0]['card']='skeleton-barrel'
    assert M.mine(r)['counts']['skeleton_barrels']==1
    assert M.mine(r)['counts']['certain_in_flight']==0


def test_overlap_and_unknown_opening_are_not_unique_attribution():
    for variant in ('overlap','opening','casts'):
        r=sample()
        if variant=='overlap':r['frames'][1]['projectiles']*=2
        elif variant=='opening':r['frames']=r['frames'][1:]
        else:r['log'].insert(1,dict(r['log'][0],tick=11,play_index=2))
        assert M.mine(r)['counts']['certain_in_flight']==0


def test_new_same_target_cast_censors_anonymous_continuous_presence():
    r=sample();r['log'][1]['tick']=30
    r['log'].append(dict(r['log'][0],tick=25,play_index=2))
    r['frames'].append(dict(r['frames'][1],tick=30))
    assert M.mine(r)['counts']['certain_in_flight']==0


def test_only_opposite_side_accepted_logs_count_and_private_fields_do_not():
    r=sample();expected=M.mine(r)
    r['players']=[dict(hand=['private'],elixir=1000)]
    for f in r['frames']:f['elixir']=[999,999]
    assert M.mine(r)==expected
    r['log'][1]['side']=1
    assert M.aggregate([M.mine(r)])['descriptive_bounds']==[0,0]
    r=sample();r['log'][1]['accepted']=False
    assert M.mine(r)['counts']['possible_full_metric']==0


def test_empty_denominators_and_conflicting_duplicate_frames_fail_honestly():
    assert M.aggregate([])['descriptive_bounds'] is None
    r=sample();r['frames'].append(copy.deepcopy(r['frames'][0]))
    r['frames'][-1]['projectiles']=[[1,8000,15000,3000,5000,'GoblinBarrel']]
    with pytest.raises(ValueError,match='Conflicting duplicate'):M.mine(r)


def test_identical_duplicate_frames_are_collapsed_without_double_counting():
    r=sample();before=M.mine(r)
    r['frames']+=copy.deepcopy(r['frames'])
    after=M.mine(r)
    assert after['barrels']==before['barrels']
    assert after['counts']['duplicate_equivalent_projectile_frames']==2
    assert after['counts']['certain_in_flight']==before['counts']['certain_in_flight']==1


def test_elixir_or_other_irrelevant_changes_cannot_change_projectile_duplicate_handling():
    r=sample();r['frames']+=copy.deepcopy(r['frames'])
    before=M.mine(r)
    r['frames'][-1]['elixir']=[3,8]
    r['frames'][-1]['players']=[dict(hand=['hidden'],next='hidden')]
    assert M.mine(r)==before
