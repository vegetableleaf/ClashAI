"""What would hbt9 (W4: play iff p > tau, else at >= 9 elixir play w.p. 1 - exp(-rate(p) * step)) have done on a logged
live stretch? Exact P(no play yet) from the logged per-decision p and elixir; gate_rate copied from W4's branch (ae78cff)."""
import json, math, sys
import numpy as np

def gate_rate(p, S=2.0, W=1.0):
    p = min(max(p, 1e-9), 1 - 1e-9); o = p / (1 - p); r = math.log1p(o / S)
    for _ in range(40):
        e = math.exp(r * W); r -= (S * r * e - o) / (S * e * (1 + W * r))
    return max(r, 0.0)

f, t0, t1, mark = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
decs, last = [], None
for line in open(f):
    try: d = json.loads(line)
    except ValueError: continue
    if d.get('event') == 'decision' and t0 <= int(d['tick']) <= t1:
        decs.append((int(d['tick']), float(d['public']['model_own_elixir'] or 0), d['decision']['p_play'], d['decision']['name']))
surv, prev, at, cards = 1.0, None, {}, {}
for t, el, p, name in decs:
    step = 0.5 if prev is None else min((t - prev) / 20, 1.0)
    prev = t
    if el >= 9:
        q = -math.expm1(-gate_rate(p) * step)
        cards[name] = cards.get(name, 0) + surv * q
        surv *= 1 - q
    at[t] = 1 - surv
for s in (0, 5, 10, 15):
    tt = max([t for t in at if t <= mark + 20 * s] or [t0])
    print(f'P(hbt9 played by {s:>2} s after tick {mark}) = {at[tt]:.2f}')
print('P(played before the logged play at', t1, ') =', round(1 - surv, 2), ' card if played:',
      {k: round(v / max(1 - surv, 1e-9), 2) for k, v in cards.items()})
