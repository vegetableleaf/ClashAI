"""Per anchor card: J1 strict agreement (live vs sim[0]) before vs after our towers went level 16 (10-19 14:02), and a
mix-adjusted overall: the L16-era per-card rates re-weighted to the pre-era card mix (does the drop come from the mix or from
within cards?).  python era.py RUN_DIR [RUN_DIR ...]"""
import glob, json, os, sys
from collections import defaultdict
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
FORM = ('', ' evo', ' hero')
g = defaultdict(lambda: defaultdict(list))
for run in sys.argv[1:]:
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
            g[lab][era].append(F.card_agree(c['live'], c['sim'][0])[0])
rate = lambda xs: sum(xs) / len(xs) if xs else float('nan')
tot = {e: sum(len(v[e]) for v in g.values()) for e in ('pre', 'L16')}
print('card | n pre | agree pre | n L16 | agree L16 | delta | share pre -> L16')
for lab, v in sorted(g.items(), key=lambda kv: -len(kv[1]['pre']) - len(kv[1]['L16']))[:40]:
    print(f"{lab} | {len(v['pre'])} | {rate(v['pre']):.3f} | {len(v['L16'])} | {rate(v['L16']):.3f} | "
          f"{rate(v['L16']) - rate(v['pre']):+.3f} | {len(v['pre'])/tot['pre']:.3f} -> {len(v['L16'])/tot['L16']:.3f}")
both = [lab for lab, v in g.items() if v['pre'] and v['L16']]
w = {lab: len(g[lab]['pre']) for lab in both}
adj = sum(w[l] * rate(g[l]['L16']) for l in both) / sum(w.values())
pre = sum(w[l] * rate(g[l]['pre']) for l in both) / sum(w.values())
raw = {e: rate([a for v in g.values() for a in v[e]]) for e in ('pre', 'L16')}
print(f"\noverall pre {raw['pre']:.4f}, L16 {raw['L16']:.4f}; L16 per-card rates on the PRE card mix: {adj:.4f} (pre on the same cards {pre:.4f})")
