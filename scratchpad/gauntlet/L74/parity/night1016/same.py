import json, sys, glob, os
a, b = sys.argv[1], sys.argv[2]
same = diff = 0; dl = []
for f in sorted(glob.glob(os.path.join(b, 'matches', '*.json'))):
    g = os.path.join(a, 'matches', os.path.basename(f))
    if not os.path.exists(g):
        dl.append('missing ' + os.path.basename(f)); continue
    x, y = json.load(open(f)), json.load(open(g))
    strip = lambda d: [{k: v for k, v in r.items() if k != 'stamp'} for r in d.get('fights', [])]
    if strip(x) == strip(y): same += 1
    else: diff += 1; dl.append(os.path.basename(f))
print('identical fights per match:', same, 'differ:', diff, dl[:8])
