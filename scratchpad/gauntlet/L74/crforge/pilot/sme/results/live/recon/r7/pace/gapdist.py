import json, sys, statistics as st
from pathlib import Path
H = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/humanlike')
sys.path[:0] = [str(H), str(H.parent), 'C:/Users/benpe/ClashBot']
import card
import live_table as LT
def q(v, ps=(.02, .05, .1, .25, .5, .75, .9)):
    v = sorted(v); return [round(v[int(len(v) * p)], 2) for p in ps]
live = []
for r in card.live_records('calibration'):
    d = LT.cached(card.LOGS / r['id'])
    if not d: continue
    c = sorted(t for t, n in d['own_conf'] if t)
    live += [(b - a) / 20 for a, b in zip(c, c[1:])]
print('LIVE confirmed-play gaps (s) quantiles .02 .05 .10 .25 .50 .75 .90:', q(live), 'n', len(live), 'share < 1.5 s %.3f' % (sum(g < 1.5 for g in live) / len(live)), 'share < 2.0 s %.3f' % (sum(g < 2.0 for g in live) / len(live)))
for f in sys.argv[1:]:
    g = []
    for l in open(f):
        r = json.loads(l)
        acc = sorted(q_[1] for q_ in r['hab']['own'] if q_[3])
        g += [(b - a) / 20 for a, b in zip(acc, acc[1:])]
    print('SIM', Path(f).parent.parent.parent.name, 'accepted-play gaps:', q(g), 'n', len(g), 'share < 1.5 s %.3f' % (sum(x < 1.5 for x in g) / len(g)), 'share < 2.0 s %.3f' % (sum(x < 2.0 for x in g) / len(g)))
