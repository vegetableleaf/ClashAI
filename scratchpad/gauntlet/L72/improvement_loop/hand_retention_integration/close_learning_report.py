"""Bind the once-only paired-model report to verified evidence and delivery."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent/'learning'
CHECKS=ROOT/'scratchpad/gauntlet/L71/integration/checks';REPORT_ID='model-public-hand-belief-pair-final'
def read(p):return json.loads(p.read_text())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert not (HERE/'reviewed_results.json').exists()
    e=read(HERE/'reviewed_evidence.json');r=read(HERE/'results_verified.json')
    assert e['complete'] and e['bindings']['results_verified.json']==sha(HERE/'results_verified.json')
    directory=ROOT/'reports/discord/deliveries'/REPORT_ID;delivery=read(directory/'delivery.json')
    message=(HERE/'message.md').read_text(encoding='utf-8')
    assert delivery['report_id']==REPORT_ID and delivery['status']=='delivered'
    assert delivery['text_sha256']==hashlib.sha256(message.encode()).hexdigest()
    assert (directory/'message.md').read_text(encoding='utf-8')==message
    chunks=delivery['chunks'];assert chunks and all(c['status']=='delivered' and c['http_status']==200 and c['message_id'] for c in chunks)
    receipts={}
    for name in ('l72-hand-learning-reviewed-evidence','l72-hand-learning-discord'):
        path=CHECKS/(name+'.json');q=read(path);out=path.with_suffix('.out')
        assert q['exit_code']==0 and q['matched'] and hashlib.sha256(out.read_text().encode()).hexdigest()==q['output_sha256']
        receipts[name]=dict(receipt_sha256=sha(path),output_sha256=sha(out),seconds=q['seconds'])
    cli={}
    for name,code in (('l72-hand-final-live-check',1),('l72-hand-final-live-check-v3',0)):
        path=CHECKS/(name+'.json');q=read(path);out=path.with_suffix('.out');text=out.read_text()
        assert q['exit_code']==code and q['matched']==(code==0)
        assert hashlib.sha256(text.encode()).hexdigest()==q['output_sha256'] and '--check' in q['command']
        if code:
            assert "ModuleNotFoundError: No module named 'hero_button'" in text
        else:
            settings=[json.loads(line) for line in text.splitlines() if line.startswith('{"check":')]
            assert len(settings)==1
            setting=settings[0];trained=read(HERE/'trained.json')
            assert setting['check']=='LIVE_CHECK_PASS' and setting['sha256']==trained['arms']['hand_belief_v5']['checkpoint_sha256']
            assert setting['device']=='cpu' and setting['tau']==.35 and setting['public_audit'] and not setting['anti_leak']
            assert setting['decision_options']['card_choice']==setting['decision_options']['spell_aim']=='argmax'
        cli[name]=dict(receipt_sha256=sha(path),output_sha256=sha(out),seconds=q['seconds'],exit_code=code)
    assert len({c['message_id'] for c in chunks})==len(chunks)
    result=dict(complete=True,source_sha256=sha(Path(__file__)),receipts=receipts,
        evidence_sha256=sha(HERE/'reviewed_evidence.json'),results_sha256=sha(HERE/'results_verified.json'),
        message_sha256=sha(HERE/'message.md'),delivery_sha256=sha(directory/'delivery.json'),
        message_ids=[c['message_id'] for c in chunks],cli_receipts=cli,
        cli_sources={name:sha(HERE.parent/name) for name in ('live_play_hand_v2.py','live_play_hand_v3.py','LIVE_ENTRYPOINT_CORRECTION.md')},
        continuation_passed=r['continuation_passed'],accepted=False,deployed=False)
    (HERE/'reviewed_results.json').write_text(json.dumps(result,indent=2));print('HAND_LEARNING_REPORT_REVIEWED')
if __name__=='__main__':main()
