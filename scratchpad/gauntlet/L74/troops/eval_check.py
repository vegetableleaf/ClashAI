"""Eval-path check for the tower-troop option: the promotion eval's exact D3 command (gap.py / livecal / search_s0) on
the first N seeds of the live-pool plan (seed 741200), run from THIS checkout.

    cd CHECKOUT && ROYALE_RUNTIME=fork36-linux PYTHONPATH=. PY scratchpad/gauntlet/L74/troops/eval_check.py OUT N [EXTRA...]

Writes OUT/D3/matches.jsonl and OUT/rows.json (the per-match result fields, wall-clock fields dropped) so two
checkouts' outputs can be compared byte for byte (cmp)."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT/'scratchpad/gauntlet/L74/gap')]
import gap  # noqa: E402

CK = 'icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt'
out, n, extra = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3:]
plan = gap.prepare(out/'inputs', CK, 741200, None, .1, 'scratchpad/gauntlet/L74/mix/decks_live_eval.json')
job = dict(plan['jobs'][0], seeds=plan['jobs'][0]['seeds'][:n])
cmd = gap.command('D3', job, out/'inputs'/plan['censuses'][job['census']]['path'], out/'D3', sys.executable, extra)
env = dict(os.environ, ROYALE_HEROIW_FORM='hero', ROYALE_HEROIW_PRESS='live', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
           OPENBLAS_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT))
with (out/'D3.log').open('w') as log:
    subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
DROP = {'wall_s', 's_per_searched', 'search_s', 'wall_truncated'}
rows = sorted((json.loads(s) for s in (out/'D3/matches.jsonl').read_text().splitlines() if s.strip()), key=lambda r: r['seed'])
(out/'rows.json').write_text(json.dumps([{k: v for k, v in r.items() if k not in DROP} for r in rows], indent=0, sort_keys=True))
for r in rows:
    print(r['seed'], r['outcome'], r['crowns_for'], r['crowns_against'], r['tower_hp_diff'], r['plays_accepted'],
          r['end_tick'], r.get('opp_tower', '-'), r['opp_deck_name'])
