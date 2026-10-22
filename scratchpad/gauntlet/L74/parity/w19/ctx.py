"""Fight CONTEXT of own plays by era (does the bot's play pattern change at 10-19?): for each strict stamped fight anchored on
an own play of CARD, the live distance from the play point to the nearest enemy troop at the play tick, enemy troops within
3 tiles, whether the play is on our half, and the J1 outcome (live vs sim[0]). Bins: agreement per context bin per era.
  python ctx.py CARD LIVE_DIR RUN_DIR [RUN_DIR ...]"""
import glob
import json
import math
import os
import sys
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402

catalog, _ = load_catalog()
card, live = sys.argv[1], Path(sys.argv[2])
g = defaultdict(lambda: defaultdict(list))
for run in sys.argv[3:]:
    for p in sorted(glob.glob(run + '/matches/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped') or not s.get('phase3b_births'):
            continue
        fs = [r for r in d['fights'] if 'error' not in r and r.get('card') and r['card']['sim'][0] is not None and r['own']
              and r['anchor']['name'] == card and F.is_clean(r, 'strict')]
        if not fs:
            continue
        m, _ = F.read_match(str(live / (s['match'] + '.jsonl')))
        ev, _ = F.deployments(m, catalog)
        ticks = [t for t, _ in m['frames']]
        era = 'L16' if s['match'][10:23] >= '20261019_1402' else 'pre'
        ky = next((bd['y'] for bd in m['frames'][0][1] if bd['tower'] and bd['side'] == m['side'] and bd['id'].endswith('K')), 0)
        for r in fs:
            e = next((e for e in ev if e['side'] == m['side'] and e['name'] == card and e['tick'] == r['anchor']['tick'] and 'x' in e), None)
            if e is None:
                continue
            fr = m['frames'][max(0, bisect_right(ticks, e['tick']) - 1)][1]
            en = [math.hypot(b['x'] - e['x'], b['y'] - e['y']) for b in fr if not b['tower'] and b['side'] != m['side']]
            dmin = min(en) if en else 99999
            n3 = sum(x <= 3000 for x in en)
            own_half = (e['y'] < 16000) == (ky < 16000)
            ok = F.card_agree(r['card']['live'], r['card']['sim'][0])[0]
            bin_ = 'on top (<1.5t)' if dmin < 1500 else 'near (1.5-4t)' if dmin < 4000 else 'far (>4t)' if dmin < 99999 else 'no enemy'
            g['dist ' + bin_][era].append(ok)
            g[f'enemies within 3t: {min(n3, 4)}'][era].append(ok)
            g['our half' if own_half else 'their half'][era].append(ok)
rate = lambda xs: f'{sum(xs)/len(xs):.3f} ({len(xs)})' if xs else '-'
tot = {e: sum(len(v[e]) for k, v in g.items() if k.startswith('dist ')) for e in ('pre', 'L16')}
print(card, 'context | pre | L16 | share pre -> L16')
for k in sorted(g):
    v = g[k]
    print(f"{k} | {rate(v['pre'])} | {rate(v['L16'])} | {len(v['pre'])/max(1, tot['pre']):.2f} -> {len(v['L16'])/max(1, tot['L16']):.2f}")
if os.environ.get('CTX_JSON'):
    json.dump({k: dict(v) for k, v in g.items()}, open(os.environ['CTX_JSON'], 'w'))
