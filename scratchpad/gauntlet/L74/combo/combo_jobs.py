"""L74 combo (10-17): gap.py's D3 run on a SLICE of a paired seed block's jobs (so two pods can share one block), or on a hand-picked
seed list. Same plan (gap.prepare), same command (gap.command 'D3' + combo_arms.ARMS[ARM] as --extra), same rows (+ 'census').
    python combo_jobs.py ARM SEED_START A B WORKERS OUT          jobs A..B-1 of the block's 40 (12 seeds each)
    python combo_jobs.py ARM SEED_START picks:FILE WORKERS OUT   only the (census, seed) pairs in FILE (json [[census, seed], ...])
-> OUT/D3/matches.jsonl (+ OUT/inputs). Needs COMBO_MEASURE=1 in the environment for measure_shim (combo_queue.sh sets it)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / 'scratchpad/gauntlet/L74/gap'), str(HERE), str(ROOT)]
import gap  # noqa: E402
from combo_arms import ARMS, CK  # noqa: E402

arm, seed = sys.argv[1], int(sys.argv[2])
if sys.argv[3].startswith('picks:'):
    workers, out = int(sys.argv[4]), Path(sys.argv[5])
    picks = {tuple(p) for p in json.loads(Path(sys.argv[3][6:]).read_text())}
else:
    a, b, workers, out = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), Path(sys.argv[6])
    picks = None
plan = gap.prepare(out / 'inputs', CK, seed, census_file='scratchpad/gauntlet/L74/mix/decks_live_eval.json')
if picks is None:
    plan['jobs'] = plan['jobs'][a:b]
else:
    plan['jobs'] = [dict(j, seeds=[s for s in j['seeds'] if (j['census'], s) in picks]) for j in plan['jobs']]
    plan['jobs'] = [j for j in plan['jobs'] if j['seeds']]
print(arm, seed, len(plan['jobs']), 'jobs', sum(len(j['seeds']) for j in plan['jobs']), 'matches', flush=True)
gap.run_arm('D3', plan, out / 'inputs', out / 'D3', sys.executable, workers, extra=ARMS[arm].split(), runtime='fork36-linux')
