import hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
import torch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[5];LOOP=HERE.parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('hand_reference_scoring',LOOP/'development_iteration_10/shared.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
c=prior.c
OUT=ROOT/'icebow/data/bench/hand_belief_learning_20261006'
SEQ=ROOT/'icebow/data/bench/hand_retention_sequence_20261006'
INIT=c.OUT/'ordinary_v5/candidate_portable.pt'
ARMS={'hand_blind_control_v5':False,'hand_belief_v5':True}
STEPS=1000;SEED=2026100613
CONTROLS={k:prior.CONTROLS[k] for k in ('r1e_corrected','ordinary_v5')}
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,allow_nan=False,separators=(',',':'))+'\n',encoding='utf-8')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def arrays(p):
    with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def sources():
    files=list((ROOT/'pipeline').glob('*.py'))+list(HERE.glob('*.py'))+[HERE/'PLAN.md',HERE/'METRICS.md',
        HERE.parent/'MODEL_METRICS.md',HERE.parent/'MODEL_METRICS_V2.md',HERE.parent/'model_verified.json',HERE.parent/'mirror_replays_verified.json',HERE.parent/'sequence_data/verified.json',
        HERE.parent/'sequence_data/collected.json',HERE.parent/'sequence_data/started.json',SEQ/'features.npz',
        INIT,c.DATA,c.SOURCE,c.OUT/'indices.npz',LOOP/'development_iteration_10/shared.py',c.HERE/'common.py',
        c.HERE/'metrics.py',c.HERE/'recount_v2.py',LOOP/'development_iteration_4/extra_masks.py',
        prior.MASKS,prior.DEFENSE,prior.CONTEXT,prior.CONTEXT_ROWS,SEQ/'audit.npz',
        LOOP/'development_iteration_10/results_verified.json',*CONTROLS.values()]
    return {str(p.relative_to(ROOT)):sha(p) for p in files}
def check():
    p=read(HERE/'prepared.json');assert p['complete'] and p['sources']==sources()
    assert p['schedule_sha256']==sha(OUT/'schedule.npz')
    for part,h in p['feature_hashes'].items():assert sha(OUT/(part+'_features.npz'))==h
    return p
class HandRows:
    def __init__(self,base,features,device):
        self.base=base;self.idx=base.idx;self.features={k:torch.as_tensor(v,device=device) for k,v in features.items()}
    def batch(self,ix):
        b=self.base.batch(ix)
        for k,v in self.features.items():b[k]=v[torch.as_tensor(ix,device=v.device)]
        return b
def load_part(part,device):
    ids,sub,meta,base=c.load_part(part,device)
    z=arrays(OUT/(part+'_features.npz'));assert set(z)=={'ids','opp_hand','opp_hand_quality'}
    pos=np.searchsorted(z['ids'],ids);assert np.array_equal(z['ids'][pos],ids)
    return ids,sub,meta,HandRows(base,{k:z[k][pos] for k in ('opp_hand','opp_hand_quality')},device)
def audit_masks(ids,cv):
    z=arrays(SEQ/'audit.npz');f=arrays(SEQ/'features.npz');pos=np.searchsorted(z['ids'],ids)
    assert np.array_equal(z['ids'][pos],ids) and np.array_equal(z['ids'],f['ids'])
    a=z['descriptors'][pos];q=f['opp_hand_quality'][pos]
    m={f'retention_status_{j}':a[:,0]==j for j in range(6)}
    m.update(retention_truncated=a[:,8]==1,retention_complete_window=a[:,8]==0,
        retention_enemy_revealed=a[:,7]==1,hand_full=q[:,1]==1,hand_partial=q[:,1]==0,
        hand_issue=q[:,2]==1,hand_no_issue=q[:,2]==0)
    for card in ('ice-spirit','skeletons','tesla','x-bow','knight','the-log','rocket','tornado'):
        if card in cv:m['retention_response_'+card]=np.isin(a[:,0],[4,5])&(a[:,2]==cv.index(card))
    return m,a
