"""Isolated learned tower features from existing public scalars; no action rules."""
import torch
from torch import nn
from pipeline.model_gen import GenModel
from pipeline.model_v3 import PATCH_X,PATCH_Y,N_PATCHES,cell_index
from pipeline import obs_contract as obs

TAG='public_tower_spatial_v1'
def anchors():
    return [(obs.KING_X,obs.MY_KING_Y),(obs.PRINCESS_X_L,obs.MY_PRINCESS_Y),
        (obs.PRINCESS_X_R,obs.MY_PRINCESS_Y),(obs.KING_X,obs.OPP_KING_Y),
        (obs.PRINCESS_X_L,obs.OPP_PRINCESS_Y),(obs.PRINCESS_X_R,obs.OPP_PRINCESS_Y)]

class TowerModel(GenModel):
    def __init__(self,**kwargs):
        super().__init__(feature_version=6,**kwargs);self.feature_version=7
        self.tower_spatial_in=nn.Sequential(nn.Linear(5,self.d),nn.GELU(),nn.Linear(self.d,self.d))
        self.tower_spatial_spread=nn.Conv2d(self.d,self.d,3,padding=1,groups=self.d,bias=False)
        nn.init.zeros_(self.tower_spatial_spread.weight)
        self.register_buffer('tower_spatial_xy',torch.tensor(anchors(),dtype=torch.float32))
        self.register_buffer('tower_spatial_side',torch.tensor([0,0,0,1,1,1],dtype=torch.float32))
        self.register_buffer('tower_spatial_kind',torch.tensor([0,1,1,0,1,1],dtype=torch.float32))

    def tower_features(self,sc):
        alive=sc[:,64:70]>.5;raw=sc[:,52:58]
        known=(sc[:,58:64]>.5)&alive&torch.isfinite(raw)
        hp=torch.where(known,raw,0)
        b=len(sc);side=self.tower_spatial_side.expand(b,-1);kind=self.tower_spatial_kind.expand(b,-1)
        return torch.stack([side,kind,hp,known.to(sc.dtype),alive.to(sc.dtype)],-1),alive

    def tower_unspread(self,sc):
        features,alive=self.tower_features(sc)
        vectors=self.tower_spatial_in(features)
        vectors=torch.where(alive.unsqueeze(-1),vectors,0)
        index=cell_index(self.tower_spatial_xy,PATCH_X,PATCH_Y)
        patches=vectors.new_zeros((len(sc),N_PATCHES,self.d))
        patches.scatter_add_(1,index[None,:,None].expand(len(sc),-1,self.d),vectors)
        return patches.transpose(1,2).reshape(len(sc),self.d,PATCH_Y,PATCH_X)

    def tower_patches(self,b):
        return self.tower_spatial_spread(self.tower_unspread(b['sc'])).flatten(2).transpose(1,2)

    def encode_gen(self,b):
        enc=super().encode_gen(b)
        return dict(enc,p=enc['p']+self.tower_patches(b))

def construct(state):
    a=state['args']
    return TowerModel(d=int(a['d']),layers=int(a['layers']),d_c=int(state['d_c']),n_cards=len(state['card_vocab']))

def migrate(state,base):
    model=construct(state);missing=model.load_state_dict(base.state_dict(),strict=False)
    expected={k for k in model.state_dict() if k.startswith('tower_spatial_')}
    assert set(missing.missing_keys)==expected and not missing.unexpected_keys
    assert all(torch.equal(v,model.state_dict()[k]) for k,v in base.state_dict().items())
    return model

def load_checkpoint(path,device='cpu'):
    state=torch.load(path,map_location='cpu',weights_only=True)
    assert state['architecture']==TAG and state['args']['feature_version']==7
    model=construct(state)
    for key in ('tower_spatial_xy','tower_spatial_side','tower_spatial_kind'):
        assert torch.equal(state['model'][key],model.state_dict()[key]),key
    model.load_state_dict(state['model'],strict=True)
    assert torch.equal(model.tower_spatial_xy,torch.tensor(anchors(),dtype=torch.float32))
    return model.to(device),state
