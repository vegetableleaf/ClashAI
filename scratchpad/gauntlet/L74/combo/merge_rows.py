"""L74 combo (10-17): assemble the analysis layout DIR/<arm>_<seed>/D3/matches.jsonl from the pod parts.
    python merge_rows.py OUT ARM SEED PART_DIR [PART_DIR ...]           job-slice parts (combo_jobs.py OUT dirs): concatenated
    python merge_rows.py OUT cur SEED --offc OFFC_MATCHES PICKS_DIR      the fast-plays offc rows (= cur, identity-checked on 12 seeds)
        with every row whose match had a cur combo replaced by its re-run (+ spell log / combo_rule); own_plays_x = offc's P1 own_plays
Checks: no duplicate (census, seed); with --offc, every re-run row equals its offc row outside the measurement keys."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from combo_arms import MEASURE_KEYS  # noqa: E402


def rows(p):
    return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]


out, arm, seed = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
dest = out / f'{arm}_{seed}' / 'D3'
dest.mkdir(parents=True, exist_ok=True)
if sys.argv[4] == '--offc':
    base = rows(sys.argv[5])
    rerun = {(r['census'], r['seed']): r for r in rows(Path(sys.argv[6]) / 'D3' / 'matches.jsonl')}
    merged, same = [], 0
    for r in base:
        k = (r['census'], r['seed'])
        if k in rerun:
            q = rerun[k]
            same += {a: b for a, b in q.items() if a not in MEASURE_KEYS} == {a: b for a, b in r.items() if a not in MEASURE_KEYS}
            merged.append(q)
        else:
            merged.append(dict(r, own_plays_x=r.get('own_plays')))
    print(f'cur {seed}: {len(merged)} rows, {len(rerun)} re-run, {same} of them identical to offc outside the measurement keys')
else:
    merged = [r for d in sys.argv[4:] for r in rows(Path(d) / 'D3' / 'matches.jsonl')]
keys = [(r['census'], r['seed']) for r in merged]
assert len(keys) == len(set(keys)), 'duplicate (census, seed)'
(dest / 'matches.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in merged))
print(dest, len(merged), 'rows')
