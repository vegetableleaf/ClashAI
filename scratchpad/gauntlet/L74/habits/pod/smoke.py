"""Pod smoke for the habits probe: one 2-seed D3 worker per env setting (run from /workspace/habits/cb)."""
import json, os, subprocess, sys, shutil
from pathlib import Path
sys.path.insert(0, 'scratchpad/gauntlet/L74/gap')
import gap
CK = 'icebow/data/bench/rl_royale/rlarm_succ_levels/rlarm_succ_levels_u0065_grafted.pt'
EXTRA = '--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014'.split()
D = Path('/workspace/habits/smoke'); shutil.rmtree(D, ignore_errors=True)
plan = gap.prepare(D/'inputs', CK, 741200, census_file='scratchpad/gauntlet/L74/mix/decks_live_eval.json')
job = dict(plan['jobs'][0], seeds=plan['jobs'][0]['seeds'][:2])
for name, extra_env in (('base', {}), ('g5m', dict(HABITS_XBOW_GATE='5', HABITS_GATE_MODE='mask')), ('z0', dict(HABITS_OPP_CONST='0'))):
    out = D/name
    cmd = gap.command('D3', job, D/'inputs'/plan['censuses'][job['census']]['path'], out, '/workspace/venvf36/bin/python', EXTRA)
    env = dict(os.environ, ROYALE_RUNTIME='fork36-linux', ROYALE_HEROIW_FORM='hero', ROYALE_HEROIW_PRESS='live', OMP_NUM_THREADS='1',
               MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.getcwd(), HABITS_REC='1', **extra_env)
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print(name, 'exit', r.returncode, r.stdout[-600:], r.stderr[-1500:])
    for l in open(out/'matches.jsonl'):
        j = json.loads(l); h = j['hab']
        print(name, j['seed'], j['outcome'], 'own', len(h['own']), 'opp', len(h['opp']), 'samples', len(h['samples']), 'bytes', len(l),
              {k: j[k] for k in j if k.startswith('hab_gate')}, h['env'], h['L'], h['mirror'])
        print('  own[:3]', h['own'][:3]); print('  opp[:3]', h['opp'][:3]); print('  s[5]', json.dumps(h['samples'][5])[:700])
