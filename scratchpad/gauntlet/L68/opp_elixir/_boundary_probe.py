"""Exploratory: solve the switch tick B from every clean frame pair straddling a phase change.
delta = r1*(B-t0) + r2*(t1-B)  ->  B = t0 + (r2*(t1-t0) - delta) / (r2 - r1)."""
import json, glob, collections
REG = {'single->double': (2300, 2500, 0.0178, 0.0357), 'double->triple': (4700, 4900, 0.0357, 0.0537),
       'triple->stop': (5900, 6100, 0.0537, 0.0)}
B = collections.defaultdict(collections.Counter)
for deck in ('icebow', 'hogeq'):
    for f in sorted(glob.glob(f'scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json')):
        d = json.load(open(f))
        plays = [(e['tick'], e['side']) for e in d['log'] if e.get('accepted')]
        fr = d['frames']
        for a, b in zip(fr, fr[1:]):
            t0, t1 = a['tick'], b['tick']
            for name, (lo, hi, r1, r2) in REG.items():
                if not (lo <= t0 < hi and t1 > t0): continue
                for s in (0, 1):
                    e0, e1 = a['elixir'][s], b['elixir'][s]
                    if e1 >= 10 or e0 >= 10 or any(t0 <= t < t1 and ps == s for t, ps in plays): continue
                    dl = e1 - e0
                    if abs(dl - r1 * (t1 - t0)) < 2e-3 or abs(dl - r2 * (t1 - t0)) < 2e-3: continue
                    B[name][round(t0 + (r2 * (t1 - t0) - dl) / (r2 - r1), 1)] += 1
for k, v in B.items():
    print(k, v.most_common(6))
