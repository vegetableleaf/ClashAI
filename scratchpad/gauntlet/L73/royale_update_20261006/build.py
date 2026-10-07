"""Build the pinned upstream pair without touching either active experiment runtime."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).parent
STACK=ROOT/'research/ext/Royale-20261006'
PY=ROOT/'research/ext/Royale/.venv/Scripts/python.exe'
PINS=dict(RoyaleSim='d088f53162c3d3349f192276621a372826653fb3',
          RoyaleGym='75adf8b396c2d10a85fbaa33a58f6940ca2f53fc')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(folder,*args):
    return subprocess.check_output(['git','-C',str(folder),*args],text=True,encoding='utf-8').strip()


def run(name,command,cwd):
    receipt=HERE/(name+'.json')
    if receipt.exists():
        raise ValueError('Fresh build step required: '+name)
    env=dict(os.environ,CARGO_BUILD_JOBS='6')
    log=HERE/(name+'.out')
    print('START',name,flush=True);start=time.time()
    with log.open('w',encoding='utf-8') as stream:
        p=subprocess.run([str(s) for s in command],cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
    receipt.write_text(json.dumps(dict(command=[str(s) for s in command],cwd=str(cwd),exit_code=p.returncode,
        output_sha256=sha(log),seconds=time.time()-start),indent=2))
    if p.returncode:
        raise RuntimeError(name+' failed; see '+str(log))
    print('DONE',name,flush=True)


def main():
    inventory={}
    for name,pin in PINS.items():
        previous=ROOT/'research/ext/Royale-20261005'/name;source=STACK/name
        if git(source,'rev-parse','HEAD')!=pin or git(source,'status','--porcelain','--untracked-files=no'):
            raise ValueError('Pinned source is not clean: '+name)
        old=git(previous,'rev-parse','HEAD')
        commits=[]
        for line in git(previous,'log','--format=%H\t%cs\t%s',old+'..'+pin).splitlines():
            commit,date,subject=line.split('\t',2)
            commits.append(dict(commit=commit,date=date,subject=subject))
        inventory[name]=dict(old=old,new=pin,commits=commits,
            tracked_local_changes=git(previous,'status','--porcelain','--untracked-files=no'),
            changed_files=git(previous,'diff','--name-status',old,pin).splitlines())
    old=ROOT/'research/ext/Royale-20261005/RoyaleSim'
    inventory['old_runtime_data']={str(p.relative_to(old)):sha(p) for p in [old/'data/calibration.json',
        old/'data/derived/cards.json',old/'data/derived/globals.json',old/'data/derived/arena.json']}
    (HERE/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    sim=STACK/'RoyaleSim';gym=STACK/'RoyaleGym'
    run('stage_arena',[PY,'tools/extract_arena.py'],sim)
    run('stage_cards_2018',[PY,'tools/extract_cards.py','--vintage','2018'],sim)
    shutil.copy2(sim/'data/derived/cards-15.535.json',sim/'data/derived/cards.json')
    run('stage_globals',[PY,'tools/extract_globals.py'],sim)
    # The upstream stager removes only this generated package-data directory.
    target=(sim/'python/royalesim/data').resolve()
    if not target.is_relative_to(STACK.resolve()) or target.exists():
        raise ValueError('Expected a fresh isolated package-data destination')
    run('stage_wheel_data',[PY,'tools/stage_wheel_data.py'],sim)
    run('build_sim',[PY,'-m','maturin','build','--release','--no-default-features','-i',PY,'--out',STACK/'wheels'],sim)
    run('build_gym',[PY,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',STACK/'wheels',gym],STACK)
    wheels=sorted((STACK/'wheels').glob('*.whl'))
    if len(wheels)!=2:
        raise ValueError('Expected exactly the two pinned wheels')
    runtime=STACK/'runtime'
    if runtime.exists():
        raise ValueError('Fresh runtime destination required')
    run('install_isolated',[PY,'-m','pip','install','--no-deps','--no-index','--target',runtime,*wheels],STACK)
    manifest=dict(schema=1,pins=PINS,build_script_sha256=sha(__file__),
        wheels={p.name:sha(p) for p in wheels},runtime=str(runtime),
        files={str(p.relative_to(runtime)):sha(p) for p in sorted(runtime.rglob('*'))
               if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'})
    (HERE/'build_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('UPSTREAM_PAIR_BUILT_ISOLATED_REQUIRES_TESTS',flush=True)


if __name__=='__main__':main()
