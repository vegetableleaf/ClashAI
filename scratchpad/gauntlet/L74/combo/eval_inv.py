"""Pod check that --spell-log is MEASUREMENT ONLY on the real promotion eval: the FIRST job (12 seeds) of the factorial plan, the
exact D3 command gap.py runs (fork36-linux, Hero IW press live, Mark CXXXVIII), with and without --spell-log, with and without
the live combo rules. Every row minus 'spell' / 'wall_s' must be identical between the twin arms (the tracker makes the engine
step one tick at a time while our Rocket is up; RoyaleSim must be step-size invariant). Prints the spell events it logged.
    python eval_inv.py OUT        (cd CB, PYTHONPATH=CB; 4 processes, one per arm)"""
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
COMBO = '--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river on'
ARMS = {'off': BASE, 'sv': f'{BASE} --spell-log', 'offc': f'{BASE} {COMBO}', 'svc': f'{BASE} {COMBO} --spell-log'}
TWINS = (('off', 'sv'), ('offc', 'svc'))

out = Path(sys.argv[1])
plan = gap.prepare(out / 'inputs', CK, 741200, census_file='scratchpad/gauntlet/L74/mix/decks_live_eval.json')
job = plan['jobs'][0]
env = dict(os.environ, ROYALE_RUNTIME='fork36-linux', ROYALE_HEROIW_FORM='hero', ROYALE_HEROIW_PRESS='live', OMP_NUM_THREADS='1',
           PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
procs = {}
for arm, extra in ARMS.items():
    cmd = gap.command('D3', job, out / 'inputs' / plan['censuses'][job['census']]['path'], out / arm, sys.executable,
                      extra.split())
    procs[arm] = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(out / f'{arm}.log', 'w'), stderr=subprocess.STDOUT)
for arm, p in procs.items():
    print(arm, 'exit', p.wait(), flush=True)
rows = {}
for arm in ARMS:
    f = out / arm / 'matches.jsonl'
    rows[arm] = {r['seed']: r for r in map(json.loads, f.read_text().splitlines())} if f.exists() else {}
ok = True
for a, b in TWINS:
    strip = (lambda r: {k: v for k, v in r.items() if k not in ('spell', 'wall_s')})
    same = sum(strip(rows[a][s]) == strip(rows[b].get(s, {})) for s in rows[a])
    ok &= same == len(rows[a]) == len(job['seeds'])
    print(f"{a} vs {b}: {len(rows[a])} / {len(rows[b])} rows, identical minus spell / wall_s: {same}; wins "
          f"{sum(r['outcome'] == 'win' for r in rows[a].values())} / {sum(r['outcome'] == 'win' for r in rows[b].values())}")
    for s, r in sorted(rows[b].items()):
        sp = r.get('spell') or {}
        ev = [{k: e[k] for k in ('tick', 'aim', 'kill', 'dmg', 'princess', 'king')} | {'tornado': bool(e['tornado'])}
              for e in sp.get('events', [])]
        print(f"  {b} seed {s} {r['outcome']}: {json.dumps(sp.get('summary'))} {json.dumps(ev)}")
print('EVAL_INV', 'PASS' if ok else 'FAIL')
