"""ENG-FIX5 census: how late does the reader first list the bodies of a play? For every play (kind play) of the records,
the first frame in [run + 1, run + 40] showing a new body of its side within 1,500 (Manhattan) of its point (order_inputs'
test), and the lag = that frame - (run + 1). crforge shows a play's bodies from run + 1.
python -I late_census.py LIVE_DIR MINLAG INPUTS.jsonl [...]"""
import collections, json, os, sys
from pathlib import Path
S = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(S), str(S / 'bp9')]
_argv, sys.argv = sys.argv, [sys.argv[0], '', '']
import order_inputs as oi  # noqa: E402
import live_frames  # noqa: E402
sys.argv = _argv
LD, MIN = sys.argv[1], int(sys.argv[2])
hist, late = collections.Counter(), []
for f in sys.argv[3:]:
    for l in open(f):
        r = json.loads(l)
        fr = [(x['t'], x) for x in live_frames.convert(os.path.join(LD, r['match'] + '.jsonl'))]
        for p in r['plays']:
            if p['kind'] != 'play':
                continue
            q = oi.first_new([(t, x) for t, x in fr if t <= p['tick'] + 40], dict(p), p['tick'] + 1)
            if q is None:
                hist['none'] += 1; continue
            # first_new looks in [run', run' + 10]; widen by stepping the start
            lag = q[0] - (p['tick'] + 1)
            hist[min(lag, 10)] += 1
            if lag >= MIN:
                late.append((Path(f).parent.name + '/' + Path(f).name, r['match'][10:], p['side'], p['card'], p.get('source'), p['tick'], q[0], lag))
print('lag histogram (first listing - (run + 1)):', sorted(hist.items(), key=lambda kv: str(kv[0])))
print('plays listed >= %d ticks late: %d' % (MIN, len(late)))
for x in late:
    print('  %s %s side %d %s %s run %d first %d lag %d' % x)
