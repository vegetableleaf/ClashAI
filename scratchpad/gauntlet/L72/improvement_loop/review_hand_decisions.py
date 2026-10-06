"""Once-only receipt/source review of completed cached hand decision diagnosis."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent/'hand_decision_audit'
CHECKS=ROOT/'scratchpad/gauntlet/L71/integration/checks'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 assert not (HERE/'reviewed.json').exists()
 c=read(HERE/'collected.json');v=read(HERE/'verified.json');end=read(HERE/'chain_complete.json')
 assert c['complete'] and v['complete'] and end['complete'] and v['rows']==54723
 assert v['collected_sha256']==sha(HERE/'collected.json') and v['controls']==dict(positive=2,negative=8)
 for p,h in read(HERE/'started.json')['sources'].items():assert sha(ROOT/p)==h,p
 receipts={}
 for name in ('l72-hand-decisions-collect','l72-hand-decisions-verify'):
  p=CHECKS/(name+'.json');q=read(p);out=p.with_suffix('.out')
  assert q['exit_code']==0 and q['matched'] and hashlib.sha256(out.read_text().encode()).hexdigest()==q['output_sha256']
  receipts[name]=dict(seconds=q['seconds'],receipt_sha256=sha(p),output_sha256=sha(out))
 result=dict(complete=True,source_sha256=sha(Path(__file__)),receipts=receipts,
  bindings={n:sha(HERE/n) for n in ('started.json','collected.json','verified.json','chain_complete.json')},
  model_calls=0,optimizer_updates=0,new_model=False,accepted=False,deployed=False)
 (HERE/'reviewed.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('HAND_DECISIONS_REVIEWED')
if __name__=='__main__':main()
