"""CPU-only checks, including a real four-arm train/eval/checkpoint smoke on toy data."""
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scale
from features import add_richer_inputs, public_area_timeline, align_area_age, bridge_events, bridge_mask
from metrics import row_metrics, summarize, paired_ci, helps, phase, group_masks
from pipeline.model_gen import GenModel
from pipeline.obs_contract import catalog_card_form
from pipeline import vocab

torch.set_num_threads(1)


@pytest.fixture
def work_dir():
    # Avoid pytest's owner-only Windows temp ACL, which this managed workspace
    # cannot subsequently traverse. Retain tiny smoke artifacts for diagnosis.
    root = Path(os.environ.get('SCALE_TEST_ROOT', Path(__file__).resolve().parent/'test_artifacts'))/uuid.uuid4().hex
    root.mkdir(parents=True)
    return root


def effect_name():
    name, _ = catalog_card_form(26000038)
    return vocab.base_key(vocab.engine_key(name)).replace('_', '-')


def frames():
    return [dict(tick=t, entities=[[1, 3500, y, 'Knight', 100, 100, 15, 26000000, 99]],
                 public_objects=dict(area_effects=[dict(side=1, card_id=26000038, category=3, id='track',
                      x=3500, y=15000, source_elapsed_ms=999999, source_remaining_ms=1234)]))
            for t, y in [(10, 16100), (20, 15900), (30, 15800), (40, 15700)]]


def toy_batch(n=4):
    b = dict(tok=torch.zeros(n, 64, 14), mask=torch.zeros(n, 64, dtype=torch.bool), sc=torch.zeros(n, 70),
             past=torch.zeros(n, 3, 5), unit_form=torch.zeros(n, 64, dtype=torch.long), opp_past=torch.zeros(n, 3, 5),
             opp_cycle=torch.zeros(n, 8, 4), projectiles=torch.zeros(n, 64, 8), effects=torch.zeros(n, 32, 6),
             own_ability=torch.zeros(n, 8, 7), xy=torch.zeros(n, 2), gate=torch.tensor([1., 0., 1., 0.])[:n],
             slot=torch.tensor([0, -1, 2, -1])[:n], wait=torch.ones(n, dtype=torch.long),
             value=torch.full((n,), 3, dtype=torch.long), card=torch.ones(n, dtype=torch.long), form=torch.zeros(n, dtype=torch.long))
    for key, shape in [('hand_card', (n, 4)), ('deck_card', (n, 8)), ('next_card', (n,))]:
        b[key] = torch.ones(shape, dtype=torch.long)
        b[key.replace('card', 'form')] = torch.zeros(shape, dtype=torch.long)
    b['mask'][:, 0] = True
    b['tok'][:, 0, 0] = 1
    return b


def test_arm_configs_and_parameter_counts():
    arms = scale.arm_configs()
    assert [(a.d, a.layers, a.richer_inputs) for a in arms] == [(128,4,False),(256,4,False),(128,6,False),(128,4,True)]
    counts = {a.name: sum(p.numel() for p in scale.construct(a, 121).parameters()) for a in arms}
    assert counts['B'] > counts['C'] > counts['A']
    assert counts['D']-counts['A'] == 128  # 2 area channels * d_c(64)
    assert not scale.Arm('test', 128, 4).richer_inputs


def test_default_off_byte_identical_features_and_model():
    b = toy_batch()
    before = {k: v.numpy().tobytes() for k,v in b.items()}
    assert add_richer_inputs(b) is b
    assert add_richer_inputs(b, torch.randn(4,32,2), richer_inputs=False) is b
    assert before == {k: v.numpy().tobytes() for k,v in b.items()}
    torch.manual_seed(740); baseline = GenModel(feature_version=5, n_cards=10).eval()
    torch.manual_seed(740); arm = scale.construct(scale.arm_configs()[0], 10).eval()
    assert all(torch.equal(v, arm.state_dict()[k]) for k,v in baseline.state_dict().items())
    with torch.inference_mode():
        a, c = baseline(b, card=b['card']), arm(add_richer_inputs(b), card=b['card'])
    assert all(torch.equal(a[k], c[k]) for k in a)


