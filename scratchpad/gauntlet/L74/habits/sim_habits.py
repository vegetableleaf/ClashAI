"""SIM promotion-eval habit rows (--habit-log), CXXXVIII vs CLIII, standard + fresh seeds: Rockets / match by kind, early bridge
X-Bow, win. Paired by (seed, census) across the two checkpoints.
    python sim_habits.py"""
import json
import random
from pathlib import Path

B = Path('C:/Users/benpe/pod_backup_weekend')
RUNS = {('CXXXVIII', 'std'): [B / f'pod1017_cue_ab/results/eval/cxxxviii_{s}/D3/matches.jsonl' for s in (741200, 742000)],
        ('CLIII', 'std'): [B / f'pod1017_successor/succ_levels/eval/succ_levels_{s}/D3/matches.jsonl' for s in (741200, 742000)],
        ('CXXXVIII', 'fresh'): [B / f'pod1017_successor/fresh_ref_cxxxviii/eval/fresh_ref_cxxxviii_{s}/D3/matches.jsonl' for s in (743000, 744000)],
        ('CLIII', 'fresh'): [B / f'pod1017_successor/fresh_succ_levels/eval/fresh_succ_levels_{s}/D3/matches.jsonl' for s in (743000, 744000)]}


def rows(paths):
    out = {}
    for p in paths:
        for l in open(p, encoding='utf-8'):
            r = json.loads(l)
            out[(r['seed'], r.get('census'))] = r
    return out


def stats(R):
    n = len(R)
    h = [r['habits'] for r in R]
    op = [r for r in R if r['habits']['xbow_open_hand']]
    return dict(n=n, win=sum(r['outcome'] == 'win' for r in R) / n, rocket=sum(x['rocket'] for x in h) / n,
                rocket_princess=sum(x['rocket_princess'] for x in h) / n, rocket_lethal=sum(x['rocket_lethal'] for x in h) / n,
                rocket_late=sum(x['late']['rocket'] for x in h) / n, tornado=sum(x['tornado'] for x in h) / n,
                xbow_off=sum(x['xbow_off'] for x in h) / n, xbow=sum(x['xbow'] for x in h) / n,
                early_bridge_given_open=sum(r['habits']['xbow_off_first2'] for r in op) / max(1, len(op)), n_open=len(op),
                win_early=sum(r['outcome'] == 'win' for r in op if r['habits']['xbow_off_first2']) / max(1, sum(r['habits']['xbow_off_first2'] for r in op)),
                win_not=sum(r['outcome'] == 'win' for r in op if not r['habits']['xbow_off_first2']) / max(1, sum(not r['habits']['xbow_off_first2'] for r in op)))


def paired(a, b, f, B_=2000):
    k = sorted(set(a) & set(b))
    d = [f(a[x]) - f(b[x]) for x in k]
    rng = random.Random(0)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(B_))
    return round(sum(d) / len(d), 3), (round(bs[50], 3), round(bs[-51], 3)), len(k)


R = {k: rows(v) for k, v in RUNS.items()}
for k, v in R.items():
    print(k, {a: round(b, 3) if isinstance(b, float) else b for a, b in stats(list(v.values())).items()})
for s in ('std', 'fresh'):
    a, b = R[('CLIII', s)], R[('CXXXVIII', s)]
    print(f'CLIII - CXXXVIII ({s}, paired by seed): Rockets/match', paired(a, b, lambda r: r['habits']['rocket']),
          'princess Rockets', paired(a, b, lambda r: r['habits']['rocket_princess']),
          'lethal-rule Rockets', paired(a, b, lambda r: r['habits']['rocket_lethal']),
          'win', paired(a, b, lambda r: float(r['outcome'] == 'win')))
