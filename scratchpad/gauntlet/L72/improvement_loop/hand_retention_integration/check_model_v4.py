"""Initial identity, real-row gradient, strict loader and public live-input controls."""
import copy,hashlib,json,sys,tempfile
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from pipeline.model_hand_belief_v2 import initialize,load_checkpoint,construct
from pipeline.model_gen import load_model
from pipeline.eval_gen import GenRows
from pipeline.train_rocket_curriculum import load_subset
from pipeline.train_gen import losses

PARENT=ROOT/'icebow/data/bench/development_iteration_1_20261005/ordinary_v5/candidate_portable.pt'
DATA=ROOT/'icebow/data/bench/spawner_identity_20261005/gen_dataset_v5_public.npz'
SEQ=ROOT/'icebow/data/bench/hand_retention_sequence_20261006'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    assert not (HERE/'model_verified.json').exists()
    v=json.loads((HERE/'sequence_data/verified.json').read_text());assert v['complete'] and v['features_sha256']==sha(SEQ/'features.npz')
    assert sha(PARENT)=='c0ba1ab910df50fdcbe1fcf4191aedd584c86fe94c5a6d3248359bda059db419'
    torch.set_num_threads(1)
    with np.load(ROOT/'icebow/data/bench/development_iteration_1_20261005/indices.npz') as z:ids=z['train'][:128]
    sub,meta=load_subset(DATA,ids);rows=GenRows(sub,np.arange(128),'cpu')
    with np.load(SEQ/'features.npz') as z:
        pos=np.searchsorted(z['ids'],ids);np.testing.assert_array_equal(z['ids'][pos],ids)
        features={k:torch.as_tensor(z[k][pos]) for k in ('opp_hand','opp_hand_quality')}
    b=dict(rows.batch(np.arange(128)),**features)
    parent,_=load_model(PARENT,'cpu');candidate,state=initialize(PARENT,enabled=True,seed=2026100613)
    control,cstate=initialize(PARENT,enabled=False,seed=2026100613)
    assert all(torch.equal(v,control.state_dict()[k]) for k,v in candidate.state_dict().items())
    before={k:v.clone() for k,v in candidate.state_dict().items()}
    counts=0
    for mirror in (False,True):
        # losses has the original mirror semantics, including unchanged nonspatial hand tokens.
        parent.eval();candidate.eval();control.eval()
        with torch.no_grad():
            pl,_=losses(parent,b,mirror=mirror,grid=meta['grid'])
            for m in (candidate,control):
                actual,_=losses(m,b,mirror=mirror,grid=meta['grid']);assert torch.equal(pl,actual)
        from pipeline.model_gen import mirror_gen
        mb=dict(b)
        if mirror:
            mb['tok'],mb['sc'],mb['past'],mb['xy']=mirror_gen(b['tok'],b['sc'],b['past'],b['xy'])
            op=b['opp_past'].clone();op[...,2]=torch.where(op[...,0]>0,1-op[...,2],op[...,2]);mb['opp_past']=op
            for key,cols in (('projectiles',(2,4)),('effects',(2,))):
                obj=b[key].clone()
                for col in cols:
                    known=obj[...,0]>0
                    if key=='projectiles' and col==4:known=known&(obj[...,4]>=0)&(obj[...,5]>=0)
                    obj[...,col]=torch.where(known,1-obj[...,col],obj[...,col])
                mb[key]=obj
        with torch.no_grad():
            expected=parent(mb,card=mb['card'],form=mb['form'])
            for m in (candidate,control):
                output=m(mb,card=mb['card'],form=mb['form'])
                for k in expected:assert torch.equal(expected[k],output[k]),k
                counts+=128
    loss,_=losses(candidate,b,mirror=False,grid=meta['grid']);loss.backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in candidate.parameters())
    assert candidate.hand_context[-1].weight.grad.abs().sum()>0
    assert all(torch.equal(v,candidate.state_dict()[k]) for k,v in before.items())
    candidate.zero_grad(set_to_none=True);assert all(p.grad is None for p in candidate.parameters())
    malformed=0
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'initial.pt';torch.save(dict(state,model=before),path)
        restored,loaded=load_checkpoint(path);restored.eval()
        assert all(torch.equal(v,restored.state_dict()[k]) for k,v in before.items())
        for field,value in [('architecture','wrong'),('hand_belief_version',3),('feature_version',6),('hand_information_enabled',1)]:
            bad=copy.deepcopy(loaded)
            if field=='architecture':bad[field]=value
            else:bad['args'][field]=value
            try:construct(bad)
            except ValueError:malformed+=1
            else:raise AssertionError('Malformed metadata accepted')
        bad=copy.deepcopy(loaded);del bad['model']['hand_context.2.weight'];torch.save(bad,Path(folder)/'bad.pt')
        try:load_checkpoint(Path(folder)/'bad.pt')
        except RuntimeError:malformed+=1
        else:raise AssertionError('Missing tensor accepted')
        for badbatch in ({k:v for k,v in b.items() if k!='opp_hand'},dict(b,opp_hand=b['opp_hand'][:,:7]),
                         dict(b,opp_hand_quality=torch.full_like(b['opp_hand_quality'],float('nan')))):
            try:candidate(badbatch)
            except (KeyError,ValueError):malformed+=1
            else:raise AssertionError('Malformed feature input accepted')
        # Exercise true memory-reader row path without ADB, taps or live startup.
        from pipeline.live_hand_v2 import HandGenPilot
        from pipeline.tests.test_live_gen_afford import frame
        p=HandGenPilot(path,device='cpu',extrapolate_ticks=26,public_audit=True)
        f=frame(10);p.observe(f)
        p.public.plays=[dict(tick=f['game_tick']-5,side=1-p.public.side,card='rocket',accepted=True,x=4.5,y=6.0,form=0)]
        live,info=p.row(f);audit=copy.deepcopy(p._public_audit_snapshot)
        private=copy.deepcopy(f)
        for player in private['players']:
            if int(player['side'])!=p.public.side:
                player.update(elixir_raw=999999,deck_card_ids=[999999]*8,hidden_hand=['rocket']*4,
                    next_deck_index=99,private_secret='NEVER_INPUT')
        other,_=p.row(private)
        for k in live:assert torch.equal(live[k],other[k]),k
        assert audit==p._public_audit_snapshot and 'NEVER_INPUT' not in json.dumps(audit)
        ambiguous=copy.deepcopy(private)
        for player in ambiguous['players']:
            if int(player['side'])!=p.public.side:player['hand_deck_indices']=[99]*4
        try:p.row(ambiguous)
        except ValueError as error:
            assert 'exactly one side' in str(error);malformed+=1
        else:raise AssertionError('Ambiguous reader ownership accepted')
        p.public.plays.append(dict(tick=f['game_tick']+1,side=1-p.public.side,card='the-log',x=4.5,y=6.0,form=0))
        future,_=p.row(f)
        for k in ('opp_hand','opp_hand_quality'):assert torch.equal(live[k],future[k])
        p.reset_match();empty,_=p.row(f);assert not empty['opp_hand'].any()
    # Unsaved diagnostic sensitivity: same tensors, turn on the residual only in clones.
    probe=copy.deepcopy(candidate);blind=copy.deepcopy(control)
    with torch.no_grad():
        torch.manual_seed(2026100613);probe.hand_context[-1].weight.normal_(0,.01)
        blind.load_state_dict(probe.state_dict())
    probe.eval();blind.eval()
    changed=dict(b,opp_hand=b['opp_hand'].clone(),opp_hand_quality=b['opp_hand_quality'].clone())
    changed['opp_hand'][:,:,0]=meta['card_vocab'].index('rocket');changed['opp_hand'][:,:,1]=1
    changed['opp_hand'][:,:,2:4]=0
    with torch.no_grad():
        assert not torch.equal(probe.encode_gen(b)['g'],probe.encode_gen(changed)['g'])
        assert torch.equal(blind.encode_gen(b)['g'],blind.encode_gen(changed)['g'])
        reordered=dict(changed,opp_hand=changed['opp_hand'].flip(1))
        assert torch.equal(probe.encode_gen(changed)['g'],probe.encode_gen(reordered)['g'])
    assert all(torch.equal(v,candidate.state_dict()[k]) for k,v in before.items())
    result=dict(third_failed_probe_sha256=sha(HERE/'check_model_v3.py'),third_failed_receipt_sha256=sha(ROOT/'scratchpad/gauntlet/L71/integration/checks/l72-hand-model-qualified-v3.json'),original_model_source_sha256=sha(ROOT/'pipeline/model_hand_belief.py'),second_failed_probe_sha256=sha(HERE/'check_model_v2.py'),second_failed_receipt_sha256=sha(ROOT/'scratchpad/gauntlet/L71/integration/checks/l72-hand-model-qualified-v2.json'),live_fixture_receipt_sha256=sha(ROOT/'scratchpad/gauntlet/L71/integration/checks/l72-hand-live-fixture.json'),original_failed_probe_sha256=sha(HERE/'check_model.py'),original_failed_receipt_sha256=sha(ROOT/'scratchpad/gauntlet/L71/integration/checks/l72-hand-model-qualified.json'),complete=True,parent_sha256=sha(PARENT),real_row_comparisons=counts,loss=float(loss.detach()),
        finite_backward=True,optimizer_updates=0,weights_unchanged=True,malformed_rejections=malformed,
        live_private_invariance=True,live_future_hand_invariance=True,live_reset=True,control_invariance=True,
        feature_sensitivity=True,roundtrip_exact=True,sequence_verified_sha256=sha(HERE/'sequence_data/verified.json'),
        sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),HERE/'MODEL_METRICS_V2.md',
            ROOT/'pipeline/model_hand_belief_v2.py',ROOT/'pipeline/live_hand_v2.py',HERE/'live_play_hand_v2.py']})
    (HERE/'model_verified.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result));print('HAND_MODEL_QUALIFIED')
if __name__=='__main__':main()
