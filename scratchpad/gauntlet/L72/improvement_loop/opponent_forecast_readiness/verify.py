"""Scalar reconstruction from original commands/public streams; no producer algorithms."""
import copy
from collections import Counter,defaultdict
from common import *
from pipeline import vocab

def canonical(name):
 value=vocab.engine_key(name)
 return vocab.base_key(value).replace('_','-') if value else None
def pub_ref(events,side,gid):
 result=[]
 for index,event in enumerate(events):
  if event['side']==side or not event.get('accepted',True) or event.get('ability'):continue
  result.append((int(event['tick']),index,gid.get(canonical(event.get('card') or ''),0),int(bool(event.get('gap_before'))),int(bool(event.get('identity_unknown')))))
 return sorted(result,key=lambda x:(x[0],x[1]))
def cmd_ref(log,side,gid):
 result=[]
 for index,event in enumerate(log):
  if not event.get('accepted') or event.get('ability') or not event.get('card') or event['side']==side:continue
  when=event['engine_tick'] if 'engine_tick' in event else event['tick']
  result.append((int(when),index,gid.get(canonical(event['card']),0)))
 return sorted(result,key=lambda x:(x[0],x[1]))
def history_ref(public,q):
 h=[];indices=[]
 for t,index,card,gap,unknown in public:
  if t>=q:continue
  h.append([card,q-t,gap,unknown]);indices.append(index)
 return np.array(([[0]*4]*16+h)[-16:],np.int32),np.array(([-1]*16+indices)[-16:],np.int32)
def target_ref(public,commands,q,end,mirror):
 d=dict(zip(COLS,[0,-1,-1,-1,0,0,-1,-1,0,0,0,-1,-1,int(end-q>=400),end,0,0]))
 nextc=[];nextp=[];matches=[]
 for c in commands:
  if c[0]<=q or c[0]-q>400:continue
  if not nextc or c[0]==nextc[0][0]:nextc.append(c)
 for p in public:
  if p[0]<=q or p[0]-q>500:continue
  if not nextp or p[0]==nextp[0][0]:nextp.append(p)
 if nextc:
  c=nextc[0];d.update(command_tick=c[0],command_index=c[1],command_card=c[2],command_count=len(nextc))
 if nextp:
  p=nextp[0];d.update(public_tick=p[0],public_index=p[1],public_card=p[2],public_count=len(nextp),sighting_gap=p[3],sighting_unknown=p[4])
  for event in commands:
   if p[2]!=0 and event[2]==p[2] and 0<=p[0]-event[0]<=100:matches.append(event)
  d['join_count']=len(matches)
  if len(matches)==1:d['join_index']=matches[0][1]
 if nextc and nextp:d['delay']=nextp[0][0]-nextc[0][0]
 if not nextc:
  d['status']=13 if nextp and nextp[0][0]-q<=400 else (1 if end-q>=400 else 2)
 else:
  c=nextc[0]
  if len(nextc)>1:d['status']=3
  elif c[2]==0:d['status']=4
  elif c[2]==mirror:d['status']=5
  elif not nextp:d['status']=14 if end<c[0]+100 else 6
  else:
   p=nextp[0]
   if len(nextp)>1:d['status']=7
   elif p[3] or p[4] or p[2]==0:d['status']=8
   elif len(matches)==1 and matches[0][0]<=q:d['status']=9
   elif p[2]!=c[2]:d['status']=10
   elif p[0]<c[0] or p[0]>c[0]+100:d['status']=11
   elif len(matches)!=1 or matches[0][1]!=c[1]:d['status']=12
   else:d['forecast_class']=c[2]
 return np.array([d[k] for k in COLS],np.int64)
def aggregate_ref(targets,rows,features):
 def group(indices):
  status=[0]*15;complete=0;unique=set();cards={};delays=Counter();belief=dict(in_hand=0,out_of_hand=0,unknown=0)
  quality={str(k):dict(rows=0,eligible=0) for k in range(5)}
  for i in indices:
   d=dict(zip(COLS,map(int,targets[i])));s=d['status'];status[s]+=1;complete+=d['window_complete'];key=str(d['command_card'])
   if key not in cards:cards[key]=dict(rows=0,status=[0]*15)
   cards[key]['rows']+=1;cards[key]['status'][s]+=1
   for k,value in enumerate(features['opp_hand_quality'][i]):
    if value>0:quality[str(k)]['rows']+=1;quality[str(k)]['eligible']+=int(s==0)
   if s==0:
    unique.add((int(rows['rep'][i]),int(rows['side'][i]),d['command_index']));delays[str(d['delay'])]+=1
    state='unknown'
    for token in features['opp_hand'][i]:
     if token[0]==d['forecast_class']:
      if token[1]:state='in_hand'
      elif token[2]:state='out_of_hand'
      break
    belief[state]+=1
  return dict(rows=len(indices),status=status,window_complete=complete,eligible_unique_commands=len(unique),by_command_card=cards,eligible_delays=dict(delays),eligible_belief=belief,quality=quality)
 by=defaultdict(list)
 for i,rep in enumerate(rows['rep']):by[str(int(rep))].append(i)
 return dict(all=group(list(range(len(targets)))),by_replay={k:group(v) for k,v in by.items()})
