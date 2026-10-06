"""Outside once-only receipt/provenance closure; no repeated target computation."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent/'opponent_forecast_readiness'
OUT=ROOT/'icebow/data/bench/opponent_forecast_readiness_20261006';CHECKS=ROOT/'scratchpad/gauntlet/L71/integration/checks'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 assert not (HERE/'reviewed.json').exists()
 c=read(HERE/'collected.json');v=read(HERE/'verified.json');end=read(HERE/'chain_complete.json')
 assert c['complete'] and v['complete'] and end['complete'] and v['rows']==213995 and v['replays']==1573
 assert v['controls']==dict(positive=1,negative=11) and v['fixtures']==dict(status_fixtures=19,causal_private_invariance=3,prefix_positive=4)
 assert v['collected_sha256']==sha(HERE/'collected.json') and c['started_sha256']==sha(HERE/'started.json')
 assert c['outputs']==v['outputs']=={p.name:sha(p) for p in OUT.iterdir()}
 for p,h in read(HERE/'started.json')['sources'].items():assert sha(ROOT/p)==h,p
 receipts={}
 for job,token in [('collect','OPPONENT_FORECAST_TARGETS_COLLECTED'),('verify','OPPONENT_FORECAST_TARGETS_VERIFIED')]:
  p=CHECKS/('l72-opponent-forecast-'+job+'.json');r=read(p);o=p.with_suffix('.out')
  assert r['exit_code']==0 and r['matched'] and r['expected']==token and hashlib.sha256(o.read_text().encode()).hexdigest()==r['output_sha256']
  assert Path(r['command'][-1]).resolve()==(HERE/(job+'.py')).resolve() and Path(r['cwd']).resolve()==ROOT
  receipts[job]=dict(seconds=r['seconds'],receipt_sha256=sha(p),output_sha256=sha(o))
 result=dict(complete=True,source_sha256=sha(Path(__file__)),receipts=receipts,
  bindings={n:sha(HERE/n) for n in ('started.json','collected.json','verified.json','chain_complete.json')},
  model_calls=0,optimizer_updates=0,new_model=False,trainable=False,accepted=False,deployed=False)
 (HERE/'reviewed.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('OPPONENT_FORECAST_REVIEWED')
if __name__=='__main__':main()
