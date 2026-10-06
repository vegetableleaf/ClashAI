"""One outside source/receipt review; never repeats collection or scalar checks."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent/'hand_cycle_sensitivity_cpu'
OUT=ROOT/'icebow/data/bench/hand_cycle_sensitivity_cpu_20261006';CHECKS=ROOT/'scratchpad/gauntlet/L71/integration/checks'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 assert not (HERE/'reviewed.json').exists()
 c=read(HERE/'collected.json');v=read(HERE/'verified.json');end=read(HERE/'chain_complete.json')
 assert c['complete'] and v['complete'] and end['complete'] and v['rows']==1024 and v['model_row_views']==4096
 assert v['controls']==dict(positive=2,negative=8) and v['collected_sha256']==sha(HERE/'collected.json')
 assert c['outputs']==v['outputs']=={p.name:sha(p) for p in OUT.iterdir()}
 for p,h in read(HERE/'started.json')['sources'].items():assert sha(ROOT/p)==h,p
 receipts={}
 for job in ('collect','verify'):
  p=CHECKS/('l72-hand-cycle-cpu-'+job+'.json');r=read(p);o=p.with_suffix('.out')
  assert r['exit_code']==0 and r['matched'] and hashlib.sha256(o.read_text().encode()).hexdigest()==r['output_sha256']
  receipts[job]=dict(seconds=r['seconds'],receipt_sha256=sha(p),output_sha256=sha(o))
 result=dict(complete=True,source_sha256=sha(Path(__file__)),receipts=receipts,
  bindings={n:sha(HERE/n) for n in ('started.json','collected.json','verified.json','chain_complete.json')},
  backward_calls=0,optimizer_updates=0,new_model=False,accepted=False,deployed=False)
 (HERE/'reviewed.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('HAND_CYCLE_CPU_REVIEWED')
if __name__=='__main__':main()
