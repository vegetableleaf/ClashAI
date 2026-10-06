"""Separately corrected canonical event-card spelling; original failure retained."""
import copy
from test_adapter import A, FRAME, T, PublicObserver, vocab

def test_auxiliary_lifecycle_preserves_canonical_event_identity():
    f=copy.deepcopy(FRAME);f['projectiles']=[];f['effects']=[]
    f['character_identity']={'schema':1,'build':A.BUILD}
    hero=T(5000010,15,0,3000,10000,911,911,A.HERO_ID,'0x1')
    hero.update(native_name='IceWizardHero',native_name_status='ok')
    cube=copy.deepcopy(hero);cube.update(address='0x2',category=5000011,native_name='IceWizardHeroFloatingCube')
    ice=copy.deepcopy(cube);ice.update(address='0x3',category=5000012,native_name='IceWizardHero_IceCube')
    observer=PublicObserver(1)
    f['entities']=[cube,ice];observer.update(A.adapt(f),source='reader')
    assert observer.plays==[]
    f['game_tick']+=10;f['entities']=[hero,cube,ice];observer.update(A.adapt(f),source='reader')
    assert len(observer.plays)==1
    f['game_tick']+=200;f['entities']=[hero];observer.update(A.adapt(f),source='reader')
    f['game_tick']+=10;f['entities']=[hero,cube,ice];observer.update(A.adapt(f),source='reader')
    assert len(observer.plays)==1 and observer.plays[0]['card']==vocab.engine_key('IceWizard')
    assert observer.plays[0]['form']==2
