"""Log hit-set before/after (same matches): paired ground bodies near the roll; confusion, timing, by cause."""
import json, sys, statistics
from collections import Counter, defaultdict
sys.path.insert(0, 'scratchpad/gauntlet/L74/parity/diag1016')
from capture import engine
eng = engine()
def load(f, matches=None):
    R = [json.loads(l) for l in open(f)]
    return [r for r in R if (matches is None or r['match'] in matches) and r['name'] in eng.ids and not eng.cat[eng.ids[r['name']]]['flying'] and r['paired']]
after = load(sys.argv[2]); ms = {r['match'] for r in after}
before = load(sys.argv[1], ms)
for lab, R in (('before', before), ('after', after)):
    conf = Counter((r['live_hit'] is not None, r['sim_hit'] is not None) for r in R)
    hit = conf[True, True] + conf[True, False] + conf[False, True]
    ev = defaultdict(list)
    for r in R:
        if r['live_hit'] and r['sim_hit']: ev[r['match'], r['tL']].append(r['sim_hit'] - r['live_hit'])
    med = [statistics.median(v) for v in ev.values()]
    print(f"{lab}: bodies hit on either side {hit}, both {conf[True,True]}, live-only {conf[True,False]}, SIM-only {conf[False,True]}, "
          f"disagree {(conf[True,False]+conf[False,True])/hit:.3f}; casts {len(med)}: |SIM-live first hit| <= 2 ticks {sum(abs(x) <= 2 for x in med)/len(med):.3f}, SIM >= 8 early {sum(x <= -8 for x in med)}, >= 8 late {sum(x >= 8 for x in med)}")
    mis = Counter(r['name'] for r in R if (r['live_hit'] is None) != (r['sim_hit'] is None))
    print('   mismatch by unit', mis.most_common(10))
