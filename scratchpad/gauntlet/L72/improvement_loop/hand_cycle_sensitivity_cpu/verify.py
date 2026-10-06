"""No model calls: independent sampling, scalar censorship and saved-output math."""
import copy,math
from common import *
from pipeline.opp_elixir_count import card_cost

def scalar_rows(a,b,s):
 result={};n=len(s['ids'])
 for head in HEADS:
  x=a[head].reshape(n,-1);y=b[head].reshape(n,-1)
  signed=[];absolute=[];maxima=[];arg=[]
  for left,right in zip(x,y):
   values=[]
   for l,r in zip(left,right):
    if not math.isfinite(float(l)) or not math.isfinite(float(r)):
     assert head in ('card','wait') and float(l)==float(r)==-math.inf
    else:values.append(float(r)-float(l))
   assert values;signed.append(math.fsum(values)/len(values));absolute.append(math.fsum(abs(v) for v in values)/len(values))
   maxima.append(max(abs(v) for v in values));arg.append(int(max(range(len(left)),key=lambda j:float(left[j]))!=max(range(len(right)),key=lambda j:float(right[j]))))
  result[head+'_signed']=np.array(signed);result[head+'_absolute']=np.array(absolute);result[head+'_max']=np.array(maxima)
  if head!='gate':result[head+'_argmax_changed']=np.array(arg,np.int64)
 for key in ('wait_to_play','play_to_wait','chosen_card_changed','called_card_changed'):result[key]=[]
 for i in range(n):
  calls=[];choices=[]
  for z in (a,b):
   candidates=[j for j,allowed in enumerate(s['allowed'][i]) if allowed]
   calls.append(1/(1+math.exp(-float(z['gate'][i])))>.35 and bool(candidates))
   slot=max(candidates,key=lambda j:float(z['card'][i,j])) if candidates else 0
   choices.append(int(s['hand_card'][i,slot]))
  result['wait_to_play'].append(int(not calls[0] and calls[1]));result['play_to_wait'].append(int(calls[0] and not calls[1]))
  result['chosen_card_changed'].append(int(choices[0]!=choices[1]));result['called_card_changed'].append(int(choices[0]!=choices[1] and calls[0] and calls[1]))
 for key in ('wait_to_play','play_to_wait','chosen_card_changed','called_card_changed'):result[key]=np.array(result[key],np.int64)
 return result

def close(a,b):
 assert type(a)==type(b),(type(a),type(b))
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:close(a[k],b[k])
 elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12),(a,b)
 else:assert a==b,(a,b)

def scalar_groups(rows,s,cv):
 names=['all','play','wait','full','partial','full_no_issue','issue','zero_reveal']+['expert_'+k for k in ('ice-spirit','skeletons','tesla','x-bow','knight','the-log','rocket','tornado')]
 result={}
 def reduced(indices):
  out={}
  for k,v in rows.items():
   data=[v[i].item() for i in indices]
   out[k]=sum(data) if v.dtype.kind in 'iu' else max(data,default=0.) if k.endswith('_max') else math.fsum(data)/len(data) if data else 0.
  return out
 for name in names:
  ix=[]
  for i in range(len(s['ids'])):
   play=int(s['y_gate'][i])==1;q=s['quality_full'][i]
   if name=='all':yes=True
   elif name=='play':yes=play
   elif name=='wait':yes=not play
   elif name=='full':yes=bool(q[1])
   elif name=='partial':yes=not q[1]
   elif name=='full_no_issue':yes=bool(q[1]) and not q[2]
   elif name=='issue':yes=bool(q[2])
   elif name=='zero_reveal':yes=q[0]==0
   else:yes=play and int(s['y_card'][i])==cv.index(name[len('expert_'):])
   if yes:ix.append(i)
  reps={int(s['rep'][i]) for i in ix};by={}
  for rep in reps:
   selected=[i for i in ix if int(s['rep'][i])==rep];by[str(rep)]=dict(rows=len(selected),metrics=reduced(selected))
  result[name]=dict(rows=len(ix),replays=len(by),metrics=reduced(ix),by_replay=by)
 return result

def fixtures():
 s=dict(ids=np.array([1]),allowed=np.array([[1,1,0,0]],bool),hand_card=np.array([[1,2,3,4]]))
 a=dict(gate=np.array([-1.]),card=np.array([[1.,0.,-np.inf,-np.inf]]),wait=np.array([[1.,0.]]),value=np.array([[0.,1.]]),cell=np.array([[0.,1.,2.]]))
 for case in range(2):
  b={k:v.copy() for k,v in a.items()}
  if case:b['gate'][0]=1;b['card'][0,:2]=[0,2];b['cell'][0]=[4,0,0]
  one=row_measures(a,b,s);two=scalar_rows(a,b,s)
  for k in one:np.testing.assert_allclose(one[k],two[k],rtol=1e-10,atol=1e-12)
  if case:assert two['wait_to_play'][0]==two['chosen_card_changed'][0]==two['cell_argmax_changed'][0]==1
  else:assert all(not np.any(v) for v in two.values())
 return 2

