import numpy as np, sys, torch; sys.path.insert(0,'.')
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
sc=a['sc'][idx]; el=np.rint(sc[:,3]*10).astype(int); t=sc[:,0]*300
L2=[]
L2.append('ENGINE: fraction of frames with p<0.02  (the live run measured 37/205 = 18.0%)')
L2.append('  all rows                     %.1f%%' % (100*float((p<0.02).mean())))
L2.append('  units<=1 (any elixir)        %.1f%%' % (100*float((p[nun<=1]<0.02).mean())))
L2.append('  units<=1 and elixir>=8       %.1f%%' % (100*float((p[(nun<=1)&(el>=8)]<0.02).mean())))
L2.append('  units<=1 and t<60s           %.1f%%' % (100*float((p[(nun<=1)&(t<60)]<0.02).mean())))
L2.append('  units>=2                     %.1f%%' % (100*float((p[nun>=2]<0.02).mean())))
L2.append('')
L2.append('ENGINE occupancy: %.1f%% of rows have <=1 unit' % (100*float((nun<=1).mean())))
open('scratchpad/gauntlet/L67/_occ2.txt','w').write('\n'.join(L2)); print('\n'.join(L2))
