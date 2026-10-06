from common import *

def main():
 assert not (HERE/'started.json').exists()
 OUT.mkdir(parents=True,exist_ok=True);bound=bindings();write(HERE/'started.json',dict(sources=bound))
 ids,labels,ps,groups,desc,prior=load();reports={}
 for control in CONTROLS:
  x=effects(labels,ps[control],ps['hand_belief_v5'],desc)
  np.savez_compressed(OUT/(control+'.npz'),ids=ids,fields=np.array(FIELDS),effects=x)
  reports[control]=summarize(ids,labels,groups,x)
  for group in ('all','rocket','rocket_late_overtime_clock','defensive_sequence','retention_status_4'):
   v=reports[control][group]['counts']
   assert v['hybrid_000']==prior['counts'][control][group]['action']
   assert v['hybrid_111']==prior['counts']['hand_belief_v5'][group]['action']
 write(OUT/'groups.json',reports)
 assert bindings()==bound
 write(HERE/'collected.json',dict(complete=True,rows=len(ids),groups=len(groups),comparisons=len(CONTROLS),
  started_sha256=sha(HERE/'started.json'),outputs={p.name:sha(p) for p in OUT.iterdir()},
  model_calls=0,optimizer_updates=0,accepted=False,deployed=False))
 print('HAND_DECISIONS_COLLECTED')

if __name__=='__main__':main()
