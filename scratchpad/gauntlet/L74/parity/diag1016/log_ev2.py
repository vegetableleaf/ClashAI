"""Does the elixir-wait explain the early SIM Log casts? per cast: observed SIM-live offset vs predicted wait."""
import json, sys, statistics
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.core import ps
rows = [json.loads(l) for l in open(sys.argv[1])]
ev = defaultdict(list)
for r in rows:
    if r['live_hit'] and r['sim_hit']:
        ev[r['match'], r['tL']].append(r['sim_hit']-r['live_hit'])
plays = {}
for mt in {k[0] for k in ev}:
    pl = []
    for raw in open(ps.LIVE/(mt+'.jsonl'), 'rb'):
        if b'"play"' in raw[:40]:
            j = json.loads(raw)
            if j['name'] == 'Log': pl.append(j)
    plays[mt] = pl
pairs = []
for (mt, tL), v in ev.items():
    p = min(plays[mt], key=lambda j: abs(j['tick']+24-tL))
    tpe = 45.5/(1 if p['tick'] < 2400 else 2 if p['tick'] < 4800 else 3)
    pairs.append((statistics.median(v), max(0, 2-p['elixir'])*tpe))
early = [w for o, w in pairs if o <= -8]; ontime = [w for o, w in pairs if abs(o) <= 2]
print('early casts', len(early), 'predicted wait median', statistics.median(early), 'share wait>5', round(sum(w > 5 for w in early)/len(early), 3))
print('on-time casts', len(ontime), 'predicted wait median', statistics.median(ontime), 'share wait>5', round(sum(w > 5 for w in ontime)/len(ontime), 3))
print('residual (offset + wait) for early casts:', sorted(Counter(round(o+w) for o, w in pairs if o <= -8).items()))
