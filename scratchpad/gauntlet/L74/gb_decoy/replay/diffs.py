"""Where off != on: inside an evo cast's flight / answer window (throw - 2 .. landing + 40), after it, or elsewhere."""
import json, glob, os, sys, collections
win = json.load(open(sys.argv[2]))
c = collections.Counter()
for path in glob.glob(os.path.join(sys.argv[1], '*.jsonl')):
    f = os.path.basename(path)
    evo = [w for w in win.get(f, []) if w['kind'] == 'evo']
    for l in open(path):
        r = json.loads(l)
        if r['off'] is None or r['off'] == r['on']:
            continue
        t = r['tick']
        where = ('in_evo_window' if any(w['t0'] - 2 <= t <= w['tland'] + 40 for w in evo) else
                 'after_evo_window' if any(t > w['tland'] + 40 for w in evo) else 'no_evo_before')
        what = 'p_play_only' if {k for k in r['off'] if r['off'][k] != r['on'][k]} == {'p_play'} else 'decision'
        c[where, what] += 1
print(dict(c))
