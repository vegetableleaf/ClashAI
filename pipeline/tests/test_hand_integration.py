"""Mirror slot inference operates on plays, never raw duplicate bodies."""
import copy
import numpy as np

from pipeline.opponent_hand_v2 import belief_at,belief_tokens,normalize_public_plays


def events(cards):
    return [dict(tick=(i+1)*20,side=1,card=c,event_id=str(i)) for i,c in enumerate(cards)]


def test_consecutive_actual_plays_identify_mirror():
    x=events(['HogRider','HogRider'])
    normalized,n=normalize_public_plays(x,50,0)
    assert n==1 and [e['card'] for e in normalized]==['hog-rider','mirror']
    assert normalized[-1]['copied_card']=='hog-rider'
    b=belief_at(x,50,0)
    assert b['revealed']==['hog-rider','mirror'] and not b['issues']
    assert b['plays_to_return']=={'hog-rider':[3,3],'mirror':[4,4]}
    assert b['inferred_mirror_plays']==1 and not b['certified']


def test_explicit_mirror_and_forms():
    n,count=normalize_public_plays(events(['Knight@evolution','Mirror']),50,0)
    assert count==0 and [e['card'] for e in n]==['knight','mirror']
    n,count=normalize_public_plays(events(['Knight@evolution','Knight']),50,0)
    assert count==1 and n[-1]['card']=='mirror'


def test_ability_own_play_and_rejected_play_do_not_rotate():
    x=events(['HogRider','HogRider'])
    x += [dict(tick=30,side=1,card='Knight',ability=True),dict(tick=32,side=0,card='Rocket'),
          dict(tick=34,side=1,card='Zap',accepted=False)]
    assert belief_at(x,50,0)==belief_at(events(['HogRider','HogRider']),50,0)


def test_duplicate_retransmission_is_not_mirror():
    x=events(['HogRider'])
    assert belief_at(x+x,50,0)==belief_at(x,50,0)
    assert belief_at(x+x,50,0)['inferred_mirror_plays']==0


def test_triple_repeat_abstains_instead_of_replaying_queued_mirror():
    b=belief_at(events(['HogRider']*3),70,0)
    assert b['inferred_mirror_plays']==1
    assert b['issues'] and not b['in_hand'] and not b['out_of_hand']


def test_known_eight_card_deck_cannot_gain_mirror():
    cards=['Knight','Rocket','Log','Tesla','Skeletons','Tornado','IceWizard','Xbow','Xbow']
    b=belief_at(events(cards),200,0)
    assert 'mirror' not in b['revealed'] and b['inferred_mirror_plays']==0
    assert b['issues'] and not b['full_hand']


def test_ties_gaps_and_unsupported_rules_do_not_infer_mirror():
    x=events(['HogRider','HogRider']);x[1]['tick']=20
    assert belief_at(x,50,0)['inferred_mirror_plays']==0
    x=events(['HogRider','HogRider']);x[1]['gap_before']=True
    assert belief_at(x,50,0)['inferred_mirror_plays']==0
    assert belief_at(events(['HogRider','HogRider']),50,0,rules='unknown')['inferred_mirror_plays']==0


def test_features_public_only_causal_and_no_deck_filling():
    x=events(['HogRider','HogRider','Knight','Zap','Rocket','Log'])
    gid={n:i+1 for i,n in enumerate(['hog-rider','mirror','knight','zap','rocket','the-log'])}
    base=belief_tokens(x,125,0,gid)
    changed=copy.deepcopy(x)
    for e in changed:e.update(hidden_hand=['secret'],hidden_elixir=999,next='secret',deck=['secret']*8)
    changed.extend(events(['Tesla']))
    changed[-1]['tick']=200
    for k,v in belief_tokens(changed,125,0,gid).items():np.testing.assert_array_equal(v,base[k])
    assert np.count_nonzero(base['opp_hand'][:,0])==6
    assert base['opp_hand_quality'][-1]==1
    changed[0]['card']='GoblinBarrel'
    assert not np.array_equal(belief_tokens(changed,125,0,gid)['opp_hand'],base['opp_hand'])
