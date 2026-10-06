import hashlib,json,os,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];LIVE=ROOT/'scratchpad/gauntlet/L70/live'
EXPECTED=ROOT/'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt'
SHA='76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd'
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 assert not (HERE/'verified.json').exists()
 assert Path((LIVE/'CKPT_OVERRIDE').read_text().strip()).resolve()==EXPECTED.resolve() and digest(EXPECTED)==SHA
 assert (LIVE/'HAND_READER_ENABLED').read_text().strip()=='0'
 stop=LIVE/'STOP';before=(stop.stat().st_mtime_ns,stop.read_bytes())
 env={k:v for k,v in os.environ.items() if k.upper() not in ('CKPT','HAND_READER')}
 command=['C:/Program Files/Git/bin/bash.exe','scratchpad/gauntlet/L70/live/start_live.sh','--check']
 p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
 (HERE/'startup_check.out').write_text(p.stdout+p.stderr,encoding='utf-8');assert p.returncode==0,(p.returncode,p.stderr)
 settings=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{"check":')];assert len(settings)==1
 s=settings[0];assert s['check']=='LIVE_CHECK_PASS' and Path(s['checkpoint']).resolve()==EXPECTED.resolve() and s['sha256']==SHA
 assert s['device']=='cpu' and s['tau']==.35 and s['public_audit'] and not s['anti_leak']
 assert s['decision_options']['card_choice']==s['decision_options']['spell_aim']=='argmax'
 assert 'hand-reader model input: 0' in p.stdout and before==(stop.stat().st_mtime_ns,stop.read_bytes())
 result=dict(complete=True,settings=s,command=command,exit_code=p.returncode,stop_mtime_ns=before[0],stop_unchanged=True,live_started=False,
  sources={str(q.relative_to(ROOT)):digest(q) for q in (Path(__file__),HERE/'PLAN.md',LIVE/'start_live.sh',LIVE/'run_live.sh',LIVE/'live_config.sh',LIVE/'HAND_READER_ENABLED',LIVE/'CKPT_OVERRIDE')},
  output_sha256=digest(HERE/'startup_check.out'))
 (HERE/'verified.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('OWNER_R1E_RESTORED')
if __name__=='__main__':main()
