"""Mirror-aware successor: causal public play identities and explicit hand tokens.

is conditional on that feed describing consecutive genuine plays, and its use is
reported to the learned model rather than treated as certified hand truth.
"""
from itertools import groupby
import numpy as np

from .dataset_gen import card_key
from .opponent_hand import from_public_plays, STANDARD_RULES

TOKEN_COLUMNS = ('card', 'in_hand', 'out_of_hand', 'unknown', 'return_min', 'return_max')
QUALITY_COLUMNS = ('revealed_fraction', 'full_hand', 'has_issue', 'mirror_inferred', 'untrusted_events')


def normalize_public_plays(plays, tick, own_side, *, rules=STANDARD_RULES):
    selected=[dict(e) for e in plays if int(e['side'])!=int(own_side)
              and int(e['tick'])<int(tick) and e.get('accepted',True) and not e.get('ability')]
    selected.sort(key=lambda e:int(e['tick']))
    out=[];revealed=set();previous=None;ids={};mirror_count=0
    for t,group in groupby(selected,key=lambda e:int(e['tick'])):
        batch=[]
        for e in group:
            eid=e.get('event_id')
            if eid is not None:
                signature=(int(e['tick']),e.get('card'))
                if eid in ids:
                    if ids[eid]!=signature:raise ValueError('Conflicting public event ID')
                    continue
                ids[eid]=signature
            e['card']=card_key(e.get('card') or '')
            batch.append(e)
        if not batch:continue
        if len(batch)!=1 or any(e.get('gap_before') or e.get('identity_unknown') for e in batch):
            previous=None
        for e in batch:
            raw=e['card']
            e['observed_card']=raw
            e['mirror_inferred']=False
            if (rules==STANDARD_RULES and len(batch)==1 and previous is not None
                    and raw is not None and raw==previous['observed_card']):
                prefix=from_public_plays(out,t,own_side,rules=rules)
                possible=(previous['card']!='mirror'
                          and not (len(revealed)==8 and 'mirror' not in revealed)
                          and 'mirror' not in prefix['out_of_hand'])
                if possible:
                    e['card']='mirror';e['mirror_inferred']=True
                    e['copied_card']=raw;mirror_count+=1
                else:
                    e['identity_unknown']=True;e['gap_before']=True
                    e['identity_reason']='consecutive_copy_conflicts_with_public_cycle'
            out.append(e)
            if e['card'] and not e.get('identity_unknown'):revealed.add(e['card'])
        previous=(batch[0] if len(batch)==1 and not batch[0].get('identity_unknown') else None)
    return out,mirror_count


def belief_at(plays,tick,own_side,*,rules=STANDARD_RULES):
    events,mirrors=normalize_public_plays(plays,tick,own_side,rules=rules)
    result=from_public_plays(events,tick,own_side,rules=rules,complete_events=False)
    result['inferred_mirror_plays']=mirrors
    return result


def belief_tokens(plays,tick,own_side,gid,*,rules=STANDARD_RULES):
    belief=belief_at(plays,tick,own_side,rules=rules)
    tokens=np.zeros((8,len(TOKEN_COLUMNS)),np.float32)
    # Fixed canonical identity ordering, independent of hidden deck order.
    for i,card in enumerate(sorted(belief['revealed'])[:8]):
        cid=gid.get(card,0)
        if not cid:continue
        inside=card in belief['in_hand'];outside=card in belief['out_of_hand']
        low,high=belief['plays_to_return'].get(card,(0,4))
        tokens[i]=(cid,inside,outside,not (inside or outside),low/4,high/4)
    quality=np.array([min(8,len(belief['revealed']))/8,belief['full_hand'],
                      bool(belief['issues']),bool(belief['inferred_mirror_plays']),True],np.float32)
    return dict(opp_hand=tokens,opp_hand_quality=quality)
