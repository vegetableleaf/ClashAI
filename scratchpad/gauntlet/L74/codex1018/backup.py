"""Copy immutable finished result directories; verify archive and every extracted file."""
import argparse
import base64
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile

HERE=Path(__file__).resolve().parent
DEST=Path('C:/Users/benpe/pod_backup_weekend/codex1018')
KEY=str(Path.home()/'.ssh/runpod_clashbot')
REMOTE=r'''
import hashlib,json,pathlib,tarfile,sys,re
P=pathlib.Path
spec=json.loads(sys.argv[1]); roots=[P(x) for x in spec['roots']]
allowed=('s2/runs/','combo/runs/','ab2/results_','c3/results_','results/r7','results/v7_','results/v7c_','results/FIN12','results/FIN13','results/FIN14','codex1018_parity','codex1018/results','codex1018_combo_eval/results','codex1018_combo_fresh_rules/results')
for p in roots:
 rel=p.relative_to('/workspace').as_posix()
 assert rel.startswith(allowed) and p.is_dir(),rel
 finished=(p/'DONE').exists() or (p/'ALL_DONE').exists()
 # gap.py writes SUMMARY.txt only after every chunk has completed. Its finished
 # seed directories are immutable even while a later seed in the parent runs.
 if re.fullmatch(r'(?:codex1018(?:_combo_eval|_combo_fresh_rules)?/results|c3/results_[A-Za-z0-9_]+/eval|combo/runs/[A-Za-z0-9_]+/eval_offc?)/[A-Za-z0-9_]+_74[0-9]{4}',rel):
  finished=(p/'SUMMARY.txt').is_file() and (p/'score.json').is_file() and sum(1 for line in (p/'D3/matches.jsonl').open() if line.strip())==480
 assert finished,rel
files={}
for root in roots:
 for p in sorted(root.rglob('*')):
  if not p.is_file() or p.is_symlink():continue
  rel=p.relative_to('/workspace').as_posix()
  assert not any(s in rel.lower() for s in ('reader','webhook','overlayed_replays','.anthropic'))
  with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
  files[rel]=dict(sha256=sha,bytes=p.stat().st_size)
 # A finished Stage-2 train directory contains a checkpoint manifest, while
 # the immutable gate checkpoints themselves are outside that directory.
 if re.fullmatch(r's2_all_il_s[AB]',root.name):
  checkpoint_dir=P('/workspace/cb_tt/icebow/data/bench/rl_royale')/root.name
  selected=[]
  for line in (root/'ckpts.sha').read_text().splitlines():
   match=re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.*)',line.strip())
   assert match,'invalid Stage-2 checkpoint manifest'
   name=match[2]
   if not re.fullmatch(re.escape(root.name)+r'_u0(?:025|045|060|065|100|130)\.pt',name):continue
   p=checkpoint_dir/name
   assert p.is_file() and not p.is_symlink()
   with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
   assert sha==match[1].lower(),'Stage-2 checkpoint SHA mismatch'
   files[p.relative_to('/workspace').as_posix()]=dict(sha256=sha,bytes=p.stat().st_size)
   selected.append(name)
  assert root.name+'_u0130.pt' in selected,'Stage-2 final checkpoint missing'
out=P('/workspace/codex1018_backup');out.mkdir(exist_ok=True)
archive=out/(spec['stamp']+'.tgz')
with tarfile.open(archive,'w:gz',compresslevel=1,dereference=True) as tar:
 for rel in files:tar.add('/workspace/'+rel,arcname=rel,recursive=False)
with archive.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
manifest=dict(roots=[str(p) for p in roots],archive=str(archive),archive_sha256=sha,files=files)
manifest_path=archive.with_suffix('.manifest.json');manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(archive=str(archive),manifest=str(manifest_path),sha256=sha,files=len(files))))
'''

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def normalize_sha(line):
    m=re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.*)',line.strip())
    if not m:raise ValueError('invalid sha256 manifest line')
    return m[1].lower(),m[2]

def copy(host,port,roots):
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    spec=dict(roots=roots,stamp=stamp)
    enc=base64.b64encode(REMOTE.encode()).decode()
    payload=base64.b64encode(json.dumps(spec).encode()).decode()
    command='python3 -c "import base64,sys;sys.argv=[\'backup\',base64.b64decode(\''+payload+'\').decode()];exec(base64.b64decode(\''+enc+'\'))"'
    opts=['-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=30','-i',KEY]
    raw=subprocess.check_output(['ssh','-n',*opts,'-p',str(port),'root@'+host,command],text=True)
    info=json.loads(raw)
    dest=DEST/str(port)/stamp;dest.mkdir(parents=True)
    for remote in (info['archive'],info['manifest']):
        subprocess.run(['scp','-q',*opts,'-P',str(port),'root@'+host+':'+remote,str(dest)],check=True)
    archive=dest/Path(info['archive']).name
    manifest=json.loads((dest/Path(info['manifest']).name).read_text())
    assert digest(archive)==info['sha256']==manifest['archive_sha256'],'archive SHA mismatch'
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            assert member.isfile() and member.name in manifest['files'],'unexpected archive member'
            target=(dest/member.name).resolve()
            assert target.is_relative_to(dest.resolve()),'unsafe archive path'
        tar.extractall(dest,filter='data')
    for rel,record in manifest['files'].items():
        p=dest/rel
        assert p.stat().st_size==record['bytes'] and digest(p)==record['sha256'],'file SHA mismatch: '+rel
    # Exercise Linux and Git-Bash manifest modes with the same real archive digest.
    assert normalize_sha(info['sha256']+' *archive.tgz')==normalize_sha(info['sha256']+'  archive.tgz')
    evidence=dict(host=host,port=port,utc=stamp,roots=roots,files=len(manifest['files']),archive_sha256=info['sha256'],local=str(dest),verified=True)
    (dest/'COPY_VERIFIED.json').write_text(json.dumps(evidence,indent=2)+'\n')
    summary=HERE/('backup_'+str(port)+'_'+stamp+'.json');summary.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('host');ap.add_argument('port',type=int);ap.add_argument('roots',nargs='+');a=ap.parse_args()
    copy(a.host,a.port,a.roots)