def test_rich_channels_forward_backward_and_mirror():
    b = toy_batch()
    age = torch.ones(4,32,2)
    rich = add_richer_inputs(b, age, richer_inputs=True)
    assert torch.equal(rich['effects'][..., :6], b['effects'])
    assert b['effects'].shape[-1] == 6
    with pytest.raises(ValueError):
        add_richer_inputs(b, richer_inputs=True)
    model = scale.construct(scale.arm_configs()[-1], 10)
    rich['effects'][:, 0, 0] = 1
    loss, _ = scale.losses(model, rich, mirror=True, grid='lattice')
    loss.backward()
    assert torch.isfinite(loss)
    assert model.effect_in[0].weight.grad[:, -2:].abs().sum() > 0


def test_public_age_is_causal_and_private_fields_irrelevant():
    fs = frames(); gid = {effect_name(): 1}
    timeline = public_area_timeline(fs, gid)
    prefix = public_area_timeline(fs[:2], gid)
    assert prefix == timeline[:2]
    altered = json.loads(json.dumps(fs))
    for f in altered:
        f['players'] = [{'hand': ['SECRET'], 'elixir': 999, 'ability_ready': True}]
        f['public_objects']['area_effects'][0]['source_elapsed_ms'] = -999
        f['public_objects']['area_effects'][0]['source_remaining_ms'] = 0
    assert public_area_timeline(altered, gid) == timeline
    values = list(timeline[1][1][0].values())
    assert values[0] == (10*.05/30, 1.)
    altered[1]['public_objects']['area_effects'] = []
    assert list(public_area_timeline(altered, gid)[2][1][0].values())[0] == (0., 1.)


def test_alignment_masks_and_no_future_frame():
    timeline = public_area_timeline(frames(), {effect_name():1})
    effects = np.zeros((3,32,6), np.float32)
    effects[1:,0,:4] = [1,1,3500/18000,1-15000/32000]
    out = align_area_age(timeline, [0,19,20], [0,0,0], effects)
    assert out[0].sum() == 0 and out[1,0,0] == 0
    assert out[2,0,0] == pytest.approx(.5/30)
    effects[2,0,2] = .99
    with pytest.raises(ValueError, match='cannot join'):
        align_area_age(timeline, [0,19,20], [0,0,0], effects)


def test_ambiguous_area_age_and_missing_export():
    fs = frames()
    fs[0]['public_objects']['area_effects'] *= 2
    assert list(public_area_timeline(fs, {effect_name():1})[0][1][0].values()) == [(0.,0.)]
    with pytest.raises(ValueError, match='missing'):
        public_area_timeline([{'tick':10}], {})


def test_bridge_transition_not_presence_or_spawn():
    events = bridge_events(frames())
    assert events[0].tolist() == [20] and not len(events[1])
    assert bridge_mask(events, [19,20,40,41,30], [0,0,0,0,1]).tolist() == [False,True,True,False,False]
    fs = frames(); fs[0]['entities'] = []
    assert not len(bridge_events(fs)[0])
    fs = frames(); fs[0]['entities'][0][2] = 20000
    assert not len(bridge_events(fs)[0])


def test_phase_and_group_boundaries():
    assert phase([2399,2400,4799,4800]).tolist() == [1,2,2,3]
    groups = group_masks(np.array([1,2,3]), np.array([True,False,True]), np.array([True,True,False]))
    assert groups['icebow/bridge'].tolist() == [True,False,False]
    assert groups['all_decks/bridge/3x'].sum() == 1


