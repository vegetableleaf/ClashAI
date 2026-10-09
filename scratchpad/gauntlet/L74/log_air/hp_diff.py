"""Paired tower-HP difference (a continuous, less noisy outcome) and crown difference over the candidate games, per arm.
python hp_diff.py <dir with base_* and the arms>"""
import glob, json, math, os, sys
D = sys.argv[1]


def rows(p):
    out = {}
    for f in glob.glob(p):
        for l in open(f):
            r = json.loads(l)
            out[(r['tag'], os.path.basename(os.path.dirname(f)).split('_')[1])] = r
    return out


base = rows(f'{D}/base_*/matches.jsonl')
for arm in ('retarget', 'block'):
    res = rows(f'{D}/{arm}_*/matches.jsonl')
    for field in ('tower_hp_diff', 'crowns_diff'):
        d = [res[k][field] - base[k][field] for k in res if k in base]
        n = len(d)
        m = sum(d) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(n - 1, 1))
        hw = 1.96 * sd / math.sqrt(n)
        print(f'{arm} {field}: {n} candidate games, mean {arm} - base {m:+.1f} (95% CI {m - hw:+.1f} .. {m + hw:+.1f}); '
              f'better {sum(x > 0 for x in d)} / worse {sum(x < 0 for x in d)}')