def main():
 assert not (HERE/'verified.json').exists();c=read(HERE/'collected.json');start=read(HERE/'started.json');bound=bindings()
 assert c['complete'] and c['started_sha256']==sha(HERE/'started.json') and start['sources']==bound
 hashes={p.name:sha(p) for p in OUT.iterdir()};assert hashes==c['outputs']
 s=arrays(OUT/'sample.npz');train=arrays(INDEX)['train'];rng=np.random.default_rng(2026100613);draw=[];mirror=[]
 for _ in range(1000):draw.append(train[rng.choice(len(train),128)]);mirror.append(rng.random()<.5)
 draw=np.array(draw);mirror=np.array(mirror);schedule=arrays(BASE/'schedule.npz')
 assert np.array_equal(draw,schedule['rows']) and np.array_equal(mirror,schedule['mirror'])
 assert np.array_equal(s['ids'],draw[SELECT].reshape(-1)) and np.array_equal(s['mirror'],np.repeat(mirror[SELECT],128))
 raw=arrays(RAW);f=arrays(SEQ/'features.npz');rp={int(v):i for i,v in enumerate(raw['ids'])};fp={int(v):i for i,v in enumerate(f['ids'])}
 with np.load(DATA,allow_pickle=False) as z:assert np.array_equal(s['hand_card'],z['hand_card'][s['ids']])
 h=np.zeros_like(s['hand_full']);q=s['quality_full'].copy();q[:,1]=0
 for i,oid in enumerate(s['ids']):
  j=rp[int(oid)];k=fp[int(oid)]
  for key in ('rep','y_gate','y_card','y_xy','sc'):assert np.array_equal(s[key][i],raw[key][j]),key
  assert np.array_equal(s['hand_full'][i],f['opp_hand'][k]) and np.array_equal(s['quality_full'][i],f['opp_hand_quality'][k])
  for slot,token in enumerate(f['opp_hand'][k]):
   if token[0]>0:h[i,slot]=[token[0],0,0,1,0,1]
  elixir=math.floor(float(np.float32(s['sc'][i,3]*np.float32(10)+np.float32(1e-3))))
  for slot,card in enumerate(s['hand_card'][i]):
   cost=card_cost(c['card_vocab'][int(card)].replace('-','_')) or 0
   assert bool(s['allowed'][i,slot])==(int(card)>0 and cost<=elixir)
 assert np.array_equal(h,s['hand_censored']) and np.array_equal(q,s['quality_censored'])
 base=read(OUT/'base_hashes.json');assert len(base)==32
 for bi in range(8):
  records=[r for r in base if r['batch']==bi];assert len(records)==4 and len({r['sha256'] for r in records})==1
  assert {(r['arm'],r['condition']) for r in records}=={(a,b) for a in ARMS for b in ('full','censored')}
 expected={};expected_rows={};saved_rows={};positive=fixtures()
 for arm in ARMS:
  a=arrays(OUT/(arm+'_full.npz'));b=arrays(OUT/(arm+'_censored.npz'))
  assert set(a)==set(b)==set(HEADS)|{'g'} and a['cell'].shape==b['cell'].shape==(1024,2304)
  assert np.isfinite(a['g']).all() and np.isfinite(b['g']).all()
  assert c['weights'][arm]['unchanged'] and c['weights'][arm]['gradients_empty']
  assert c['weights'][arm]['checkpoint_sha256']==sha(BASE/arm/'candidate.pt')
  if arm==ARMS[0]:
   for key in a:assert np.array_equal(a[key],b[key]),key
  rows=scalar_rows(a,b,s);expected_rows[arm]=rows;saved_rows[arm]=arrays(OUT/(arm+'_row_measures.npz'))
  expected[arm]=scalar_groups(rows,s,c['card_vocab'])
 actual=read(OUT/'groups.json')
 def validate(report,measures,inputs,sources,outputs):
  close(report,expected);assert sources==bound and outputs==hashes
  for k,v in s.items():assert np.array_equal(v,inputs[k]),k
  for arm in ARMS:
   assert measures[arm].keys()==expected_rows[arm].keys()
   for key,v in expected_rows[arm].items():
    if v.dtype.kind in 'iu':assert np.array_equal(measures[arm][key],v)
    else:np.testing.assert_allclose(measures[arm][key],v,rtol=1e-10,atol=1e-12)
 validate(actual,saved_rows,s,start['sources'],c['outputs']);negative=0
 for case in range(8):
  r=copy.deepcopy(actual);m=copy.deepcopy(saved_rows);x=copy.deepcopy(s);src=dict(bound);out=dict(hashes)
  if case==0:x['ids'][0]=-1
  elif case==1:x['hand_censored'][0,0,1]=1
  elif case==2:x['quality_censored'][0,1]=1
  elif case==3:m[ARMS[0]]['gate_signed'][0]=1
  elif case==4:r[ARMS[1]]['all']['metrics']['chosen_card_changed']+=1
  elif case==5:r[ARMS[1]]['all']['by_replay'][next(iter(r[ARMS[1]]['all']['by_replay']))]['rows']+=1
  elif case==6:src[next(iter(src))]='bad'
  else:out[next(iter(out))]='bad'
  try:validate(r,m,x,src,out)
  except AssertionError:negative+=1
  else:raise AssertionError('Corruption accepted')
 assert positive==2 and negative==8 and bindings()==bound
 compact={a:{g:{k:v for k,v in r.items() if k!='by_replay'} for g,r in gs.items()} for a,gs in expected.items()}
 write(HERE/'verified.json',dict(complete=True,rows=1024,model_row_views=4096,unique_rows=len(set(map(int,s['ids']))),
  replays=len(set(map(int,s['rep']))),controls=dict(positive=positive,negative=negative),summaries=compact,
  collected_sha256=sha(HERE/'collected.json'),outputs=hashes,backward_calls=0,optimizer_updates=0))
 print('HAND_CYCLE_CPU_VERIFIED')
if __name__=='__main__':main()
