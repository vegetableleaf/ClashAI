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
    """Resume after maturin.exe was blocked (OS4551): stages and cargo build already ran; see assemble_sim_wheel.py."""
    sim=STACK/'RoyaleSim';gym=STACK/'RoyaleGym'
    for name,pin in PINS.items():
        if git(STACK/name,'rev-parse','HEAD')!=pin or git(STACK/name,'status','--porcelain','--untracked-files=no'):
            raise ValueError('Pinned source is not clean: '+name)
    run('assemble_sim_wheel',[PY,HERE/'assemble_sim_wheel.py'],sim)
    run('build_gym',[PY,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',STACK/'wheels',gym],STACK)
    wheels=sorted((STACK/'wheels').glob('*.whl'))
    if len(wheels)!=2:
        raise ValueError('Expected exactly the two pinned wheels')
    runtime=STACK/'runtime'
    if runtime.exists():
        raise ValueError('Fresh runtime destination required')
    run('install_isolated',[PY,'-m','pip','install','--no-deps','--no-index','--target',runtime,*wheels],STACK)
    manifest=dict(schema=1,pins=PINS,build_script_sha256=sha(__file__),
        build_note='royalesim wheel assembled by assemble_sim_wheel.py from cargo output (maturin.exe blocked by OS4551); build.py failed at build_sim, see build_sim_maturin_blocked.json',
        assemble_script_sha256=sha(HERE/'assemble_sim_wheel.py'),
        wheels={p.name:sha(p) for p in wheels},runtime=str(runtime),
        files={str(p.relative_to(runtime)):sha(p) for p in sorted(runtime.rglob('*'))
               if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'})
    (HERE/'build_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('UPSTREAM_PAIR_BUILT_ISOLATED_REQUIRES_TESTS',flush=True)


if __name__=='__main__':main()
