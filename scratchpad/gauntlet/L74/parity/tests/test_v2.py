"""No-SIM planning, adapter contract, pairing and negative-control tests."""
from copy import deepcopy
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

import pytest

from scratchpad.gauntlet.L74.parity import core, driver
from scratchpad.gauntlet.L74.parity.planning import forced_deal, own_logs, hydrate, plan, planning_report, OLD_HERO_REASON
from scratchpad.gauntlet.L74.parity.mechanics import SnapshotReplay, load_edited, NO_CARD

NAMES = ['Knight', 'Xbow', 'Tesla', 'IceWizard', 'Skeletons', 'Tornado', 'Log', 'Rocket']


def fixture():
    _, cat = core.ps.load_catalog()
    deck = [dict(name=n, card_id=cat[n]['card_id'], form=0, level=15) for n in NAMES]
    frames = [dict(tick=t, bodies=[], own_elixir=5) for t in [90, 100, 120, 140]]
    return dict(match='fixture', schema=1, sha256='f'*64, observer_side=0, quality={},
                decks={'0':deck, '1':[deepcopy(deck[0])]}, tower_levels=[15,15],
                frames=frames, blocks=['public_deck_side_1_has_1_cards'],
                own_decisions=[dict(tick=t, side=0, hand=[dict(name=n) for n in NAMES[:4]],
                                    next_card=dict(name='Log')) for t in [90,100,120,140]],
                plays=[dict(tick=t, side=s, name='Knight', card_id=cat['Knight']['card_id'], x=1000,y=2000)
                       for t,s in [(100,0),(101,0),(110,1),(111,1)]])


def test_forced_deal_preserves_slots_logged_next_and_empty_slots():
    f=fixture(); deck=f['decks']['0']
    h=[dict(name=n) for n in ['Tesla','Xbow','Knight','IceWizard']]
    deal=forced_deal(h,dict(name='Log'),deck)
    assert deal['hand']==['Tesla','Xbow','Knight','IceWizard']
    assert deal['order']==['Tesla','Xbow','Knight','IceWizard','Log','Skeletons','Tornado','Rocket']
    assert deal['next_observed']
    h[2]={}
    deal=forced_deal(h,None,deck)
    assert deal['hand'][2] is None and not deal['next_observed']
    assert 'Knight' in deal['queue'] and deal['next_card'] is None
    with pytest.raises(ValueError,match='next_card'):
        forced_deal(h,dict(name='Tesla'),deck)


def test_injection_ignores_cycle_and_incomplete_deck_default_off():
    f=fixture()
    assert plan(f)['blocks']==f['blocks']
    p=plan(f,True)
    assert not p['blocks'] and not p['skips']
    assert len(p['actions'])==4 and len(p['opponent_roster'])==1
    assert [(a['tick'],a['x'],a['y']) for a in p['actions']]==[(x['tick'],1000,2000) for x in f['plays']]
    assert [a['mode'] for a in p['actions']]==['logged_hand']*2+['public_injection']*2
    assert all(a['hand_tick']==100 for a in p['actions'][:2])
    assert 'opponent_elixir' not in json.dumps(p)


def test_skip_accounting_and_no_future_hand_repair():
    f=fixture()
    f['plays'][0]['tick']=80
    f['own_decisions'][1]['hand']=[]
    p=plan(f,True)
    assert p['counts']['plays_used']==2
    assert p['counts']['decisions_used']==3
    assert CounterReasons(p['skips'])=={'no_logged_hand_before_play':2,'logged_hand_not_four_slots':1}
    f['blocks'].append('levels_unknown')
    report=planning_report([f],True)
    assert report['usable_matches']==0 and report['matches'][0]['blocks']==['levels_unknown']
    assert report['skip_reasons']['levels_unknown']==1


def CounterReasons(rows):
    from collections import Counter
    return dict(Counter(r['reason'] for r in rows))


