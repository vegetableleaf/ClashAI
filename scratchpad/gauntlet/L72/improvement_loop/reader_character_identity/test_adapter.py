import copy
import importlib.util
from pathlib import Path

import pytest
import torch
from pipeline import obs_contract as O, vocab
from pipeline.tests.test_live_mem import FRAME, T
from pipeline.tests.test_live_gen_afford import pilot
from pipeline.public_observation import public_frame
from pipeline.public_observation import PublicObserver

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('character_adapter', HERE/'adapter.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)


@pytest.mark.parametrize('version', [4, 7])
@pytest.mark.parametrize('side', [0, 1])
@pytest.mark.parametrize('observer', [0, 1])
@pytest.mark.parametrize('lookahead', [0, 26])
def test_actual_body_and_public_play_paths(version, side, observer, lookahead, monkeypatch):
    p = pilot([1,2,3,4], ext_h=lookahead)
    p.feature_version=version; p.use_counter=True; p.public=p.public_battle=None
    p.gid['ice-wizard']=max(p.gid.values())+1
    f=copy.deepcopy(FRAME)
    f['players'][1]['side']=observer; f['players'][0]['side']=1-observer
    f['character_identity']={'schema':1, 'build':A.BUILD}
    f['entities']=[]; f['projectiles']=[]; f['effects']=[]
    for n,name in enumerate(['IceWizardHero','IceWizardHeroFloatingCube','IceWizardHero_IceCube',None,'UnknownHeroChild']):
        e=T(5000010+n,15,side,2499,17499,911,911,A.HERO_ID,'0x'+str(n+1))
        e.update(native_name=name,native_name_status='ok' if name else 'read_error')
        f['entities'].append(e)
    # Colocated independent real Heroes survive; no position-based deduplication.
    twin=copy.deepcopy(f['entities'][0]); twin['address']='0x999'; twin['category']=5000999
    f['entities'].append(twin)
    before=copy.deepcopy(f); actual=A.adapt(f)
    assert f==before and len(actual['entities'])==2 and len(actual['excluded_public_objects'])==4
    assert len(public_frame(actual,source='reader')['entities'])==2
    p.observe(actual); batch,info=p.row(actual)
    assert len(info['bs'].units)==2
    assert all(u.cls==vocab.unit_id('ice_wizard') and u.form==2 and u.side==int(side!=observer) for u in info['bs'].units)
    assert int(batch['mask'].sum())==2
    private=copy.deepcopy(f)
    private['players'][0].update(elixir_raw=987654,hand_deck_indices=[-9]*4,next_deck_index=9,deck_card_ids=[999]*8)
    private['future_actions']=['private sentinel']
    # The adapter's public entity result and actual public feature inputs are invariant.
    alt=A.adapt(private)
    assert alt['entities']==actual['entities'] and alt['excluded_public_objects']==actual['excluded_public_objects']
    q=pilot([1,2,3,4],ext_h=lookahead)
    q.feature_version=version; q.use_counter=True; q.public=q.public_battle=None
    q.gid=dict(p.gid)
    q.observe(alt); other,_=q.row(alt)
    assert all(torch.equal(v,other[k]) for k,v in batch.items())
    assert p.public.plays==q.public.plays
    assert len(p.public.plays)==int(side!=observer)
    assert float(batch['own_ability'][0,:,2].sum())==(2. if side==observer else 0.)


def test_elite_alias_actual_observation(monkeypatch):
    names=O._catalog_names(); O.catalog_card_form(26000043)
    forms=O.catalog_card_form.table
    monkeypatch.setattr(O,'_CATALOG_NAMES',A.extend_elite_names(names))
    monkeypatch.setattr(O.catalog_card_form,'table',A.extend_elite_forms(forms))
    assert all(O._catalog_names()[k]==v for k,v in names.items())
    assert all(O.catalog_card_form(k)==v for k,v in forms.items())
    p=pilot([1,2,3,4]); p.feature_version=7; p.use_counter=True; p.public=p.public_battle=None
    f=copy.deepcopy(FRAME)
    f['entities']=[T(5000010,15,0,5000,10000,2143,2143,A.ELITE_EVO,'0x1'),T(5000011,15,0,5000,10000,2143,2143,A.ELITE_EVO,'0x2')]
    f['projectiles']=[]; f['effects']=[]
    p.observe(f); batch,info=p.row(f)
    assert len(info['bs'].units)==2 and int(batch['mask'].sum())==2
    assert all(u.cls==35 and u.form==1 for u in info['bs'].units)
    assert O.catalog_card_form(A.ELITE_EVO)==('AngryBarbarians',1)


def test_conflicts_and_schema_fail_closed():
    for original in ({}, {A.ELITE_BASE:'Wrong'}, {A.ELITE_BASE:'AngryBarbarians',A.ELITE_EVO:'Knight'}):
        with pytest.raises(ValueError): A.extend_elite_names(original)
    for original in ({}, {A.ELITE_BASE:('AngryBarbarians',1)}, {A.ELITE_BASE:('AngryBarbarians',0),A.ELITE_EVO:('AngryBarbarians',0)}):
        with pytest.raises(ValueError): A.extend_elite_forms(original)
    for marker in (None, {'schema':2,'build':A.BUILD}, {'schema':1,'build':150535029}):
        with pytest.raises(ValueError): A.adapt({'character_identity':marker,'entities':[]})


def test_auxiliary_lifecycle_does_not_invent_enemy_plays():
    f=copy.deepcopy(FRAME); f['projectiles']=[]; f['effects']=[]
    f['character_identity']={'schema':1,'build':A.BUILD}
    hero=T(5000010,15,0,3000,10000,911,911,A.HERO_ID,'0x1')
    hero.update(native_name='IceWizardHero',native_name_status='ok')
    cube=copy.deepcopy(hero);cube.update(address='0x2',category=5000011,native_name='IceWizardHeroFloatingCube')
    ice=copy.deepcopy(cube);ice.update(address='0x3',category=5000012,native_name='IceWizardHero_IceCube')
    obs=PublicObserver(1)
    f['entities']=[cube,ice];obs.update(A.adapt(f),source='reader')
    assert obs.plays==[]
    f['game_tick']+=10;f['entities']=[hero,cube,ice];obs.update(A.adapt(f),source='reader')
    assert len(obs.plays)==1
    f['game_tick']+=200;f['entities']=[hero];obs.update(A.adapt(f),source='reader')
    f['game_tick']+=10;f['entities']=[hero,cube,ice];obs.update(A.adapt(f),source='reader')
    assert len(obs.plays)==1 and obs.plays[0]['card']=='ice-wizard'


def test_ordinary_public_and_model_inputs_exact():
    f=copy.deepcopy(FRAME);f['character_identity']={'schema':1,'build':A.BUILD}
    f['projectiles']=[];f['effects']=[]
    f['entities'].append(T(5000123,15,0,3000,10000,1000,1000,26000000,'0x123'))
    original=copy.deepcopy(f); adapted=A.adapt(f)
    assert f==original and adapted['entities']==original['entities']
    assert adapted['players']==original['players'] and adapted['projectiles']==original['projectiles'] and adapted['effects']==original['effects']
    assert public_frame(f,source='reader')==public_frame(adapted,source='reader')
    def make():
        p=pilot([1,2,3,4],ext_h=26);p.feature_version=4;p.use_counter=True;p.public=p.public_battle=None
        return p
    a,b=make(),make();a.observe(f);b.observe(adapted)
    left,li=a.row(f);right,ri=b.row(adapted)
    assert li==ri and all(torch.equal(left[k],right[k]) for k in left)
