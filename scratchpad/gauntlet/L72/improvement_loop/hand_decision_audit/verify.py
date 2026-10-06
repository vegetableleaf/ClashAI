"""Scalar reconstruction independent of the producer's vector effects/counting."""
import copy,math
from collections import defaultdict
from common import *

def row_effect(play,expert,xy,b,c,desc):
 def status(p):
  has=any(bool(v) for v in p['allowed']);g=float(p['gate'])>.35 and has
  card=int(p['chosen_card'])==expert and has;cell=int(p['expert_cell'])
  dx=(cell%36/36-float(xy[0]))*18;dy=(cell//36/64-float(xy[1]))*32
  aim=math.sqrt(dx*dx+dy*dy)<=1
  return g,card,aim
 bg,bc,ba=status(b);cg,cc,ca=status(c);bs=bg and bc and ba;cs=cg and cc and ca
 lost=play and bs and not cs;gain=play and not bs and cs
 resp=int(desc[0]) in (4,5);bsp=resp and bg and int(b['chosen_card'])==int(desc[2]);csp=resp and cg and int(c['chosen_card'])==int(desc[2])
 v=[not bg and cg,bg and not cg,play and int(b['chosen_card'])!=int(c['chosen_card']),
  play and int(b['expert_cell'])!=int(c['expert_cell']),play and not bc and cc,play and bc and not cc,
  play and not ba and ca,play and ba and not ca,gain,lost,not play and bg and not cg,not play and not bg and cg,
  (not bs and cs) if play else (bg and not cg),(bs and not cs) if play else (not bg and cg),
  lost and not cg,lost and cg and not cc,lost and cg and cc and not ca,
  gain and not bg,gain and bg and not bc,gain and bg and bc and not ba,not bsp and csp,bsp and not csp]
 for code in ('000','001','010','011','100','101','110','111'):
  g=cg if code[0]=='1' else bg;card=cc if code[1]=='1' else bc;aim=ca if code[2]=='1' else ba
  v.append(g and card and aim if play else not g)
 return list(map(int,v))

def fixtures():
 l=dict(rep=np.array([1]),y_gate=np.array([1]),y_card=np.array([7]),y_xy=np.array([[0.,0.]]))
 b=dict(gate=np.array([.35]),allowed=np.array([[True,False,False,False]]),chosen_card=np.array([7]),expert_cell=np.array([0]))
 c={k:v.copy() for k,v in b.items()};c['gate'][0]=.351;d=np.array([[4,9,7,100,120,0,0,1,0]])
 for case in range(2):
  if case:
   b['gate'][0]=.8;b['expert_cell'][0]=2;c['chosen_card'][0]=8;c['expert_cell'][0]=3
  br={k:v[0] for k,v in b.items()};cr={k:v[0] for k,v in c.items()}
  ref=row_effect(True,7,l['y_xy'][0],br,cr,d[0]);actual=effects(l,b,c,d)[0].tolist()
  assert ref==actual
  vals=dict(zip(FIELDS,ref))
  if not case:assert vals['play_gain']==vals['gain_old_gate']==vals['wait_to_play']==1
  else:assert vals['play_loss']==vals['loss_new_card']==vals['aim_loss']==1 and vals['loss_new_gate']==0
 return 2

def main():
 assert not (HERE/'verified.json').exists()
 collected=read(HERE/'collected.json');started=read(HERE/'started.json');bound=bindings()
 assert collected['complete'] and collected['started_sha256']==sha(HERE/'started.json') and started['sources']==bound
 ids,l,ps,groups,desc,prior=load();n=len(ids);positive=fixtures()
 # Independently validate new memberships using scalar saved public quality/descriptor values.
 f=arrays(SEQ/'features.npz');a=arrays(SEQ/'audit.npz');index={int(oid):i for i,oid in enumerate(f['ids'])}
 with np.load(DATA,allow_pickle=False) as z:cv=json.loads(str(z['meta']))['card_vocab']
 oldm=arrays(MASKS)
 for name,mask in groups.items():
  if 'mask_'+name in oldm:assert np.array_equal(mask,oldm['mask_'+name])
  else:
   for i,oid in enumerate(ids):
    j=index[int(oid)];q=f['opp_hand_quality'][j];d=a['descriptors'][j]
    if name=='hand_full':yes=bool(q[1])
    elif name=='hand_partial':yes=not q[1]
    elif name=='hand_issue':yes=bool(q[2])
    elif name=='hand_no_issue':yes=not q[2]
    elif name=='hand_full_no_issue':yes=bool(q[1]) and not q[2]
    elif name=='hand_mirror':yes=bool(q[3])
    elif name=='hand_zero_reveal':yes=q[0]==0
    elif name=='retention_truncated':yes=bool(d[8])
    elif name.startswith('retention_status_'):yes=int(d[0])==int(name.rsplit('_',1)[1])
    elif name.startswith('retention_response_'):yes=int(d[0]) in (4,5) and int(d[2])==cv.index(name[len('retention_response_'):])
    else:raise AssertionError(name)
    assert bool(mask[i])==yes,(name,int(oid))
 expected={};matrices={}
 for control in CONTROLS:
  b=ps[control];c=ps['hand_belief_v5'];x=[]
  for i in range(n):
   br={k:b[k][i] for k in ('gate','allowed','chosen_card','expert_cell')};cr={k:c[k][i] for k in br}
   x.append(row_effect(bool(l['y_gate'][i]),int(l['y_card'][i]),l['y_xy'][i],br,cr,desc[i]))
  matrices[control]=np.asarray(x,np.int8);res={}
  for name,mask in groups.items():
   counts=[0]*len(FIELDS);by={};rows=0
   for i,yes in enumerate(mask):
    if not yes:continue
    rows+=1;rep=str(int(l['rep'][i]));entry=by.setdefault(rep,dict(rows=0,**dict.fromkeys(FIELDS,0)));entry['rows']+=1
    for j,value in enumerate(x[i]):counts[j]+=value;entry[FIELDS[j]]+=value
   res[name]=dict(rows=rows,replays=len(by),counts=dict(zip(FIELDS,counts)),by_replay=by)
  expected[control]=res
 actual=read(OUT/'groups.json');saved={k:arrays(OUT/(k+'.npz')) for k in CONTROLS}
 actual_hashes={p.name:sha(p) for p in OUT.iterdir()}
 def validate(report,caches,sources,hashes):
  assert report==expected and sources==bound and hashes==actual_hashes
  for k,z in caches.items():
   assert np.array_equal(z['ids'],ids) and z['fields'].tolist()==FIELDS and np.array_equal(z['effects'],matrices[k])
 validate(actual,saved,started['sources'],collected['outputs'])
 negative=0
 for case in range(8):
  report=copy.deepcopy(actual);caches=copy.deepcopy(saved);sources=dict(started['sources']);hashes=dict(collected['outputs']);k=CONTROLS[0]
  if case==0:caches[k]['ids'][0]=-1
  elif case==1:caches[k]['effects'][0,0]^=1
  elif case==2:caches[k]['fields']=caches[k]['fields'][::-1]
  elif case==3:report[k]['all']['rows']+=1
  elif case==4:report[k]['all']['by_replay'][next(iter(report[k]['all']['by_replay']))]['card_gain']+=1
  elif case==5:del report[k]['rocket']
  elif case==6:sources[next(iter(sources))]='bad'
  else:hashes[next(iter(hashes))]='bad'
  try:validate(report,caches,sources,hashes)
  except AssertionError:negative+=1
  else:raise AssertionError('Corruption passed')
 assert negative==8 and positive==2 and bindings()==bound
 compact={k:{g:{f:v for f,v in r.items() if f!='by_replay'} for g,r in rows.items()} for k,rows in expected.items()}
 write(HERE/'verified.json',dict(complete=True,rows=n,groups=len(groups),controls=dict(positive=positive,negative=negative),
  summaries=compact,collected_sha256=sha(HERE/'collected.json'),outputs=actual_hashes,model_calls=0,optimizer_updates=0))
 print('HAND_DECISIONS_VERIFIED')

if __name__=='__main__':main()
