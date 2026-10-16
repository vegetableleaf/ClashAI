"""Why does an anchor group disagree? Split each strict fight's failure into its components (focus alive, tower, first
death) and name the bodies / towers responsible. Reads per-match jsons only (no SIM)."""
import json, sys, statistics
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.fights import fight_verdict, is_clean

D = Path(sys.argv[1]); mode = sys.argv[2] if len(sys.argv) > 2 else 'strict'
GROUPS = sys.argv[3].split(',') if len(sys.argv) > 3 else ['own Log', 'own Skeletons', 'own IceWizard hero', 'opp ElixirGolem']
fights = []
for p in sorted((D/'matches').glob('*.json')):
    d = json.loads(p.read_text())
    if d['summary'].get('skipped'):
        continue
    for r in d['fights']:
        if 'error' in r: continue
        r['match'] = d['summary']['match']; r['verdict'] = fight_verdict(r, 150)
        if is_clean(r, mode): fights.append(r)
for g in GROUPS:
    rs = [r for r in fights if (('own ' if r['own'] else 'opp ') + r['anchor']['name'] + ('', ' evo', ' hero')[r['anchor']['form']]) == g]
    if not rs: continue
    comp = Counter(); who_alive = Counter(); tw = Counter(); first = Counter(); terr_by = defaultdict(list)
    for r in rs:
        v = r['verdict']
        comp[(v['alive_agree'], v['tower_agree'], v['first_death_agree'])] += 1
        a = r['anchor']; bodies = [b for b in r['bodies'] if b['paired']]
        if a['source'] == 'own_spell_tap+delay':
            focus = [b for b in bodies if b['setup'] and b['side'] != a['side']]
        else:
            focus = [b for b in bodies if b['name'] == a['name'] and b['side'] == a['side'] and not b['setup'] and abs(b['born']-a['tick']) <= 12]
        focus = focus or bodies
        for b in focus:
            if (b['live_death'] is None) != (b['sim_death'] is None):
                who_alive[(b['name'], 'own' if b['side'] == r['obs'] else 'opp', 'live_only' if b['live_death'] is not None else 'sim_only')] += 1
        for k, t in r['towers'].items():
            if abs(t['live']-t['sim']) > max(150, .15*abs(t['live'])):
                tw[('own' if int(k[1]) == r['obs'] else 'opp') + k[2] + (' sim>live' if t['sim'] > t['live'] else ' sim<live')] += 1
                terr_by[k[2]].append(t['sim']-t['live'])
        if not v['first_death_agree']:
            dl = sorted((b['live_death'], b['name'], 'own' if b['side'] == r['obs'] else 'opp') for b in bodies if b['live_death'] is not None)
            ds = sorted((b['sim_death'], b['name'], 'own' if b['side'] == r['obs'] else 'opp') for b in bodies if b['sim_death'] is not None)
            first[(dl[0][1:] if dl else None, ds[0][1:] if ds else None)] += 1
    print(f'=== {g} [{mode}] n={len(rs)} agree={sum(r["verdict"]["agree"] for r in rs)}')
    print(' (alive,tower,first) ->', dict(comp.most_common()))
    print(' focus survival mismatches:', who_alive.most_common(12))
    print(' tower fails:', tw.most_common(8))
    print(' first-death (live, sim):', first.most_common(10))
