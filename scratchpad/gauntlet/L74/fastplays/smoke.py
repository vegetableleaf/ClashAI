"""Pod smoke for the fastplays arms: the FIRST job (12 seeds) of the factorial plan under each arm's EXTRA, the exact D3 command
gap.py runs. off rows minus own_plays must equal the factorial ref_cxxxviii rows of the same seeds (REF, a matches.jsonl).
    python smoke.py OUT REF_MATCHES"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'scratchpad/gauntlet/L74/gap'), str(ROOT)]
import gap  # noqa: E402

CK = 'icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt'
BASE = ('--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops '
        'DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --record-plays')
FAST = '--pipeline-decisions --pipeline-tau-delta 0'
COMBO = '--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river on'
ARMS = {'off': BASE, 'on': f'{BASE} {FAST}', 'offc': f'{BASE} {COMBO}', 'onc': f'{BASE} {COMBO} {FAST}'}

out, ref = Path(sys.argv[1]), Path(sys.argv[2])
plan = gap.prepare(out / 'inputs', CK, 741200, census_file='scratchpad/gauntlet/L74/mix/decks_live_eval.json')
job = plan['jobs'][0]
env = dict(os.environ, ROYALE_RUNTIME='fork36-linux', ROYALE_HEROIW_FORM='hero', ROYALE_HEROIW_PRESS='live', OMP_NUM_THREADS='1',
           PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
procs = {}
for arm, extra in ARMS.items():
    dest = out / arm
    cmd = gap.command('D3', job, out / 'inputs' / plan['censuses'][job['census']]['path'], dest, sys.executable,
                      extra.split())
    procs[arm] = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(out / f'{arm}.log', 'w'), stderr=subprocess.STDOUT)
for arm, p in procs.items():
    print(arm, 'exit', p.wait(), flush=True)
refrows = {r['seed']: r for r in map(json.loads, ref.read_text().splitlines()) if r['seed'] in job['seeds']}
for arm in ARMS:
    f = out / arm / 'matches.jsonl'
    rows = [json.loads(s) for s in f.read_text().splitlines()] if f.exists() else []
    same = 0
    for r in rows:
        r2 = {k: v for k, v in r.items() if k not in ('own_plays', 'wall_s')}
        q = {k: v for k, v in refrows.get(r['seed'], {}).items() if k not in ('wall_s', 'census')}
        same += r2 == q
    print(arm, len(rows), 'rows; identical to ref (minus own_plays, wall_s):', same, 'wins', sum(r['outcome'] == 'win' for r in rows),
          'pipe', [r.get('pipeline_decisions') for r in rows][:3], 'fu', [r.get('follow_ups') for r in rows][:3])
