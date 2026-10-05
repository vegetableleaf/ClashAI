import copy
import numpy as np
import pytest

from pipeline.eval_expert_context import metrics
from scratchpad.gauntlet.L71.decision_options.score_q3 import validate


def test_forced_aim_is_separate_from_fired_wrong_lane_and_wait():
    cv=['<pad>','the-log','rocket','tornado','goblin-barrel']
    n=4
    sub=dict(y_gate=np.array([1,1,0,1]),y_card=np.array([1,1,0,2]),
        y_xy=np.array([[.8,.8],[.8,.8],[-1,-1],[.5,.5]]),
        hand_card=np.array([[1,2]]*n),projectiles=np.zeros((n,2,8)))
    sub['projectiles'][:2,0]=[4,1,.5,.4,.8,.8,1,1]
    p=dict(allowed=np.array([[True,True]]*n),gate=np.array([.9,.9,.9,.9]),
        chosen_card=np.array([1,1,1,2]),expert_cell=np.array([51*36+29,51*36+7,0,32*36+18]),
        log_cell=np.array([51*36+29,51*36+7,0,0]))
    p['allowed'][2]=False
    c={k:np.zeros(n,bool) for k in ('finish','combo','xbow','xbow_no_lifetime_target')}
    c['finish'][3]=True
    result=metrics(sub,c,cv,p,dict(night_witch=np.ones(n,bool)))
    assert result['barrel']['pro_same_lane_rows']==2
    assert result['barrel']['gated_correct_lane']['n']==1
    assert result['barrel']['gated_wrong_lane']['n']==1
    assert result['rocket_finish']==dict(n=1,denominator=1,rate=1)
    assert result['global_action_agreement']['n']==3  # correct WAIT despite high gate when nothing is affordable.
    p['chosen_card'][1]=2
    result=metrics(sub,c,cv,p,dict(night_witch=np.ones(n,bool)))
    assert result['barrel']['forced_log_same_lane']['n']==1
    assert result['barrel']['gated_wrong_lane']['n']==0


def ghost():
    return dict(tag='one',k=0,outcome='win',end_tick=100,terminated=True,termination_reason='game_over',
        action_delay_ticks=26,extrapolate_ticks=26,forms_mode='deck',plays_accepted=3,
        behaviour=dict(schema='public_behaviour_v1',accepted_plays=3,
            rocket_share=dict(n=2,denominator=3),tower_rocket_share=dict(n=1,denominator=1),unknown_rocket_impacts=1))


def test_q3_unknown_impact_is_not_counted_as_known_tower_miss():
    validate([ghost()],{('one',0)})
    bad=ghost();bad['behaviour']['unknown_rocket_impacts']=0
    with pytest.raises(ValueError,match='denominators'):
        validate([bad],{('one',0)})


def test_q3_duplicate_missing_and_truncated_games_are_rejected():
    with pytest.raises(ValueError,match='Duplicate'):
        validate([ghost(),ghost()],{('one',0)})
    with pytest.raises(ValueError,match='Incomplete'):
        validate([],{('one',0)})
    bad=ghost();bad['terminated']=False
    with pytest.raises(ValueError,match='termination'):
        validate([bad],{('one',0)})
