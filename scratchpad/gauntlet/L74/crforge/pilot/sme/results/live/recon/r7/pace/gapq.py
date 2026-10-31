import json, sys
def q(v): v = sorted(v); return [round(v[int(len(v) * p)], 2) for p in (.02, .1, .25, .5, .75, .9)]
for f in sys.argv[1:]:
    g = []
    for l in open(f):
        r = json.loads(l)
        acc = sorted(x[1] for x in r['own_reasons'] if x[3])
        g += [(b - a) / 20 for a, b in zip(acc, acc[1:])]
    print(f.split('/')[-1], 'accepted-play gap quantiles (.02 .1 .25 .5 .75 .9):', q(g), 'n', len(g))