def exact(actual,expected):
 assert actual.keys()==expected.keys()
 for key in actual:
  if isinstance(expected[key],np.ndarray):
   assert actual[key].dtype==expected[key].dtype,key
   np.testing.assert_array_equal(actual[key],expected[key],err_msg=key)
  else:assert actual[key]==expected[key],key
def corruption_controls():
 expected=dict(ids=np.array([1,2]),records=np.arange(34).reshape(2,17),history=np.zeros((2,16,4),np.int32),hand=np.zeros((2,8,6),np.float32),quality=np.zeros((2,5),np.float32),report={'rows':2},source='hash')
 exact(copy.deepcopy(expected),expected);negative=0
 for key,index in [('ids',(0,)),('records',(0,0)),('records',(0,1)),('records',(0,3)),('records',(0,7)),('records',(0,10)),('history',(0,15,1)),('hand',(0,0,1)),('quality',(0,1)),('report',None),('source',None)]:
  bad=copy.deepcopy(expected)
  if index is not None:bad[key][index]+=1
  elif key=='report':bad[key]['rows']=3
  else:bad[key]='changed'
  try:exact(bad,expected)
  except (AssertionError,ValueError):negative+=1
  else:raise AssertionError(('missed corruption',key,index))
 assert negative==11
 return dict(positive=1,negative=negative)
def main():
 assert not (HERE/'verified.json').exists();c=read(HERE/'collected.json');assert c['complete']
 assert read(HERE/'started.json')['sources']==bindings()
 assert c['outputs']=={p.name:sha(p) for p in OUT.iterdir()}
 from fixtures import checks
 fixtures=checks(pub_ref,cmd_ref,history_ref,target_ref);assert fixtures==c['controls']
 controls=corruption_controls();b,rows,features=load_training();gid={name:i for i,name in enumerate(b['card_vocab'])}
 x=arrays(OUT/'inputs.npz');y=arrays(OUT/'targets.npz');n=len(rows['ids'])
 exact({k:x[k] for k in features},features);assert set(x)=={'ids','history','opp_hand','opp_hand_quality'}
 exact({k:y[k] for k in ('ids','rep','side','tick')},{k:rows[k] for k in ('ids','rep','side','tick')})
 np.testing.assert_array_equal(y['columns'],COLS);assert y['records'].shape==(n,17)
 assert set(y)=={'ids','rep','side','tick','columns','records','history_public_indices'}
 reconstructed=np.zeros_like(y['records']);sources={};count=0
 for stream in streams(set(rows['rep'].tolist())):
  rep=stream['rep'];tag=b['tags'][rep];assert stream['tag']==tag
  source=b['sources'][tag];p=ROOT/source['path'];assert sha(p)==source['sha256'];sources[tag]=source
  record=read(p);end=max(int(frame['tick']) for frame in record['frames'])
  for side in (0,1):
   public=pub_ref(stream['plays'][side],side,gid);commands=cmd_ref(record['log'],side,gid)
   for i in np.flatnonzero((rows['rep']==rep)&(rows['side']==side)):
    tick=int(rows['tick'][i]);h,hi=history_ref(public,tick);r=target_ref(public,commands,tick,end,gid['mirror'])
    exact(dict(records=y['records'][i],history=x['history'][i],indices=y['history_public_indices'][i]),dict(records=r,history=h,indices=hi))
    reconstructed[i]=r
  count+=1
  if count%25==0:write(HERE/'verification_progress.json',dict(replays=count,total=1573));print('verified replays',count,flush=True)
 assert sources==read(OUT/'raw_sources.json')
 report=aggregate_ref(reconstructed,rows,features);assert report==read(OUT/'report.json') and report['all']==c['summary']
 m=read(OUT/'manifest.json');assert m['trainable'] is False and m['targets_separate'] is True
 assert m['neural_inputs']==['history','opp_hand','opp_hand_quality'] and m['bookkeeping']==['ids']
 assert m['original_policy_label_sha256']==label_hashes(rows) and m['target_columns']==COLS and m['status']==STATUS
 assert m['rows']==n and m['replays']==count==1573 and m['horizon']==400 and m['max_delay']==100 and m['history_length']==16
 assert read(HERE/'started.json')['sources']==bindings()
 write(HERE/'verified.json',dict(complete=True,rows=n,replays=count,fixtures=fixtures,controls=controls,outputs=c['outputs'],collected_sha256=sha(HERE/'collected.json'),original_policy_labels_unchanged=True,trainable=False))
 print('OPPONENT_FORECAST_TARGETS_VERIFIED')
if __name__=='__main__':main()
