import numpy as np, sys, torch, collections; sys.path.insert(0,'.')
from pipeline.dataset import load as L
from pipeline.model_v3 import S1Model, hand_mask_from_sc
from pipeline.train_s1 import Rows
a,_=L('icebow/data/pipeline/s1_dataset_v6.npz')
P=a['past']
tri=[tuple(int(x) for x in p[:,0]) for p in P]
c=collections.Counter(tri)
tot=len(tri)
print('TRAINING history frequency (slot triples, most-recent first):')
for t in [(4,6,0),(6,0,2)]:
    print('  %-12s %6d rows (%.3f%%)' % (str(t), c[t], 100*c[t]/tot))
print('  most common overall:', c.most_common(3))
print('  distinct triples seen: %d' % len(c))
# model p on TRAINING rows carrying the live history
idx=np.flatnonzero(np.array([t==(4,6,0) for t in tri]) & (a['split']==1))
print('  VAL rows with history (4,6,0): %d' % len(idx))
if len(idx)>20:
    st=torch.load('icebow/data/pipeline/s1_icebow_v6lat_s0.pt',map_location='cpu'); ar=dict(st.get('args',{}) or {})
    m=S1Model(d=int(ar.get('d',128)),layers=int(ar.get('layers',4))); m.load_state_dict(st['model']); m.eval()
    rows=Rows(a,idx,torch.device('cpu')); ps=[]
    with torch.no_grad():
        for s0 in range(0,len(idx),512):
            b=rows.batch(idx[s0:s0+512]); enc=m.encode(b['tok'],b['mask'],b['sc'],b['past'])
            ps.append(torch.sigmoid(m.heads(enc,hand_mask_from_sc(b['sc']))['gate']).numpy())
    p=np.concatenate(ps)
    print('  model p on those ENGINE rows: mean %.4f  frac<0.02 %.3f  (pro plays %.3f)' % (p.mean(), (p<0.02).mean(), a['y_gate'][idx].mean()))
