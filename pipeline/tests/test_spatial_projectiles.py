"""Learned target residual integration, model loading and source compatibility."""
import copy
import tempfile
from pathlib import Path

import numpy as np
import torch

from pipeline.eval_gen import GenRows
from pipeline.model_gen import GenModel, load_model
from pipeline.tests.test_model_gen import toy
from pipeline.train_gen import losses


def batch():
    a = toy(n=4)['gen']
    a.update(unit_form=np.zeros(len(a['tok']),np.int8), opp_past=np.zeros((4,3,5),np.float32),
             opp_cycle=np.zeros((4,8,4),np.float32), projectiles=np.zeros((4,64,8),np.float32),
             effects=np.zeros((4,32,6),np.float32), own_ability=np.zeros((4,2,7),np.float32))
    a['projectiles'][:,0] = [2,1,.5,.4,.8,.8,.5,1]
    return GenRows(a,np.arange(4),'cpu').batch(np.arange(4))


def test_zero_initialization_preserves_tiny_outputs():
    torch.set_num_threads(1)
    for version in (4,5):
        original = GenModel(d=32,layers=1,d_c=16,n_cards=124,feature_version=version).eval()
        candidate = GenModel(d=32,layers=1,d_c=16,n_cards=124,feature_version=6).eval()
        missing = candidate.load_state_dict(original.state_dict(),strict=False)
        assert not missing.unexpected_keys
        assert len(missing.missing_keys)==5 and all(k.startswith('projectile_target_') for k in missing.missing_keys)
        b=batch()
        with torch.no_grad():
            before=original(b,card=b['card'],form=b['form'])
            after=candidate(b,card=b['card'],form=b['form'])
        assert all(torch.equal(before[k],after[k]) for k in before)


def test_version_six_checkpoint_roundtrip_and_expert_backward(tmp_path):
    torch.set_num_threads(1)
    model=GenModel(d=32,layers=1,d_c=16,n_cards=124,feature_version=6).eval()
    b=batch(); b['gate'][:]=1; b['slot'][:]=0; b['xy'][:]=torch.tensor([.8,.85])
    loss,_=losses(model,b,mirror=False,grid='lattice')
    loss.backward()
    assert model.projectile_target_spread.weight.grad.abs().sum()>0
    path=tmp_path/'v6.pt'
    torch.save(dict(gen=True,args=dict(d=32,layers=1,feature_version=6),d_c=16,
                    card_vocab=list(range(124)),model=model.state_dict()),path)
    loaded,_=load_model(path,'cpu');loaded.eval()
    with torch.no_grad():
        assert torch.equal(model(b,card=b['card'],form=b['form'])['cell'],
                           loaded(b,card=b['card'],form=b['form'])['cell'])


def test_unknown_target_mirroring_and_padding_stay_unknown():
    torch.set_num_threads(1)
    model=GenModel(d=32,layers=1,d_c=16,n_cards=124,feature_version=6).eval()
    b=batch();b['projectiles'][:,0,4:6]=-1
    captured={}
    hook=model.register_forward_pre_hook(lambda m,a: captured.update(projectiles=a[0]['projectiles'].clone()))
    losses(model,b,mirror=True,grid='lattice')
    hook.remove()
    assert (captured['projectiles'][:,0,4:6]==-1).all()
    with torch.no_grad():
        model.projectile_target_spread.weight.fill_(1)
    assert (model.target_patches(b)==0).all()
    b['projectiles'][:]=0
    assert (model.target_patches(b)==0).all()
