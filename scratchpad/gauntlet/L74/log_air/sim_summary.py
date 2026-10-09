"""log_air SIM A/B summary.  python sim_summary.py <sim dir> [evo,lad,air]
Paired by (census, match tag): wins (win 1, draw .5), better / worse / same, mean paired difference in percentage points with a
95 % normal CI (non-inferiority bar: lower bound > -3 pp), two-sided sign test; per arm the Log plays per match, the corridor
class of each Log play (hits / only_air / empty), and for the log_air arms the touched Logs (re-aimed cell_kind or blocked)
and the outcomes of the matches where it fired."""
import glob, json, math, os, sys
from collections import Counter, defaultdict

O = sys.argv[1]
SUF = sys.argv[2].split(',') if len(sys.argv) > 2 else ['evo', 'lad', 'air']


def load(arm):
    out = {}
    for s in SUF:
        p = f'{O}/{arm}_{s}/matches.jsonl'
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                if r['arm'] == 'plain':
                    out[(s, r['tag'])] = r
    return out


def fires(arm):
    out = defaultdict(list)
    for s in SUF:
        for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl'):
            for line in open(f):
                x = json.loads(line)
                out[(s, x['tag'])].append(x)
    return out


def score(r):
    return {'win': 1.0, 'draw': 0.5}.get(r['outcome'], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def compare(a, b, an, bn, keys, label):
    d = [score(b[k]) - score(a[k]) for k in keys]
    n = len(d)
    if not n:
        return
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(n - 1, 1))
    hw = 1.96 * sd / math.sqrt(n)
    up, dn = sum(x > 0 for x in d), sum(x < 0 for x in d)
    print(f'  [{label}] {bn} vs {an}: wins {sum(score(b[k]) for k in keys):.1f} vs {sum(score(a[k]) for k in keys):.1f} of {n}; '
          f'better {up} / worse {dn} / same {n - up - dn}; diff {100 * m:+.1f} pp, 95% CI [{100 * (m - hw):+.1f}, {100 * (m + hw):+.1f}] '
          f'(half-width {100 * hw:.1f}); sign p {sign_p(up, dn):.3f}; non-inferior (lower > -3 pp): {100 * (m - hw) > -3}')


arms = {n: load(n) for n in ('base', 'retarget', 'block')}
fr = {n: fires(n) for n in arms}
for n, v in arms.items():
    print(f'{n}: {len(v)} games')
for bn in ('retarget', 'block'):
    keys = sorted(set(arms['base']) & set(arms[bn]))
    print(f'--- {bn} vs base, paired games {len(keys)}')
    compare(arms['base'], arms[bn], 'base', bn, keys, 'all')
    for s in SUF:
        compare(arms['base'], arms[bn], 'base', bn, [k for k in keys if k[0] == s], s)
    hit = [k for k in keys if any(x.get('why') == 'log_air' for x in fr[bn].get(k, []))]
    compare(arms['base'], arms[bn], 'base', bn, hit, 'matches where log_air fired')
    print(f'  matches where log_air fired: {len(hit)} of {len(keys)}')
print('--- Log plays per arm (play = True) and corridor class at the decision')
for n in arms:
    games = len(arms[n])
    plays = [x for v in fr[n].values() for x in v if x['play']]
    kinds = Counter(x['kind'] for x in plays)
    print(f'  {n}: {len(plays)} Log plays in {games} games = {len(plays) / max(games, 1):.2f} per game; corridor {dict(kinds)}'
          f' ({100 * kinds["only_air"] / max(len(plays), 1):.1f} % only_air, {100 * kinds["empty"] / max(len(plays), 1):.1f} % empty)')
    if n != 'base':
        touched = [x for v in fr[n].values() for x in v if x.get('why') == 'log_air']
        if n == 'retarget':
            print(f'    log_air re-aimed {len(touched)} Logs ({len(touched) / max(games, 1):.3f} per game); new cell: '
                  f'{dict(Counter(x.get("cell_kind") for x in touched))}; new corridor class {dict(Counter(x["kind"] for x in touched))}; '
                  f'hits something (ground elixir or tower) {sum(x["kind"] == "hits" for x in touched)} of {len(touched)}; '
                  f'mean ground elixir {sum(x["ground_value"] for x in touched) / max(len(touched), 1):.2f}')
        else:
            print(f'    log_air blocked {len(touched)} Logs ({len(touched) / max(games, 1):.3f} per game)')
