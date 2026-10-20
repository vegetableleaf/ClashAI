"""J4 round 2: what are the live own-elixir drops (>= 0.5) that match no confirmed play / ability press within 6 ticks
(replay_metrics.j4's 'unmatched drops')? Live-only. For each: the drop size, the nearest play / press / decision tick, and
whether the drop is followed within 4 ticks by a rise back (a reader glitch).
  python j4_unmatched.py LOG [LOG ...]"""
import json, sys
from collections import Counter
size, near, glitch, ex = Counter(), Counter(), 0, []
n_drops = 0
for p in sys.argv[1:]:
    fr, plays, presses, taps = [], [], [], []
    with open(p, 'rb') as f:
        for raw in f:
            h = raw[:40]
            if b'"frame"' in h:
                j = json.loads(raw)
                if j.get('elixir') is not None:
                    fr.append((j['tick'], j['elixir']))
            elif b'"confirmed"' in h:
                j = json.loads(raw); plays.append((j.get('tick'), j['name']))
            elif b'"unconfirmed"' in h:
                j = json.loads(raw); taps.append((j.get('tick'), 'unconfirmed ' + j['name']))
            elif b'"ability_confirmed"' in h or b'"ability"' in h:
                j = json.loads(raw); presses.append(j.get('tick'))
    for k, ((ta, ea), (tb, eb)) in enumerate(zip(fr, fr[1:])):
        if ea - eb < .5:
            continue
        n_drops += 1
        if any(t is not None and abs(t - tb) <= 6 for t, _ in plays) or any(t is not None and abs(t - tb) <= 6 for t in presses):
            continue
        d = round(ea - eb, 1)
        back = any(e >= ea - .05 for t, e in fr[k + 2:k + 4])
        glitch += back
        size[d] += 1
        cand = [(abs(t - tb), n) for t, n in plays + taps if t is not None] + [(abs(t - tb), 'press') for t in presses if t is not None]
        dt, nm = min(cand) if cand else (None, None)
        near['none' if dt is None else '<=12' if dt <= 12 else '<=40' if dt <= 40 else '>40'] += 1
        if len(ex) < 12:
            ex.append((p[-22:-6], tb, d, ea, eb, back, dt, nm))
print('drops', n_drops, 'unmatched', sum(size.values()), 'rise back within 4 ticks (reader glitch)', glitch)
print('sizes', size.most_common(12))
print('nearest play / press', dict(near))
for e in ex:
    print(e)
