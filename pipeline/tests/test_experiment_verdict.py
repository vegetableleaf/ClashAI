"""Negative controls for diagnostic evidence and deployment nomination."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.eval_expert_context import metrics
from scratchpad.gauntlet.L71.context_teaching.score_experiments import heldout_gates, nominate, ARMS
from scratchpad.gauntlet.L71.context_teaching.verify_predictions import recount, verify_report, FAMILIES

ROOT=Path(__file__).resolve().parents[2]


def test_unchanged_baseline_cannot_pass_any_new_learning_component():
    base=json.loads((ROOT/'icebow/data/bench/expert_context_20261005/r1e_heldout/report.json').read_text())
    reports={n:copy.deepcopy(base) for n in ['r1e']+[n for n,_,_ in ARMS]}
    gates=heldout_gates('v6_rocket_both',reports)
    for key in ('spawner_action_improves','rocket_recall_improves','finishing_rocket_observed',
                'combo_rocket_improves','combo_tornado_improves','xbow_action_improves','barrel_correct_fires_improve'):
        assert gates[key] is False
    reports['v6_rocket_both']['contexts']['night_witch']['action_agreement']['rate']-=.03
    assert not heldout_gates('v6_rocket_both',reports)['night_witch_within_two_pp']


def test_partial_control_only_and_failed_runs_never_nominate():
    verdicts={n:dict(passes=True) for n,_,_ in ARMS}
    games={n:dict(ghost=dict(wins=280),reactive=dict(wins=30)) for n,_,_ in ARMS}
    assert nominate(verdicts,games,False) is None
    assert nominate({'v4_uniform':dict(passes=True)},games,True) is None
    assert nominate({n:dict(passes=False) for n in verdicts},games,True) is None
    assert nominate(verdicts,games,True)=='v6_rocket_both'
    assert nominate({n:verdicts[n] for n in ('v5_rocket_barrel','v6_rocket_barrel')},games,True)=='v5_rocket_barrel'


def fixture():
    cv=['<pad>','the-log','rocket','tornado','goblin-barrel']
    n=4
    sub=dict(y_gate=np.array([1,1,0,1]),y_card=np.array([1,1,0,2]),
        y_xy=np.array([[.8,.8],[.8,.8],[-1,-1],[.5,.5]]),
        hand_card=np.array([[1,2]]*n),projectiles=np.zeros((n,2,8)),
        sc=np.zeros((n,4)),off=np.zeros(n+1,np.int64),tok=np.empty((0,3)))
    sub['sc'][:,3]=1
    sub['sc'][2,3]=0
    sub['projectiles'][:2,0]=[4,1,.5,.4,.8,.8,1,1]
    p=dict(allowed=np.array([[True,True]]*n),gate=np.array([.9,.9,.9,.9]),
        chosen_card=np.array([1,1,1,2]),expert_cell=np.array([51*36+29,51*36+7,0,32*36+18]),
        log_cell=np.array([51*36+29,51*36+7,0,0]))
    p['allowed'][2]=False
    c={k:np.zeros(n,bool) for k in ('finish','combo','xbow','xbow_no_lifetime_target')}
    c['finish'][3]=True
    return sub,c,cv,p


def test_recount_detects_metric_and_legality_corruption():
    sub,c,cv,p=fixture()
    expected=recount(sub,c,cv,p)
    actual=metrics(sub,c,cv,p,{k:np.zeros(4,bool) for k in FAMILIES})
    verify_report(actual,expected)
    assert expected['barrel']['gated_wrong_lane']['n']==1
    assert expected['rocket_finish']['n']==1
    actual['barrel']['gated_wrong_lane']['n']=0
    with pytest.raises(ValueError,match='metric mismatch'):
        verify_report(actual,expected)
    p['chosen_card'][0]=3
    with pytest.raises(ValueError,match='absent or unaffordable'):
        recount(sub,c,cv,p)
    sub,c,cv,p=fixture()
    p['allowed'][2]=True
    with pytest.raises(ValueError,match='affordability'):
        recount(sub,c,cv,p)
