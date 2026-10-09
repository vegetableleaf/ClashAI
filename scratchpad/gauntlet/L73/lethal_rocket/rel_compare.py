"""sim_rel.sh comparison.  python rel_compare.py ~/lethal/sim_rel
off identity (main_off vs br_off: full match records); on arms: wins, paired sign test, changed matches with fires."""
import glob, json, math, os, sys
from collections import Counter, defaultdict

O = sys.argv[1]
KEYS = ('outcome', 'crowns_for', 'crowns_against', 'tower_hp_for', 'tower_hp_against', 'end_tick', 'plays_attempted',
        'plays_accepted', 'opp_plays_accepted', 'decisions', 'behaviour')


def load(arm):
    out = {}
    for s in ('evo', 'lad'):
        p = f'{O}/v3_{arm}_{s}/matches.jsonl'
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line)
                out[(s, r['tag'])] = r
    return out


def fires(arm):
    out = defaultdict(list)
    for s in ('evo', 'lad'):
        for f in glob.glob(f'{O}/fires_{arm}_{s}/fires_*.jsonl'):
            for line in open(f):
                x = json.loads(line)
                out[(s, x['tag'])].append((x['why'], round(x['t_sec'], 2), x['target']['lane'], x['target']['hp']))
    return out


def score(r):
    return {'win': 1.0, 'draw': 0.5}.get(r['outcome'], 0.0)


def sign_p(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


a, b = load('main_off'), load('br_off')
common = sorted(set(a) & set(b))
diff = [k for k in common if tuple(json.dumps(a[k].get(x), sort_keys=True) for x in KEYS) !=
        tuple(json.dumps(b[k].get(x), sort_keys=True) for x in KEYS)]
print(f'off identity (main_off vs br_off): {len(common)} common; identical {len(common) - len(diff)}; differ {diff[:10]}')
a, b = load('main_on'), load('br_on')
keys = sorted(set(a) & set(b))
print(f'on: paired {len(keys)}; main wins {sum(score(a[k]) for k in keys):.1f}, branch wins {sum(score(b[k]) for k in keys):.1f}')
up = sum(score(b[k]) > score(a[k]) for k in keys); dn = sum(score(b[k]) < score(a[k]) for k in keys)
print(f'  branch better {up} / worse {dn} (sign test p {sign_p(up, dn):.3f})')
fa, fb = fires('main_on'), fires('br_on')
print(f'  lethal fires: main {sum(map(len, fa.values()))} ({dict(Counter(f[0] for v in fa.values() for f in v))}), '
      f'branch {sum(map(len, fb.values()))} ({dict(Counter(f[0] for v in fb.values() for f in v))})')
changed = [k for k in keys if fa.get(k) != fb.get(k) or score(a[k]) != score(b[k])]
print(f'  matches whose fires or result differ: {len(changed)}')
for k in changed:
    print(f'    {k}: main {a[k]["outcome"]} end {a[k]["end_tick"]} fires {fa.get(k)} | branch {b[k]["outcome"]} '
          f'end {b[k]["end_tick"]} fires {fb.get(k)}')
