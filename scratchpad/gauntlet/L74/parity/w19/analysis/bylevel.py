"""J1 strict agreement (live vs sim[0]) split by own / opp tower level and modal card level (match summary), and by date-hour.
  python bylevel.py RUN_DIR [RUN_DIR ...]"""
import glob, json, os, sys, random
from collections import defaultdict
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

g = defaultdict(list)
for run in sys.argv[1:]:
    for p in sorted(glob.glob(run + '/matches/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped') or not s.get('phase3b_births'):
            continue
        side = s['side']; tl = s.get('tower_levels') or [None, None]; lv = s.get('levels') or {}
        keys = {'own tower L%s' % tl[side], 'opp tower L%s' % tl[1 - side], 'own cards L%s' % lv.get(f'{side}:*'),
                'opp cards L%s' % lv.get(f'{1-side}:*'), 'date ' + s['match'][10:18],
                'own L16 era' if (s['match'][10:23] >= '20261019_1402') else 'own pre-L16'}
        for r in d['fights']:
            c = r.get('card')
            if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
                continue
            a = F.card_agree(c['live'], c['sim'][0])[0]
            for k in keys:
                g[k].append((s['match'], a))


def ci(xs, B=1000):
    by = defaultdict(list)
    for m, a in xs:
        by[m].append(a)
    ms, rng, v = sorted(by), random.Random(0), []
    for _ in range(B):
        ys = [a for m in rng.choices(ms, k=len(ms)) for a in by[m]]
        v.append(sum(ys) / len(ys))
    v.sort()
    return v[int(.025 * B)], v[int(.975 * B) - 1], len(ms)


for k in sorted(g):
    xs = g[k]
    lo, hi, nm = ci(xs)
    print(f'{k:22s} fights {len(xs):6d} matches {nm:4d}  agree {sum(a for _, a in xs)/len(xs):.4f} [{lo:.4f}, {hi:.4f}]')
