"""Signed death-time error (SIM - live, sorted death lists of the anchor's bodies) per era for chosen anchor cards, all strict
fights (passing ones too): is there a systematic shift in the L16 era?   python dtera.py "own Skeletons,opp HogRider" RUN_DIR [...]"""
import glob, json, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
FORM = ('', ' evo', ' hero')
cards = sys.argv[1].split(',')
g = defaultdict(Counter); surv = defaultdict(Counter)
for run in sys.argv[2:]:
    for p in sorted(glob.glob(run + '/matches/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped') or not s.get('phase3b_births'):
            continue
        era = 'L16' if s['match'][10:23] >= '20261019_1356' else 'pre'
        for r in d['fights']:
            c = r.get('card')
            if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
                continue
            lab = ('own ' if r['own'] else 'opp ') + r['anchor']['name'] + FORM[r['anchor']['form']]
            L, S = c['live'], c['sim'][0]
            if lab not in cards or L['spell'] or len(L['own']) != len(S['own']):
                continue
            for x, y in zip(L['own'], S['own']):
                if x is None and y is None:
                    surv[(lab, era)]['both alive'] += 1
                elif x is None or y is None:
                    surv[(lab, era)]['live alive, SIM dead' if x is None else 'live dead, SIM alive'] += 1
                else:
                    dd = y - x
                    g[(lab, era)][max(-60, min(60, dd // 5 * 5))] += 1
for k in sorted(g):
    c = g[k]; n = sum(c.values())
    print(k, 'n', n, 'within 10:', round(sum(v for d, v in c.items() if -10 <= d <= 10) / n, 3),
          'SIM earlier >10:', round(sum(v for d, v in c.items() if d < -10) / n, 3), 'SIM later >10:', round(sum(v for d, v in c.items() if d > 10) / n, 3),
          dict(surv[k]))
