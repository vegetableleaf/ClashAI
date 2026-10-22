"""J1 strict agreement (live vs sim[0]) per live segment: (model, our tower level, ladder/Ranked), from the live-model timeline.
  python segments.py "own Skeletons,opp Skeletons,opp HogRider" RUN_DIR [RUN_DIR ...]"""
import glob, json, os, sys
from collections import defaultdict
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
FORM = ('', ' evo', ' hero')
SEG = [('20261018_0002', 'cue_u250, L15'), ('20261018_0735', 'CLIII_LEVELS, L15'), ('20261018_1807', 'cue_ab2, L15'),
       ('20261019_0020', 'CLX, L15'), ('20261019_1356', 'CLX, L16 ladder'), ('20261020_1328', 'CLX, L16 Ranked'),
       ('20261021_1428', 'CLXI, L16 Ranked')]
cards = sys.argv[1].split(',')
g = defaultdict(lambda: defaultdict(list))
for run in sys.argv[2:]:
    for p in sorted(glob.glob(run + '/matches/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped') or not s.get('phase3b_births'):
            continue
        key = s['match'][10:23]
        seg = [lab for t, lab in SEG if key >= t]
        seg = seg[-1] if seg else 'before 10-18'
        for r in d['fights']:
            c = r.get('card')
            if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
                continue
            lab = ('own ' if r['own'] else 'opp ') + r['anchor']['name'] + FORM[r['anchor']['form']]
            a = F.card_agree(c['live'], c['sim'][0])[0]
            g[seg]['ALL'].append(a)
            if lab in cards:
                g[seg][lab].append(a)
order = ['before 10-18'] + [lab for _, lab in SEG]
print('segment | ' + ' | '.join(['ALL'] + cards))
for seg in order:
    if seg in g:
        print(seg, '|', ' | '.join(f"{sum(g[seg][c])/len(g[seg][c]):.3f} ({len(g[seg][c])})" if g[seg][c] else '-' for c in ['ALL'] + cards))
