import numpy as np, sys, torch, json; sys.path.insert(0,'.')
from pipeline.dataset import load as L
from pipeline.model_v3 import S1Model, hand_mask_from_sc
from pipeline.train_s1 import Rows
a,_=L('icebow/data/pipeline/s1_dataset_v6.npz')
idx=np.flatnonzero(a['split']==1)
idx=np.sort(np.random.default_rng(0).choice(idx,20000,replace=False))
st=torch.load('icebow/data/pipeline/s1_icebow_v6lat_s0.pt',map_location='cpu')
ar=dict(st.get('args',{}) or {})
m=S1Model(d=int(ar.get('d',128)),layers=int(ar.get('layers',4))); m.load_state_dict(st['model']); m.eval()
rows=Rows(a,idx,torch.device('cpu')); ps=[]; nu=[]
with torch.no_grad():
    for s0 in range(0,len(idx),512):
        b=rows.batch(idx[s0:s0+512])
        enc=m.encode(b['tok'],b['mask'],b['sc'],b['past'])
        ps.append(torch.sigmoid(m.heads(enc,hand_mask_from_sc(b['sc']))['gate']).numpy())
        nu.append(b['mask'].sum(-1).numpy())
p=np.concatenate(ps); nun=np.concatenate(nu).astype(int)
sc=a['sc'][idx]; y=a['y_gate'][idx].astype(float); el=np.rint(sc[:,3]*10).astype(int); t=sc[:,0]*300
out=[]
for umin,umax,ulab in ((0,1,'0-1'),(2,3,'2-3'),(4,99,'4+')):
    for elo,ehi,elab in ((0,4,'0-4'),(5,7,'5-7'),(8,10,'8-10')):
        msk=(nun>=umin)&(nun<=umax)&(el>=elo)&(el<=ehi)
        if msk.sum()<40: continue
        out.append(f'  units {ulab:4s} elixir {elab:5s} n={int(msk.sum()):5d}  model {p[msk].mean():.3f}   pro {y[msk].mean():.3f}')
msk=(nun<=1)&(el>=8)&(t<60)
out.append(f'\ncaptured-live state (units<=1, elixir>=8, t<60s): n={int(msk.sum())} model {p[msk].mean():.3f}  pro {y[msk].mean():.3f}')
out.append('LIVE captured mean p in that state: 0.008')
# how often is the board nearly empty, engine vs live?
out.append(f'\nENGINE: {100*float((nun<=1).mean()):.1f}% of rows have <=1 unit; live capture had 28/37 with <=1')
open('scratchpad/gauntlet/L67/_occ.txt','w').write('\n'.join(out))
print('\n'.join(out))
