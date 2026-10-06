"""Regress the observed missing public defender through the actual live batch path."""
import copy
import pytest
import torch
from pipeline import vocab
from pipeline.reader_identity_aliases import extend_names, extend_forms
from pipeline.tests.test_live_gen_afford import pilot
from pipeline.tests.test_live_mem import FRAME,T


@pytest.mark.parametrize('version',[4,7])
@pytest.mark.parametrize('observer',[0,1])
@pytest.mark.parametrize('body_side',[0,1])
@pytest.mark.parametrize('lookahead',[0,26])
def test_actual_live_batch_contains_public_hero_ice_wizard(version,observer,body_side,lookahead):
    p=pilot([1,2,3,4],ext_h=lookahead)
    p.feature_version=version;p.use_counter=True;p.public=p.public_battle=None
    p.gid['ice-wizard']=max(p.gid.values())+1
    f=copy.deepcopy(FRAME)
    f['players'][1]['side']=observer;f['players'][0]['side']=1-observer
    f['entities']=[T(5000014,15,body_side,2499,17499,911,911,203000023,'0xhero')]
    f['projectiles']=[];f['effects']=[]
    p.observe(f);batch,info=p.row(f)
    active=batch['tok'][0][batch['mask'][0]]
    assert len(active)==1 and int(active[0,0])==vocab.unit_id('ice_wizard')
    assert int(batch['unit_form'][0,0])==2
    assert len(info['bs'].units)==1 and info['bs'].units[0].side==int(body_side!=observer)
    expected={k:v.clone() for k,v in batch.items()}
    f['players'][0].update(elixir_raw=999999,deck_card_ids=[999]*8,next_deck_index=999)
    actual,_=p.row(f)
    assert all(torch.equal(expected[k],actual[k]) for k in expected)


def test_alias_preserves_catalog_and_rejects_conflicts():
    names={26000023:'IceWizard',26000000:'Knight'}
    forms={26000023:('IceWizard',0),26000000:('Knight',0)}
    assert extend_names(names)=={**names,203000023:'IceWizard'}
    assert extend_forms(forms)=={**forms,203000023:('IceWizard',2)}
    assert 203000023 not in names and 203000023 not in forms
    with pytest.raises(ValueError):extend_names({**names,203000023:'Knight'})
    with pytest.raises(ValueError):extend_forms({**forms,203000023:('IceWizard',0)})
