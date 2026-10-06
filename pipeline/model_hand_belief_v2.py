"""Opt-in learned public-hand representation; no tactical holding rules."""
import copy
import torch
from torch import nn
from .model_gen import GenModel,_pool

TAG='public_hand_belief_v2'
VERSION=2

def canonical_hand(hand):
    # Lexicographic order across all public fields makes the pooled multiset
    # bitwise invariant, including duplicated-card diagnostic inputs. No labels,
    # private data, card-specific ordering or strategic preference is involved.
    ordered=hand
    for column in reversed(range(6)):
        index=torch.argsort(ordered[...,column],dim=1,stable=True)
        ordered=ordered.gather(1,index.unsqueeze(-1).expand_as(ordered))
    return ordered

class HandBeliefModel(GenModel):
    def __init__(self,*,hand_information_enabled=True,**kwargs):
        if int(kwargs.get('feature_version',5))!=5:raise ValueError('Hand branch requires public v5 base')
        kwargs['feature_version']=5
        super().__init__(**kwargs)
        self.hand_information_enabled=bool(hand_information_enabled)
        self.hand_token=nn.Sequential(nn.Linear(self.d_c+5,self.d),nn.GELU(),nn.Linear(self.d,self.d))
        self.hand_context=nn.Sequential(nn.Linear(3*self.d+5,self.d),nn.GELU(),nn.Linear(self.d,self.d))
        nn.init.zeros_(self.hand_context[-1].weight);nn.init.zeros_(self.hand_context[-1].bias)

    def encode_gen(self,b):
        hand=b['opp_hand'];quality=b['opp_hand_quality']
        if hand.shape!=(len(b['sc']),8,6) or quality.shape!=(len(b['sc']),5):
            raise ValueError('Wrong public hand feature schema')
        if not torch.isfinite(hand).all() or not torch.isfinite(quality).all():raise ValueError('Nonfinite hand input')
        ids=hand[...,0]
        if not ((ids==ids.round())&(ids>=0)&(ids<self.n_cards)).all():raise ValueError('Invalid public card identity')
        if not ((hand[...,1:]>=0)&(hand[...,1:]<=1)).all() or not ((quality>=0)&(quality<=1)).all():
            raise ValueError('Invalid hand belief range')
        if not ((ids==0)|(hand[...,1:4].sum(-1)==1)).all():raise ValueError('Contradictory hand status')
        if not self.hand_information_enabled:
            hand=torch.zeros_like(hand);quality=torch.zeros_like(quality);quality[:,4]=1
        hand=canonical_hand(hand)
        enc=super().encode_gen(b)
        embeddings=self.card_id(hand[...,0].long())
        tokens=self.hand_token(torch.cat([embeddings,hand[...,1:]],-1))
        pooled=_pool(tokens,hand[...,0]>0)
        residual=self.hand_context(torch.cat([enc['g'],pooled,quality],-1))
        return dict(enc,g=enc['g']+residual)

def construct(state):
    a=state['args']
    if state.get('architecture')!=TAG or a.get('hand_belief_version')!=VERSION or a.get('feature_version')!=5:
        raise ValueError('Unsupported public hand architecture/version')
    if type(a.get('hand_information_enabled')) is not bool:raise ValueError('Explicit hand-information mode required')
    return HandBeliefModel(d=int(a['d']),layers=int(a['layers']),d_c=int(state['d_c']),n_cards=len(state['card_vocab']),
        feature_version=5,hand_information_enabled=a['hand_information_enabled'])

def load_checkpoint(path,device='cpu'):
    state=torch.load(path,map_location='cpu',weights_only=True)
    if not state.get('gen'):raise ValueError('Generalist checkpoint required')
    model=construct(state);model.load_state_dict(state['model'],strict=True)
    return model.to(device),state

def initialize(parent,*,enabled,seed):
    state=torch.load(parent,map_location='cpu',weights_only=True)
    if state.get('architecture') or state['args'].get('feature_version')!=5:raise ValueError('Ordinary v5 parent required')
    result={k:copy.deepcopy(v) for k,v in state.items() if k not in ('model','optimizer','val','eval')}
    result.update(architecture=TAG)
    result['args'].update(hand_belief_version=VERSION,hand_information_enabled=bool(enabled))
    with torch.random.fork_rng():
        torch.manual_seed(seed);model=construct(result)
    loaded=model.load_state_dict(state['model'],strict=False)
    if loaded.unexpected_keys or set(loaded.missing_keys)!={k for k in model.state_dict() if k.startswith(('hand_token.','hand_context.'))}:
        raise ValueError('Non-hand parent tensor mismatch')
    if not all(torch.equal(v,model.state_dict()[k]) for k,v in state['model'].items()):raise ValueError('Parent tensor drift')
    return model,result
