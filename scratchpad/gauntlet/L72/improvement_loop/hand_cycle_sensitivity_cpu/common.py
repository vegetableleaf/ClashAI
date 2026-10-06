import hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];LOOP=HERE.parent
sys.path.insert(0,str(ROOT))
OLD=LOOP/'hand_retention_integration/learning'
BASE=ROOT/'icebow/data/bench/hand_belief_learning_20261006'
SEQ=ROOT/'icebow/data/bench/hand_retention_sequence_20261006'
OUT=ROOT/'icebow/data/bench/hand_cycle_sensitivity_cpu_20261006'
DATA=ROOT/'icebow/data/bench/spawner_identity_20261005/gen_dataset_v5_public.npz'
RAW=ROOT/'icebow/data/bench/match_adaptation_20261005/rows.npz'
INDEX=ROOT/'icebow/data/bench/development_iteration_1_20261005/indices.npz'
ARMS=('hand_blind_control_v5','hand_belief_v5');SELECT=np.arange(0,1000,125)
HEADS=('gate','card','wait','value','cell')

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(json.dumps(v,allow_nan=False,separators=(',',':')),encoding='utf-8')
def arrays(p):
 with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def bindings():
 files=[*HERE.glob('*.py'),HERE/'PLAN.md',HERE/'METRICS.md',*list((ROOT/'pipeline').glob('*.py')),
  LOOP/'development_iteration_1/common.py',OLD/'prepared.json',OLD/'trained.json',OLD/'results_verified.json',
  OLD/'reviewed_results.json',LOOP/'hand_decision_audit/reviewed.json',DATA,RAW,INDEX,
  BASE/'schedule.npz',SEQ/'features.npz',*[BASE/a/'candidate.pt' for a in ARMS]]
 failed=LOOP/'hand_cycle_sensitivity'
 files += [*failed.glob('*.py'),failed/'PLAN.md',failed/'METRICS.md',failed/'started.json',failed/'chain_failed.json',failed/'DIAGNOSIS.md',
  ROOT/'scratchpad/gauntlet/L71/integration/checks/l72-hand-cycle-collect.json',ROOT/'scratchpad/gauntlet/L71/integration/checks/l72-hand-cycle-collect.out',
  *list((ROOT/'icebow/data/bench/hand_cycle_sensitivity_20261006').glob('*.npz'))]
 return {str(p.relative_to(ROOT)):sha(p) for p in files}
def sample_ids():
 p=read(OLD/'prepared.json');assert p['complete'] and p['schedule_sha256']==sha(BASE/'schedule.npz')
 s=arrays(BASE/'schedule.npz');ids=s['rows'][SELECT].reshape(-1)
 assert len(ids)==1024 and np.isin(ids,arrays(INDEX)['train']).all()
 return ids,s['mirror'][SELECT]
def censor(hand,quality):
 h=hand.copy();q=quality.copy();mask=h[...,0]>0
 h[...,1:]=0;h[...,3]=mask;h[...,5]=mask;q[:,1]=0
 return h,q
def groups(sample,cv):
 q=sample['quality_full'];play=sample['y_gate']==1
 g=dict(all=np.ones(len(play),bool),play=play,wait=~play,full=q[:,1]>0,partial=q[:,1]==0,
  full_no_issue=(q[:,1]>0)&(q[:,2]==0),issue=q[:,2]>0,zero_reveal=q[:,0]==0)
 for key in ('ice-spirit','skeletons','tesla','x-bow','knight','the-log','rocket','tornado'):
  g['expert_'+key]=play&(sample['y_card']==cv.index(key))
 return g
def row_measures(full,masked,sample):
 n=len(sample['ids']);rows={}
 for name in HEADS:
  a=full[name].reshape(n,-1);b=masked[name].reshape(n,-1);finite=np.isfinite(a)
  assert np.array_equal(finite,np.isfinite(b)) and finite.any(1).all()
  assert not np.isnan(a).any() and not np.isnan(b).any()
  assert np.isfinite(a).all() if name not in ('card','wait') else (np.isneginf(a[~finite]).all() and np.isneginf(b[~finite]).all())
  delta=np.zeros_like(a,dtype=np.float64);np.subtract(b.astype(np.float64),a.astype(np.float64),out=delta,where=finite)
  rows[name+'_signed']=delta.sum(1)/finite.sum(1)
  rows[name+'_absolute']=np.abs(delta).sum(1)/finite.sum(1)
  rows[name+'_max']=np.abs(delta).max(1)
  if name!='gate':rows[name+'_argmax_changed']=(a.argmax(1)!=b.argmax(1)).astype(np.int64)
 allow=sample['allowed'];called=[];cards=[]
 for z in (full,masked):
  gate=1/(1+np.exp(-z['gate'].astype(np.float64)));called.append((gate>.35)&allow.any(1))
  slot=np.where(allow,z['card'],-np.inf).argmax(1)
  cards.append(sample['hand_card'][np.arange(n),slot])
 rows['wait_to_play']=(~called[0]&called[1]).astype(np.int64)
 rows['play_to_wait']=(called[0]&~called[1]).astype(np.int64)
 rows['chosen_card_changed']=(cards[0]!=cards[1]).astype(np.int64)
 rows['called_card_changed']=((cards[0]!=cards[1])&called[0]&called[1]).astype(np.int64)
 return rows
def reduce_rows(rows,ix):
 out={}
 for k,v in rows.items():
  a=v[ix]
  out[k]=(int(a.sum()) if v.dtype.kind in 'iu' else float(a.max(initial=0)) if k.endswith('_max') else float(a.mean()) if len(ix) else 0.)
 return out
def summarize(rows,sample,cv):
 result={}
 for name,mask in groups(sample,cv).items():
  ix=np.flatnonzero(mask);by={}
  for rep in np.unique(sample['rep'][ix]):
   j=ix[sample['rep'][ix]==rep];by[str(int(rep))]=dict(rows=len(j),metrics=reduce_rows(rows,j))
  result[name]=dict(rows=len(ix),replays=len(by),metrics=reduce_rows(rows,ix),by_replay=by)
 return result
