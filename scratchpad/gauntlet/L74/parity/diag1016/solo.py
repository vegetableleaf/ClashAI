"""Agreement of anchor groups split by what else happens in the 12 s window (reads match jsons only)."""
import json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.fights import fight_verdict, is_clean
D = Path(sys.argv[1]); mode = sys.argv[2]
G = ['own Log', 'own Skeletons', 'own IceWizard hero', 'own Tesla', 'own Knight', 'own Xbow', 'opp ElixirGolem']
acc = defaultdict(lambda: [0, 0, 0.0])
for p in sorted((D/'matches').glob('*.json')):
    d = json.loads(p.read_text())
    if d['summary'].get('skipped'): continue
    for r in d['fights']:
        if 'error' in r or not is_clean(r, mode): continue
        v = fight_verdict(r, 150); a = r['anchor']
        g = ('own ' if r['own'] else 'opp ') + a['name'] + ('', ' evo', ' hero')[a['form']]
        if g not in G: continue
        others = [e for e in r['events'] if not (e['tick'] == a['tick'] and e['name'] == a['name'] and e['side'] == a['side'])]
        own_after = [e for e in others if e['side'] == a['side'] and e['tick'] > a['tick']]
        k = 'solo' if not others else ('+own later' if own_after else '+opp/earlier only')
        for key in (k, 'all'):
            x = acc[g, key]; x[0] += 1; x[1] += v['agree']; x[2] += v['tower_err']
for g in G:
    print(g, ' | '.join(f"{k}: n {acc[g,k][0]} agree {acc[g,k][1]/max(1,acc[g,k][0]):.3f} terr {acc[g,k][2]/max(1,acc[g,k][0]):.0f}" for k in ('all', 'solo', '+opp/earlier only', '+own later')))
