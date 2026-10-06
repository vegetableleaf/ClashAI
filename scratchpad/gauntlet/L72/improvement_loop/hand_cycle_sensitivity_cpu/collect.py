import datetime,torch
from common import *
from pipeline.train_rocket_curriculum import load_subset
from pipeline.eval_gen import GenRows
from pipeline.model_hand_belief_v2 import load_checkpoint
from pipeline.opp_elixir_count import card_cost

def main():
 assert not (HERE/'started.json').exists() and not OUT.exists()
 assert read(LOOP/'hand_decision_audit/reviewed.json')['complete']
 bound=bindings();write(HERE/'started.json',dict(sources=bound,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 spec=importlib.util.spec_from_file_location('cycle_original_common',LOOP/'development_iteration_1/common.py')
 original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original);original.setup();torch.use_deterministic_algorithms(True)
 ids,mirrors=sample_ids();unique=np.unique(ids);sub,meta=load_subset(DATA,unique);cv=meta['card_vocab']
 assert np.all(sub['split']==0);pos=np.searchsorted(unique,ids);features=arrays(SEQ/'features.npz')
 fpos=np.searchsorted(features['ids'],ids);assert np.array_equal(features['ids'][fpos],ids)
 hand=features['opp_hand'][fpos];quality=features['opp_hand_quality'][fpos];ch,cq=censor(hand,quality)
 sample={k:sub[k][pos] for k in ('rep','y_gate','y_card','y_xy','hand_card','sc')}
 costs=np.array([card_cost(k.replace('-','_')) or 0 for k in cv])
 sample.update(ids=ids,mirror=np.repeat(mirrors,128),hand_full=hand,quality_full=quality,hand_censored=ch,quality_censored=cq,
  allowed=(sample['hand_card']>0)&(costs[sample['hand_card']]<=np.floor(sample['sc'][:,3]*10+1e-3)[:,None]))
 OUT.mkdir();np.savez_compressed(OUT/'sample.npz',**sample)
 rows=GenRows(sub,np.arange(len(unique)),'cpu');summaries={};before_after={};base_hashes=[]
 for arm in ARMS:
  path=BASE/arm/'candidate.pt';assert sha(path)==read(OLD/'trained.json')['arms'][arm]['checkpoint_sha256']
  model,state=load_checkpoint(path,'cpu');model.eval();before={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
  stored={}
  for condition in ('full','censored'):
   output={k:[] for k in (*HEADS,'g')}
   for bi in range(8):
    a=slice(bi*128,(bi+1)*128);b=original.augment(rows.batch(pos[a]),bool(mirrors[bi]))
    b.update(opp_hand=torch.as_tensor(sample['hand_'+condition][a],device='cpu'),
     opp_hand_quality=torch.as_tensor(sample['quality_'+condition][a],device='cpu'))
    digest=hashlib.sha256()
    for key in sorted(set(b)-{'opp_hand','opp_hand_quality'}):
     x=b[key].detach().cpu().numpy();digest.update(key.encode());digest.update(str((x.dtype,x.shape)).encode());digest.update(x.tobytes())
    base_hashes.append(dict(arm=arm,condition=condition,batch=bi,sha256=digest.hexdigest()))
    with torch.inference_mode():z=model(b,card=b['card'],form=b['form'])
    for key in output:output[key].append(z[key].cpu().numpy())
   stored[condition]={k:np.concatenate(v) for k,v in output.items()}
   assert np.isfinite(stored[condition]['g']).all()
   np.savez_compressed(OUT/(arm+'_'+condition+'.npz'),**stored[condition])
  assert all(torch.equal(v,model.state_dict()[k].detach().cpu()) for k,v in before.items())
  assert all(p.grad is None for p in model.parameters()) and sha(path)==read(OLD/'trained.json')['arms'][arm]['checkpoint_sha256']
  before_after[arm]=dict(unchanged=True,gradients_empty=True,checkpoint_sha256=sha(path))
  if arm==ARMS[0]:
   for k in stored['full']:assert np.array_equal(stored['full'][k],stored['censored'][k]),k
  stats=row_measures(stored['full'],stored['censored'],sample)
  np.savez_compressed(OUT/(arm+'_row_measures.npz'),**stats);summaries[arm]=summarize(stats,sample,cv)
  write(HERE/'progress.json',dict(completed_arm=arm,model_row_views=(ARMS.index(arm)+1)*2048))
  print('COLLECTED',arm,flush=True);del model
 for bi in range(8):assert len({r['sha256'] for r in base_hashes if r['batch']==bi})==1
 write(OUT/'groups.json',summaries);write(OUT/'base_hashes.json',base_hashes)
 assert bindings()==bound
 write(HERE/'collected.json',dict(complete=True,rows=1024,model_row_views=4096,card_vocab=cv,weights=before_after,
  outputs={p.name:sha(p) for p in OUT.iterdir()},started_sha256=sha(HERE/'started.json'),backward_calls=0,optimizer_updates=0,runtime=dict(device='cpu',threads=torch.get_num_threads(),deterministic=torch.are_deterministic_algorithms_enabled())))
 print('HAND_CYCLE_CPU_COLLECTED')
if __name__=='__main__':main()