def test_metrics_manual_oracle_and_empty_groups():
    b = toy_batch()
    out = {'card':torch.zeros(4,4), 'cell':torch.zeros(4,8), 'wait':torch.zeros(4,8),
           'value':torch.zeros(4,7), 'gate':torch.tensor([1.,-1.,-1.,1.])}
    out['card'][0,0] = 5; out['card'][2,1] = 5
    out['cell'][:,0] = 2; out['cell'][2,1] = 4
    stats = row_metrics(out,b)
    ev = summarize(stats,np.ones(4,bool))
    assert ev['card_top1'] == .5 and ev['card_top1_n'] == 2
    assert ev['cell_top1'] == .5 and ev['cell_top5'] == 1 and ev['gate_acc'] == .5
    assert ev['loss'] == pytest.approx(sum(np.nanmean(stats['loss_'+k]) for k in ('card','cell','wait','value','gate')))
    empty = summarize(stats, np.zeros(4,bool))
    assert empty['loss'] is None and empty['cell_top1'] is None


def test_nonfinite_metrics_fail_instead_of_reporting_zero_loss():
    b=toy_batch()
    out={'card':torch.zeros(4,4),'cell':torch.zeros(4,8),'wait':torch.zeros(4,8),
         'value':torch.zeros(4,7),'gate':torch.zeros(4)}
    out['cell'][0,0]=float('nan')
    with pytest.raises(ValueError,match='Nonfinite'):
        row_metrics(out,b)
    out['cell'][0,0]=0
    out['card'][0,:]=float('-inf')
    with pytest.raises(ValueError,match='Invalid'):
        row_metrics(out,b)


def test_paired_ci_and_conjunctive_verdict():
    rep = np.repeat(np.arange(20), 3)
    a = np.zeros(60); b = np.ones(60)
    positive = paired_ci(a,b,rep,draws=200)
    zero = paired_ci(a,a,rep,draws=200)
    negative = paired_ci(b,a,rep,draws=200)
    assert positive['lo'] == positive['hi'] == 1
    assert zero['lo'] == zero['hi'] == 0
    assert negative['hi'] == -1
    assert helps({'card_top1':positive, 'cell_top1':positive})
    assert not helps({'card_top1':positive, 'cell_top1':zero})
    assert not helps({'card_top1':positive, 'cell_top1':negative})
    assert paired_ci([0],[1],[0])['lo'] is None
    with pytest.raises(ValueError):
        paired_ci([np.nan],[1],[0])


def test_cluster_ci_keeps_repeated_rows_together():
    # Treating 1000 repeated rows as independent would falsely narrow this CI.
    rep = np.repeat([0,1], 1000)
    a = np.repeat([0.,1.],1000); b = 1-a
    ci = paired_ci(a,b,rep,draws=1000)
    assert ci['lo'] == -1 and ci['hi'] == 1 and ci['delta'] == 0


def synthetic_dataset(tmp):
    corpus = tmp/'corpus'; corpus.mkdir()
    names = sorted(scale.ICEBOW)
    names += [effect_name()]
    vocab_list = ['<pad>']+names
    tags = ['train0','train1']
    for bucket in (0,1):
        tags += [f'val{bucket}_{i}' for i in range(100) if hashlib.sha256(f'val{bucket}_{i}'.encode()).digest()[0]%2 == bucket][:2]
    n, per = len(tags)*4, 4
    for tag in tags:
        (corpus/f'replay_{tag}.json').write_text(json.dumps(dict(tag=tag,record_native=True,frames=frames(),play_frames=[])))
    a = dict(tags=np.array(tags), rep=np.repeat(np.arange(len(tags)),per).astype(np.int32),
             split=np.repeat([0,0,1,1,1,1],per).astype(np.int8), tick=np.tile([10,20,30,40],len(tags)).astype(np.int32),
             side=np.zeros(n,np.int8), effects=np.zeros((n,32,6),np.float32),
             tok=np.zeros((n,14),np.float32), off=np.arange(n+1,dtype=np.int64),sc=np.zeros((n,70),np.float32),
             unit_form=np.zeros(n,np.int8), past=np.zeros((n,3,5),np.float32),opp_past=np.zeros((n,3,5),np.float32),
             opp_cycle=np.zeros((n,8,4),np.float32),projectiles=np.zeros((n,64,8),np.float32),own_ability=np.zeros((n,8,7),np.float32),
             y_gate=np.tile([1,0,1,0],len(tags)).astype(np.int8),y_hand_pos=np.tile([0,-1,0,-1],len(tags)).astype(np.int8),
             y_card=np.ones(n,np.int16),y_wait_card=np.ones(n,np.int16),y_xy=np.full((n,2),.25,np.float32),
             y_crowns=np.zeros((n,2),np.int8),hand_card=np.tile([1,2,3,4],(n,1)).astype(np.int16),
             hand_form=np.zeros((n,4),np.int16),deck_card=np.tile(np.arange(1,9),(n,1)).astype(np.int16),
             deck_form=np.zeros((n,8),np.int16),next_card=np.full(n,5,np.int16),next_form=np.zeros(n,np.int16))
    a['tok'][:,0]=1; a['tok'][:,1]=1; a['tok'][:,4:6]=.25
    a['effects'][:,0,:4]=[9,1,3500/18000,1-15000/32000]
    meta = dict(feature_version=5,grid='lattice',card_vocab=vocab_list,corpora=[str(corpus)])
    path = tmp/'toy.npz'; np.savez(path,meta=json.dumps(meta),**a)
    return path, a


