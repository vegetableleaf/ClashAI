"""Children radius / kind vs age since spawn (T+12), from the live frame logs (read-only). Needs replay_check.json."""
import json, math, os, statistics, sys
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay_check as R

ev = json.load(open(os.path.join(R.HERE, 'replay_check.json')))['events']
byfile = defaultdict(list)
for e in ev:
    if e['status'] == 'ok' and e['tick_error'] == 0:
        byfile[e['file']].append(e)
rad, kind = defaultdict(list), defaultdict(Counter)
for fn, es in byfile.items():
    side, frames = R.load(os.path.join(R.LIVE, fn))
    fr = {t: ents for t, ents in frames}
    for e in es:
        ta = e['actual_tick']
        t_prev = max(t for t in fr if t < ta)
        before = {x['address'] for x in fr[t_prev]}
        kids = {x['address'] for x in fr[ta] if x['address'] not in before and x['max_hp'] < 300
                and x['card_id'] in (26000056, 13000056) and math.hypot(x['x'] - e['x'], x['y'] - e['y']) <= 4500}
        for t, ents in frames:
            a = t - ta
            if 0 <= a <= 30:
                for x in ents:
                    if x['address'] in kids and x['hp'] > 0:
                        rad[a].append(math.hypot(x['x'] - e['x'], x['y'] - e['y']))
                        kind[a][x['kind']] += 1
for a in sorted(rad):
    r = sorted(rad[a])
    print(a, len(r), 'radius median %d p10 %d p90 %d' % (statistics.median(r), r[len(r) // 10], r[9 * len(r) // 10]), dict(kind[a]))
