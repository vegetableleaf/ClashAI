import copy
import pytest
import torch
from pipeline.tests.test_live_mem import FRAME,T
from pipeline.tests.test_live_gen_afford import pilot
from live_play_identity import IdentityPilot

@pytest.mark.parametrize('observer',[0,1])
@pytest.mark.parametrize('lookahead',[0,26])
def test_entry_normalizes_history_and_row_with_original_audit(observer,lookahead):
    old=pilot([1,2,3,4],ext_h=lookahead)
    p=object.__new__(IdentityPilot);p.__dict__.update(old.__dict__)
    p.feature_version=4;p.use_counter=True;p.public=p.public_battle=None;p.public_audit=True
    p.gid['ice-wizard']=max(p.gid.values())+1
    f=copy.deepcopy(FRAME);f['character_identity']={'schema':1,'build':160402012}
    f['players'][1]['side']=observer;f['players'][0]['side']=1-observer
    f['projectiles']=[];f['effects']=[];f['entities']=[]
    for i,name in enumerate(['IceWizardHero','IceWizardHeroFloatingCube','IceWizardHero_IceCube']):
        e=T(5000100+i,15,observer,4000,20000,911,911,203000023,hex(100+i))
        e.update(native_name=name,native_name_status='ok');f['entities'].append(e)
    original=copy.deepcopy(f)
    p.observe(f)
    assert len(p.frames[-1][1]['entities'])==1
    b,info=p.row(f)
    assert len(info['bs'].units)==1 and int(b['mask'].sum())==1
    assert float(b['own_ability'][0,:,2].sum())==1
    audit=p._public_audit_snapshot
    assert len(audit['raw_bodies'])==3 and len(audit['model_bodies'])==1
    assert len(audit['excluded_public_objects'])==2 and f==original
    assert {e['entity']['native_name'] for e in audit['excluded_public_objects']}=={'IceWizardHeroFloatingCube','IceWizardHero_IceCube'}
    f['game_tick']+=10;p.observe(f)
    assert all(len(frame['entities'])==1 for _,frame in p.frames)
    p.row(f)
    invalid=copy.deepcopy(f);invalid.pop('character_identity')
    with pytest.raises(ValueError):p.observe(invalid)
    with pytest.raises(ValueError):p.row(invalid)
