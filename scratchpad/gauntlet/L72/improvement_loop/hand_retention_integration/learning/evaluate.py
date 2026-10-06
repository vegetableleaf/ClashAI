from shared import *
from pipeline.model_hand_belief_v2 import load_checkpoint
def main():
    check();assert not (HERE/'evaluation_started.json').exists()
    tv=read(HERE/'training_verified.json');assert tv['complete'] and tv['trained_sha256']==sha(HERE/'trained.json')
    write(HERE/'evaluation_started.json',dict(training_verified_sha256=sha(HERE/'training_verified.json')))
    c.setup();ids,sub,meta,rows=load_part('development','cuda');cv=meta['card_vocab'];n=len(ids)
    ms,target=prior.masks(ids);extra,audit=audit_masks(ids,cv);ms.update(extra);met=prior.scoring();allow=met['allowed'](sub,cv)
    results={}
    for arm in ARMS:
        folder=OUT/arm;assert sha(folder/'candidate.pt')==tv['arms'][arm]['checkpoint_sha256']
        model,state=load_checkpoint(folder/'candidate.pt','cuda');model.eval();assert state['card_vocab']==cv
        p=dict(allowed=allow,gate=np.empty(n,np.float32),gate_logit=np.empty(n,np.float32),
            chosen_card=np.empty(n,np.int32),card_logits=np.empty((n,4),np.float32),
            expert_cell=np.empty(n,np.int32),log_cell=np.empty(n,np.int32))
        with torch.inference_mode():
            for lo in range(0,n,128):
                ix=np.arange(lo,min(lo+128,n));b=rows.batch(ix);enc=model.encode_gen(b);h=model.heads_gen(enc,b)
                p['gate'][ix]=h['gate'].sigmoid().cpu().numpy();p['gate_logit'][ix]=h['gate'].cpu().numpy()
                p['card_logits'][ix]=h['card'].cpu().numpy()
                slot=h['card'].masked_fill(~torch.as_tensor(allow[ix],device='cuda'),-torch.inf).argmax(-1).cpu().numpy()
                p['chosen_card'][ix]=sub['hand_card'][ix,slot]
                p['expert_cell'][ix]=model.cell_logits_gen(enc,b['card'],b['form']).argmax(-1).cpu().numpy()
                p['log_cell'][ix]=model.cell_logits_gen(enc,torch.full_like(b['card'],cv.index('the-log')),torch.zeros_like(b['card'])).argmax(-1).cpu().numpy()
        counts=met['summarize'](sub,p,cv,ms,target);np.savez_compressed(folder/'predictions.npz',ids=ids,**p)
        results[arm]=dict(rows=n,counts=counts,cache_sha256=sha(folder/'predictions.npz'),checkpoint_sha256=sha(folder/'candidate.pt'))
        print('EVALUATED',arm,n,flush=True);del model;torch.cuda.empty_cache()
    write(HERE/'evaluated.json',dict(complete=True,arms=results,training_verified_sha256=sha(HERE/'training_verified.json'),accepted=False,deployed=False))
    check();print('HAND_LEARNING_EVALUATED')
if __name__=='__main__':main()
