"""Independent angles on the J1 strict failing fights of a fights run dir (live vs sim[0]):
 A tolerance margin: for troop anchors, the death-time error of the mismatched bodies (just past DEATH_TOL = near-miss)
 B window boundary: where in the 240-tick window the disagreement sits
 C phase of match (1x / 2x / OT) and capture date
 D card pairs: anchor x opponent card present, failure rate vs base rate
 E tower-only failures: size of the tower error vs tolerance
 F fight flags (setup_*) over-represented in failing fights (lift)
  python angles.py RUN_DIR"""
import glob, json, os, sys, statistics
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

FORM = ('', ' evo', ' hero')
fights = []
for p in sorted(glob.glob(sys.argv[1] + '/matches/*.json')):
    d = json.load(open(p, encoding='utf-8'))
    s = d['summary']
    if s.get('skipped') or not s.get('phase3b_births'):
        continue
    for r in d['fights']:
        c = r.get('card')
        if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
            continue
        ok, mis, n, tok = F.card_agree(c['live'], c['sim'][0])
        r['ok'], r['mis'], r['n'], r['tok'], r['match'] = ok, mis, n, tok, s['match']
        r['lab'] = ('own ' if r['own'] else 'opp ') + r['anchor']['name'] + FORM[r['anchor']['form']]
        fights.append(r)
fails = [r for r in fights if not r['ok']]
N, NF = len(fights), len(fails)
print(f'strict fights {N}, failing {NF} ({NF/N:.4f})')

# A: death-time error of mismatched troop bodies (sorted multiset pairing as card_agree's unmatched)
dts, kinds = [], Counter()
for r in fails:
    L, S = r['card']['live'], r['card']['sim'][0]
    if L['spell'] or not r['tok'] and r['mis'] <= int(F.SWARM_SLACK * r['n']):
        continue
    lo, so = L['own'], S['own']
    if len(lo) != len(so):
        kinds['count'] += 1; continue
    for x, y in zip(lo, so):
        if x is None and y is None:
            continue
        if (x is None) != (y is None):
            late = (x if x is not None else y) >= L['end'] - F.DEATH_TOL
            kinds['survival_late_window' if late else 'survival'] += 1
        elif abs(x - y) > F.DEATH_TOL:
            dts.append(y - x)
print('\nA mismatched troop bodies:', dict(kinds), 'timing n', len(dts))
b = Counter(min(abs(v) // 5 * 5, 60) for v in dts)
print('   |SIM - live| death ticks (5-tick bins, 60 = 60+):', sorted(b.items()))
print(f'   SIM later {sum(v > 0 for v in dts)}, SIM earlier {sum(v < 0 for v in dts)}; within 11-15 ticks (one tolerance step) '
      f'{sum(11 <= abs(v) <= 15 for v in dts)} ({sum(11 <= abs(v) <= 15 for v in dts)/max(1,len(dts)):.2f})')

# B: where the disagreement sits in the window: earliest mismatched death tick - t0
pos = []
for r in fails:
    L, S = r['card']['live'], r['card']['sim'][0]
    if L['spell']:
        continue
    ds = [v for v in L['own'] + S['own'] if v is not None]
    if ds:
        pos.append(min(ds) - r['t0'])
print('\nB first anchor death in failing troop fights, ticks after t0 (bins of 40):', sorted(Counter(p // 40 * 40 for p in pos).items()))

# C: phase and date
ph = lambda t: '1x' if t < 2400 else '2x' if t < 3600 else 'ot' if t < 6000 else 'end'
for key, f in (('phase', lambda r: ph(r['t0'])), ('date', lambda r: r['match'][10:18]),
               ('own/opp anchor', lambda r: 'own' if r['own'] else 'opp')):
    c, cf = Counter(f(r) for r in fights), Counter(f(r) for r in fails)
    print(f'\nC by {key}:', {k: (c[k], round(1 - cf[k] / c[k], 4)) for k in sorted(c)})

# D: card pairs (anchor x opponent card with a body in the fight), lift over the anchor's own failure rate
an = defaultdict(lambda: [0, 0]); pr = defaultdict(lambda: [0, 0])
for r in fights:
    an[r['lab']][0] += 1; an[r['lab']][1] += not r['ok']
    others = {b['name'] for b in r['bodies'] if b['side'] != r['anchor']['side']}
    for o in others:
        pr[r['lab'], o][0] += 1; pr[r['lab'], o][1] += not r['ok']
rows = []
for (a, o), (n, f) in pr.items():
    if n >= 25:
        ra = an[a][1] / an[a][0]
        rows.append((f - n * ra, a, o, n, f, f / n, ra))
rows.sort(reverse=True)
print('\nD card pairs with the most EXCESS failures over the anchor\'s own rate (n >= 25):')
print('excess | anchor | vs opp card present | n | fails | rate | anchor rate')
for x in rows[:25]:
    print(f'{x[0]:.1f} | {x[1]} | {x[2]} | {x[3]} | {x[4]} | {x[5]:.3f} | {x[6]:.3f}')
oc = defaultdict(lambda: [0, 0])
for r in fights:
    for o in {b['name'] for b in r['bodies'] if b['side'] != r['anchor']['side']} | {b['name'] for b in r['bodies'] if b['side'] == r['anchor']['side'] and b['name'] != r['anchor']['name']}:
        oc[o][0] += 1; oc[o][1] += not r['ok']
base = NF / N
print('\nD2 any card present in the fight (either side, not the anchor card), excess failures over the base rate:')
for o, (n, f) in sorted(oc.items(), key=lambda kv: -(kv[1][1] - kv[1][0] * base))[:25]:
    print(f'{o} | n {n} | fails {f} | rate {f/n:.3f} | excess {f - n*base:.1f}')

# E: tower-only failures
te = [(r['card']['sim'][0]['tower'] - r['card']['live']['tower'], r['card']['live']['tower'], r['lab']) for r in fails
      if r['mis'] <= int(F.SWARM_SLACK * r['n']) and not r['tok']]
print(f'\nE tower-only failures {len(te)}: SIM-live median {statistics.median([t[0] for t in te]) if te else None}; '
      f'SIM more {sum(t[0] > 0 for t in te)}; |err| bins:', sorted(Counter(min(abs(t[0]) // 100 * 100, 1000) for t in te).items()))
print('   by card:', Counter(t[2] for t in te).most_common(10))

# F: flags lift
fl, ff = Counter(), Counter()
for r in fights:
    for k in {k.split(':')[0] for k in r['flags']}:
        fl[k] += 1; ff[k] += not r['ok']
print('\nF flags: fights with the flag | failure rate | excess failures over base')
for k, n in sorted(fl.items(), key=lambda kv: -(ff[kv[0]] - kv[1] * base))[:20]:
    print(f'{k} | {n} | {ff[k]/n:.3f} | {ff[k] - n*base:.1f}')
