"""Per-family child-body correctness before (fv4) / after (fv5): native, live, SIM. Reads the three *_verify.json."""
import json, collections
nat = json.load(open('native_verify.json')); liv = json.load(open('live_verify.json')); sim = json.load(open('sim_verify.json'))
NAME = {'-1': 'MotherWitch(-1 hog/goblin)', 'WitchMother': 'MotherWitch'}
rows = collections.defaultdict(lambda: collections.Counter())
for fv, name, mhp, role, m, v in nat['rows']:
    if role in ('child', 'child_no_class'):
        rows[NAME.get(name, name)][f'nat{fv}_{m}'] += v
for k in liv['rows']:
    if len(k) == 5 and k[0] in (4, 5) and k[2] == 'child':
        rows[NAME.get(k[1], k[1])][f'live{k[0]}_{k[3]}'] += k[4]
for fam, d in sim['families'].items():
    base = fam.split('@')[0]
    for b in d.get('bodies', []):
        if b['native_role'] in ('child', 'child_no_class'):
            for fv in ('fv4', 'fv5'):
                for lab, n in b[fv].items():
                    c, f = lab.split('/')[:2]
                    rows[NAME.get(base, base)][f'sim{fv[-1]}_seen'] += n
                    rows[NAME.get(base, base)][f'sim{fv[-1]}_ok'] += n * (c == b['native_class'] and f == 'f0')
def cell(d, p):
    s = d[f'{p}_seen'] if f'{p}_seen' in d else 0
    ok = d.get(f'{p}_cls_form_ok', d.get(f'{p}_ok', 0))
    return f'{ok}/{s}' if s else '-'
print(f'{"family":28s} {"native fv4":>12s} {"native fv5":>12s} {"live fv4":>12s} {"live fv5":>12s} {"SIM fv4":>10s} {"SIM fv5":>10s}')
for fam, d in sorted(rows.items()):
    print(f'{fam:28s} {cell(d,"nat4"):>12s} {cell(d,"nat5"):>12s} {cell(d,"live4"):>12s} {cell(d,"live5"):>12s} {cell(d,"sim4"):>10s} {cell(d,"sim5"):>10s}')
