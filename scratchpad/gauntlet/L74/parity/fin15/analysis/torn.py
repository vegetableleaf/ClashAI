"""Tornado J2 victims: pull live vs SIM by card, d0 band, flying, from METRICS_J matches/."""
import json, glob, sys, statistics as S
from collections import defaultdict
rows = []
for f in sorted(glob.glob(sys.argv[1] + '/matches/*.json')):
    d = json.load(open(f))
    for fi in d.get('fights', []):
        j2 = (fi.get('jm') or {}).get('j2')
        if not j2:
            continue
        for b in j2:
            if b.get('spell') == 'Tornado' and 'pull_live' in b and b.get('mass'):
                rows.append(b)
print('tornado bodies with pulls', len(rows))
by = defaultdict(list)
for b in rows:
    by[(b['victim'].split(' ', 1)[1], b['mass'], b['flying'])].append(b)
print(f"{'card':28s} mass fly   n agree  d0   pull_live pull_sim  ratio(live/sim, d0>=3000)")
for k, g in sorted(by.items(), key=lambda kv: -len(kv[1])):
    if len(g) < 8:
        continue
    far = [b for b in g if b['d0'] >= 3000 and b['pull_sim'] > 200]
    ratio = S.median(b['pull_live'] / b['pull_sim'] for b in far) if far else float('nan')
    print(f"{k[0]:28s} {k[1]:4} {int(k[2]):3} {len(g):4} {sum(b['agree'] for b in g)/len(g):.2f} {S.median(b['d0'] for b in g):5.0f} "
          f"{S.median(b['pull_live'] for b in g):8.0f} {S.median(b['pull_sim'] for b in g):8.0f}  {ratio:.3f} (n {len(far)})")
# ground vs air, by mass, signed error in pull
for fly in (0, 1):
    for mass in sorted({b['mass'] for b in rows}):
        g = [b for b in rows if b['mass'] == mass and int(b['flying']) == fly]
        if len(g) >= 10:
            dd = [b['pull_live'] - b['pull_sim'] for b in g]
            print('fly', fly, 'mass', mass, 'n', len(g), 'agree', round(sum(b['agree'] for b in g) / len(g), 3), 'median live-sim pull', S.median(dd),
                  'share sim pulls less by >300', round(sum(x > 300 for x in dd) / len(g), 2), 'more by >300', round(sum(x < -300 for x in dd) / len(g), 2))
