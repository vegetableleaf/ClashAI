import copy
import importlib.util
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]


def module(name):
    path=ROOT/'scratchpad/gauntlet/L70/gen_v31'/f'{name}.py'
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def recording():
    def frame(t,hp,projectiles=()):
        return dict(tick=t,elixir=[9.,1.],projectiles=list(projectiles),towers=[
            [0,'king',None,9000,3000,4824,4824], [0,'princess','left',3500,6500,3000,3052],
            [1,'king',None,9000,29000,4824,4824],[1,'princess','left',3500,25500,hp,3052]])
    return dict(tag='test',log=[dict(play_index=i,tick=t,side=0,card='rocket',accepted=True,x=3500,y=25500)
                               for i,t in enumerate((100,900))],frames=[frame(100,1800),
        frame(120,1800,[[0,4000,23000,3500,25500,'Rocket']]),frame(140,1303),frame(900,1303)],
        final=dict(tick=6100,terminated=True,termination_reason='native_logic_clock_stopped'))


def test_multi_rocket_above_one_shot_hp_and_attribution_unknown():
    rows,counts=module('mine_rockets').mine(recording())
    assert counts['accepted_rockets']==2
    assert all(r['targets'] and not r['targets'][0]['one_rocket_hp_context'] for r in rows)
    assert rows[1]['targets'][0]['prior_rocket_candidates']==1
    assert rows[1]['targets'][0]['gap_s']==40
    assert rows[0]['targets'][0]['hp_drop_around_flight']==497
    assert rows[0]['crown_tower_hit'] is None and rows[0]['tiebreaker'] is None


def test_private_opponent_state_cannot_change_mined_context():
    mod=module('mine_rockets');rec=recording();want=mod.mine(rec)
    for f in rec['frames']:
        f['elixir'][1]=999
        f['players']=[dict(side=1,hand=['secret'],next=999,deck_form_flags=[2]*8)]
    rec['final_decks']={'1':['secret']*8}
    assert mod.mine(rec)==want


def test_no_geometry_or_tiebreak_invented_when_evidence_missing():
    mod=module('mine_rockets');rec=recording();rec['frames']=[]
    r,_=mod.mine(rec)
    assert r[0]['targets']==[] and r[0]['own_elixir_before'] is None
    rec['final']['termination_reason']='tiebreaker'
    assert mod.mine(rec)[0][0]['tiebreaker'] is True


def test_baseline_ratio_is_play_weighted_and_zero_missing_not_invented():
    mod=module('behavior_baselines')
    v=np.array([[1,10,1],[0,90,9]],float)
    np.testing.assert_array_equal(mod.metrics(v),[1,10])
    assert len(mod.MISSING)==11


def test_timing_estimate_uses_past_motion_and_scores_only_afterwards():
    mod=module('timing_feasibility')
    a=[1,0,0,0,100,'Rocket'];b=[1,0,50,0,100,'Rocket']
    assert mod.estimate(a,b,10)==10
    assert mod.estimate(b,a,10) is None
    rec=dict(tag='t',frames=[dict(tick=0,projectiles=[a]),dict(tick=10,projectiles=[b])])
    expected=mod.evaluate(rec)[0]['estimates']
    assert 'outside_interval_error_s' not in expected[0]
    rec['frames'].append(dict(tick=20,projectiles=[]))
    scored=mod.evaluate(rec)[0]['estimates'][0]
    assert scored['predicted_end_tick']==expected[0]['predicted_end_tick']==20
    assert scored['outside_interval_error_s']==0
