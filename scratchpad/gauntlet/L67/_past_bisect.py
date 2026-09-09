import json, sys, numpy as np, torch; sys.path.insert(0,'.')
from pipeline.dataset import load as L
from pipeline.model_v3 import S1Model, hand_mask_from_sc
recs=[json.loads(l) for l in open('icebow/data/low_gate_states.jsonl',encoding='utf-8') if l.strip()][-60:]
st=torch.load('icebow/data/pipeline/s1_icebow_v6lat_s0.pt',map_location='cpu'); ar=dict(st.get('args',{}) or {})
m=S1Model(d=int(ar.get('d',128)),layers=int(ar.get('layers',4))); m.load_state_dict(st['model']); m.eval()
a,_=L('icebow/data/pipeline/s1_dataset_v6.npz')
tp=a['past']; ok=np.flatnonzero(tp[:,0,0]>=0)
rng=np.random.default_rng(0)
def score(r,past):
    tt=torch.tensor(np.array(r['tok'],dtype=np.float32))[None]; mm=torch.tensor(np.array(r['mask'],dtype=bool))[None]
    ss=torch.tensor(np.array(r['sc'],dtype=np.float32))[None]; pp=torch.tensor(np.array(past,dtype=np.float32))[None]
    with torch.no_grad():
        enc=m.encode(tt,mm,ss,pp)
        return float(torch.sigmoid(m.heads(enc,hand_mask_from_sc(ss))['gate'][0]).item())
def variants(p):
    p=np.array(p,dtype=np.float32); out={'as captured':p}
    e=p.copy(); e[:]=-1.0; out['empty']=e
    y=p.copy(); msk=y[:,0]>=0; y[msk,3]=5.0; out['ages->5s']=y
    z=p.copy(); z[msk,1]=0.5; z[msk,2]=0.61; out['xy->training median']=z
    s2=p.copy(); s2[msk,0]=rng.integers(0,8,size=int(msk.sum())); out['slots randomised']=s2
    out['whole past from TRAINING row']=tp[ok[rng.integers(0,len(ok))]].copy()
    return out
agg={}
for r in recs:
    b=score(r,r['past'])
    for k,v in variants(r['past']).items():
        agg.setdefault(k,[]).append(score(r,v)-b)
print('captured mean p: %.4f' % np.mean([score(r,r['past']) for r in recs]))
for k,v in sorted(agg.items(), key=lambda kv:-np.mean(kv[1])):
    print('  %-30s delta %+.4f   -> p %.4f' % (k, np.mean(v), np.mean([score(r,r['past']) for r in recs])+np.mean(v)))
