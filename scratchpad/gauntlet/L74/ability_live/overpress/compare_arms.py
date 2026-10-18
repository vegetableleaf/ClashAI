"""Overpress arms vs the promotion eval's Mark CXXXVIII arm (live IW rule), paired on (seed, census).
python compare_arms.py PROMO_RESULTS_DIR OVERPRESS_DIR
Per arm: win %, paired delta vs CXXXVIII (pp, 95% bootstrap CI, 10,000 draws), IW presses / match, presses per IW
deploy, matches with >= 1 press, ability_stats sums (when present), Tornado plays / match, games identical to the
promotion eval's row for the same checkpoint (determinism check)."""
import glob
import json
import random
import sys
from pathlib import Path

PROMO, OP = Path(sys.argv[1]), Path(sys.argv[2])


def load(pattern):
    rows = {}
    for f in [g for g in glob.glob(str(pattern)) if 'failed' not in g]:
        for line in open(f):
            r = json.loads(line)
            p = Path(f).parts
            rows[(p[-4].rsplit('_', 1)[-1], p[-2], r['seed'], r['learner_side'])] = r   # seed-start, chunk, seed, side
    return rows


def key_rows(d):
    """Rows re-keyed by (seed, learner_side, opp_deck): census name is not in the per-chunk files."""
    return d


arms = {'cxxxviii (promo, live rule)': key_rows(load(PROMO / 'eval/cxxxviii_74*/D3/*/matches.jsonl')),
        'cue_ab (promo, head greedy)': key_rows(load(PROMO / 'eval/cue_ab_74*/D3/*/matches.jsonl'))}
for name in ('cx_off', 'cx_never', 'cx_live', 'ab_head', 'ws_greedy', 'ws_sample', 'ab_sample', 'ws_live', 'ws_live_sample'):
    d = key_rows(load(OP / f'{name}_74*/D3/*/matches.jsonl'))
    if d:
        arms[name] = d
base = arms['cxxxviii (promo, live rule)']
rng = random.Random(0)
win = lambda r: r['outcome'] == 'win'
print(f"{'arm':30s} {'n':>4s} {'win%':>6s} {'d_pp vs CXXXVIII [95% CI]':>28s} {'press/m':>7s} {'/deploy':>7s} {'>=1':>5s} {'torn/m':>6s}  ability_stats per match")
for name, d in arms.items():
    ks = sorted(set(d) & set(base))
    diffs = [win(d[k]) - win(base[k]) for k in ks]
    boot = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(10000)) if diffs else [0]
    rows = list(d.values())
    pr = [sum(r.get('ability_presses', {}).get(str(r['learner_side']), {}).values()) for r in rows]
    dep = [r.get('ability_deployments', {}).get(str(r['learner_side']), {}).get('IceWizard', 0) for r in rows]
    torn = [sum(1 for p in r.get('own_plays', []) if p[2] == 'tornado' and p[3]) for r in rows]
    stats = [r['ability_stats'] for r in rows if r.get('ability_stats')]
    sdesc = ''
    if stats:
        s = {k: sum(x[k] for x in stats) for k in stats[0]}
        sdesc = (f"elixir {s['elixir']/len(stats):.2f}, in-radius/press {s['in_radius']/max(1, s['presses']):.2f}, "
                 f"hit2s/press {s['hit_2s']/max(1, s['presses']):.2f}, killed2s/press {s['killed_2s']/max(1, s['presses']):.2f}, "
                 f"presses hitting {s['presses_hit']/max(1, s['presses']):.2f}")
    print(f"{name:30s} {len(rows):4d} {100*sum(map(win, rows))/len(rows):6.2f} "
          f"{100*sum(diffs)/max(1, len(diffs)):+7.2f} [{100*boot[250]:+6.2f}, {100*boot[9750]:+6.2f}] n{len(ks):4d} "
          f"{sum(pr)/len(rows):7.3f} {sum(pr)/max(1, sum(dep)):7.3f} {sum(p > 0 for p in pr)/len(rows):5.3f} {sum(torn)/len(rows):6.3f}  {sdesc}")
for a, b in (('cx_live', 'cxxxviii (promo, live rule)'), ('ab_head', 'cue_ab (promo, head greedy)')):
    if a in arms:
        ks = set(arms[a]) & set(arms[b])
        same = sum(arms[a][k]['outcome'] == arms[b][k]['outcome'] and arms[a][k]['own_plays'] == arms[b][k]['own_plays'] for k in ks)
        print(f'determinism {a} vs {b}: {same}/{len(ks)} games identical (outcome + every own play)')
