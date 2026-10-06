import hashlib,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];LOOP=HERE.parent
OUT=ROOT/'icebow/data/bench/hand_decision_audit_20261006'
OLD=LOOP/'hand_retention_integration/learning'
SEQ=ROOT/'icebow/data/bench/hand_retention_sequence_20261006'
BASE=ROOT/'icebow/data/bench/hand_belief_learning_20261006'
RAW=ROOT/'icebow/data/bench/match_adaptation_20261005/rows.npz'
MASKS=ROOT/'icebow/data/bench/development_iteration_4_20261005/development_masks.npz'
DATA=ROOT/'icebow/data/bench/spawner_identity_20261005/gen_dataset_v5_public.npz'
PATHS={'hand_blind_control_v5':BASE/'hand_blind_control_v5/predictions.npz',
       'hand_belief_v5':BASE/'hand_belief_v5/predictions.npz',
       'ordinary_v5':ROOT/'icebow/data/bench/development_iteration_1_20261005/ordinary_v5_eval_v2/predictions.npz'}
CONTROLS=('hand_blind_control_v5','ordinary_v5')
FIELDS=['wait_to_play','play_to_wait','card_changed','aim_cell_changed','card_gain','card_loss',
 'aim_gain','aim_loss','play_gain','play_loss','wait_gain','wait_loss','action_gain','action_loss',
 'loss_new_gate','loss_new_card','loss_new_aim','gain_old_gate','gain_old_card','gain_old_aim',
 'response_new_spend','response_removed_spend']+['hybrid_'+format(i,'03b') for i in range(8)]

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,allow_nan=False,separators=(',',':')),encoding='utf-8')
def arrays(p):
 with np.load(p,allow_pickle=False) as z:return {k:z[k] for k in z.files}
def bindings():
 files=[*HERE.glob('*.py'),HERE/'PLAN.md',HERE/'METRICS.md',OLD/'prepared.json',OLD/'results_verified.json',
  OLD/'reviewed_results.json',RAW,MASKS,SEQ/'audit.npz',SEQ/'features.npz',DATA,*PATHS.values()]
 return {str(p.relative_to(ROOT)):sha(p) for p in files}
def load():
 prior=read(OLD/'results_verified.json');assert prior['complete'] and read(OLD/'reviewed_results.json')['complete']
 ps={k:arrays(p) for k,p in PATHS.items()};ids=ps['hand_belief_v5']['ids'];assert len(ids)==54723
 for k,p in PATHS.items():assert sha(p)==prior['hashes'][k]['cache']
 for p in ps.values():
  assert np.array_equal(p['ids'],ids) and np.array_equal(p['allowed'],ps['hand_belief_v5']['allowed'])
  assert p['allowed'].shape==(len(ids),4) and np.isfinite(p['gate']).all()
 with np.load(DATA,allow_pickle=False) as z:cv=json.loads(str(z['meta']))['card_vocab']
 raw=arrays(RAW);ix=np.searchsorted(raw['ids'],ids);assert np.array_equal(raw['ids'][ix],ids)
 labels={k:raw[k][ix] for k in ('rep','tick','y_gate','y_card','y_xy')}
 a=arrays(SEQ/'audit.npz');f=arrays(SEQ/'features.npz');j=np.searchsorted(a['ids'],ids)
 assert np.array_equal(a['ids'],f['ids']) and np.array_equal(a['ids'][j],ids)
 desc=a['descriptors'][j];quality=f['opp_hand_quality'][j]
 m=arrays(MASKS);assert np.array_equal(m['ids'],ids)
 keys=['all','rocket','rocket_late_overtime_clock','barrel_pro','witch','night_witch','furnace',
  'defensive_sequence','defensive_rocket','phase_single_clock','phase_double_regulation_clock',
  'phase_early_overtime_clock','phase_late_overtime_clock','xbow','xbow_no_lifetime_target','combo']
 groups={k:m['mask_'+k] for k in keys}
 groups.update(hand_full=quality[:,1]>0,hand_partial=quality[:,1]==0,hand_issue=quality[:,2]>0,
  hand_no_issue=quality[:,2]==0,hand_full_no_issue=(quality[:,1]>0)&(quality[:,2]==0),
  hand_mirror=quality[:,3]>0,hand_zero_reveal=quality[:,0]==0,retention_truncated=desc[:,8]>0)
 for s in range(6):groups['retention_status_'+str(s)]=desc[:,0]==s
 for card in ('ice-spirit','skeletons','tesla','x-bow','knight','the-log','rocket','tornado'):
  groups['retention_response_'+card]=np.isin(desc[:,0],[4,5])&(desc[:,2]==cv.index(card))
 return ids,labels,ps,groups,desc,prior

def flags(labels,p):
 play=labels['y_gate']==1;has=p['allowed'].any(1);gate=(p['gate']>.35)&has
 card=(p['chosen_card']==labels['y_card'])&has
 xy=np.c_[p['expert_cell']%36/36,p['expert_cell']//36/64]
 aim=np.linalg.norm((xy-labels['y_xy'])*[18,32],axis=1)<=1
 return play,gate,card,aim

def effects(labels,b,c,desc):
 play,bg,bc,ba=flags(labels,b);_,cg,cc,ca=flags(labels,c)
 bs=bg&bc&ba;cs=cg&cc&ca;lost=play&bs&~cs;gain=play&~bs&cs
 response=np.isin(desc[:,0],[4,5]);bsp=response&bg&(b['chosen_card']==desc[:,2]);csp=response&cg&(c['chosen_card']==desc[:,2])
 cols=[~bg&cg,bg&~cg,play&(b['chosen_card']!=c['chosen_card']),play&(b['expert_cell']!=c['expert_cell']),
  play&~bc&cc,play&bc&~cc,play&~ba&ca,play&ba&~ca,gain,lost,~play&bg&~cg,~play&~bg&cg,
  np.where(play,~bs&cs,bg&~cg),np.where(play,bs&~cs,~bg&cg),lost&~cg,lost&cg&~cc,lost&cg&cc&~ca,
  gain&~bg,gain&bg&~bc,gain&bg&bc&~ba,~bsp&csp,bsp&~csp]
 for i in range(8):
  g=cg if i&4 else bg;k=cc if i&2 else bc;a=ca if i&1 else ba
  cols.append(np.where(play,g&k&a,~g))
 return np.asarray(cols,dtype=np.int8).T

def summarize(ids,labels,groups,x):
 result={}
 for name,mask in groups.items():
  idx=np.flatnonzero(mask);by={}
  for rep in np.unique(labels['rep'][idx]):
   chosen=idx[labels['rep'][idx]==rep]
   by[str(int(rep))]=dict(rows=len(chosen),**dict(zip(FIELDS,map(int,x[chosen].sum(0)))))
  result[name]=dict(rows=len(idx),replays=len(by),counts=dict(zip(FIELDS,map(int,x[idx].sum(0)))),by_replay=by)
 return result
