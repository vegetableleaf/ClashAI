"""Sweep a sight-range rule on the live target: tg := None when td > sight*mul + add. python explore3.py FILES"""

from explore2 import SIGHT, b
def ok(r, mul, add):
    s = SIGHT.get(r['name'])
    tg = r['lv']['tg']
    if tg is not None and s and r['lv']['td'] is not None and r['lv']['td'] > s*mul + add:
        tg = None
    return tg == r['sm']['tg']
for tw in (False, True):
    sel = [r for r in b if r['tw'] == tw]
    base = sum(r['lv']['tg'] == r['sm']['tg'] for r in sel)/len(sel)
    print('towers' if tw else 'troops', len(sel), 'no rule', round(base, 3))
    for mul, add in ((1, 0), (1, 500), (1, 1000), (1, 1500), (1, 2000), (1, 3000), (1.1, 0), (1.25, 0)):
        print('  mul', mul, 'add', add, round(sum(ok(r, mul, add) for r in sel)/len(sel), 3))
