import copy
from shared import *
from pipeline.model_hand_belief_v2 import initialize,load_checkpoint
def verify_log(logs,draws,mirror):
    assert len(logs)==STEPS and [v['step'] for v in logs]==list(range(1,STEPS+1))
    for i,r in enumerate(logs):
        assert np.isfinite(r['loss']) and r['loss']>=0
        assert set(r['parts'])=={'cell','card','wait','gate','value'}
        assert all(np.isfinite(v) and v>=0 for v in r['parts'].values())
        assert abs(r['loss']-sum(r['parts'].values()))<1e-4
        assert type(r['mirror']) is bool and r['mirror']==bool(mirror[i])
        assert r['draw_sha256']==hashlib.sha256(draws[i].tobytes()).hexdigest()
        assert np.isfinite(r['seconds']) and r['seconds']>=0
        if i:assert r['seconds']>=logs[i-1]['seconds']
def main():
    p=check();assert not (HERE/'training_verified.json').exists();c.setup()
    t=read(HERE/'trained.json');assert t['complete'] and t['steps_per_arm']==STEPS and t['prepared_sha256']==sha(HERE/'prepared.json')
    train=c.indices('train');dev=c.indices('development');s=arrays(OUT/'schedule.npz')
    assert s['rows'].shape==(STEPS,128) and s['mirror'].shape==(STEPS,) and s['mirror'].dtype==bool
    rng=np.random.default_rng(SEED)
    for i in range(STEPS):
        assert np.array_equal(s['rows'][i],train[rng.choice(len(train),128)])
        assert s['mirror'][i]==(rng.random()<.5)
    assert not np.intersect1d(s['rows'],dev).size
    allfeatures=arrays(SEQ/'features.npz')
    for part,ids in [('train',train),('development',dev)]:
        z=arrays(OUT/(part+'_features.npz'));ix=np.searchsorted(allfeatures['ids'],ids)
        for k,v in z.items():np.testing.assert_array_equal(v,allfeatures[k][ix])
    parent=torch.load(INIT,map_location='cpu',weights_only=True);results={}
    for arm,enabled in ARMS.items():
        folder=OUT/arm
        for key,name in [('checkpoint','candidate.pt'),('optimizer','optimizer.pt'),('log','train.jsonl'),('run','run.json')]:
            assert sha(folder/name)==t['arms'][arm][key+'_sha256']
        logs=[json.loads(x) for x in (folder/'train.jsonl').read_text().splitlines()];verify_log(logs,s['rows'],s['mirror'])
        negatives=0
        for key,value in [('step',0),('loss',float('nan')),('loss',-1),('parts',{'cell':0}),
                          ('mirror',not bool(s['mirror'][0])),('draw_sha256','0'*64),('seconds',-1)]:
            bad=copy.deepcopy(logs);bad[0][key]=value
            try:verify_log(bad,s['rows'],s['mirror'])
            except AssertionError:negatives+=1
            else:raise AssertionError('Corrupt log accepted')
        initial,istate=initialize(INIT,enabled=enabled,seed=SEED)
        model,state=load_checkpoint(folder/'candidate.pt','cpu');run=read(folder/'run.json')
        assert state['args']==istate['args'] and state['hand_learning']==run
        assert run['enabled'] is enabled and run['initial_sha256']==sha(INIT) and run['schedule_sha256']==p['schedule_sha256']
        assert run['steps']==STEPS and run['seed']==SEED and run['batch']==128 and run['optimizer']=='fresh AdamW'
        changed=[];initial_state=initial.state_dict();final=model.state_dict();assert set(initial_state)==set(final)
        params=dict(model.named_parameters())
        for k,v in final.items():
            assert v.shape==initial_state[k].shape and v.dtype==initial_state[k].dtype and torch.isfinite(v).all()
            if k not in params:assert torch.equal(v,initial_state[k]),k
            if not torch.equal(v,initial_state[k]):changed.append(k)
        assert changed and any(k.startswith('hand_context.') for k in changed)
        opt=torch.load(folder/'optimizer.pt',map_location='cpu',weights_only=True)
        assert len(opt['param_groups'])==2
        base=[k for k in params if not k.startswith(('hand_token.','hand_context.'))]
        branch=[k for k in params if k.startswith(('hand_token.','hand_context.'))]
        names=base+branch;expected_ids=[]
        for group,lr,nn in zip(opt['param_groups'],(1e-5,1e-3),(base,branch)):
            assert group['lr']==lr and group['weight_decay']==.01 and len(group['params'])==len(nn)
            expected_ids+=group['params']
        assert set(opt['state'])==set(expected_ids) and len(expected_ids)==104
        for index,name in zip(expected_ids,names):
            item=opt['state'][index];assert int(item['step'].item())==STEPS
            for k in ('exp_avg','exp_avg_sq'):
                assert item[k].shape==params[name].shape and torch.isfinite(item[k]).all()
        results[arm]=dict(controls=dict(positive=1,negative=negatives),optimizer_parameters=104,optimizer_steps=STEPS,
            changed_tensors=changed,checkpoint_sha256=sha(folder/'candidate.pt'))
    write(HERE/'training_verified.json',dict(complete=True,steps_per_arm=STEPS,draws_per_arm=128000,arms=results,
        trained_sha256=sha(HERE/'trained.json'),prepared_sha256=sha(HERE/'prepared.json')))
    print('HAND_LEARNING_TRAINING_VERIFIED')
if __name__=='__main__':main()
