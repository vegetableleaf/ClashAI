"""Opportunity size per drift (from drift.json): share x win-rate gap for (a) the 13k-meta card group the training pool
under-represents, (b) the owner's six unfavourable archetypes, (c) tower-troop opponents.   -> drift3.txt"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import drift as D                                                          # noqa: E402

d = json.loads((HERE / 'drift.json').read_text())
rows, P, A, bs = d['live'], d['pools'], D.A, D.base_set
CORE = {'megaknight', 'witch', 'firecracker', 'hogrider', 'electrogiant', 'elixirgolem', 'goldenknight'}
UNF = [a for a in A.ORDER if A.unfavorable(a)]
W = {'since 10-15 (both Marks)': [r for r in rows if r['log'] >= 'live_play_20261015'],
     'CXXIV (u250) window': [r for r in rows if r['mark'] == 'CXXIV'],
     'CXXXVIII all': [r for r in rows if r['mark'] == 'CXXXVIII'],
     'CXXXVIII >= 12.8k': [r for r in rows if r['mark'] == 'CXXXVIII' and (r['before'] or 0) >= 12800]}


def pool_share(pool, test):
    """share of pool draws whose deck passes test(base canon set); pool decks re-read with their draw weights."""
    path, kind = {'train': (D.TRAIN, 'train'), 'd3': (D.D3, 'd3'), 'exploit': (D.EXPLOIT, 'x')}[pool]
    return sum(q for eng, q in D.pool(path, kind) if test({A.canon(n.split('@')[0]) for n in eng}))


T = []
w = T.append
tests = {'any 13k-core card (' + ','.join(sorted(CORE)) + ')': lambda s: bool(s & CORE),
         'megaknight': lambda s: 'megaknight' in s, 'witch': lambda s: 'witch' in s,
         'unfavourable six (owner)': lambda s: A.classify(s) in UNF}
for name, t in tests.items():
    tr, d3, ex = pool_share('train', t), pool_share('d3', t), pool_share('exploit', t)
    w(f"== {name}: pool share train {100*tr:.1f}%, train+B {100*(0.7*tr+0.3*ex):.1f}%, d3 {100*d3:.1f}%")
    for k, rs in W.items():
        g = [r['win'] for r in rs if t(bs(r))]; o = [r['win'] for r in rs if not t(bs(r))]
        if not g or not o:
            continue
        pg, po = sum(g) / len(g), sum(o) / len(o)
        ci = D.wilson(sum(g), len(g))
        share = len(g) / len(rs)
        w(f"   {k:26s} live share {100*share:5.1f}% (n {len(g):3d}) win {100*pg:5.1f}% [{ci[0]:.1f}, {ci[1]:.1f}] vs rest "
          f"{100*po:5.1f}% (n {len(o)}) | ceiling if closed to the rest: +{100*share*(po-pg):.1f} pp overall")
(HERE / 'drift3.txt').write_text('\n'.join(T) + '\n', encoding='utf-8')
print('\n'.join(T))
