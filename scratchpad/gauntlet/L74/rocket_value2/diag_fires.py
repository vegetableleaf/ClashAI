"""Why did iteration 1 (--rocket-value, cost x hp fraction) lose?  Paired by (census, tag), first fire only.
  python diag_fires.py DIR [ARM=rv9]     DIR/{base,ARM}_{evo,lad}/matches.jsonl + DIR/fires_{base,ARM}_{evo,lad}/bw_*.jsonl (rv2_diag_s0.py)

For every first fire of ARM (a decision with why == ARM's override) we look at
  A  what was in the blast (names, hp, elixir value, level-11 Rocket damage vs the body's hp),
  B  the board 3 / 6 / 10 s after the fire in ARM and in BASE (same seed, identical until the fire): enemy hp-weighted elixir on my half,
     my elixir, my tower HP, my unit value;
  C  what BASE did in the 10 s after the fire (cards played) and what ARM did.
Value of a body = card cost / bodies x hp fraction (decision_options.body_value)."""
import glob, json, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.getcwd())
import numpy as np
from pipeline import decision_options as D
from pipeline import vocab
from pipeline.rocket_teaching import scaled_stat, catalog

DIR, ARM = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'rv9')
WHY = 'rocket_value'
RADIUS = 2.0
KEY = {}


def stat(name):
    """(elixir value per body, hp level 11, collision radius tiles) of a vocab name, from the catalog (cached); None unknown."""
    if name in KEY:
        return KEY[name]
    out = None
    try:
        k = vocab.base_key(name)
        out = (D.unit_values().get(k, 0.0), None, None)
    except Exception:
        pass
    KEY[name] = out
    return out


def val(name, hp):
    s = stat(name)
    return 0.0 if s is None or hp is None or name.endswith('_ability') else s[0] * hp


def load(arm, census):
    out = defaultdict(list)
    for f in glob.glob(f'{DIR}/fires_{arm}_{census}/bw_*.jsonl'):
        for line in open(f):
            d = json.loads(line)
            out[d['tag']].append(d)
    for v in out.values():
        v.sort(key=lambda d: d['t'])
    return out


def matches(arm, census):
    out = {}
    for line in open(f'{DIR}/{arm}_{census}/matches.jsonl'):
        r = json.loads(line)
        if r.get('arm') == 'plain':
            out[r['tag']] = r
    return out


def score(r): return {'win': 1.0, 'draw': 0.5}.get(r['outcome'], 0.0)


def on_my_half(b): return b[2] >= 16.0


def board_at(rows, t):
    """The last logged board with time <= t (None if none)."""
    prev = None
    for d in rows:
        if d['t'] <= t + 1e-6:
            prev = d
        else:
            break
    return prev


def summ(d):
    en = sum(val(n, h) for n, x, y, h in d['enemy'] if y >= 16.0)
    me = sum(val(n, h) for n, x, y, h in d['mine'])
    my_tow = sum((tw[3] or 0) for tw in d['towers'] if tw[0] == 0 and tw[1] == 'princess')
    return dict(en=en, me=me, el=d['el'], tow=my_tow)


rows = []
for census in ('evo', 'lad'):
    A, B = matches('base', census), matches(ARM, census)
    FA, FB = load('base', census), load(ARM, census)
    for tag, bws in FB.items():
        fires = [d for d in bws if d['play'] and d['why'] == WHY]
        if not fires or tag not in A or tag not in B:
            continue
        f = fires[0]
        t0 = f['t']
        base_rows = FA.get(tag, [])
        cx, cy = f['cell']
        inside = [(n, x, y, h) for n, x, y, h in f['enemy'] if np.hypot(x - cx, y - cy) <= RADIUS + 0.5]
        rec = dict(census=census, tag=tag, t0=t0, el=f['el'], hand=f['hand'], cell=f['cell'],
                   inside=[(n, h, round(np.hypot(x - cx, y - cy), 1)) for n, x, y, h in inside],
                   inside_val=sum(val(n, h) for n, x, y, h in inside), n_fires=len(fires),
                   bscore=score(A[tag]), ascore=score(B[tag]))
        for dt in (3.0, 6.0, 10.0):
            a, b = board_at(bws, t0 + dt), board_at(base_rows, t0 + dt)
            rec[f'a{int(dt)}'] = summ(a) if a and a['t'] > t0 else None
            rec[f'b{int(dt)}'] = summ(b) if b and b['t'] > t0 else None
        b0 = board_at(base_rows, t0)
        rec['base_at_t0'] = None if not b0 or abs(b0['t'] - t0) > 0.01 else dict(play=b0['play'], card=b0['card'], why=b0['why'])
        rec['base_plays'] = [(d['t'] - t0, d['card']) for d in base_rows if t0 - 0.01 <= d['t'] <= t0 + 10 and d['play']]
        rec['arm_plays'] = [(round(d['t'] - t0, 1), d['card']) for d in bws if t0 - 0.01 <= d['t'] <= t0 + 10 and d['play']]
        rows.append(rec)

print(f'{len(rows)} matches with a first {ARM} fire')
if not rows:
    sys.exit()
d = Counter()
for r in rows:
    d[(r['bscore'], r['ascore'])] += 1
print('outcome base -> arm:', dict(d), '| net wins', sum(r['ascore'] - r['bscore'] for r in rows))
print('base at the same decision: ', Counter((r['base_at_t0'] or {}).get('card') for r in rows).most_common(8))
print('base at the same decision (play?): ', Counter((r['base_at_t0'] or {}).get('play') for r in rows))
names = Counter(n for r in rows for n, h, dist in r['inside'])
print('bodies in the blast (all fires):', names.most_common(20))
print('mean blast value %.2f, mean bodies %.2f, my elixir at the fire %.2f' % (np.mean([r['inside_val'] for r in rows]),
      np.mean([len(r['inside']) for r in rows]), np.mean([r['el'] for r in rows])))
for k in ('3', '6', '10'):
    pairs = [(r['a' + k], r['b' + k]) for r in rows if r['a' + k] and r['b' + k]]
    if not pairs:
        continue
    print(f'+{k:>2}s n={len(pairs)}: ' + ' | '.join(
        f'{f} arm-base {np.mean([a[f] - b[f] for a, b in pairs]):+.2f}' for f in ('en', 'me', 'el', 'tow')))
json.dump(rows, open(f'{DIR}/diag_rows_{ARM}.json', 'w'))
