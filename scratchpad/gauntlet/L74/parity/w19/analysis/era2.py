"""One anchor card, pre vs L16 era: agreement by opponent card present in the fight, and by fight flags (reader / set-up
features), to see whether the era drop is the interaction mix, a setup / capture change, or across the board.
  python era2.py "own Skeletons" RUN_DIR [RUN_DIR ...]"""
import glob, json, os, sys
from collections import defaultdict
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
FORM = ('', ' evo', ' hero')
want = sys.argv[1]
opp = defaultdict(lambda: defaultdict(list)); flg = defaultdict(lambda: defaultdict(list)); allr = defaultdict(list)
for run in sys.argv[2:]:
    for p in sorted(glob.glob(run + '/matches/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped') or not s.get('phase3b_births'):
            continue
        era = 'L16' if s['match'][10:23] >= '20261019_1402' else 'pre'
        for r in d['fights']:
            c = r.get('card')
            if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
                continue
            lab = ('own ' if r['own'] else 'opp ') + r['anchor']['name'] + FORM[r['anchor']['form']]
            if lab != want:
                continue
            a = F.card_agree(c['live'], c['sim'][0])[0]
            allr[era].append(a)
            for o in {b['name'] for b in r['bodies'] if b['side'] != r['anchor']['side']}:
                opp[o][era].append(a)
            for k in {k.split(':')[0] for k in r['flags']}:
                flg[k][era].append(a)
            n_opp = len({b['name'] for b in r['bodies'] if b['side'] != r['anchor']['side']})
            flg[f'n_opp_cards={min(n_opp, 4)}'][era].append(a)
rate = lambda xs: f'{sum(xs)/len(xs):.3f} ({len(xs)})' if xs else '-'
print(want, 'pre', rate(allr['pre']), 'L16', rate(allr['L16']))
print('\nby opponent card present (n >= 20 in both eras): pre | L16 | share pre -> L16')
for o, v in sorted(opp.items(), key=lambda kv: -len(kv[1]['L16'])):
    if len(v['pre']) >= 20 and len(v['L16']) >= 20:
        print(f"{o} | {rate(v['pre'])} | {rate(v['L16'])} | {len(v['pre'])/len(allr['pre']):.2f} -> {len(v['L16'])/len(allr['L16']):.2f}")
print('\nby flag: pre | L16 | share pre -> L16')
for k, v in sorted(flg.items(), key=lambda kv: -len(kv[1]['L16'])):
    if len(v['pre']) + len(v['L16']) >= 40:
        print(f"{k} | {rate(v['pre'])} | {rate(v['L16'])} | {len(v['pre'])/max(1,len(allr['pre'])):.2f} -> {len(v['L16'])/max(1,len(allr['L16'])):.2f}")
