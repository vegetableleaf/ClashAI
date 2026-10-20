"""Is the trophy-difficulty slope (beta in analyze.fit_logit) real, or an artefact of regressing a match outcome on a random
walk's own position?  Under H0 (each Mark wins with a constant p, trophies do not matter) simulate every Mark's outcome sequence
with its observed n, start trophies and win rate (+30 / -30 per match, no loss below the 13,000 floor), re-fit the same model, and
compare the observed beta with the null distribution.  python null_beta.py"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as AN  # noqa: E402

rows = [r for r in AN.load_live() if r['m']]
merged = [dict(r, m='CLX' if r['m'] == 'CLX_T16' else r['m']) for r in rows]
rng = np.random.default_rng(1)
for label, rows in (('CLX pooled over both tower levels', merged), ('CLX split at the tower level-up (CLX / CLX_T16)', rows)):
  th, beta, ms, w0, bs = AN.fit_logit(rows, B=1)
  print(f'== {label}: observed beta {beta[0]:+.3f} per 1,000 trophies')
  by = {m: sorted([r for r in rows if r['m'] == m], key=lambda r: r['ts']) for m in ms}
  null = []
  for it in range(200):
    sim = []
    for m, rs in by.items():
        p = sum(r['win'] == 1 for r in rs) / len(rs)
        t = rs[0]['tro']
        for _ in rs:
            w = rng.random() < p
            sim.append(dict(m=m, tro=t, win=1.0 if w else 0.0))
            t = t + 30 if w else (t if t - 30 < 13000 <= t else t - 30)
    null.append(AN.fit_logit(sim, B=1)[1][0])
  null = np.array(null)
  print(f'null beta (no trophy effect, 200 sims): mean {null.mean():+.3f}, 2.5-97.5% [{np.percentile(null, 2.5):+.3f}, '
        f'{np.percentile(null, 97.5):+.3f}]; share of null betas <= observed {np.mean(null <= beta[0]):.3f}')

# the same question for the trophy-BINNED difference: simulate each Mark at its own constant p, compute strat_diff for the
# adjacent links, and compare its mean with the true p_b - p_a (any gap = bias of the binned estimator itself)
links = [('CXII', 'CXVII'), ('CXVII', 'CXXIV'), ('CXXIV', 'CXXXVIII'), ('CXXXVIII', 'CLIII'), ('CLIII', 'CLIX'), ('CLIII', 'CLX')]
pm = {m: sum(r['win'] == 1 for r in rs) / len(rs) for m, rs in by.items()}
acc = {l: [] for l in links}
for it in range(300):
    sim = {}
    for m, rs in by.items():
        t, out = rs[0]['tro'], []
        for _ in rs:
            w = rng.random() < pm[m]
            out.append(dict(m=m, tro=t, win=1.0 if w else 0.0))
            t = t + 30 if w else (t if t - 30 < 13000 <= t else t - 30)
        sim[m] = out
    for a, b in links:
        d = AN.strat_diff(sim[a], sim[b])
        if d:
            acc[(a, b)].append(d[0])
for (a, b), v in acc.items():
    v = np.array(v)
    print(f'binned {b:9s} - {a:9s}: true {100 * (pm[b] - pm[a]):+5.1f} pp, binned estimator mean {100 * v.mean():+5.1f} '
          f'(bias {100 * (v.mean() - (pm[b] - pm[a])):+5.1f}), sims with shared bins {len(v)}/300')
