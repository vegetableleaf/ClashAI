"""Review finished paired-model evidence; no training or inference."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent/'learning'
CHECKS=ROOT/'scratchpad/gauntlet/L71/integration/checks'
def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert not (HERE/'reviewed_evidence.json').exists()
    p=read(HERE/'prepared.json');t=read(HERE/'trained.json');v=read(HERE/'training_verified.json')
    e=read(HERE/'evaluated.json');r=read(HERE/'results_verified.json');end=read(HERE/'chain_complete.json')
    assert all(x['complete'] for x in (p,t,v,e,r,end))
    assert t['prepared_sha256']==v['prepared_sha256']==sha(HERE/'prepared.json')
    assert v['trained_sha256']==sha(HERE/'trained.json') and e['training_verified_sha256']==sha(HERE/'training_verified.json')
    assert r['evaluated_sha256']==sha(HERE/'evaluated.json') and r['rows']==54723
    assert r['controls']==dict(positive=3,negative=16)
    assert t['steps_per_arm']==v['steps_per_arm']==1000 and v['draws_per_arm']==128000
    for arm in ('hand_blind_control_v5','hand_belief_v5'):
        assert v['arms'][arm]['optimizer_parameters']==104 and v['arms'][arm]['optimizer_steps']==1000
        assert v['arms'][arm]['controls']==dict(positive=1,negative=7)
        assert t['arms'][arm]['checkpoint_sha256']==v['arms'][arm]['checkpoint_sha256']==e['arms'][arm]['checkpoint_sha256']
        assert e['arms'][arm]['cache_sha256']==r['hashes'][arm]['cache']
    for path,h in p['sources'].items():assert sha(ROOT/path)==h,path
    receipts={}
    for name in ('l72-hand-model-qualified-v3','l72-hand-learning-prepare','l72-hand-learning-train',
                 'l72-hand-learning-verify_training','l72-hand-learning-evaluate','l72-hand-learning-verify_results'):
        path=CHECKS/(name+'.json');q=read(path);out=path.with_suffix('.out')
        assert q['exit_code']==0 and q['matched'] and hashlib.sha256(out.read_text().encode()).hexdigest()==q['output_sha256']
        receipts[name]=dict(seconds=q['seconds'],receipt_sha256=sha(path),output_sha256=sha(out))
    assert r['continuation_passed']==all(all(v.values()) for v in r['filters'].values())
    assert not r['accepted'] and not r['deployed']
    result=dict(complete=True,receipts=receipts,bindings={name:sha(HERE/name) for name in
        ('prepared.json','trained.json','training_verified.json','evaluated.json','results_verified.json','chain_complete.json')},
        source_sha256=sha(Path(__file__)),continuation_passed=r['continuation_passed'],accepted=False,deployed=False)
    (HERE/'reviewed_evidence.json').write_text(json.dumps(result,indent=2));print('HAND_LEARNING_EVIDENCE_REVIEWED')
if __name__=='__main__':main()
