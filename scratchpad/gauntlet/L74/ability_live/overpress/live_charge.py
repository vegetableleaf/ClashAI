"""Live game truth for the Hero IW ability's readiness: per IceWizardHero body (phase-2 units in the reader captures),
the own_action fields (charges_raw, availability_ms_raw, cooldown_ms, state_raw) from the body's first frame on, and
the entity's deploy flag (kind 15 = deploying?) -> ticks from first sight to the first charge.
Also: per body, did any enemy carry IceWizardHeroCold/Slow when the charge appeared (is readiness tied to a marked enemy)?"""
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/Users/benpe/ClashBot/icebow/data/p3_captures')
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
bodies = {}
trans = Counter()
n = 0
for fr in sorted(ROOT.glob('*/frames.jsonl'))[:LIMIT]:
    n += 1
    with open(fr, 'rb') as f:
        for raw in f:
            if b'"IceWizardHero"' not in raw:
                continue
            j = json.loads(raw)
            p = j.get('phase2') or {}
            if not p.get('valid'):
                continue
            t = j['game_tick']
            ents = {e['address']: e for e in j.get('entities', [])}
            marked = any(b['name'] in ('IceWizardHeroCold', 'IceWizardHeroSlow')
                         for u in p['units'] for b in (u.get('buffs') or []))
            for u in p['units']:
                if u['name'] != 'IceWizardHero' or not u.get('ability'):
                    continue
                a = u['ability'].get('own_action') or {}
                a = dict(charges_raw=a.get('charges_raw', -9), availability_ms_raw=a.get('availability_ms_raw', -9), state_raw=a.get('state_raw', -9))
                k = (fr.parent.name, u['generation'])
                e = ents.get(u['address'], {})
                b = bodies.setdefault(k, dict(first=t, hist=[]))
                row = (a['charges_raw'], a['availability_ms_raw'], a['state_raw'], e.get('kind'), e.get('behavior_state_raw'))
                if not b['hist'] or b['hist'][-1][1:6] != row:
                    b['hist'].append((t,) + row + (marked,))
first_charge = []
for k, b in bodies.items():
    h = b['hist']
    for i, r in enumerate(h):
        if r[1] > 0:
            first_charge.append((r[0] - b['first'], r[6], h[0][1:6]))
            break
print('captures', n, 'IW bodies', len(bodies))
fc = [x[0] for x in first_charge]
print('first sight -> first charges_raw > 0 (ticks): n', len(fc), 'median', st.median(fc) if fc else None,
      'deciles', [round(x) for x in st.quantiles(fc, n=10)] if len(fc) > 2 else fc)
print('an enemy marked at that tick:', Counter(x[1] for x in first_charge))
print('first-sight state (charges, avail_ms, state, kind, behavior):', Counter(x[2] for x in first_charge).most_common(5))
for k, b in list(bodies.items())[:4]:
    print(k, b['hist'][:8])
# state_raw transitions: per body, ticks from first sight to each new state, and whether an enemy was marked then
tr = Counter(); first_state = Counter(); seq = Counter()
for k, b in bodies.items():
    s = [r[3] for r in b['hist']]
    seq[tuple(dict.fromkeys(s))] += 1
    for r0, r1 in zip(b['hist'], b['hist'][1:]):
        if r1[3] != r0[3]:
            tr[(r0[3], r1[3], r1[6])] += 1
print('state sequences', seq.most_common(8))
print('state transitions (from, to, enemy marked at the change)', tr.most_common(12))
d9_2 = [r1[0] - b['first'] for b in bodies.values() for r0, r1 in zip(b['hist'], b['hist'][1:]) if r0[3] == 9 and r1[3] == 2]
print('first sight -> 9->2 change (ticks)', sorted(d9_2)[:30])
