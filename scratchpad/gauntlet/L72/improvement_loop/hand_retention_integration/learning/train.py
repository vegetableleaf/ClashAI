import time
from shared import *
from pipeline.model_hand_belief_v2 import initialize
def main():
    p=check();assert not (HERE/'training_started.json').exists()
    write(HERE/'training_started.json',dict(prepared_sha256=sha(HERE/'prepared.json')))
    c.setup();assert torch.cuda.is_available()
    ids,sub,meta,rows=load_part('train','cuda');s=arrays(OUT/'schedule.npz');pos=np.searchsorted(ids,s['rows'])
    assert np.array_equal(ids[pos],s['rows']);results={}
    for arm,enabled in ARMS.items():
        folder=OUT/arm;folder.mkdir()
        model,state=initialize(INIT,enabled=enabled,seed=SEED);model=model.to('cuda')
        base=[v for k,v in model.named_parameters() if not k.startswith(('hand_token.','hand_context.'))]
        new=[v for k,v in model.named_parameters() if k.startswith(('hand_token.','hand_context.'))]
        opt=torch.optim.AdamW([dict(params=base,lr=1e-5),dict(params=new,lr=1e-3)],weight_decay=.01)
        assert not opt.state
        config=dict(arm=arm,enabled=enabled,steps=STEPS,batch=128,seed=SEED,initial_sha256=sha(INIT),
            schedule_sha256=p['schedule_sha256'],prepared_sha256=sha(HERE/'prepared.json'),
            optimizer='fresh AdamW',base_lr=1e-5,branch_lr=1e-3,weight_decay=.01,clip_norm=1,
            loss='original five terms',selection='final1000only',training_rows=len(ids))
        write(folder/'run.json',config);torch.manual_seed(SEED);begin=time.time()
        with (folder/'train.jsonl').open('x') as log:
            for i,chosen in enumerate(pos):
                b=c.augment(rows.batch(chosen),bool(s['mirror'][i]));loss,parts=c.train_step(model,b,opt,False,meta['grid'])
                record=dict(step=i+1,loss=loss,parts=parts,mirror=bool(s['mirror'][i]),
                    draw_sha256=hashlib.sha256(s['rows'][i].tobytes()).hexdigest(),seconds=time.time()-begin)
                log.write(json.dumps(record,allow_nan=False)+'\n')
                if (i+1)%100==0:
                    log.flush();write(HERE/'progress.json',dict(arm=arm,**record));print(arm,i+1,loss,flush=True)
        checkpoint=dict(state,model=model.cpu().state_dict(),hand_learning=config)
        torch.save(checkpoint,folder/'candidate.pt');torch.save(opt.state_dict(),folder/'optimizer.pt')
        results[arm]={k+'_sha256':sha(folder/n) for k,n in [('checkpoint','candidate.pt'),('optimizer','optimizer.pt'),
            ('log','train.jsonl'),('run','run.json')]}
        del opt,model;torch.cuda.empty_cache()
        check()
    write(HERE/'trained.json',dict(complete=True,steps_per_arm=STEPS,arms=results,prepared_sha256=sha(HERE/'prepared.json'),
        accepted=False,deployed=False));print('HAND_LEARNING_TRAINED')
if __name__=='__main__':main()
