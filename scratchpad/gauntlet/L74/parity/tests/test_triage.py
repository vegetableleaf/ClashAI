"""Synthetic public observations; no engine, live logs, or network."""
from copy import deepcopy
import json

import pytest

from scratchpad.gauntlet.L74.parity.core import ps, Tracks, compare
from scratchpad.gauntlet.L74.parity.inference import repair_injections, public_tracks
from scratchpad.gauntlet.L74.parity.planning import plan
from scratchpad.gauntlet.L74.parity.mechanics import SnapshotReplay
from test_v2 import fixture, FakeBattle

CAT, NAMES = ps.load_catalog()


def body(name, key, x, y, hp, cid=None, side=1):
    return dict(card_id=cid or NAMES[name]['card_id'], key=key, side=side,
                x=x, y=y, hp=hp, max_hp=hp, tower=False)


def source(name, rows, play_rows):
    s = fixture()
    s['frames'] = [dict(tick=t, bodies=b) for t, b in rows]
    s['plays'] = [dict(tick=t, name=name, side=1, card_id=NAMES[name]['card_id'],
                       x=x, y=y, source='first_seen_body_proxy') for t,x,y in play_rows]
    s['decks']['1'] = [dict(name=name, card_id=NAMES[name]['card_id'], form=0, level=15)]
    return s


@pytest.mark.parametrize('name,root_hp,child_hp', [('Tombstone',770,119), ('GoblinHut',1885,212),
                                                ('GoblinGiant',4519,193), ('Witch',1000,100)])
def test_parent_id_child_and_death_spawn_excluded(name, root_hp, child_hp):
    root=body(name,'p',9000,10000,root_hp)
    child=body(name,'c',9500,10500,child_hp)
    s=source(name,[(90,[]),(100,[root]),(110,[root]),(140,[child]),(150,[dict(child,y=12000)])],
             [(100,9000,10000),(140,9500,10500)])
    fixed, receipts=repair_injections(s,CAT)
    assert list(fixed)==[0] and fixed[0]['tick']==95
    assert receipts[1]['reason']=='parent_id_child_body'
    assert fixed[0]['inference']['visibility_tick_interval']==[91,100]
    assert fixed[0]['inference']['deploy_tick_exact'] is False


def test_drill_target_is_surface_but_tick_is_travel_start():
    b=lambda key,x,y,hp:body('GoblinDrill',key,x,y,hp)
    s=source('GoblinDrill',[(90,[]),(100,[b('dig',9000,4000,3720)]),
             (110,[b('dig',9000,7000,3720)]),(160,[b('dig',14000,22000,3720)]),
             (170,[b('hut',15000,25000,1908)]),(180,[b('hut',15000,25000,1908)]),
             (190,[b('gob',15000,26000,293)])],
             [(100,9000,4000),(170,15000,25000),(190,15000,26000)])
    fixed, receipts=repair_injections(s,CAT)
    assert list(fixed)==[0]
    assert (fixed[0]['tick'],fixed[0]['x'],fixed[0]['y'])==(95,15000,25000)
    assert receipts[1]['reason']=='drill_surface_or_child_not_new_deploy'
    assert receipts[2]['reason']=='parent_id_child_body'


def test_drill_emergence_alone_does_not_invent_deploy_time():
    b=body('GoblinDrill','hut',15000,25000,1908)
    s=source('GoblinDrill',[(90,[]),(100,[b]),(110,[b])],[(100,15000,25000)])
    assert not repair_injections(s,CAT)[0]


def test_drill_ambiguous_destinations_are_not_chosen_by_nearest_distance():
    b=lambda key,x,y,hp:body('GoblinDrill',key,x,y,hp)
    surface=[b('s1',14000,25000,1908),b('s2',15000,25000,1908)]
    s=source('GoblinDrill',[(90,[]),(100,[b('d',9000,4000,3720)]),
             (110,[b('d',9000,7000,3720)]),(160,[b('d',14000,22000,3720)]),
             (170,surface),(180,surface)],[(100,9000,4000)])
    assert repair_injections(s,CAT)[1][0]['reason']=='drill_destination_unresolved'


def test_evolved_drill_relocation_does_not_inject_an_extra_card():
    b=lambda key,x,y,hp:body('GoblinDrill',key,x,y,hp,cid=NAMES['GoblinDrill']['evolution_form_id'])
    s=source('GoblinDrill',[(90,[]),(100,[b('d',9000,4000,3720)]),
             (110,[b('d',9000,7000,3720)]),(160,[b('d',14000,22000,3720)]),
             (170,[b('s',15000,25000,1908)]),(180,[b('s',15000,25000,1908)]),
             (190,[b('d2',15000,25000,3720)]),(200,[b('d2',15000,22000,3720)])],
             [(100,9000,4000),(190,15000,25000)])
    fixed, receipts=repair_injections(s,CAT)
    assert list(fixed)==[0] and fixed[0]['observed_form']==1
    assert receipts[1]['reason']=='drill_relocation_not_new_deploy'


@pytest.mark.parametrize('name',['Prince','DarkPrince','RamRider','BattleRam','Miner'])
def test_moving_charger_or_miner_not_restarted_as_fresh_deploy(name):
    b=body(name,'a',4000,14000,3000)
    s=source(name,[(90,[]),(100,[b]),(110,[dict(b,y=15000)])],[(100,4000,14000)])
    assert not repair_injections(s,CAT)[0]


