"""S2-01 / S2-03 dry run: gap.py's own prepare + run_arm (D3, the promotion-eval EXTRA) on the FIRST 2 seeds of the first job.
    cd CHECKOUT && PYTHONPATH=. ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero PY pod/dry.py OUT CKPT CENSUS [OPP_CKPT [OPP_T [OPP_DE]]]
Prints the 2 rows' outcome / end_tick / opponent levels and the run.json receipt shas."""
import json, sys
from pathlib import Path
sys.path.insert(0, 'scratchpad/gauntlet/L74/gap')
import gap
EXTRA = '--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014'
out, ck, census = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
opp = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != '-' else None
T = float(sys.argv[5]) if len(sys.argv) > 5 else .1
de = int(sys.argv[6]) if len(sys.argv) > 6 else None
plan = gap.prepare(out/'inputs', ck, 741200, opp, T, census)
plan['jobs'] = [dict(plan['jobs'][0], seeds=plan['jobs'][0]['seeds'][:2])]
gap.run_arm('D3', plan, out/'inputs', out/'D3', sys.executable, 2, 'hero', 'live', EXTRA.split(), (), gap.opp_flags(de, None),
            'fork36-linux')
rows = [json.loads(s) for s in (out/'D3'/'matches.jsonl').read_text().splitlines() if s.strip()]
rj = json.loads(next((out/'D3').glob('*/run.json')).read_text())
assert len(rows) == 2, len(rows)
for r in rows:
    print('row', r['seed'], r['outcome'], 'end_tick', r['end_tick'], 'opp levels', r.get('levels', {}).get('opp'), 'opp_tower', r.get('opp_tower'))
print('receipt gen', rj['gen_sha256'][:8], 'opp', rj['opp_gen_sha256'][:8], 'live_levels', rj.get('live_levels'),
      'opp_decide_every', rj.get('opp_decide_every'))
print('DRY_OK')
