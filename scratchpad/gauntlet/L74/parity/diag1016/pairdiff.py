"""Paired before/after: same fight (match, anchor name/side/tap) in two run dirs -> agree transitions, per anchor group."""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.fights import fight_verdict, is_clean
mode = sys.argv[3] if len(sys.argv) > 3 else 'strict'
def load(d):
    out = {}
    for p in sorted((Path(d)/'matches').glob('*.json')):
        j = json.loads(p.read_text())
        if j['summary'].get('skipped'): continue
        for r in j['fights']:
            if 'error' in r: continue
            a = r['anchor']; key = (p.stem, a['side'], a['name'], a['source'], r['t0'] if a['source'] != 'own_spell_tap+delay' else a['tick'] - (r['events'][0]['tick'] if False else 0))
            out[(p.stem, a['side'], a['name'], a['source'], len(out))] = r
    return out
def bykey(d):
    out = {}
    for p in sorted((Path(d)/'matches').glob('*.json')):
        j = json.loads(p.read_text())
        if j['summary'].get('skipped'): continue
        seen = Counter()
        for r in j['fights']:
            if 'error' in r: continue
            a = r['anchor']; k = (p.stem, a['side'], a['name'], a['source']); seen[k] += 1
            out[k + (seen[k],)] = r          # the n-th fight of this anchor kind in the match
    return out
A, B = bykey(sys.argv[1]), bykey(sys.argv[2])
T = defaultdict(Counter)
for k in A.keys() & B.keys():
    ra, rb = A[k], B[k]
    if not (is_clean(ra, mode) and is_clean(rb, mode)): continue
    va, vb = fight_verdict(ra, 150), fight_verdict(rb, 150)
    g = ('own ' if ra['own'] else 'opp ') + k[2]
    for gg in (g, 'ALL'):
        T[gg][(va['agree'], vb['agree'])] += 1
        T[gg]['n'] += 1
        T[gg]['terr_b'] += va['tower_err']; T[gg]['terr_a'] += vb['tower_err']
for g in sorted(T, key=lambda g: -T[g]['n'])[:14]:
    t = T[g]
    print(f"{g:22s} n {t['n']:4d} agree before {(t[(True,True)]+t[(True,False)])/t['n']:.3f} after {(t[(True,True)]+t[(False,True)])/t['n']:.3f} "
          f"| fixed {t[(False,True)]} broke {t[(True,False)]} | mean tower err {t['terr_b']/t['n']:.0f} -> {t['terr_a']/t['n']:.0f}")
if len(sys.argv) > 4:
    for k in sorted(A.keys() & B.keys()):
        ra, rb = A[k], B[k]
        if not (is_clean(ra, mode) and is_clean(rb, mode)): continue
        va, vb = fight_verdict(ra, 150), fight_verdict(rb, 150)
        if va['agree'] != vb['agree']:
            print(k, 't0', ra['t0'], rb['t0'], 'anchor tick', ra['anchor']['tick'], rb['anchor']['tick'], 'before', {x: va[x] for x in ('alive_agree', 'tower_agree', 'first_death_agree', 'tower_err')},
                  'after', {x: vb[x] for x in ('alive_agree', 'tower_agree', 'first_death_agree', 'tower_err')}, rb['flags'])