def test_stationary_prince_keeps_position_and_bounded_deploy_interval():
    b=body('Prince','a',4000,14000,3000)
    s=source('Prince',[(90,[]),(100,[b]),(110,[b])],[(100,4000,14000)])
    fixed,_=repair_injections(s,CAT)
    assert fixed[0]['tick']==95 and fixed[0]['y']==14000
    assert not fixed[0]['inference']['initial_state_exact']


@pytest.mark.parametrize('form',[0,1,2])
def test_per_sighting_form_is_not_match_maximum(form):
    c=NAMES['Valkyrie']; cid=c[('card_id','evolution_form_id','hero_form_id')[form]]
    b=body('Valkyrie','a',4000,14000,3000,cid=cid)
    s=source('Valkyrie',[(90,[]),(100,[b]),(110,[b])],[(100,4000,14000)])
    s['decks']['1'][0]['form']=2
    fixed,_=repair_injections(s,CAT)
    assert fixed[0]['observed_form']==form


def test_distinct_id_spawn_near_parent_and_opposite_side_control():
    child=body('Skeletons','s',9000,11000,100)
    parent=body('Tombstone','p',9000,10000,770)
    s=source('Skeletons',[(90,[parent]),(100,[parent,child]),(110,[child])],[(100,9000,11000)])
    assert repair_injections(s,CAT)[1][0]['reason']=='spawn_or_play_ambiguous_near_parent'
    parent['side']=0
    assert list(repair_injections(s,CAT)[0])==[0]


def test_recycled_identity_gap_opening_and_unknown_body_fail_closed():
    b=body('Prince','a',4000,14000,3000)
    s=source('Prince',[(100,[b]),(110,[b]),(200,[b]),(210,[b])],[(100,4000,14000),(200,4000,14000)])
    assert len(public_tracks(s,CAT))==2
    assert not repair_injections(s,CAT)[0]
    s['plays'][0]['x']=6000
    assert repair_injections(s,CAT)[1][0]['reason']=='proxy_body_not_uniquely_identified'


def test_default_off_immutable_source_and_chronological_replan():
    s=fixture(); original=deepcopy(s)
    assert plan(s,True)==plan(s,True,False)
    with pytest.raises(ValueError,match='require_mechanics'):
        plan(s,False,True)
    fixed=plan(s,True,True)
    assert s==original
    assert all(a['side']==0 for a in fixed['actions'])  # no visible enemy bodies in fixture
    assert fixed['counts']['plays_used']+sum(r['kind']=='play' for r in fixed['skips'])==len(s['plays'])


def test_form_sync_edits_only_injected_card_and_preserves_combat():
    b=FakeBattle();b.reset(1,[[0],[0]],0,0,None,None,[])
    b.s['players'][1].update(evo=[dict(card=100,form=200,plays=0,cycles=2),
                                      dict(card=101,form=201,plays=1,cycles=2)], heroes=[100,102])
    adapter=object.__new__(SnapshotReplay)
    adapter.battle=b;adapter.internal={'Knight':100}
    adapter.form_templates={('Knight',1):[dict(card=100,form=200,plays=0,cycles=2)],('Knight',0):[]}
    adapter.sync(1,['Knight',None,None,None],[],True,('Knight',1))
    player=json.loads(b.save())['players'][1]
    assert player['evo'][-1]['plays']==2 and player['evo'][0]['card']==101
    assert player['heroes']==[102]
    adapter.sync(1,['Knight',None,None,None],[],True,('Knight',0))
    assert all(e['card']!=100 for e in b.s['players'][1]['evo'])
    assert b.s['entities']==['combat-preserved'] and b.s['projectiles']==['preserved']


def test_role_match_does_not_pair_giant_with_rider_when_spawn_order_differs():
    cid=NAMES['GoblinGiant']['card_id']
    parent=body('GoblinGiant','p',5000,10000,4519)
    child=body('GoblinGiant','c',4000,10000,193)
    live,sim=Tracks({(cid,1):('GoblinGiant',4519)}),Tracks({(cid,1):('GoblinGiant',4519)})
    live.assign(100,[parent]);sim.assign(100,[child])
    rows=compare(live.assign(110,[parent,child]),sim.assign(110,[parent,child]))
    assert all(r['hp_error']==0 and r['position_error_tiles']==0 for r in rows)


def test_age_buckets_boundaries_and_missing_is_not_zero_hp():
    from scratchpad.gauntlet.L74.parity.triage_analysis import age_bin, time_bin, Aggregate
    assert [age_bin(t) for t in (0,39,40,99,100,200,201)]==[
        '0-2 s','0-2 s','2-5 s','2-5 s','5-10 s','5-10 s','>10 s']
    assert time_bin(600)=='30-60 s' and time_bin(3600)=='180+ s'
    a=Aggregate()
    a.add(dict(tower=False,missing='sim',position_error_tiles=None,hp_error=None))
    a.add(dict(tower=False,missing=None,position_error_tiles=2,hp_error=100))
    assert a.report()['hp_mae']==100 and a.report()['matched']==1 and a.report()['missing_sim']==1