def test_partitions_are_replay_disjoint(work_dir):
    _, arr = synthetic_dataset(work_dir)
    tr,sel,test=scale.partitions(arr)
    sets=[set(arr['rep'][i]) for i in (tr,sel,test)]
    assert not sets[0]&sets[1] and not sets[0]&sets[2] and not sets[1]&sets[2]
    assert len(tr)+len(sel)+len(test)==len(arr['rep'])


def test_failure_always_writes_summary_and_done(work_dir):
    args=scale.parser().parse_args(['--out',str(work_dir),'--device','cpu'])
    assert scale.execute(args)==1
    assert (work_dir/'DONE').read_text().strip()=='FAILED'
    assert (work_dir/'SUMMARY.txt').read_text().startswith('Verdict:')
    assert 'no evidence' in (work_dir/'SUMMARY.txt').read_text()
    old=(work_dir/'SUMMARY.txt').read_bytes()
    with pytest.raises(FileExistsError):
        scale.execute(args)
    assert (work_dir/'SUMMARY.txt').read_bytes()==old


def test_four_arm_cpu_integration(work_dir,monkeypatch):
    path,_=synthetic_dataset(work_dir)
    out=work_dir/'results'
    original=scale.latency
    monkeypatch.setattr(scale,'latency',lambda model,b,device: original(model,b,device,iterations=2))
    args=scale.parser().parse_args(['--data',str(path),'--out',str(out),'--device','cpu','--allow-cpu-smoke',
        '--amp','none','--epochs','1','--min-epochs','1','--bs','4','--eval-bs','4','--bootstrap-draws','100'])
    assert scale.execute(args)==0, (out/'failure.txt').read_text() if (out/'failure.txt').exists() else ''
    report=json.loads((out/'report.json').read_text())
    assert report['status']=='SMOKE ONLY' and set(report['arms'])==set('ABCD')
    for arm in 'ABCD':
        st=torch.load(out/f'{arm}.pt',weights_only=False)
        cfg=next(a for a in scale.arm_configs() if a.name==arm)
        model=scale.construct(cfg,len(st['card_vocab']))
        model.load_state_dict(st['model'],strict=True)
        assert (out/f'{arm}_held_out.npz').exists() and (out/f'{arm}.jsonl').exists()
        assert report['arms'][arm]['latency']['cpu']['mean_ms']>0
    assert (out/'DONE').read_text().strip()=='SMOKE ONLY'
    assert (out/'SUMMARY.txt').read_text().startswith('Verdict: capacity no evidence; richer inputs no evidence.')
    from pipeline.model_gen import load_model
    with pytest.raises(ValueError,match='Unsupported checkpoint architecture'):
        load_model(out/'D.pt','cpu')


def test_area_timeline_keeps_later_duplicate_tick_frame():
    # native recordings can repeat their last frame at the same tick (pod E, 10-12): later frame wins, no raise
    f = lambda t: {'tick': t, 'public_objects': {'area_effects': []}}  # noqa: E731
    out = public_area_timeline([f(0), f(10), f(10)], {})
    assert [t for t, _ in out] == [0, 10]
