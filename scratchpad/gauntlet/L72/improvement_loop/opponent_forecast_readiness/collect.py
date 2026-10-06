"""Qualify targets only; no model, optimization, or policy label rewriting."""
import datetime,os
from collections import Counter
from common import *
from pipeline.dataset_gen import card_key

def public_projection(events,side,gid):
 # This allowlist is the ONLY path into the new public-history input.
 return sorted([(int(e['tick']),i,gid.get(card_key(e.get('card') or ''),0),
  int(bool(e.get('gap_before'))),int(bool(e.get('identity_unknown'))))
  for i,e in enumerate(events) if int(e['side'])!=side and e.get('accepted',True) and not e.get('ability')])
def command_projection(log,side,gid):
 return sorted([(int(e.get('engine_tick',e['tick'])),i,gid.get(card_key(e['card']),0))
  for i,e in enumerate(log) if int(e['side'])!=side and e.get('accepted') and not e.get('ability') and e.get('card')])
def history(public,q):
 past=[e for e in public if e[0]<q][-16:]
 h=np.zeros((16,4),np.int32);ix=np.full(16,-1,np.int32)
 for j,e in enumerate(past,16-len(past)):h[j]=[e[2],q-e[0],e[3],e[4]];ix[j]=e[1]
 return h,ix
def target(public,commands,q,end,mirror):
 c=[e for e in commands if q<e[0]<=q+400];p=[e for e in public if q<e[0]<=q+500]
 a=np.array([0,-1,-1,-1,0,0,-1,-1,0,0,0,-1,-1,int(end>=q+400),end,0,0],np.int64)
 if c:
  t,i,k=c[0];a[2:6]=[i,t,k,sum(x[0]==t for x in c)]
 if p:
  t,i,k,g,u=p[0];a[6:10]=[i,t,k,sum(x[0]==t for x in p)];a[15:17]=[g,u]
  joins=[x for x in commands if k and x[2]==k and t-100<=x[0]<=t]
  a[10]=len(joins);a[11]=joins[0][1] if len(joins)==1 else -1
 else:joins=[]
 if c and p:a[12]=a[7]-a[3]
 if not c:s=13 if p and p[0][0]<=q+400 else 1 if end>=q+400 else 2
 elif a[5]!=1:s=3
 elif not a[4]:s=4
 elif a[4]==mirror:s=5
 elif not p:s=6 if end>=a[3]+100 else 14
 elif a[9]!=1:s=7
 elif a[15] or a[16] or not a[8]:s=8
 elif len(joins)==1 and joins[0][0]<=q:s=9
 elif a[8]!=a[4]:s=10
 elif not 0<=a[12]<=100:s=11
 elif a[10]!=1 or a[11]!=a[2]:s=12
 else:s=0
 a[0]=s
 if s==0:a[1]=a[4]
 return a
def summarize(t,rows,features):
 def one(ix):
  a=t[ix];h=features['opp_hand'][ix];q=features['opp_hand_quality'][ix];ok=a[:,0]==0
  bycard={}
  for card in sorted(set(a[:,4])):
   m=a[:,4]==card;bycard[str(int(card))]=dict(rows=int(m.sum()),status=np.bincount(a[m,0],minlength=15).tolist())
  inhand=outhand=unknown=0
  for j in np.flatnonzero(ok):
   tok=h[j][h[j,:,0]==a[j,1]]
   if len(tok) and tok[0,1]:inhand+=1
   elif len(tok) and tok[0,2]:outhand+=1
   else:unknown+=1
  return dict(rows=len(ix),status=np.bincount(a[:,0],minlength=15).tolist(),
   window_complete=int(a[:,13].sum()),eligible_unique_commands=len(set(zip(rows['rep'][ix][ok].tolist(),rows['side'][ix][ok].tolist(),a[ok,2].tolist()))),
   by_command_card=bycard,eligible_delays=dict(sorted(Counter(map(str,a[ok,12])).items())),
   eligible_belief=dict(in_hand=inhand,out_of_hand=outhand,unknown=unknown),
   quality={str(k):dict(rows=int((q[:,k]>0).sum()),eligible=int(((q[:,k]>0)&ok).sum())) for k in range(5)})
 return dict(all=one(np.arange(len(t))),by_replay={str(int(rep)):one(np.flatnonzero(rows['rep']==rep)) for rep in np.unique(rows['rep'])})
def main():
 assert not (HERE/'started.json').exists() and not OUT.exists();OUT.mkdir(parents=True)
 bound=bindings();write(HERE/'started.json',dict(pid=os.getpid(),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=bound))
 from fixtures import checks
 controls=checks(public_projection,command_projection,history,target)
 b,rows,features=load_training();gid={c:i for i,c in enumerate(b['card_vocab'])};mirror=gid['mirror']
 n=len(rows['ids']);hist=np.zeros((n,16,4),np.int32);hi=np.full((n,16),-1,np.int32);targets=np.zeros((n,len(COLS)),np.int64)
 sources={};count=0
 for stream in streams(set(rows['rep'].tolist())):
  rep=stream['rep'];tag=b['tags'][rep];assert tag==stream['tag'];source=b['sources'][tag];p=ROOT/source['path'];assert sha(p)==source['sha256']
  record=read(p);sources[tag]=source;end=max(int(f['tick']) for f in record['frames'])
  for side in (0,1):
   public=public_projection(stream['plays'][side],side,gid);commands=command_projection(record['log'],side,gid)
   for j in np.flatnonzero((rows['rep']==rep)&(rows['side']==side)):
    q=int(rows['tick'][j]);hist[j],hi[j]=history(public,q);targets[j]=target(public,commands,q,end,mirror)
  count+=1
  if count%25==0:write(HERE/'progress.json',dict(replays=count,total=1573));print('replays',count,flush=True)
 np.savez_compressed(OUT/'inputs.npz',ids=rows['ids'],history=hist,opp_hand=features['opp_hand'],opp_hand_quality=features['opp_hand_quality'])
 np.savez_compressed(OUT/'targets.npz',ids=rows['ids'],rep=rows['rep'],side=rows['side'],tick=rows['tick'],records=targets,columns=np.array(COLS),history_public_indices=hi)
 report=summarize(targets,rows,features);write(OUT/'report.json',report);write(OUT/'raw_sources.json',sources)
 manifest=dict(trainable=False,split='training_only',rows=n,replays=1573,
  neural_inputs=['history','opp_hand','opp_hand_quality'],bookkeeping=['ids'],targets_separate=True,
  history_columns=['card','age_ticks','gap_before','identity_unknown'],target_columns=COLS,status=STATUS,
  original_policy_label_sha256=label_hashes(rows),horizon=400,max_delay=100,history_length=16,
  limitations=['reconstructed command oracle, not original match truth','selective public visibility','correlated overlapping targets','parent exposed training only','no profitability or policy acceptance'])
 write(OUT/'manifest.json',manifest)
 assert bindings()==bound
 result=dict(complete=True,rows=n,replays=count,controls=controls,summary=report['all'],outputs={p.name:sha(p) for p in OUT.iterdir()},started_sha256=sha(HERE/'started.json'),model_calls=0,optimizer_updates=0,trainable=False)
 write(HERE/'collected.json',result);print('OPPONENT_FORECAST_TARGETS_COLLECTED')
if __name__=='__main__':main()
