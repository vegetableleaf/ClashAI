"""One bounded read-only client qualification. Never starts a match or a policy."""
import hashlib,json,os,re,statistics,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
ADB=[r'C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe','-s','127.0.0.1:16384']
REMOTE='/data/local/tmp/re_live_sampler3_20261006'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def adb(*args,input=None,timeout=20):
    p=subprocess.run([*ADB,*args],input=input,text=True,capture_output=True,timeout=timeout,env=dict(os.environ,MSYS_NO_PATHCONV='1'))
    assert p.returncode==0,(args,p.returncode,p.stderr)
    return p.stdout
def main():
    assert not (HERE/'passive_v2_started.json').exists()
    report=json.loads((HERE/'verified.json').read_text());assert report['complete']
    binary=HERE/'live_sampler3';assert sha(binary)==report['generated']['live_sampler3']
    stop=ROOT/'scratchpad/gauntlet/L70/live/STOP'
    stop_before=(stop.exists(),stop.stat().st_mtime_ns if stop.exists() else None)
    sources=[Path(__file__),HERE/'PASSIVE_V2_PLAN.md',binary,HERE/'live_sampler3.c',HERE/'character_name.h',HERE/'verified.json']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in sources}
    (HERE/'passive_v2_started.json').write_text(json.dumps(dict(time=time.time(),sources=hashes,stop_before=stop_before),indent=2))
    package=adb('shell','dumpsys package com.supercell.clashroyale')
    version=re.findall(r'versionCode=(\d+)',package);assert set(version)=={'160402012'}
    pid=adb('shell','pidof com.supercell.clashroyale').strip();assert re.fullmatch(r'\d+',pid)
    maps=adb('shell',f'cat /proc/{pid}/maps')
    rows=[]; zero_maps=[]
    for line in maps.splitlines():
        parts=line.split()
        if len(parts)>=6 and parts[-1].endswith('/libg.so'):
            rows.append(int(parts[0].split('-')[0],16)-int(parts[2],16))
            if int(parts[2],16)==0:zero_maps.append(int(parts[0].split('-')[0],16))
    assert rows and len(zero_maps)==1 and min(rows)==zero_maps[0]
    base=zero_maps[0]
    (HERE/'passive_v2_maps.txt').write_text('\n'.join(line for line in maps.splitlines() if '/libg.so' in line))
    original=json.loads((ROOT/'scratchpad/gauntlet/L70/reader/identity.json').read_text())
    oldbase=int(original['base'],16)
    requests=[(base+int(addr,16)-oldbase,n,bytes.fromhex(h)) for addr,n,h,error in original['rows']]
    payload=''.join(f'{a:#x} {n}\n' for a,n,b in requests)
    raw=adb('shell',f'/data/local/tmp/re_peek {pid}',input=payload)
    parsed=[]
    for line in raw.splitlines():
        parts=line.split();assert len(parts)==3 and parts[2]!='ERR'
        parsed.append((int(parts[0],0),int(parts[1],0),bytes.fromhex(parts[2])))
    assert len(parsed)==len(requests)
    for i,((a,n,b),(want_a,want_n,old)) in enumerate(zip(parsed,requests)):
        assert (a,n,len(b))==(want_a,want_n,want_n)
        if i==0:assert b==old
        else:
            assert all(int.from_bytes(b[k:k+8],'little')-base==int.from_bytes(old[k:k+8],'little')-oldbase for k in range(0,n,8))
    identity=dict(version=version[0],pid=int(pid),base=hex(base),public_windows=[dict(offset=hex(a-base),size=n,sha256=hashlib.sha256(b).hexdigest()) for a,n,b in parsed])
    (HERE/'passive_v2_identity.json').write_text(json.dumps(identity,indent=2))
    exists=adb('shell',f'if [ -e {REMOTE} ]; then sha256sum {REMOTE}; else echo ABSENT; fi').strip()
    if exists=='ABSENT':
        adb('push',str(binary),REMOTE);adb('shell',f'chmod 755 {REMOTE}')
    else:assert exists.split()[0]==sha(binary),'Existing path contains another binary'
    assert adb('shell',f'sha256sum {REMOTE}').split()[0]==sha(binary)
    cmd=f'{REMOTE} {pid} 500 0x1aeef98 0x18 --unified 120 --extended --character-identity'
    run=subprocess.run([*ADB,'shell',cmd],capture_output=True,text=True,timeout=90,env=dict(os.environ,MSYS_NO_PATHCONV='1'))
    (HERE/'passive_v2_raw.jsonl').write_text(run.stdout);(HERE/'passive_v2.err').write_text(run.stderr)
    assert run.returncode==0
    frames=[json.loads(s) for s in run.stdout.splitlines()];assert len(frames)==120
    names={};statuses={};eligible=0;raw_heroes=0;read_us=[]
    for f in frames:
        assert f['character_identity']=={'schema':1,'build':160402012}
        read_us.append(f['read_us'])
        if f['battle_active'] and f['coherent']:eligible+=1
        for e in f.get('entities',[]):
            if e['card_id']!=203000023:continue
            raw_heroes+=1;status=e['native_name_status'];statuses[status]=statuses.get(status,0)+1
            assert status in ('ok','read_error','invalid_pointer','invalid_name')
            if status=='ok':
                assert re.fullmatch(r'[A-Za-z0-9_]{1,128}',e['native_name'])
                names[e['native_name']]=names.get(e['native_name'],0)+1
            else:assert e['native_name'] is None
    median=statistics.median(read_us);p95=sorted(read_us)[113];maximum=max(read_us)
    known={'IceWizardHero','IceWizardHeroFloatingCube','IceWizardHero_IceCube'}
    pass_scene=eligible>0 and names.get('IceWizardHero',0)>0 and names.get('IceWizardHeroFloatingCube',0)>0 and set(names)<=known
    passed=pass_scene and median<=5000 and p95<=20000
    stop_after=(stop.exists(),stop.stat().st_mtime_ns if stop.exists() else None)
    result=dict(complete=True,engineering_pass=passed,scene_qualified=pass_scene,frames=len(frames),active_coherent=eligible,
        raw_shared_id_entries=raw_heroes,names=names,statuses=statuses,read_us=dict(median=median,p95=p95,maximum=maximum),
        identity=identity,sources=hashes,raw_sha256=sha(HERE/'passive_v2_raw.jsonl'),stderr_sha256=sha(HERE/'passive_v2.err'),
        command=cmd,exit_code=run.returncode,stop_before=stop_before,stop_after=stop_after,assistant_changed_stop=False,
        owner_policy_changed=False,live_match_started=False,new_reader_activated=False,model_calls=0)
    (HERE/'passive_v2.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));print('READER_CHARACTER_PASSIVE_V2_COMPLETE')
if __name__=='__main__':main()
