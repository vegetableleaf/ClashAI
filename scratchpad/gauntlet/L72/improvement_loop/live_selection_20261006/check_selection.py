"""Actual offline startup routing, strict compatibility and unchanged STOP proof."""
import hashlib,json,os,subprocess,time
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
LIVE=ROOT/'scratchpad/gauntlet/L70/live'
BASH=Path('C:/Program Files/Git/bin/bash.exe')
TOWER=ROOT/'icebow/data/bench/development_iteration_5_20261005/tower_spatial_v7/candidate.pt'
HAND=ROOT/'icebow/data/bench/hand_belief_learning_20261006/hand_belief_v5/candidate.pt'
EXPECTED='2feffe4f0990d93721ceb0b6661338f52e7f935e85b80e29535ea713ad6569a0'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    assert not (HERE/'verified.json').exists()
    assert BASH.is_file() and sha(TOWER)==EXPECTED
    pointer=(LIVE/'CKPT_OVERRIDE').read_text().strip()
    assert Path(pointer).resolve()==TOWER.resolve()
    assert (LIVE/'HAND_READER_ENABLED').read_text().strip()=='0'
    stop=LIVE/'STOP';before=(stop.stat().st_mtime_ns,stop.read_bytes())
    env=dict(os.environ)
    for key in list(env):
        if key.upper() in ('CKPT','HAND_READER'):del env[key]
    records={}
    for script in ('start_live.sh','run_live.sh','live_config.sh'):
        p=subprocess.run([str(BASH),'-n',str(LIVE/script)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
        assert p.returncode==0,(script,p.stderr)
    cases=[('default',{},True),('hand_opt_in',{'HAND_READER':'1','CKPT':str(HAND)},True),
           ('invalid_flag',{'HAND_READER':'bogus'},False),('incompatible_tower',{'HAND_READER':'1'},False)]
    for name,extra,success in cases:
        started=time.time()
        command=[str(BASH),'scratchpad/gauntlet/L70/live/start_live.sh','--check']
        p=subprocess.run(command,cwd=ROOT,env={**env,**extra},capture_output=True,text=True,timeout=180)
        output=p.stdout+p.stderr;(HERE/(name+'.out')).write_text(output,encoding='utf-8')
        assert (p.returncode==0)==success,(name,p.returncode,output)
        settings=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{"check":')]
        if success:
            assert len(settings)==1 and settings[0]['check']=='LIVE_CHECK_PASS'
            s=settings[0];expected=TOWER if name=='default' else HAND
            assert Path(s['checkpoint']).resolve()==expected.resolve() and s['sha256']==sha(expected)
            assert s['device']=='cpu' and s['tau']==.35 and s['public_audit'] and not s['anti_leak']
            assert s['decision_options']['card_choice']==s['decision_options']['spell_aim']=='argmax'
            assert f"hand-reader model input: {int(name=='hand_opt_in')}" in p.stdout
        else:
            assert not settings
            assert ('HAND_READER must be 0 or 1' in output) if name=='invalid_flag' else ('AssertionError' in output or 'ValueError' in output)
        records[name]=dict(command=command,seconds=time.time()-started,exit_code=p.returncode,
            settings=settings,output_sha256=sha(HERE/(name+'.out')))
    assert before==(stop.stat().st_mtime_ns,stop.read_bytes())
    assert Path((LIVE/'CKPT_OVERRIDE').read_text().strip()).resolve()==TOWER.resolve()
    assert (LIVE/'HAND_READER_ENABLED').read_text().strip()=='0'
    sources=[Path(__file__),HERE/'PLAN.md',LIVE/'start_live.sh',LIVE/'run_live.sh',LIVE/'live_config.sh',LIVE/'HAND_READER_ENABLED',
        ROOT/'scratchpad/gauntlet/L72/improvement_loop/hand_retention_integration/live_play_hand_v4.py']
    result=dict(complete=True,tower_sha256=EXPECTED,hand_input_default=False,stop_unchanged=True,
        live_started=False,positive_controls=2,negative_controls=2,cases=records,
        sources={str(p.relative_to(ROOT)):sha(p) for p in sources})
    (HERE/'verified.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('OWNER_LIVE_SELECTION_VERIFIED')

if __name__=='__main__':main()
