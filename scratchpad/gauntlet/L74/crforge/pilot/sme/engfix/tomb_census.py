"""ENG-FIX: hero Tombstone census on live logs: per passive-monster generation, how it ended (swap to active with the
building listed = press; swap with the building gone; removed passive = death), and whether a dev / fresh set holds it.
    python -I tomb_census.py LOGS.txt LIVE_DIR SET.jsonl..."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
names, live = [l.strip() for l in open(sys.argv[1]) if l.strip()], sys.argv[2]
sets = {}
for f in sys.argv[3:]:
    for l in open(f):
        sets.setdefault(json.loads(l)['match'], []).append(os.path.basename(f))
tot = {}
for m in names:
    gens, build_seen = {}, {}
    for line in open(os.path.join(live, m + '.jsonl'), 'rb'):
        if b'"frame"' not in line[:40] or b'TombstoneHero' not in line:
            continue
        d = json.loads(line)
        t = d['tick']
        if t is None or t < 0:
            continue
        us = (d.get('phase2') or {}).get('units', [])
        build = {u.get('side') for u in us if u.get('name') == 'TombstoneHero'}
        for u in us:
            n, g = u.get('name'), u.get('generation')
            if n == 'TombstoneHero_Monster_Passive':
                r = gens.setdefault(g, {'side': u.get('side'), 'first': t})
                r['last_passive'] = t
                r['build_last'] = u.get('side') in build
            elif n == 'TombstoneHero_Monster_Active' and g in gens and 'active' not in gens[g]:
                gens[g]['active'] = t
                gens[g]['build_at_swap'] = u.get('side') in build
    kinds = []
    for g, r in gens.items():
        k = 'press' if r.get('active') and r['build_at_swap'] else 'swap_no_building' if r.get('active') else 'no_swap'
        kinds.append(k)
        tot[k] = tot.get(k, 0) + 1
    print(m, sets.get(m, '-'), len(gens), {k: kinds.count(k) for k in set(kinds)},
          [(r['side'], r['last_passive'], r.get('active')) for r in gens.values() if r.get('active')])
print('total', tot)
