import copy
import json
from pathlib import Path
import numpy as np
from pipeline.public_outcomes import label_recording, summarize
from pipeline.own_ability import observe


def fixture():
    frames=[]
    for t in range(95,126):
        frames.append(dict(tick=t,towers=[dict(side=1,kind='princess',x=3500,y=25500,hp=300 if t<120 else 0)],
            bodies=[dict(side=1,id=1,card='knight',x=3500,y=25500,hp=100 if t<120 else 10)],
            projectiles=[dict(card='rocket',side=0,x=3500,y=25500,tx=3500,ty=25500)] if 101<=t<120 else [],
            areas=[dict(card='rocket',side=0,x=3500,y=25500)] if t==120 else []))
    log=[dict(tick=100,side=0,card='Rocket',x=3500,y=25500,accepted=True),
         dict(tick=115,side=0,card='Tornado',x=3500,y=25500,accepted=True)]
    return dict(tag='fixture',frames=frames,log=log)


def test_recorded_outcomes_and_both_combo_orders():
    rec=fixture();r=label_recording(rec,normalized=True)['rockets'][0]
    assert r['tower_rocket'] and r['defensive_rocket'] and r['tower_hits'][0]['finish']
    assert r['rocket_then_tornado'] and not r['tornado_then_rocket']
    rec['log'][1]['tick']=98
    r=label_recording(rec,normalized=True)['rockets'][0]
    assert not r['rocket_then_tornado'] and r['tornado_then_rocket']
    # R2b: geometry labels are independent of HP confirmation, including K=4.
    for f in rec['frames']: f['towers'][0]['hp']=300
    row=label_recording(rec,normalized=True)['rockets'][0]
    assert row['tower_rocket'] and not row['tower_hits'][0]['hp_confirmed']
    rec['frames']=[f for f in rec['frames'] if f['tick']%4==0]
    assert label_recording(rec,normalized=True)['rockets'][0]['tower_rocket']


def test_own_ability_never_reads_opposing_internals():
    e=dict(side=0,card_id=999,name='MiniPekka',status_flags=16,hp=100,ability_available=True)
    frame=dict(entities=[e,dict(e,side=1)])
    a=observe(frame,0,'sim'); frame['entities'][1].update(ability_available='secret',charges=999)
    assert observe(frame,0,'sim')==a
    assert a and a[0][-2:]==(-1.,0.)


def test_telemetry_off_matches_legacy_engine_and_outputs():
    from pipeline.tests.test_gen_v31_legacy import head
    from pipeline.tests.gen_v3.test_sim_integration import policy,NAMES
    from pipeline.tests.test_rl_gen import _cfg
    from pipeline import e1_eval as E, royale_env as RE
    from pipeline.tests.test_royale_forms import digest
    spec=dict(tag='telemetry-parity',learner_side=0,learner_deck=NAMES,opp_deck=NAMES,seed=3,opp={'id':'old'})
    outputs=[]
    for mod,env in ((head('e1_eval'),head('royale_env')),(E,RE)):
        m=mod.SelfPlayMatch(env.RoyaleSelfPlayEnv(forms_mode='deck',tail_cap=200),spec,0,
            _cfg(record=False,entry_index=0),_cfg(record=False,entry_index=0),policy(1),policy(1))
        while True:
            ds=m.due()
            if not ds:break
            for s in ds:s.prepare();s.apply(.1,dict(play=False,slot=-1,cell=-1,why='test'))
        r=m.result();r.pop('wall_s')
        outputs.append((json.dumps(r),m.env.core.save_state()))
    assert outputs[0]==outputs[1]


def test_telemetry_records_sim_without_private_fields_and_forks():
    from pipeline.tests.gen_v3.test_sim_integration import match,policy
    from pipeline.search_s0 import fork_into
    from pipeline.royale_env import RoyaleSelfPlayEnv
    m=match(policy(1),behaviour_telemetry=True,entry_index=0)
    m.env.advance_to(120)
    collector=m.env.behaviour_telemetry
    assert len(collector.frames)>=30
    assert all(set(f)=={'tick','towers','bodies','projectiles','areas'} for f in collector.frames)
    result=m.result();assert 'behaviour' in result
    fork=fork_into(m,RoyaleSelfPlayEnv(),m.env.core.save_state())
    assert fork.env.behaviour_telemetry is None and m.env.behaviour_telemetry is collector


def test_native_public_effects_and_causal_motion_K1234():
    from pipeline.projectile_observation import objects
    from pipeline.projectile_motion import ProjectileMotion
    for gap in (1,2,3,4,10):
        motion=ProjectileMotion(catalog_fallback=True);frames=[]
        for t in (10,10+gap):
            frames.append(dict(tick=t,public_objects=dict(projectiles=[dict(card_id=28000003,side=0,x=t*100,y=0,target_x=5000,target_y=0)],
                area_effects=[dict(card_id=28000012,side=0,x=2000,y=3000,source_remaining_ms=450)])))
        first=motion.update(objects(frames[0],source='native'),10)
        second=motion.update(objects(frames[1],source='native'),10+gap)
        assert first['projectiles'][0][-1]>0 and second['projectiles'][0][-1]>0
        assert second['effects'][0][-1]==450


def test_own_charges_cooldown_and_future_press_privacy():
    from pipeline.own_ability import tokens
    rows=[('boss-bandit',0,1,-1.,0.)];gid={'boss-bandit':1}
    events=[dict(tick=0,card='BossBandit',accepted=True),dict(tick=40,card='BossBandit',accepted=True,ability=True)]
    at=tokens(rows,gid,events,41)[0]
    assert at[3:6].tolist()==[0.,1.,1.] and at[6]>0
    assert tokens(rows,gid,events,101)[0,3]==1
    events.append(dict(tick=120,card='BossBandit',accepted=True,ability=True))
    assert tokens(rows,gid,events,101)[0,3]==1
    assert tokens(rows,gid,events,121)[0,5]==0
    assert tokens(rows,gid,[],101)[0,4]==0


def test_telemetry_on_does_not_change_sim_state_with_deployments():
    from pipeline.tests.gen_v3.test_sim_integration import match,policy
    states=[]
    for enabled in (False,True):
        m=match(policy(1),behaviour_telemetry=enabled,entry_index=0)
        for side in (0,1):
            st=m.env.core.state().players[side]
            idx=m.env.deck_ids[side].index(st.hand[0])
            m.env.eng.act(side=side,deck_index=idx,x=9000,y=9000 if side==0 else 23000)
        m.env.advance_to(300)
        states.append(m.env.core.save_state())
        if enabled:assert m.env.behaviour_telemetry.plays
    assert states[0]==states[1]