def test_hydration_allowlist_hash_and_next_absence():
    folder=driver.HERE/'output'/('v2_test_'+uuid.uuid4().hex)
    folder.mkdir(parents=True)
    path=folder/'fixture.jsonl'
    row=dict(event='decision',tick=10,public=dict(observer_side=0,
             own_hand=[dict(name='Knight', secret='SECRET')], own_next_card=dict(name='Tesla'),
             opponent_hand='SECRET',opponent_elixir='SECRET',opponent_next_card='SECRET'))
    raw=(json.dumps(row)+'\n').encode(); path.write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest()
    result=own_logs(path,sha)
    assert 'SECRET' not in json.dumps(result)
    assert result[0]['next_card']==dict(name='Tesla')
    with pytest.raises(ValueError,match='hash_mismatch'):
        own_logs(path,'bad')
    row['public'].pop('own_next_card'); raw=(json.dumps(row)+'\n').encode();path.write_bytes(raw)
    assert own_logs(path,hashlib.sha256(raw).hexdigest())[0]['next_card'] is None
    f=fixture(); f.pop('own_decisions'); f['sha256']='bad'
    assert plan(hydrate(f,folder),True)['blocks']


class FakeBattle:
    """Deliberately different catalogue/internal indices and validating snapshot load."""
    instances=[]
    reject_hero=False
    def __init__(self,*args,**kwargs):
        self.calls=[]; self.loads=[]; self.instances.append(self)
    def catalogue_json(self):return json.dumps([[n] for n in NAMES])
    @staticmethod
    def hash(s):
        value=deepcopy(s);value.pop('state_hash',None)
        return int(hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:16],16)
    def reset(self,seed,decks,shuffle,tick,elixir,hp,spawns,**kw):
        if self.reject_hero and any(2 in x for x in kw.get('forms',[])):
            raise ValueError('IceWizard has no loadable hero form: fixture')
        self.s=dict(tick=tick, players=[dict(hand=[c+100 for c in deck[:4]],
                    queue=[c+100 for c in deck[4:]],refill_ms=0,mana=5000) for deck in decks],
                    mana_unit=1000,calib=dict(max_mana=10), entities=['combat-preserved'],
                    projectiles=['preserved'],state_hash=0)
    def save(self):
        self.s['state_hash']=self.hash(self.s)
        return json.dumps(self.s).encode()
    def load(self,blob):
        v=json.loads(blob);got=self.hash(v)
        if v['state_hash']!=got:
            raise ValueError(f"snapshot self-check failed: saved hash {v['state_hash']:#x}, rebuilt {got:#x}")
        self.s=v;self.loads.append(deepcopy(v))
    def state_json(self):
        return json.dumps(dict(tick=self.s['tick'],entities=[],players=[dict(team=i,
            hand=[x-100 if x!=NO_CARD else -1 for x in p['hand']],elixir_milli=p['mana'])
            for i,p in enumerate(self.s['players'])]))
    def step(self,commands,ticks):
        self.s['tick']+=ticks
        rows=[]
        for side,slot,x,y in commands:
            p=self.s['players'][side]
            ok=p['hand'][slot]!=NO_CARD and p['mana']>=1000
            rows.append((p['hand'][slot]-100,0 if ok else 4,self.s['tick'],x,y))
            self.calls.append(dict(tick=self.s['tick'],side=side,slot=slot,hand=list(p['hand']),mana=p['mana']))
            if ok:
                p['hand'][slot]=NO_CARD;p['mana']-=1000
        return rows


def fake_runtime(monkeypatch, hero=False):
    FakeBattle.instances=[];FakeBattle.reject_hero=hero
    sim=SimpleNamespace(Battle=FakeBattle,ENTITY_FIELDS=['uid','team','card_id','x','y','hp','max_hp','status_flags'],
                        CATALOGUE_FIELDS=['name'], DEPLOY_REASONS=['OK','B','C','D','NOT_ENOUGH_ELIXIR'])
    monkeypatch.setitem(sys.modules,'royalesim',sim)
    monkeypatch.setitem(sys.modules,'pipeline.royale_runtime',SimpleNamespace(activate=lambda:{},RUNTIME=driver.ROOT))
    monkeypatch.setattr(metadata,'distributions',lambda **k:[SimpleNamespace(metadata={'Name':'royalesim'},version='0.1.17')])
    return sim


