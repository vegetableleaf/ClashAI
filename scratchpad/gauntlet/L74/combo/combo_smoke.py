"""L74 combo pod smoke (10-17): the FIRST job (12 seeds) of the 741200 factorial plan under each arm, the exact D3 command gap.py runs
(+ COMBO_MEASURE=1: measure_shim). The cur arm's rows minus the measurement keys must equal the fast-plays 'offc' rows of the same
seeds (REF = offc_741200/D3/matches.jsonl): the old combo options are byte-identical after the change, tracker included.
    python combo_smoke.py OUT REF_MATCHES [ARM ...]"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / 'scratchpad/gauntlet/L74/gap'), str(ROOT)]
import gap  # noqa: E402
from combo_arms import ARMS, CK, MEASURE_KEYS  # noqa: E402

out, ref = Path(sys.argv[1]), Path(sys.argv[2])
arms = sys.argv[3:] or list(ARMS)
import tempfile  # noqa: E402
plan = gap.prepare((Path(tempfile.mkdtemp()) / 'inputs') if os.environ.get('SMOKE_COMPARE_ONLY') else out / 'inputs', CK, 741200, census_file='scratchpad/gauntlet/L74/mix/decks_live_eval.json')
job = plan['jobs'][0]
env = dict(os.environ, ROYALE_RUNTIME='fork36-linux', ROYALE_HEROIW_FORM='hero', ROYALE_HEROIW_PRESS='live', OMP_NUM_THREADS='1',
           PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1', COMBO_MEASURE='1')
procs = {}
for arm in [] if os.environ.get('SMOKE_COMPARE_ONLY') else arms:     # SMOKE_COMPARE_ONLY=1: compare finished rows only
    cmd = gap.command('D3', job, out / 'inputs' / plan['censuses'][job['census']]['path'], out / arm, sys.executable, ARMS[arm].split())
    procs[arm] = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(out / f'{arm}.log', 'w'), stderr=subprocess.STDOUT)
for arm, p in procs.items():
    print(arm, 'exit', p.wait(), flush=True)
refrows = {r['seed']: r for r in map(json.loads, ref.read_text().splitlines()) if r['seed'] in job['seeds'] and r['census'] == job['census']}
for arm in arms:
    f = out / arm / 'matches.jsonl'
    rows = [json.loads(s) for s in f.read_text().splitlines()] if f.exists() else []
    same = 0
    for r in rows:
        r2 = {k: v for k, v in r.items() if k not in MEASURE_KEYS}
        q = {k: v for k, v in refrows.get(r['seed'], {}).items() if k not in MEASURE_KEYS + ('census',)}
        same += r2 == q
        if r2 != q and arm == 'cur':
            print('  DIFF seed', r['seed'], sorted(k for k in set(r2) | set(q) if r2.get(k) != q.get(k))[:12])
    fires = sum(len(r.get('combo_rule', [])) for r in rows)
    ev = [e for r in rows for e in (r.get('spell') or {}).get('events', [])]
    print(arm, len(rows), 'rows; identical to offc (minus measurement keys):', same, '| wins', sum(r['outcome'] == 'win' for r in rows),
          '| rule combos', fires, '| rocket events', len(ev), 'with a setup tornado', sum(e.get('tornado') is not None for e in ev))
