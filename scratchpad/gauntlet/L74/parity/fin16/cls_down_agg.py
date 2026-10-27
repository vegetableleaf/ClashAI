"""cls_down_agg.py MOVED.json CLS_BASE_DIR CLS_ARM_DIR OUT.txt: join cls_down.py's per-arm first divergences (live vs SIM) onto
the down fights of down_dossier.py: per fight, the arm's (fin16) failing body + kind and the first divergence of the bodies
next to it, beside the base's (fin15) first divergence of the same fight; then counts by mechanism / first-divergence body."""
import json
import sys
from collections import Counter
from pathlib import Path

moved, cb, ca, out = sys.argv[1:5]
down = {x['key']: x for x in json.load(open(moved)) if x['dir'] == 'down'}


def load(d):
    res = {}
    for f in Path(d).glob('*/cls.jsonl'):
        for line in open(f):
            j = json.loads(line)
            for c in j['fights']:
                res[f"{c['match'][10:]}@{c['t0']} {c['lab']}"] = c
    return res


B, A = load(cb), load(ca)
lines, kinds, bodies, glob_b, sk_first, dts = [], Counter(), Counter(), Counter(), 0, []
for k, x in sorted(down.items()):
    a, b = A.get(k), B.get(k)
    bad = (a or {}).get('bad') or [{}]
    f = bad[0].get('first') or {}
    g = (a or {}).get('first_global') or {}
    gb = (b or {}).get('first_global') or {}
    kinds[bad[0].get('kind')] += 1
    bodies[f.get('body')] += 1
    glob_b[g.get('body')] += 1
    sk_first += 'Skeletons' in str(f.get('body')) or 'Skeletons' in str(g.get('body'))
    if f.get('dt') is not None:
        dts.append(f['dt'])
    lines.append(f"{k} | mech {x['mech']} | changed plays {[e[2] + '@' + str(e[0]) for e in x['plays_changed']]} set-up {x['setup_changed']}"
                 f" | fin16 fails: {bad[0].get('kind')} {bad[0].get('body')} @dt {bad[0].get('dt')}; first div {f.get('kind')} {f.get('body')} @dt {f.get('dt')}"
                 f" | fin16 first global {g.get('kind')} {g.get('body')} @dt {g.get('dt')} | fin15 first global {gb.get('kind')} {gb.get('body')} @dt {gb.get('dt')}")
summary = [f'down fights {len(down)}, classified fin16 {sum(k in A for k in down)}, fin15 {sum(k in B for k in down)}',
           f'fin16 failing kind: {kinds.most_common()}',
           f'fin16 first divergence (bodies next to the failing one): {bodies.most_common(12)}',
           f'fin16 first global divergence: {glob_b.most_common(12)}',
           f'Skeletons body at the first or first-global divergence: {sk_first} / {len(down)}',
           f'first divergence dt (ticks after t0): median {sorted(dts)[len(dts) // 2] if dts else None}, <= 40: {sum(d <= 40 for d in dts)} / {len(dts)}']
Path(out).write_text('\n'.join(summary + [''] + lines) + '\n')
print('\n'.join(summary))