def test_worker_mechanics_repeated_plays_and_combat_preservation(monkeypatch):
    fake_runtime(monkeypatch)
    f=fixture()
    result=driver.drive(f,'old',True)
    battle=FakeBattle.instances[0]
    assert all(p['accepted'] for p in result['commands'])
    assert [c['tick'] for c in battle.calls]==[100,101,110,111]
    assert [c['mana'] for c in battle.calls]==[5000,4000,10000,10000]
    assert all(c['hand'][0]==100 for c in battle.calls)
    assert battle.s['entities']==['combat-preserved'] and battle.s['projectiles']==['preserved']
    assert battle.s['tick']==140
    assert battle.s['players'][0]['hand']==[100,101,102,103]
    assert battle.s['players'][0]['queue'][0]==106  # explicitly logged next
    assert result['planning_counts']['opponent_injections']==2
    assert result['deal_candidates']==[None,None]


def test_snapshot_adapter_refuses_unrelated_errors_and_rolls_back():
    b=FakeBattle(); b.reset(1,[[0],[0]],0,0,None,None,[])
    before=json.loads(b.save());after=deepcopy(before);after['players'][0]['mana']=123
    real=b.load
    def refuse(blob):
        if json.loads(blob)['players'][0]['mana']==123:raise ValueError('different card data')
        real(blob)
    b.load=refuse
    with pytest.raises(ValueError,match='different card data'):load_edited(b,before,after)
    assert json.loads(b.save())==before


def test_old_hero_expected_only_when_actual_reset_refuses(monkeypatch):
    fake_runtime(monkeypatch,hero=True)
    f=fixture();f['decks']['0'][3]['form']=2
    assert plan(f,True)['old_unsupported']==OLD_HERO_REASON
    r=driver.drive(f,'old',True)
    assert r['status']=='UNSUPPORTED_EXPECTED' and r['skip_reason']==OLD_HERO_REASON and 'error' not in r
    FakeBattle.reject_hero=False
    assert driver.drive(f,'old',True)['status']=='EXPLORATORY_MECHANICS'


def test_old_hero_probe_precedes_unknown_new_opponent_card(monkeypatch):
    fake_runtime(monkeypatch,hero=True)
    f=fixture();f['decks']['0'][3]['form']=2
    f['decks']['1'][0]['name']='FutureCard'
    for play in f['plays']:
        if play['side']==1:play['name']='FutureCard'
    assert driver.drive(f,'old',True)['status']=='UNSUPPORTED_EXPECTED'


def measured(rt,match,ticks=(10,20)):
    body=dict(card_id=-1,side=0,tower=True,missing=None,position_error_tiles=0,hp_error=2,mismatch=True)
    return dict(runtime=rt,match=match,samples=[dict(match=match,tick=t,rows=[body]) for t in ticks],
                commands=[],divergence_seconds=0,divergence_tick=0)


def test_pairing_fallback_only_expected_old_and_common_rows():
    results=[measured(rt,'normal') for rt in ('old','new','fork')]
    results += [dict(runtime='old',match='hero',status='UNSUPPORTED_EXPECTED',skip_reason=OLD_HERO_REASON),
                measured('new','hero'),measured('fork','hero',(10,))]
    results += [dict(runtime='old',match='broken',error='engine_crash'),measured('new','broken'),measured('fork','broken')]
    report=driver.summarize([dict(match=m) for m in ('normal','hero','broken','missing')],results,['old','new','fork'])
    assert report['paired_matches']==['hero','normal'] and len(report['failures'])==1
    assert report['expected_unsupported_jobs']==1
    assert report['comparison_groups']['all_requested']['matches']==['normal']
    fallback=report['comparison_groups']['new_fork_unsupported_old']
    assert fallback['matches']==['hero'] and fallback['decision_rows_used']==1
    assert fallback['runtimes']['new']['rows_used']==1
    assert report['skip_reasons']['missing_worker_result']==3
    assert report['skip_reasons']['not_available_in_all_group_runtimes']==1
    assert report['runtimes']['new']['ranking']
    assert 'body rows=' in driver.text_report(report)


def test_empty_results_never_claim_measurements():
    rows=[measured(rt,'empty',()) for rt in ('new','fork')]
    report=driver.summarize([dict(match='empty')],rows,['new','fork'])
    assert report['status']=='NO_PAIRED_MEASUREMENTS'
    assert report['skip_reasons']['no_common_measurement_rows']==1
